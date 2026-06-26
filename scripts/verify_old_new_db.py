#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_old_new_db.py
=====================
旧システム(SQL Server: imotomc/imotodb)と新システム(PostgreSQL: machcore_dev)の
データを全件機械的に比較し、不一致を検出するスクリプト。

第1弾: ①基本情報(MC) + ②ツーリング

実行方法:
  python3 verify_old_new_db.py [--limit N] [--out /path/to/output.json]

出力:
  JSON形式の中間データ(後続のHTMLレポート生成スクリプトの入力)
"""
import sys, os, re, json, argparse
from datetime import datetime

PG_DSN       = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
SS_MC_SERVER = "192.168.1.9"
SS_MC_USER   = "sa"
SS_MC_PASS   = "RTW65b"
SS_MC_DB     = "imotomc"
SS_PB_DB     = "imotodb"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def pg_connect():
    import psycopg2
    return psycopg2.connect(PG_DSN)


def ss_connect(db):
    import pymssql
    return pymssql.connect(server=SS_MC_SERVER, user=SS_MC_USER, password=SS_MC_PASS,
                            database=db, tds_version="7.4")


# ────────────────────────────────────────────────────────────
# 正規化ヘルパー（インポート時の正規化ロジックと完全に同じものを適用する）
# 正規化済みの新データと、正規化をかけた旧データを比較することで
# 「既知の差(インポート修正で意図的に変えた表記)」を誤検出しないようにする。
# ────────────────────────────────────────────────────────────

def normalize_h(raw_h):
    """H列正規化: 数字のみならH付与。mc_full_import.py PHASE2と同一ロジック。"""
    if raw_h is None:
        return None
    s = str(raw_h).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return f"H{s}"
    return s


def normalize_dvalue(raw_d):
    """D値正規化: 小数点以下3桁固定。page.tsx fmtDValueと同一ロジック。
    旧データはSQL Server側でfloat型のため末尾ゼロが失われているが、
    値そのもの(数値として)は新データと一致するはずなので、
    両者を同じ「3桁固定文字列」に変換して比較する。
    """
    if raw_d is None:
        return None
    s = str(raw_d).strip()
    if not s:
        return None
    try:
        n = float(s)
    except (TypeError, ValueError):
        return s
    return f"{n:.3f}"


def normalize_str(raw):
    """前後空白除去・全角/半角スペース統一。NULL/空文字はNoneに統一。"""
    if raw is None:
        return None
    s = str(raw).strip()
    s = re.sub(r"[\s\u3000]+", " ", s)
    return s or None


def normalize_num(raw):
    """数値として比較する場合の正規化(整数/小数どちらでも数値的に同一なら一致とみなす)。"""
    if raw is None:
        return None
    try:
        return round(float(raw), 6)
    except (TypeError, ValueError):
        return str(raw).strip() or None


def values_equal(a, b, kind="str"):
    if kind == "dvalue":
        return normalize_dvalue(a) == normalize_dvalue(b)
    if kind == "h":
        return normalize_h(a) == normalize_h(b)
    if kind == "num":
        return normalize_num(a) == normalize_num(b)
    return normalize_str(a) == normalize_str(b)


# ────────────────────────────────────────────────────────────
# ① 基本情報(MC) 比較
# ────────────────────────────────────────────────────────────

def verify_basic_info(ss_mc, pg, limit=None):
    log("① 基本情報(MC) 比較開始...")
    mcc = ss_mc.cursor()
    pgc = pg.cursor()

    # 機械名マップ(machine_code → machines.id) と逆引き(id → machine_code)
    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type IN ('MC','BOTH')")
    machine_id_to_code = {r[0]: r[1] for r in pgc.fetchall()}

    # 旧側: 部品ID, MCID, 加工ID, バージョン, MC工程No, フォルダ1/2, ファイル名,
    #       機械(文字列), 加工時間H/M/S, 加工個数, クランプ, 備考
    mcc.execute("""
        SELECT
            mc.部品ID, mc.MCID, mc.加工ID,
            m.ﾊﾞｰｼﾞｮﾝ, m.[MC工程No,], m.ﾌｫﾙﾀﾞ1, m.ﾌｫﾙﾀﾞ2, m.ﾌｧｲﾙ名,
            m.機械, m.加工時間H, m.加工時間M, m.加工時間S,
            m.加工個数, m.ｸﾗﾝﾌﾟ, m.備考
        FROM ACC_MC mc
        INNER JOIN ACC_マシニングraw m ON mc.加工ID = m.加工ID
        ORDER BY mc.MCID
    """)
    old_rows = mcc.fetchall()
    log(f"  旧DB取得: {len(old_rows)}件")
    if limit:
        old_rows = old_rows[:limit]

    # 新側: mc_programs + mc_machining_details を machining_id(=加工ID) で結合
    pgc.execute("""
        SELECT mp.legacy_mcid, mp.machining_id, mmd.version, mmd.mc_process_no,
               mmd.folder1, mmd.folder2, mmd.file_name, mmd.machine_id,
               mmd.cycle_time_sec, mp.machining_qty, mmd.clamp_note, mp.note
        FROM mc_programs mp
        JOIN mc_machining_details mmd ON mp.machining_id = mmd.machining_id
    """)
    new_by_mcid = {}
    for r in pgc.fetchall():
        new_by_mcid[r[0]] = r  # legacy_mcid をキー

    results = []
    matched = mismatched = missing_in_new = 0

    for row in old_rows:
        (buhin_id, mcid, kakoid, version, process_no, folder1, folder2, file_name,
         machine_name, time_h, time_m, time_s, qty, clamp, note) = row

        new_row = new_by_mcid.get(mcid)
        if not new_row:
            missing_in_new += 1
            results.append({
                "mcid": mcid, "kakoid": kakoid, "status": "MISSING_IN_NEW",
                "fields": [],
            })
            continue

        (n_mcid, n_kakoid, n_version, n_process_no, n_folder1, n_folder2,
         n_file_name, n_machine_id, n_cycle_sec, n_qty, n_clamp, n_note) = new_row

        # ★mc_full_import.py(PHASE1)と完全に同じ判定基準に統一:
        #   H/M/S 3つ全部NULLの時だけNone、それ以外(1つでも値があれば)は合計値。
        #   (修正前はNULLでも無条件に0扱いしていたため、新側None vs 旧側0で
        #    誤MISMATCHが288件発生していた)
        old_cycle_sec = None
        if time_h is not None or time_m is not None or time_s is not None:
            try:
                h = int(time_h or 0); m = int(time_m or 0); s = int(time_s or 0)
                old_cycle_sec = h * 3600 + m * 60 + s
            except (TypeError, ValueError):
                pass

        n_machine_code = machine_id_to_code.get(n_machine_id)

        field_checks = [
            ("加工ID",       kakoid,       n_kakoid,     "num"),
            ("バージョン",    version,      n_version,    "str"),
            ("MC工程No",     process_no,   n_process_no, "num"),
            ("フォルダ1",     folder1,      n_folder1,    "str"),
            ("フォルダ2",     folder2,      n_folder2,    "str"),
            ("ファイル名",    file_name,    n_file_name,  "str"),
            ("機械",         machine_name, n_machine_code, "str"),
            ("サイクルタイム(秒)", old_cycle_sec, n_cycle_sec, "num"),
            ("加工個数",      qty,          n_qty,        "num"),
            ("クランプ",      clamp,        n_clamp,      "str"),
            ("備考",         note,         n_note,       "str"),
        ]

        diffs = []
        for label, old_v, new_v, kind in field_checks:
            if not values_equal(old_v, new_v, kind):
                diffs.append({
                    "field": label,
                    "old": "" if old_v is None else str(old_v),
                    "new": "" if new_v is None else str(new_v),
                })

        if diffs:
            mismatched += 1
            results.append({
                "mcid": mcid, "kakoid": kakoid, "status": "MISMATCH",
                "fields": diffs,
            })
        else:
            matched += 1

    summary = {
        "category": "基本情報(MC)",
        "total": len(old_rows),
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_new": missing_in_new,
    }
    log(f"  ① 完了: total={len(old_rows)} matched={matched} mismatched={mismatched} missing={missing_in_new}")
    return summary, results


# ────────────────────────────────────────────────────────────
# ② ツーリング 比較
# ────────────────────────────────────────────────────────────

def verify_tooling(ss_mc, pg, limit=None):
    log("② ツーリング 比較開始...")
    mcc = ss_mc.cursor()
    pgc = pg.cursor()

    # ★重要: 新側(mc_tooling)は順番列の値をそのままsort_orderに格納しているため、
    #   旧側も「ツーリングID(登録順)」ではなく「順番列の値」基準で並べないと
    #   両者の行が正しく対応しない(順番列の値とAccess登録順は必ずしも一致しない)。
    #   順番が同値の行(枝番重複等)はツーリングIDで安定させ、
    #   順番がNULLの行は最後に回す(新側のsort_orderと対応が崩れないよう)。
    mcc.execute("""
        SELECT 加工ID, 順番, N, 工具, T, H, D, D値, SUB, コメント, ツーリングID
        FROM ACC_ツーリング
        ORDER BY 加工ID,
                 CASE WHEN 順番 IS NULL THEN 1 ELSE 0 END,
                 順番,
                 ツーリングID
    """)
    old_rows = mcc.fetchall()
    log(f"  旧DB取得: {len(old_rows)}件")
    if limit:
        old_rows = old_rows[:limit]

    # machining_id(=加工ID) ごとにグルーピング
    # ★ACC_ツーリングには加工ID(先頭列)がNULLの孤立行が存在するため、
    #   ソート不能(int同士でないと比較できない)エラーを避けて別集計にする。
    from collections import defaultdict
    old_by_kakoid = defaultdict(list)
    orphan_old_count = 0
    for row in old_rows:
        if row[0] is None:
            orphan_old_count += 1
            continue
        old_by_kakoid[row[0]].append(row)
    if orphan_old_count:
        log(f"  [WARN] 旧DB側で加工IDがNULLの孤立行: {orphan_old_count}件（比較対象外として除外）")

    pgc.execute("""
        SELECT mt.machining_id, mt.sort_order, mt.tool_no, mt.tool_name, mt.t_no,
               mt.length_offset_no, mt.dia_offset_no, mt.d_value_content,
               mt.sub_pg_no, mt.note
        FROM mc_tooling mt
        ORDER BY mt.machining_id, mt.sort_order
    """)
    new_by_kakoid = defaultdict(list)
    orphan_new_count = 0
    for row in pgc.fetchall():
        if row[0] is None:
            orphan_new_count += 1
            continue
        new_by_kakoid[row[0]].append(row)
    if orphan_new_count:
        log(f"  [WARN] 新DB側でmachining_idがNULLの孤立行: {orphan_new_count}件（比較対象外として除外）")

    results = []
    matched = mismatched = missing_in_new = row_count_mismatch = 0
    kakoids = sorted(old_by_kakoid.keys())

    for kakoid in kakoids:
        old_list = old_by_kakoid[kakoid]
        new_list = new_by_kakoid.get(kakoid)

        if new_list is None:
            missing_in_new += 1
            results.append({
                "kakoid": kakoid, "status": "MISSING_IN_NEW",
                "rows": [],
            })
            continue

        if len(old_list) != len(new_list):
            row_count_mismatch += 1
            results.append({
                "kakoid": kakoid, "status": "ROW_COUNT_MISMATCH",
                "old_count": len(old_list), "new_count": len(new_list),
                "rows": [],
            })
            continue

        row_diffs = []
        for idx, (old_r, new_r) in enumerate(zip(old_list, new_list)):
            (o_kakoid, o_order, o_n, o_tool, o_t, o_h, o_d, o_dval, o_sub, o_comment, o_tid) = old_r
            (n_kakoid, n_sort, n_tool_no, n_tool_name, n_t_no,
             n_h, n_d, n_dval, n_sub, n_note) = new_r

            field_checks = [
                ("N",       o_n,        n_tool_no,   "str"),
                ("工具",     o_tool,     n_tool_name, "str"),
                ("T",       o_t,        n_t_no,      "str"),
                ("H",       o_h,        n_h,         "h"),
                ("D",       o_d,        n_d,         "str"),
                ("D値",     o_dval,     n_dval,       "dvalue"),
                ("SUB",     o_sub,      n_sub,        "str"),
                ("コメント", o_comment, n_note,       "str"),
            ]
            diffs = []
            for label, old_v, new_v, kind in field_checks:
                if not values_equal(old_v, new_v, kind):
                    diffs.append({
                        "field": label,
                        "old": "" if old_v is None else str(old_v),
                        "new": "" if new_v is None else str(new_v),
                    })
            if diffs:
                row_diffs.append({"row_index": idx + 1, "fields": diffs})

        if row_diffs:
            mismatched += 1
            results.append({
                "kakoid": kakoid, "status": "MISMATCH",
                "rows": row_diffs,
            })
        else:
            matched += 1

    summary = {
        "category": "ツーリング",
        "total": len(kakoids),
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_new": missing_in_new,
        "row_count_mismatch": row_count_mismatch,
    }
    log(f"  ② 完了: total={len(kakoids)} matched={matched} mismatched={mismatched} "
        f"row_count_mismatch={row_count_mismatch} missing={missing_in_new}")
    return summary, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="検証対象を先頭N件に制限(テスト用)")
    ap.add_argument("--out", default="/tmp/verify_result.json")
    args = ap.parse_args()

    log("DB接続中...")
    ss_mc = ss_connect(SS_MC_DB)
    pg = pg_connect()
    log("接続完了")

    summary1, results1 = verify_basic_info(ss_mc, pg, args.limit)
    summary2, results2 = verify_tooling(ss_mc, pg, args.limit)

    output = {
        "generated_at": datetime.now().isoformat(),
        "summaries": [summary1, summary2],
        "details": {
            "basic_info": results1,
            "tooling": results2,
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"結果をJSON保存: {args.out}")

    ss_mc.close()
    pg.close()
    log("完了")


if __name__ == "__main__":
    main()
