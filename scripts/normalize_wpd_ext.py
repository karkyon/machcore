#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_wpd_ext.py — プログラムフォルダ拡張子 .WPD の大文字統一（再利用スクリプト）

対象:
  ・"{加工ID}.pwd"(旧命名の誤り) / ".wpd" 等、大文字の ".WPD" 以外になっているもの全て
  ・DB: mc_machining_details(file_name, pg_folder_name, folder1, folder2)
        nc_machining_details(folder_name, file_name)
        mc_files / nc_files(original_name, stored_name, folder_name, file_path)
        ※ source_path(旧システム側の取込元パス)は旧サーバの実在パスのため変更しない
  ・実フォルダ: 上記 file_path 内のフォルダ名、および
        {upload_base_path}/MC/files/Programs/{加工ID}/*.wpd 等
        {upload_base_path}/プログラム/*.wpd 等
    を ".WPD" にリネームする(同名の大文字フォルダが既にあれば中身を移して統合)。

実行:
  python3 scripts/normalize_wpd_ext.py            # 本番実行
  python3 scripts/normalize_wpd_ext.py --dry-run  # 変更内容の確認のみ
run_nightly_full_reimport_and_verify.py から再投入直後に自動実行される。
"""
import os, re, sys, shutil, argparse
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

WPD_RE = re.compile(r'\.(?:wpd|pwd)(?=$|[/\\])', re.IGNORECASE)
SEG_RE = re.compile(r'\.(?:wpd|pwd)$', re.IGNORECASE)


def norm_wpd(s):
    """文字列中の ".wpd" / ".pwd"(フォルダ名・パスの区切り直前)を ".WPD" に統一する。None はそのまま返す。"""
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    return WPD_RE.sub('.WPD', s)


def _dsn():
    url = os.environ.get('DATABASE_URL')
    if not url:
        env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apps', 'api', '.env')
        with open(env, encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^DATABASE_URL=["\']?([^"\'\n]+)', line.strip())
                if m:
                    url = m.group(1); break
    if not url:
        raise RuntimeError('DATABASE_URL が見つかりません(環境変数 or apps/api/.env)')
    allowed = {'sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'connect_timeout',
               'application_name', 'target_session_attrs'}
    p = urlparse(url)
    q = {k: v for k, v in parse_qs(p.query).items() if k in allowed}
    return urlunparse(p._replace(query=urlencode(q, doseq=True)))


def _merge_dir(old, new, dry, log):
    """old ディレクトリを new(.WPD) に統合する。同名ファイルは更新日時の新しい方を残す。"""
    if dry:
        log(f"  [dry] 統合 {old} → {new}")
        return True
    for name in os.listdir(old):
        src = os.path.join(old, name); dst = os.path.join(new, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                _merge_dir(src, dst, dry, log); continue
            if os.path.exists(dst): os.remove(dst)
            shutil.move(src, dst)
        else:
            # 同名ファイルは更新日時の新しい方を残す(古い方は破棄)
            if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
                os.remove(src)
            else:
                os.replace(src, dst)
    os.rmdir(old)
    log(f"  統合 {old} → {new}")
    return True


def rename_dir(old, dry, log, stats):
    """old(末尾が .wpd/.pwd 等)を .WPD にリネーム。成功(または不要)なら True。"""
    parent, base = os.path.split(old.rstrip('/'))
    new = os.path.join(parent, norm_wpd(base))
    if new == old:
        return True
    if not os.path.isdir(old):
        return True  # 既にリネーム済み、または実体なし
    try:
        if os.path.exists(new):
            _merge_dir(old, new, dry, log); stats['merged'] += 1
        else:
            if not dry:
                os.rename(old, new)
            log(f"  {'[dry] ' if dry else ''}リネーム {old} → {new}")
            stats['renamed'] += 1
        return True
    except Exception as e:
        log(f"  [NG] リネーム失敗 {old}: {e}")
        stats['failed'] += 1
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    dry = args.dry_run

    def log(m):
        print(m, flush=True)

    import psycopg2
    con = psycopg2.connect(_dsn())
    cur = con.cursor()
    cur.execute("SELECT current_database()")
    log(f"[WPD正規化] 対象DB={cur.fetchone()[0]} {'(dry-run)' if dry else ''}")
    stats = {'renamed': 0, 'merged': 0, 'failed': 0}

    # ── 1. 実フォルダ: file_path に含まれるフォルダ ──
    failed_prefix = []
    for tbl in ('mc_files', 'nc_files'):
        cur.execute(f"SELECT DISTINCT file_path FROM {tbl} WHERE file_path ~* %s", (r'\.(wpd|pwd)(/|$)',))
        for (fp,) in cur.fetchall():
            segs = fp.split('/')
            for i, sg in enumerate(segs):
                if SEG_RE.search(sg) and norm_wpd(sg) != sg:
                    old_dir = '/'.join(segs[:i + 1])
                    if not rename_dir(old_dir, dry, log, stats):
                        failed_prefix.append(old_dir)
                    break

    # ── 2. 実フォルダ: 保存先の走査(DBに出てこないフォルダも統一) ──
    cur.execute("SELECT upload_base_path FROM company_settings LIMIT 1")
    r = cur.fetchone()
    base = (r[0] if r else None)
    if base:
        roots = []
        prg = os.path.join(base, 'MC', 'files', 'Programs')
        if os.path.isdir(prg):
            for d in os.listdir(prg):
                p = os.path.join(prg, d)
                if os.path.isdir(p): roots.append(p)
        ncp = os.path.join(base, 'プログラム')
        if os.path.isdir(ncp): roots.append(ncp)
        for root in roots:
            for d in os.listdir(root):
                p = os.path.join(root, d)
                if os.path.isdir(p) and SEG_RE.search(d) and norm_wpd(d) != d:
                    if not rename_dir(p, dry, log, stats):
                        failed_prefix.append(p)

    # ── 3. DB値 ──
    cols = {
        'mc_machining_details': ['file_name', 'pg_folder_name', 'folder1', 'folder2'],
        'nc_machining_details': ['folder_name', 'file_name'],
        'mc_files': ['original_name', 'stored_name', 'folder_name', 'file_path'],
        'nc_files': ['original_name', 'stored_name', 'folder_name', 'file_path'],
    }
    pk = {'mc_machining_details': 'machining_id', 'nc_machining_details': 'k_id',
          'mc_files': 'id', 'nc_files': 'id'}
    total = 0
    for tbl, cs in cols.items():
        for c in cs:
            cur.execute(f"SELECT {pk[tbl]}, {c} FROM {tbl} WHERE {c} ~* %s", (r'\.(wpd|pwd)(/|$)',))
            n = 0
            for rid, val in cur.fetchall():
                nv = norm_wpd(val)
                if nv == val:
                    continue
                if c == 'file_path' and any(val.startswith(fp + '/') or val == fp for fp in failed_prefix):
                    log(f"  [SKIP] 実フォルダのリネーム失敗のためDB据え置き: {tbl}.{c} id={rid}")
                    continue
                if not dry:
                    cur.execute(f"UPDATE {tbl} SET {c}=%s WHERE {pk[tbl]}=%s", (nv, rid))
                n += 1
            if n:
                log(f"  {tbl}.{c}: {n}件 {'(dry)' if dry else '更新'}")
            total += n
    if dry:
        con.rollback()
    else:
        con.commit()
    con.close()
    log(f"[WPD正規化] DB更新 {total}件 / フォルダ リネーム {stats['renamed']}件・統合 {stats['merged']}件・失敗 {stats['failed']}件")
    return 1 if stats['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
