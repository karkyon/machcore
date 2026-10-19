#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_multi_drawing_parts.py — Ridoc に同一図面番号で複数の図面が登録されている部品を探す（読むだけ）

  MachCore の部品(MC/NC 加工データがあるもの)の図面番号ごとに
  RidocImageAPI /v1/DrawingImages/search を呼び、
    ・文書名一致が2件以上（= 図面切替 ◀ ▶ の確認用サンプル）
    ・キーワードヒット > 文書名一致（= 備考一致の別図面を除外できている確認用サンプル）
  を一覧表示し、scripts/verify_reports/multi_drawing_parts_日時.tsv に保存する。

実行例(.11 / .14 どのリポジトリからでも。DB は DATABASE_URL か apps/api/.env):
  python3 scripts/find_multi_drawing_parts.py                 # 複数登録を20件見つけたら終了
  python3 scripts/find_multi_drawing_parts.py --found 50 --workers 4
  python3 scripts/find_multi_drawing_parts.py --all           # 全図面番号を走査(時間がかかる)

オプション:
  --ridoc-url URL   RidocImageAPI(既定: 環境変数 RIDOC_API_URL → http://192.168.1.207:5087)
  --found N         複数登録の部品をN件見つけたら終了(既定 20)
  --all             件数で止めずに全件走査
  --workers N       同時問い合わせ数(既定 4。RSN サーバー負荷のため上げすぎない)
  --timeout SEC     1件あたりのタイムアウト(既定 60)
"""
import os
import re
import sys
import json
import time
import argparse
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def database_dsn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_path = os.path.join(ROOT, "apps", "api", ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r'^DATABASE_URL=["\']?([^"\'\n]+)', line)
                    if m:
                        url = m.group(1)
                        break
    if not url:
        sys.exit("DATABASE_URL が見つかりません(環境変数 or apps/api/.env)")
    allowed = {"sslmode", "sslcert", "sslkey", "sslrootcert", "connect_timeout",
               "application_name", "target_session_attrs"}
    p = urlparse(url)
    kept = {k: v for k, v in parse_qs(p.query).items() if k in allowed}
    return urlunparse(p._replace(query=urlencode(kept, doseq=True)))


SQL = """
SELECT p.id, p.part_id, p.drawing_no, COALESCE(p.name, ''),
       COALESCE(string_agg(DISTINCT mc.id::text || ':' || COALESCE(mc.legacy_mcid::text, '-'), ',') FILTER (WHERE mc.id IS NOT NULL), ''),
       COALESCE(string_agg(DISTINCT nc.id::text, ',') FILTER (WHERE nc.id IS NOT NULL), '')
  FROM parts p
  LEFT JOIN mc_programs mc ON mc.part_id = p.id
  LEFT JOIN nc_programs nc ON nc.part_id = p.id
 WHERE COALESCE(TRIM(p.drawing_no), '') <> ''
 GROUP BY p.id, p.part_id, p.drawing_no, p.name
HAVING COUNT(mc.id) > 0 OR COUNT(nc.id) > 0
 ORDER BY p.drawing_no, p.id
"""


def search(base, drawing_no, timeout):
    url = f"{base}/v1/DrawingImages/search?docId={urllib.parse.quote(drawing_no)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
        names = [c.get("name", "") for c in body.get("candidates", [])]
        return drawing_no, int(body.get("totalCount", 0)), int(body.get("keywordHitCount", -1)), names, None
    except Exception as e:  # noqa: BLE001
        return drawing_no, 0, 0, [], str(e)


def main():
    ap = argparse.ArgumentParser(description="Ridoc 複数登録図面のサンプル部品を探す(読むだけ)")
    ap.add_argument("--ridoc-url", default=os.environ.get("RIDOC_API_URL") or "http://192.168.1.207:5087")
    ap.add_argument("--found", type=int, default=20)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()
    base = a.ridoc_url.rstrip("/")

    conn = psycopg2.connect(database_dsn())
    cur = conn.cursor()
    cur.execute("SELECT current_database()")
    dbname = cur.fetchone()[0]
    cur.execute(SQL)
    rows = cur.fetchall()
    conn.close()

    by_dno = {}
    for pid, part_id, dno, name, mcs, ncs in rows:
        by_dno.setdefault(dno.strip(), []).append((pid, part_id, name, mcs, ncs))
    dnos = list(by_dno.keys())
    print(f"DB={dbname}  Ridoc={base}  対象図面番号={len(dnos)}件(MC/NC 加工データのある部品)")

    multi, excluded, errors = [], [], []
    scanned = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        it = iter(dnos)
        pending = set()

        def submit_next():
            dno = next(it, None)
            if dno is not None:
                pending.add(ex.submit(search, base, dno, a.timeout))

        for _ in range(max(1, a.workers) * 2):
            submit_next()
        while pending:
            done = next(as_completed(pending))
            pending.discard(done)
            dno, total, hits, names, err = done.result()
            scanned += 1
            if err:
                errors.append((dno, err))
            else:
                if total >= 2:
                    multi.append((dno, total, hits, names))
                    print(f"  [複数] {dno}  文書名一致={total}  キーワード={hits}  {' / '.join(names)}")
                elif hits > total:
                    excluded.append((dno, total, hits, names))
            if scanned % 200 == 0:
                print(f"  … {scanned}/{len(dnos)} 件確認 ({time.time() - t0:.0f}秒) 複数={len(multi)} 除外あり={len(excluded)} エラー={len(errors)}")
            if not a.all and len(multi) >= a.found:
                for f in pending:
                    f.cancel()
                break
            submit_next()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join(ROOT, "scripts", "verify_reports")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"multi_drawing_parts_{stamp}.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("種別\t図面番号\t文書名一致\tキーワードヒット\t文書名\t部品ID\tparts.id\t名称\tMC(id:旧MCID)\tNC(id)\n")
        for kind, lst in (("複数登録", multi), ("備考一致を除外", excluded)):
            for dno, total, hits, names in lst:
                for pid, part_id, name, mcs, ncs in by_dno[dno]:
                    f.write(f"{kind}\t{dno}\t{total}\t{hits}\t{' / '.join(names)}\t{part_id}\t{pid}\t{name}\t{mcs}\t{ncs}\n")
        for dno, err in errors:
            f.write(f"エラー\t{dno}\t\t\t{err}\t\t\t\t\t\n")

    def show(title, lst, n):
        print(f"\n■ {title}: {len(lst)}件" + (f"（先頭{n}件）" if len(lst) > n else ""))
        print(f"  {'部品ID':<8} {'図面番号':<16} {'一致':>4} {'KW':>4}  {'MC(id:旧MCID)':<20} {'NC(id)':<12} 文書名")
        for dno, total, hits, names in lst[:n]:
            for pid, part_id, name, mcs, ncs in by_dno[dno]:
                print(f"  {part_id:<8} {dno:<16} {total:>4} {hits:>4}  {mcs:<20} {ncs:<12} {' / '.join(names)}")

    show("同一図面番号で複数登録（◀ ▶ 切替の確認用）", multi, 50)
    show("キーワードヒットのうち別図面を除外（F42186A01 と同じ型の確認用）", excluded, 10)
    if errors:
        print(f"\n■ 問い合わせエラー: {len(errors)}件（先頭5件）")
        for dno, err in errors[:5]:
            print(f"  {dno}: {err}")
    print(f"\n確認 {scanned}/{len(dnos)} 件 ({time.time() - t0:.0f}秒)  保存: {out}")


if __name__ == "__main__":
    main()
