#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_conversion_test.py — 本番DB(machcore_dev)を一切変更せずにデータコンバートを試験する(再利用スクリプト)

  1. machcore_dev を丸ごと複製した試験用DB(既定 machcore_convtest)を作る
  2. 試験用DBに対して MC/NC の全フェーズコンバートを実行する
     (--skip-file-copy: 図・写真・プログラムの実ファイルには一切触れない)
  3. 新旧DB検証(verify_old_new_db.py / verify_nc_old_new_db.py)を試験用DBで実行し、HTMLレポートを作る
  4. これまでに直した不具合が解消しているかを項目ごとに確認する(OK/NG)
  5. 試験用DBを削除する(--keep で残す)

  結果: scripts/verify_reports/conversion_test_YYYYMMDD_HHMMSS.md (+ 検証のjson/html)
  ログ: logs/conversion_test/ (本番コンバートのログには書かない)

実行:
  python3 scripts/run_conversion_test.py            # 試験して試験用DBを削除
  python3 scripts/run_conversion_test.py --keep     # 試験用DBを残す(画面確認などに使う)
"""
import os, re, sys, json, time, argparse, subprocess
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse, urlunparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "verify_reports")
LOG_DIR = os.path.join(ROOT, "logs", "conversion_test")
sys.path.insert(0, HERE)

LINES = []


def out(m=""):
    print(m, flush=True)
    LINES.append(m)


def src_dsn():
    with open(os.path.join(ROOT, "apps", "api", ".env"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^DATABASE_URL="?([^"\n]*)"?$', line.strip())
            if m:
                return m.group(1).split("?", 1)[0]
    raise RuntimeError("DATABASE_URL が apps/api/.env にありません")


def with_db(dsn, db):
    p = urlparse(dsn)
    return urlunparse(p._replace(path="/" + db))


def sh(cmd, env=None, label=None, capture=False):
    t0 = time.time()
    if label:
        out(f"\n===== {label} =====\n$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=HERE, env=env, text=True,
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None)
    el = time.time() - t0
    if label:
        out(f"----- {label}: {'OK' if r.returncode == 0 else f'FAILED(rc={r.returncode})'} ({el/60:.1f}分)")
    return r.returncode, (r.stdout or ""), el


# ──────────────────────────────────────────────────────────────
# 試験用DB
# ──────────────────────────────────────────────────────────────
def find_container(port):
    rc, o, _ = sh("docker ps --format '{{.Names}}\t{{.Ports}}'", capture=True)
    if rc != 0:
        return None
    for line in o.splitlines():
        name, _, ports = line.partition("\t")
        if f":{port}->" in ports:
            return name
    return None


def create_test_db(dsn, test_db):
    import psycopg2
    p = urlparse(dsn)
    src_db = p.path.lstrip("/")
    if test_db == src_db:
        raise RuntimeError("試験用DB名が本番DBと同じです")
    admin = psycopg2.connect(with_db(dsn, "postgres")); admin.autocommit = True
    c = admin.cursor()
    c.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
    c.execute(f'CREATE DATABASE "{test_db}"')
    admin.close()
    user, pw, port = p.username, p.password or "", p.port or 5432
    cont = find_container(port)
    if cont:
        cmd = (f"docker exec -e PGPASSWORD='{pw}' {cont} sh -c "
               f"\"pg_dump -U {user} -d {src_db} | psql -q -v ON_ERROR_STOP=1 -U {user} -d {test_db}\" > /dev/null")
    else:
        cmd = (f"PGPASSWORD='{pw}' pg_dump -h {p.hostname} -p {port} -U {user} -d {src_db} | "
               f"PGPASSWORD='{pw}' psql -q -v ON_ERROR_STOP=1 -h {p.hostname} -p {port} -U {user} -d {test_db} > /dev/null")
    rc, _, _ = sh(cmd, label=f"試験用DB {test_db} に {src_db} を複製" + (f"(コンテナ {cont})" if cont else ""))
    if rc != 0:
        raise RuntimeError("試験用DBの複製に失敗")


def drop_test_db(dsn, test_db):
    import psycopg2
    admin = psycopg2.connect(with_db(dsn, "postgres")); admin.autocommit = True
    c = admin.cursor()
    c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (test_db,))
    c.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
    admin.close()
    out(f"\n試験用DB {test_db} を削除しました")


# ──────────────────────────────────────────────────────────────
# 不具合の再発チェック
# ──────────────────────────────────────────────────────────────
RESULTS = []


def check(no, title, ok, detail):
    RESULTS.append((no, title, "OK" if ok is True else ("NG" if ok is False else "参考"), detail))
    out(f"[{'OK' if ok is True else ('NG' if ok is False else '参考')}] {no} {title}: {detail}")


def q1(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchone()[0]


def run_checks(test_dsn):
    import psycopg2
    from legacy_sheet_link import to_date
    import verify_nc_old_new_db as V
    pg = psycopg2.connect(test_dsn); c = pg.cursor()
    ss = V.ss_connect(); sc = ss.cursor()
    out("\n===== 不具合の再発チェック(試験用DB) =====")

    # ── NC: バージョン ──
    bad = q1(c, r"SELECT COUNT(*) FROM nc_machining_details WHERE version !~ '^[0-9]+\.[0-9]{4}$'")
    tot = q1(c, "SELECT COUNT(*) FROM nc_machining_details")
    check("NC-V1", "NCバージョンが X.YYZZ 形式(旧101→1.0001)", bad == 0, f"形式外 {bad}/{tot}件")
    bad = q1(c, r"""SELECT COUNT(*) FROM change_history WHERE (version_before IS NOT NULL AND version_before !~ '^[0-9]+\.[0-9]{4}$')
                    OR (version_after IS NOT NULL AND version_after !~ '^[0-9]+\.[0-9]{4}$')""")
    check("NC-V2", "NC変更履歴のバージョンが X.YYZZ 形式", bad == 0, f"形式外 {bad}件")
    bad = q1(c, r"SELECT COUNT(*) FROM setup_sheet_logs WHERE version IS NOT NULL AND version !~ '^[0-9]+\.[0-9]{4}$'")
    check("NC-V3", "NC印刷履歴のバージョンが X.YYZZ 形式", bad == 0, f"形式外 {bad}件")
    c.execute("SELECT legacy_ver, version, COUNT(*) FROM nc_machining_details GROUP BY 1,2 ORDER BY 3 DESC LIMIT 6")
    check("NC-V4", "旧Ver→新Verの対応(上位)", None, ", ".join(f"{a}→{b}({n}件)" for a, b, n in c.fetchall()))

    # ── NC: 作業記録の備考・担当者 ──
    bad = q1(c, r"SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL AND note ~ '(^|\n)(段取|加工): '")
    check("NC-W1", "NC作業記録の備考に担当者名を書いていない", bad == 0, f"担当者名入り {bad}件")
    tot = q1(c, "SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL")
    noop = q1(c, """SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL
                    AND (setup_operator_ids IS NULL OR jsonb_typeof(setup_operator_ids::jsonb)<>'array' OR jsonb_array_length(setup_operator_ids::jsonb)=0)
                    AND (production_operator_ids IS NULL OR jsonb_typeof(production_operator_ids::jsonb)<>'array' OR jsonb_array_length(production_operator_ids::jsonb)=0)""")
    check("NC-W2", "NC作業記録の担当者(段取/量産)", None, f"作業記録 {tot}件のうち担当者が両方空 {noop}件(旧の名前がusersに無いもの。詳細はNCコンバートログの[WARN])")

    # ── NC: 印刷履歴(回収済み/未回収・仮登録・sheet_type) ──
    sc.execute("SELECT K_id, Out_Cont, Out_Date, In_Cont FROM ACC_History")
    exp_sl = exp_unc = exp_new = 0
    kid_n = defaultdict(int)
    c.execute("SELECT machining_id, COUNT(*) FROM nc_programs GROUP BY 1")
    for k, n in c.fetchall():
        kid_n[k] = n
    for kid, oc, od, ic in sc.fetchall():
        oc = str(oc or "").strip()
        if kid is None or not od or not ("印刷" in oc or oc == "仮登録"):
            continue
        n = kid_n.get(int(kid), 0)
        exp_sl += n
        if oc == "仮登録":
            exp_new += n
        if ic is None and (oc.startswith("印刷") or oc == "仮登録"):
            exp_unc += n
    act_sl = q1(c, "SELECT COUNT(*) FROM setup_sheet_logs")
    act_unc = q1(c, "SELECT COUNT(*) FROM setup_sheet_logs WHERE NOT work_collected")
    act_new = q1(c, "SELECT COUNT(*) FROM setup_sheet_logs WHERE sheet_type='NEW'")
    nul = q1(c, "SELECT COUNT(*) FROM setup_sheet_logs WHERE sheet_type IS NULL")
    check("NC-S1", "NC印刷履歴の件数(印刷+仮登録)", act_sl == exp_sl, f"旧 {exp_sl}件 / 新 {act_sl}件")
    check("NC-S2", "NC未回収の件数(旧判定: 印刷*/仮登録 かつ In_Cont空)", act_unc == exp_unc, f"旧 {exp_unc}件 / 新 {act_unc}件")
    check("NC-S3", "NC仮登録(新規段取シート)の印刷履歴", act_new == exp_new, f"旧 {exp_new}件 / 新 {act_new}件")
    check("NC-S4", "NC印刷履歴の新規/リピート区分", nul == 0, f"区分なし {nul}件")
    c.execute("""SELECT s.printed_at + interval '9 hour', s.work_collected, s.sheet_type FROM setup_sheet_logs s
                 JOIN nc_programs p ON p.id=s.nc_program_id WHERE p.legacy_nc_id=6049
                 AND s.printed_at + interval '9 hour' >= '2026-09-16' ORDER BY 1""")
    rows = c.fetchall()
    sc.execute("""SELECT h.Out_Cont, h.Out_Date, h.In_Cont FROM ACC_History h WHERE h.NC_id=6049 AND h.Out_Date >= '2026-09-16'""")
    leg = sc.fetchall()
    check("NC-S5", "No.30 NC_id 6049 の 9/16 の段取シート", None,
          f"旧: {[(str(a).strip(), str(b), c_) for a, b, c_ in leg]} / 新: {[(str(a), ('回収済' if b else '未回収'), t) for a, b, t in rows]}")

    # ── NC: 承認者 ──
    appr = q1(c, "SELECT COUNT(*) FROM nc_programs WHERE status='APPROVED'")
    appr_by = q1(c, "SELECT COUNT(*) FROM nc_programs WHERE status='APPROVED' AND approved_by IS NOT NULL")
    sc.execute("SELECT K_id, In_Cont FROM ACC_History WHERE In_Cont IS NOT NULL")
    leg_appr = {k for k, ic in sc.fetchall() if k is not None and "承認" in str(ic)}
    check("NC-A1", "NC承認者・承認日の取り込み", (appr_by > 0) if leg_appr else (appr_by == 0),
          f"旧の「承認」行がある加工ID {len(leg_appr)}件 / 新で承認者あり {appr_by}件(承認済 {appr}件)")

    # ── NC: 作業記録と段取シートの結び付け ──
    sc.execute("SELECT K_id, Out_Cont, Out_Date, Dan_Op, Dan_H, Dan_M, La_H, La_M, P FROM ACC_History")
    exp_link = 0
    for kid, oc, od, dop, dh, dm, lh, lm, p in sc.fetchall():
        oc = str(oc or "").strip()
        if kid is None or not od or not ("印刷" in oc or oc == "仮登録"):
            continue
        if str(dop or "").strip() or int(dh or 0) or int(dm or 0) or int(lh or 0) or int(lm or 0) or int(p or 0):
            exp_link += kid_n.get(int(kid), 0)
    act_link = q1(c, "SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL AND nc_setup_sheet_log_id IS NOT NULL")
    check("NC-L1", "NC作業記録と段取シートの結び付け(同じ旧履歴行)", act_link == exp_link, f"期待 {exp_link}件 / 結び付け {act_link}件")

    # ── NC: 加工リスト(T_id順・TNo・ノーズR) ──
    big = q1(c, r"SELECT COUNT(*) FROM nc_tools WHERE nose_r ~ '^[0-9]+\.[0-9]{2,}$'")
    check("NC-T1", "NCノーズRを丸めずに継承(例 0.25/0.05)", big > 0, f"小数2桁以上のノーズR {big}件(0件なら丸めが残っている)")

    # ── MC ──
    tot = q1(c, "SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL")
    noted = q1(c, "SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND note IS NOT NULL AND note<>''")
    check("MC-W1", "MC作業記録の備考(No.2)", noted > 0, f"作業記録 {tot}件のうち備考あり {noted}件")
    linked = q1(c, "SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND mc_setup_sheet_log_id IS NOT NULL")
    check("MC-L1", "MC作業記録と段取シートの結び付け", None, f"{linked}/{tot}件を結び付け")
    bad = q1(c, r"SELECT COUNT(*) FROM mc_machining_details WHERE version !~ '^[0-9]+\.[0-9]{4}$'")
    c.execute(r"SELECT version, COUNT(*) FROM mc_machining_details WHERE version !~ '^[0-9]+\.[0-9]{4}$' GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
    check("MC-V1", "MCバージョンの形式", bad == 0, f"X.YYZZ形式外 {bad}件 {c.fetchall()}")
    adm = q1(c, "SELECT COUNT(*) FROM mc_programs p JOIN users u ON u.id=p.registered_by WHERE u.employee_code='ADMIN001'")
    check("MC-O1", "MCオペレーターが管理者で代替された件数(No.3)", None, f"{adm}件(旧のオペレーター名がusersに無いもの)")

    # MC: 結び付かない作業記録の内訳(旧データで判定)
    sc.execute("""SELECT MCID, 内容, 内容区分ID, 入力日, R_IN_DATE, 総時間 FROM ACC_変更履歴 ORDER BY MCID, 入力日""")
    prints = defaultdict(list)
    cat = defaultdict(int)
    for mcid, content, nk, ind, rin, total in sc.fetchall():
        try: nk = int(nk or 0)
        except (TypeError, ValueError): nk = 0
        content = str(content or "").strip()
        if nk in (1, 3, 7):
            prints[mcid].append({"in": ind, "rin": to_date(rin), "ref": nk == 1 and "参考" in content, "used": False, "row_work": False})
        has_work = (nk == 17) or (total is not None and str(total).strip() != "")
        if not has_work or not isinstance(ind, datetime):
            continue
        if nk in (1, 3, 7):
            cat["同じ行に印刷"] += 1; prints[mcid][-1]["used"] = True; continue
        pool = [p for p in prints[mcid] if not p["used"] and not p["ref"] and (p["in"] is None or p["in"] <= ind)]
        hit = [p for p in pool if p["rin"] == ind.date()]
        hit2 = [p for p in pool if p["rin"] is None]
        if hit:
            max(hit, key=lambda x: x["in"] or datetime.min)["used"] = True; cat["R_IN_DATE=入力日"] += 1
        elif hit2:
            max(hit2, key=lambda x: x["in"] or datetime.min)["used"] = True; cat["戻り日が空→作業記録より前の最新の印刷"] += 1
        elif not prints[mcid]:
            cat["(結び付かず)その部品に印刷が1件も無い"] += 1
        elif not pool:
            cat["(結び付かず)それより前の未使用の印刷が無い"] += 1
        elif all(p["rin"] is None for p in pool):
            cat["(結び付かず)前の印刷はあるが戻り日(R_IN_DATE)が空"] += 1
        else:
            near = min((abs((p["rin"] - ind.date()).days) for p in pool if p["rin"]), default=None)
            cat[f"(結び付かず)戻り日が入力日と違う(差{'1日' if near == 1 else ('2〜7日' if near and near <= 7 else '8日以上')})"] += 1
    check("MC-L2", "MC作業記録の結び付け内訳(旧データ)", None, ", ".join(f"{k}: {v}" for k, v in sorted(cat.items())))

    users = q1(c, "SELECT COUNT(*) FROM users")
    check("CM-U1", "ユーザーマスタ(コンバートで変更しない)", None, f"{users}件")
    pg.close(); ss.close()


def summarize_verify(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        out(f"\n----- {label} 新旧DB検証の集計 -----")
        for s in d.get("summaries", []):
            out("  " + ", ".join(f"{k}={v}" for k, v in s.items()))
    except Exception as e:
        out(f"{label} 検証結果を読めませんでした: {e}")
        return
    # 不一致の内訳(項目別件数と具体例)
    from collections import Counter
    for cat, items in (d.get("details") or {}).items():
        if not items:
            continue
        fc = Counter()
        for x in items:
            st = x.get("status")
            if st and st != "MISMATCH":
                fc[st] += 1
            flds = list(x.get("fields") or []) + [f for r in (x.get("rows") or []) for f in (r.get("fields") or [])]
            for fd in flds:
                fc[fd.get("field")] += 1
        out(f"  [{label}/{cat}] 不一致 {len(items)}件 内訳: {dict(fc)}")
        for x in items[:12]:
            out("    " + json.dumps(x, ensure_ascii=False)[:400])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-db", default="machcore_convtest")
    ap.add_argument("--keep", action="store_true", help="試験用DBを残す")
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    t0 = time.time()
    dsn = src_dsn()
    test_dsn = with_db(dsn, a.test_db)
    env = dict(os.environ, MACHCORE_PG_DSN=test_dsn, DATABASE_URL=test_dsn, MACHCORE_IMPORT_LOG_DIR=LOG_DIR)
    py = sys.executable
    out(f"# コンバート試験 {ts}\n試験用DB: {a.test_db}(本番DBは変更しない) / 実ファイルのコピーなし")
    ok = True
    try:
        create_test_db(dsn, a.test_db)
        for cmd, label in [([py, "mc_full_import.py", "--phase", "0", "--skip-file-copy"], "MCコンバート(全フェーズ・ファイル除く)"),
                           ([py, "nc_full_import_v2.py", "--phase", "0", "--skip-file-copy"], "NCコンバート(全フェーズ・ファイル除く)")]:
            rc, _, _ = sh(cmd, env=env, label=label)
            if rc != 0:
                ok = False; raise RuntimeError(f"{label} が失敗")
        mj = os.path.join(OUT_DIR, f"convtest_mc_{ts}.json"); nj = os.path.join(OUT_DIR, f"convtest_nc_{ts}.json")
        sh([py, "verify_old_new_db.py", "--out", mj], env=env, label="MC新旧DB検証")
        sh([py, "generate_verify_report.py", "--in", mj, "--out", mj.replace(".json", ".html")], env=env, label="MC検証レポート")
        sh([py, "verify_nc_old_new_db.py", "--out", nj], env=env, label="NC新旧DB検証")
        sh([py, "generate_verify_report_nc.py", "--in", nj, "--out", nj.replace(".json", ".html")], env=env, label="NC検証レポート")
        summarize_verify(mj, "MC"); summarize_verify(nj, "NC")
        run_checks(test_dsn)
    except Exception as e:
        ok = False
        out(f"\n!!! 試験を中断: {e}")
    finally:
        if not a.keep:
            try: drop_test_db(dsn, a.test_db)
            except Exception as e: out(f"試験用DBの削除に失敗: {e}")
        ng = [r for r in RESULTS if r[2] == "NG"]
        out(f"\n===== まとめ: 所要 {(time.time()-t0)/60:.1f}分 / チェック {len(RESULTS)}項目 NG {len(ng)}件 =====")
        for r in ng:
            out(f"  NG {r[0]} {r[1]}: {r[3]}")
        md = os.path.join(OUT_DIR, f"conversion_test_{ts}.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("\n".join(LINES) + "\n")
        out(f"結果: {md}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
