#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_masters_from_11.py — .11(UAT で確かめてきた環境)のマスタを .14 の internal / group にそろえる(再利用スクリプト)

UAT を .11 から .14 へ移すとき、.11 で UAT 中に管理画面から直したマスタ(利用者・機械・帳票の印字位置・
営業日カレンダー・候補マスタ等)が .14 に無いと、画面の動きが .11 と変わる。parity_check.py で見つかった違いを
次の規則で .14 にそろえる。

  そろえ方(既定は表示だけ。--apply で書き込む。書き込む前に対象の表を JSON に保存する)
  ┌──────────────────────┬───────────┬──────────────────────────────────────────────────┐
  │ 表                   │ internal  │ やること                                          │
  ├──────────────────────┼───────────┼──────────────────────────────────────────────────┤
  │ 利用者 users         │ ○        │ .11 にいて .14 にいない人を追加、違う項目は .11 に。.14 だけの人は残す │
  │ 機械 machines        │ ○        │ 同上(機械コードで照合)                            │
  │ 帳票の印字位置       │ ○        │ 同上(テンプレート名・項目・ページ・順で照合)。group も同じ帳票なので対象 │
  │ 営業日カレンダー     │ ○        │ 同上(日付で照合)。.14 だけの日は残す              │
  │ システム設定         │ ○        │ .11 にだけある設定を追加、違う値は .11 に(配布物の版など .14 固有のものは除く) │
  │ 候補マスタ           │ ○        │ .11 と同じ内容に置き換える(クランプ5表・NC加工リスト4表。コンバートは候補が │
  │                      │           │ 空の時だけ投入するため、置き換えないと .11 と候補が違うまま)。消した .14 の行は結果に出す │
  └──────────────────────┴───────────┴──────────────────────────────────────────────────┘
  ・group も internal と同じく全マスタを .11 にそろえる(2026-10-20 方針)。group の既定の言語だけは group のまま
  ・.14 にだけいる利用者で .11 の利用者と同じ氏名のものは消す(同じ氏名が2人いるとコンバートで担当者が空欄になるため)
  ・特殊シートの PDF が格納先に無いものは、以前の格納先から探して複写する(internal / group とも)
  ・会社設定(プリンタ・格納先)は環境ごとに違うのが正しいためそろえない

実行(.14 で):
  python3 scripts/sync_masters_from_11.py --target internal            # 何が変わるかを表示するだけ
  python3 scripts/sync_masters_from_11.py --target internal --apply    # 書き込む(前に JSON バックアップ)
  python3 scripts/sync_masters_from_11.py --target internal --restore ~/machcore-backups/internal/masters_before_sync_日時.json
  .11 の DB: 既定 192.168.1.11:5440/machcore_dev(--src で変更)
"""
import os
import re
import sys
import json
import argparse
import unicodedata
from datetime import datetime, date
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
SRC_DEFAULT = "postgresql://machcore:machcore_pass_change_me@192.168.1.11:5440/machcore_dev"
REPOS = {"internal": HOME / "projects" / "machcore-internal", "group": HOME / "projects" / "machcore-group"}

CANDIDATES = ["clamp_vise", "clamp_chuck", "clamp_tsume", "clamp_shiki", "clamp_index",
              "nc_tool_shave1_master", "nc_tool_shave2_master", "nc_tool_chip_master", "nc_tool_holder_master"]
SETTINGS_KEEP = {"upload_agent_version"}   # .14 固有(配布している UploadAgent の版)
SETTINGS_KEEP_GROUP = {"default_language"}   # group(ベトナムのグループ会社)の画面の既定の言語


def dsn_of(repo):
    for line in (repo / "apps" / "api" / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r'^\s*DATABASE_URL\s*=\s*"?([^"\n]*)"?\s*$', line)
        if m:
            return m.group(1).split("?", 1)[0]
    raise SystemExit(f"{repo}/apps/api/.env に DATABASE_URL がありません")


def rows(c, sql, args=None):
    c.execute(sql, args)
    names = [d.name for d in c.description]
    return [dict(zip(names, r)) for r in c.fetchall()]


def jdef(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def show(v):
    s = "—" if v is None else str(v)
    return s if len(s) <= 60 else s[:60] + "…"


class Plan:
    def __init__(self):
        self.ops = []   # (table, kind, key, detail)

    def add(self, table, kind, key, detail=""):
        self.ops.append((table, kind, key, detail))

    def count(self, table=None):
        from collections import Counter
        return Counter(k for t, k, _, _ in self.ops if table is None or t == table)


# ──────────────── 合わせ方: 照合キーで追加・更新(.14 だけの行は残す) ────────────────
def merge(sc, tc, plan, table, key, cols, apply, where_extra="", insert_extra=None, xform=None):
    src = rows(sc, f"SELECT * FROM {table} {where_extra}")
    if xform:
        src = [x for x in (xform(r) for r in src) if x is not None]
    dst = rows(tc, f"SELECT * FROM {table} {where_extra}")
    kf = (lambda r: tuple(str(r.get(k)) for k in key)) if not callable(key) else key
    dmap = {kf(r): r for r in dst}
    inserted = []
    for s in src:
        k = kf(s)
        d = dmap.get(k)
        if d is None:
            plan.add(table, "追加", "/".join(k))
            inserted.append(k)
            if apply:
                vals = {c: s.get(c) for c in cols}
                if insert_extra:
                    vals.update(insert_extra(s))
                names = list(vals)
                tc.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join(['%s'] * len(names))})",
                           [json.dumps(v) if isinstance(v, (dict, list)) else v for v in vals.values()])
            continue
        ch = {c: s.get(c) for c in cols if _norm(s.get(c)) != _norm(d.get(c))}
        if ch:
            plan.add(table, "更新", "/".join(k), ", ".join(f"{c}: {show(d.get(c)) if c != 'password_hash' else '(旧)'}→"
                                                          f"{show(v) if c != 'password_hash' else '(.11 のもの)'}" for c, v in ch.items()))
            if apply:
                sets = ", ".join(f"{c}=%s" for c in ch)
                idcol = "key" if table == "system_settings" else "id"
                tc.execute(f"UPDATE {table} SET {sets} WHERE {idcol}=%s",
                           [json.dumps(v) if isinstance(v, (dict, list)) else v for v in ch.values()] + [d[idcol]])
    srckeys = {kf(s) for s in src}
    for k, d in dmap.items():
        if k not in srckeys:
            plan.add(table, ".14 だけ(残す)", "/".join(k))
    return inserted


def _norm(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    if isinstance(v, float):
        return round(v, 6)
    return v


# ──────────────── 置き換え: 候補マスタを .11 と同じ内容に ────────────────
def replace_table(sc, tc, plan, table, apply):
    src = rows(sc, f"SELECT * FROM {table} ORDER BY sort_order, id")
    dst = rows(tc, f"SELECT * FROM {table} ORDER BY sort_order, id")
    cols = [c for c in (src[0].keys() if src else []) if c not in ("id", "created_at", "updated_at")]

    def sig(r):
        return json.dumps({c: r.get(c) for c in cols}, ensure_ascii=False, sort_keys=True, default=str)
    if sorted(map(sig, src)) == sorted(map(sig, dst)):
        return
    sset = {sig(r) for r in src}
    gone = [r for r in dst if sig(r) not in sset]
    plan.add(table, "置き換え", f"{len(dst)}件 → {len(src)}件",
             (f".14 から無くなる {len(gone)}件: " + ", ".join(str(r.get("name")) + (f"({r.get('model') or r.get('size') or r.get('machine') or ''})"
                                                                        if any(r.get(x) for x in ('model', 'size', 'machine')) else "")
                                                         for r in gone[:25]) + (" ほか" if len(gone) > 25 else "")) if gone else "")
    if apply:
        tc.execute(f"DELETE FROM {table}")
        for r in src:
            tc.execute(f"INSERT INTO {table} ({','.join(cols)}, created_at, updated_at) VALUES ({','.join(['%s'] * len(cols))}, NOW(), NOW())",
                       [r.get(c) for c in cols])
        tc.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), GREATEST(COALESCE((SELECT MAX(id) FROM {table}),1),1))")


def dedupe_users(sc, tc, plan, apply):
    """.14 にだけいる利用者で、.11 の利用者と同じ氏名(表記ゆれを正規化)のものを消す。
       同じ氏名の利用者が2人いると、コンバートは誤った人に結び付けないよう担当者を空欄にする
       (例: .11 の NC001 タイ と .14 で登録した STAFF… タイ → 旧データの「タイ」が全件空欄)。
       他の記録から参照されていて消せないときは、無効にして氏名の末尾に「(重複)」を付け、照合から外す"""
    sys.path.insert(0, str(HERE))
    from name_match import person_key
    sc.execute("SELECT employee_code, name FROM users")
    src = sc.fetchall()
    scodes = {r[0].upper() for r in src}
    skeys = {person_key(r[1]): r[0] for r in src if r[1]}
    tc.execute("SELECT id, employee_code, name FROM users ORDER BY id")
    for uid, code, name in tc.fetchall():
        if code.upper() in scodes or not name or person_key(name) not in skeys or name.endswith("(重複)"):
            continue
        dup = skeys[person_key(name)]
        if not apply:
            plan.add("users", "同じ氏名の重複を消す", f"{code} {name}", f".11 の {dup} と同じ氏名(残すとこの名前の記録が担当者空欄)")
            continue
        try:
            tc.execute("SAVEPOINT d")
            tc.execute("DELETE FROM users WHERE id=%s", (uid,))
            tc.execute("RELEASE SAVEPOINT d")
            plan.add("users", "同じ氏名の重複を消す", f"{code} {name}", f".11 の {dup} と同じ氏名")
        except Exception as e:
            tc.execute("ROLLBACK TO SAVEPOINT d")
            tc.execute("UPDATE users SET is_active=false, name=left(name, 45) || '(重複)', updated_at=NOW() WHERE id=%s", (uid,))
            plan.add("users", "同じ氏名の重複を無効化", f"{code} {name}",
                     f".11 の {dup} と同じ氏名。他の記録から参照されているため消さずに無効・氏名に(重複)を付けて照合から外す({e.__class__.__name__})")


def fix_special_sheet_pdfs(tc, plan, apply):
    """特殊シートの PDF がこのインスタンスの格納先に無いものを、以前の格納先(共有フォルダ・旧既定の uploads 等)から探して複写する。
       管理画面のアップロードは「その時の upload_base_path/special_sheets/」に保存するため、格納先を移したときに取り残されることがある"""
    import shutil
    import subprocess
    tc.execute("SELECT upload_base_path FROM company_settings ORDER BY id LIMIT 1")
    r = tc.fetchone()
    base = (r[0] if r else "") or ""
    base = base.rstrip("/")
    tc.execute("SELECT id, sheet_name, pdf_path FROM special_sheets WHERE pdf_path IS NOT NULL AND pdf_path <> '' ORDER BY id")
    sheets = tc.fetchall()
    if not base or not sheets:
        return
    roots = ["/mnt/mc_files", "/mnt/mcfiles", str(HOME / "projects" / "machcore" / "uploads")]
    roots += [str(p) for p in sorted((HOME / "machcore-storage").glob("*"))]
    roots += [str(p / "uploads") for p in sorted((HOME / "projects").glob("*"))]
    roots += [str(p / "apps" / "api" / "uploads") for p in sorted((HOME / "projects").glob("*"))]
    for sid, name, rel in sheets:
        dst = os.path.join(base, rel)
        if os.path.isfile(dst):
            continue
        fn = os.path.basename(rel)
        found = None
        for root in roots:
            if os.path.realpath(root) == os.path.realpath(base):
                continue
            for cand in (os.path.join(root, rel), os.path.join(root, "special_sheets", fn)):
                if os.path.isfile(cand):
                    found = cand
                    break
            if found:
                break
        if not found:
            # ホーム以下を名前で探す(node_modules・.git は見ない)
            try:
                out = subprocess.run(["find", str(HOME), "(", "-name", "node_modules", "-o", "-name", ".git", ")", "-prune",
                                      "-o", "-type", "f", "-name", fn, "-print"], capture_output=True, text=True, timeout=300).stdout
                hits = [x for x in out.splitlines() if x and os.path.realpath(x) != os.path.realpath(dst)]
                found = hits[0] if hits else None
            except Exception:
                found = None
        if found:
            plan.add("special_sheets", "PDF を複写", f"{name}", f"{found} → {dst}")
            if apply:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(found, dst)
        else:
            plan.add("special_sheets", "PDF が見つからない(要対応)", f"{name}",
                     f"{rel} がどこにもありません。管理画面の特殊シートで PDF をアップロードし直してください")


def backup(tc, tables, target, inserted):
    d = HOME / "machcore-backups" / target
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"masters_before_sync_{TS}.json"
    data = {"taken_at": TS, "target": target, "tables": {}, "inserted": inserted}
    for t in tables:
        data["tables"][t] = rows(tc, f"SELECT * FROM {t}")
    out.write_text(json.dumps(data, ensure_ascii=False, default=jdef, indent=0), encoding="utf-8")
    return out


def restore(tc, path):
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    for t, rs in data["tables"].items():
        if t in CANDIDATES or t in ("pdf_field_definitions", "business_calendars", "system_settings"):
            tc.execute(f"DELETE FROM {t}")
            for r in rs:
                names = list(r)
                tc.execute(f"INSERT INTO {t} ({','.join(names)}) VALUES ({','.join(['%s'] * len(names))})",
                           [json.dumps(v) if isinstance(v, (dict, list)) else v for v in r.values()])
            if t != "system_settings":
                tc.execute(f"SELECT setval(pg_get_serial_sequence('{t}','id'), GREATEST(COALESCE((SELECT MAX(id) FROM {t}),1),1))")
        else:   # users / machines: 他の表から参照されるため、値を戻し、追加した行は参照が無ければ消す
            key = "employee_code" if t == "users" else "machine_code"
            for r in rs:
                cols = [c for c in r if c not in ("id",)]
                vals = [json.dumps(r[c]) if isinstance(r[c], (dict, list)) else r[c] for c in cols]
                tc.execute(f"UPDATE {t} SET {', '.join(f'{c}=%s' for c in cols)} WHERE id=%s", vals + [r["id"]])
                if tc.rowcount == 0:   # 重複として消した利用者を入れ直す
                    tc.execute(f"INSERT INTO {t} (id, {','.join(cols)}) VALUES (%s, {','.join(['%s'] * len(cols))})",
                               [r["id"]] + vals)
            for k in data.get("inserted", {}).get(t, []):
                try:
                    tc.execute("SAVEPOINT s")
                    tc.execute(f"DELETE FROM {t} WHERE {key}=%s", (k[0],))
                    tc.execute("RELEASE SAVEPOINT s")
                except Exception as e:
                    tc.execute("ROLLBACK TO SAVEPOINT s")
                    print(f"  [注意] {t} {k[0]} は他の記録から参照されているため消せません({e.__class__.__name__})")
    print(f"[OK] 戻しました: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["internal", "group"], required=True)
    ap.add_argument("--src", default=SRC_DEFAULT, help=".11 の DB(既定 192.168.1.11:5440/machcore_dev)")
    ap.add_argument("--apply", action="store_true", help="書き込む(既定は表示だけ)")
    ap.add_argument("--restore", default=None, help="バックアップ JSON から戻す")
    a = ap.parse_args()
    import psycopg2
    repo = REPOS[a.target]
    tdsn = dsn_of(repo)
    tg = psycopg2.connect(tdsn)
    tc = tg.cursor()
    if a.restore:
        restore(tc, a.restore)
        tg.commit()
        return
    print(f"[.11] {a.src.split('@')[-1]} → [.14 {a.target}] {tdsn.split('@')[-1]}  ({'書き込み' if a.apply else '表示だけ'})")
    sg = psycopg2.connect(a.src, connect_timeout=15)
    sg.set_session(readonly=True)
    sc = sg.cursor()
    plan = Plan()
    inserted = {}
    full = True   # internal / group とも .11 と同じマスタにする(group も同じデータを登録する方針 2026-10-20)
    keep = SETTINGS_KEEP | (SETTINGS_KEEP_GROUP if a.target == "group" else set())
    tables = ["users", "machines", "pdf_field_definitions", "business_calendars", "system_settings"] + CANDIDATES
    bk = None
    if a.apply:
        bk = backup(tc, tables, a.target, {})
    try:
        if full:
            inserted["users"] = merge(sc, tc, plan, "users", ("employee_code",),
                                      ["employee_code", "name", "name_kana", "password_hash", "role", "is_active",
                                       "can_approve", "system_type"], a.apply,
                                      insert_extra=lambda s: {"created_at": datetime.now(), "updated_at": datetime.now()})
            dedupe_users(sc, tc, plan, a.apply)
            inserted["machines"] = merge(sc, tc, plan, "machines", ("machine_code",),
                                         ["machine_code", "machine_name", "machine_type", "maker", "sort_order", "is_active",
                                          "system_type", "mc_specs", "pg_is_folder"], a.apply,
                                         insert_extra=lambda s: {"created_at": datetime.now(), "updated_at": datetime.now()})
        # 帳票の印字位置(テンプレート名で照合して template_id を .14 側の id に置き換える)
        sc.execute("SELECT id, name FROM pdf_templates")
        sname = dict(sc.fetchall())
        tc.execute("SELECT name, id FROM pdf_templates")
        tid = dict(tc.fetchall())

        def fx(s):
            n = sname.get(s["template_id"])
            if n not in tid:
                plan.add("pdf_field_definitions", "対象外(.14 にテンプレートが無い)", f"{n}/{s['field_key']}")
                return None
            s = dict(s)
            s["template_id"] = tid[n]
            return s
        merge(sc, tc, plan, "pdf_field_definitions",
              lambda r: (str(r["template_id"]), r["field_key"], str(r["page_number"]), str(r["sort_order"])),
              ["template_id", "field_key", "label", "x", "y", "font_size", "data_source", "page_number", "sort_order",
               "is_active", "note"], a.apply, xform=fx)
        if full:
            merge(sc, tc, plan, "business_calendars", ("work_date",), ["work_date", "is_holiday", "note"], a.apply,
                  insert_extra=lambda s: {"created_at": datetime.now()})

            def keep_settings(s):
                return None if s["key"] in keep else s
            merge(sc, tc, plan, "system_settings", ("key",), ["key", "value", "description"], a.apply, xform=keep_settings,
                  insert_extra=lambda s: {"updated_at": datetime.now()})
            for t in CANDIDATES:
                replace_table(sc, tc, plan, t, a.apply)
        fix_special_sheet_pdfs(tc, plan, a.apply)
        if a.apply:
            # バックアップに「追加した行」を書き足す(戻すときに使う)
            data = json.loads(bk.read_text(encoding="utf-8"))
            data["inserted"] = {k: [list(x) for x in v] for k, v in inserted.items()}
            bk.write_text(json.dumps(data, ensure_ascii=False, default=jdef, indent=0), encoding="utf-8")
            tg.commit()
        else:
            tg.rollback()
    except Exception:
        tg.rollback()
        raise
    # 表示
    for t in tables + ["special_sheets"]:
        if t == "special_sheets" and not any(o[0] == t for o in plan.ops):
            continue
        ops = [o for o in plan.ops if o[0] == t]
        if not ops:
            print(f"■ {t}: .11 と同じ")
            continue
        cnt = plan.count(t)
        print(f"■ {t}: " + " / ".join(f"{k} {v}件" for k, v in cnt.items()))
        for _, kind, key, det in ops[:60]:
            print(f"    [{kind}] {key}" + (f"  {det}" if det else ""))
        if len(ops) > 60:
            print(f"    … ほか {len(ops) - 60}件")
    if a.apply:
        print(f"\n[OK] 書き込みました。元に戻す: python3 scripts/sync_masters_from_11.py --target {a.target} --restore {bk}")
    else:
        print("\n(表示だけです。書き込むには --apply)")


if __name__ == "__main__":
    main()
