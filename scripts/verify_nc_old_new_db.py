#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_nc_old_new_db.py
==========================
旧システム(SQL Server: imotomc)と新システム(PostgreSQL: machcore_dev)の
NC側データを全件機械的に比較し、不一致を検出するスクリプト。

MC側 verify_old_new_db.py と同じ実装パターンを採用し、
nc_full_import_v2.py のPHASE1〜4の判定ロジックと完全に整合させた。

検証項目:
  ① 基本情報(NC)  : ACC_NC×ACC_Lathe vs nc_programs+nc_machining_details
  ② ツーリング     : ACC_Tool vs nc_tools (machining_id=K_id単位グルーピング)
  ③ 履歴(変更/印刷/作業記録): ACC_History(K_id単位) vs 3テーブル
       (共通部品: 同一K_idに対応する全nc_programs.id群で件数を合算して比較)

【MC側との設計上の重要な違い】
  MC側はlegacy_mcidが1対1でmc_programs.idに対応するのに対し、
  NC側はlegacy_nc_id(旧NC_id)が1対1でnc_programs.idに対応するが、
  K_id(加工データ本体)は複数のNC_id(=nc_programs)から共有されうる(共通部品)。
  そのため、①基本情報とNC固有情報の比較は「legacy_nc_id単位」で行い、
  ③履歴(K_id単位で記録される旧データ)の比較は「K_id単位で期待値を算出し、
  対応する全nc_programs.id群の実績を合算」という、MC側verify_historyと
  同じ考え方をK_id基準で適用する。

  ワークオフセット/インデックスプログラムに相当する旧NC概念は存在しないため、
  NC側検証スクリプトには含めない。

実行方法:
  python3 verify_nc_old_new_db.py [--limit N] [--out /path/to/output.json]

出力:
  JSON形式の中間データ(generate_verify_report.pyと同形式)
"""
import sys, os, re, json, argparse, unicodedata
from collections import defaultdict
from datetime import datetime

PG_DSN    = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
SS_SERVER = "192.168.1.9"
SS_USER   = "sa"
SS_PASS   = "RTW65b"
SS_DB     = "imotomc"  # NC側ビューもMC側と同じDB内に存在(nc_full_import_v2.pyと同じ接続設定)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def pg_connect():
    import psycopg2
    return psycopg2.connect(PG_DSN)


def ss_connect():
    import pymssql
    return pymssql.connect(server=SS_SERVER, user=SS_USER, password=SS_PASS,
                            database=SS_DB, tds_version="7.4")


# ────────────────────────────────────────────────────────────
# 正規化ヘルパー(MC側verify_old_new_db.pyと完全に同一の実装を使用。
# 比較ロジックの一貫性を保つため、移植元と差分を作らない)
# ────────────────────────────────────────────────────────────

def normalize_str(raw):
    """前後空白除去・全角/半角スペース統一。NULL/空文字はNoneに統一。"""
    if raw is None:
        return None
    s = str(raw).strip()
    s = re.sub(r"[\s\u3000]+", " ", s)
    return s or None


def normalize_machine(raw):
    """機械名正規化: 全角/半角・大文字/小文字・ハイフン/アンダースコア/空白の表記ゆれを統一する。"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = unicodedata.normalize("NFKC", s)
    s = s.upper()
    s = re.sub(r"[\s\-_]+", "", s)
    return s or None


def normalize_num(raw):
    """数値として比較する場合の正規化。"""
    if raw is None:
        return None
    try:
        return round(float(raw), 6)
    except (TypeError, ValueError):
        return str(raw).strip() or None


def normalize_dvalue(raw_d):
    """D値正規化: 小数点以下3桁固定(NorzRはノーズR値、MC側D値と同種の浮動小数表記ゆれ対策)。"""
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


def values_equal(a, b, kind="str"):
    if kind == "num":
        return normalize_num(a) == normalize_num(b)
    if kind == "machine":
        return normalize_machine(a) == normalize_machine(b)
    if kind == "dvalue":
        return normalize_dvalue(a) == normalize_dvalue(b)
    return normalize_str(a) == normalize_str(b)


# ────────────────────────────────────────────────────────────
# ① 基本情報(NC) 比較
#   ACC_NC(部品×加工の対応行) × ACC_Lathe(加工データ本体) vs
#   nc_programs(legacy_nc_id単位) + nc_machining_details(k_id単位)
#   ※ legacy_nc_id は旧NC_idと1対1対応のため、MC側のMCID単位比較と
#     同じ考え方で「行単位」の突合が可能(K_idの共有は加工データ側のみ)。
# ────────────────────────────────────────────────────────────

def verify_basic_info_nc(ss, pg, limit=None):
    log("① 基本情報(NC) 比較開始...")
    ssc = ss.cursor()
    pgc = pg.cursor()

    # 機械コードマップ: ACC_Lathe.Machine は ACC_Machine.m_id(整数ID)を指している。
    # nc_full_import_v2.py PHASE1①と完全に同じ2段階変換を行う:
    #   m_id → ACC_Machine.Model(文字列) → machines.machine_code との直引き
    # (旧Machine列をそのままmachine_codeと比較すると型もセマンティクスも異なり、
    #  必ず不一致になってしまう)
    ssc.execute("SELECT m_id, Model FROM ACC_Machine")
    acc_machine_rows = ssc.fetchall()
    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type IN ('NC','BOTH')")
    machine_id_to_code = {r[0]: r[1] for r in pgc.fetchall()}
    machine_code_set = set(machine_id_to_code.values())
    mid_to_model = {}
    for m_id, model in acc_machine_rows:
        model_str = str(model or "").strip()
        if model_str in machine_code_set:
            mid_to_model[m_id] = model_str

    # 旧側: ACC_NC(部品×加工対応) と ACC_Lathe(加工データ本体)をK_idで結合
    ssc.execute("""
        SELECT
            nc.NC_id, nc.B_id, nc.K_id,
            l.L, l.Clamp, l.Machine, l.Tm, l.Ts, l.FD_name, l.F_name,
            l.oNo, l.Note, l.Fig, l.Photo, l.Ver
        FROM ACC_NC nc
        INNER JOIN ACC_Lathe l ON nc.K_id = l.K_id
        ORDER BY nc.NC_id
    """)
    old_rows = ssc.fetchall()
    log(f"  旧DB取得: {len(old_rows)}件")
    if limit:
        old_rows = old_rows[:limit]

    # 新側: nc_programs(legacy_nc_id単位) + nc_machining_details(machining_id=k_id結合)
    pgc.execute("""
        SELECT np.legacy_nc_id, np.machining_id, nmd.process_l, nmd.clamp_note,
               nmd.machine_id, nmd.machining_time, nmd.setup_time_ref,
               nmd.folder_name, nmd.file_name, nmd.o_number,
               nmd.drawing_count, nmd.photo_count, nmd.version
        FROM nc_programs np
        JOIN nc_machining_details nmd ON np.machining_id = nmd.k_id
        WHERE np.legacy_nc_id IS NOT NULL
    """)
    new_by_ncid = {}
    for r in pgc.fetchall():
        new_by_ncid[r[0]] = r  # legacy_nc_id をキー(1対1のはず)

    results = []
    matched = mismatched = missing_in_new = 0

    for row in old_rows:
        (ncid, bid, kid, l_no, clamp, machine_raw, tm, ts, fd_name, f_name,
         ono, note, fig, photo, ver) = row

        new_row = new_by_ncid.get(ncid)
        if not new_row:
            missing_in_new += 1
            results.append({
                "mcid": ncid, "kakoid": kid, "status": "MISSING_IN_NEW",
                "fields": [],
            })
            continue

        (n_ncid, n_kid, n_process_l, n_clamp_note, n_machine_id, n_machining_time,
         n_setup_time_ref, n_folder_name, n_file_name, n_onumber,
         n_drawing_count, n_photo_count, n_version) = new_row

        # 旧側: m_id(整数) → ACC_Machine.Model(文字列)。新側: machines.id → machine_code(文字列)。
        # 両者とも「machine_code相当の文字列」に変換してから比較する。
        old_machine_str = mid_to_model.get(machine_raw) if machine_raw is not None else None
        n_machine_code = machine_id_to_code.get(n_machine_id)

        # clamp_noteはnc_full_import_v2.py PHASE1①で
        # "クランプ: {clamp}\n{note}" 形式に合成されているため、
        # 旧側もそれを再現したうえで比較する(さもないと必ず不一致になる)。
        clamp_str = str(clamp or "").strip() or None
        note_str = str(note or "").strip() or None
        old_clamp_note = "\n".join([s for s in (
            (f"クランプ: {clamp_str}" if clamp_str else None),
            note_str,
        ) if s]) or None

        folder_name_old = str(fd_name or "").strip() or "(未設定)"

        field_checks = [
            ("K_id",        kid,        n_kid,            "num"),
            ("L(工程No)",   l_no,       n_process_l,       "num"),
            ("機械",        old_machine_str, n_machine_code, "machine"),
            ("フォルダ名",  folder_name_old, n_folder_name,  "str"),
            ("ファイル名",  f_name,     n_file_name,        "str"),
            ("oNo",        ono,        n_onumber,          "str"),
            ("クランプ/備考", old_clamp_note, n_clamp_note,  "str"),
            ("図枚数",      fig,        n_drawing_count,     "num"),
            ("写真枚数",    photo,      n_photo_count,       "num"),
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
                "mcid": ncid, "kakoid": kid, "status": "MISMATCH",
                "fields": diffs,
            })
        else:
            matched += 1

    summary = {
        "category": "基本情報(NC)",
        "total": len(old_rows),
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_new": missing_in_new,
    }
    log(f"  ① 完了: total={len(old_rows)} matched={matched} mismatched={mismatched} missing={missing_in_new}")
    return summary, results


# ────────────────────────────────────────────────────────────
# ② ツーリング 比較
#   ACC_Tool vs nc_tools (machining_id = K_id単位でグルーピング)
#   nc_full_import_v2.py PHASE2のソート基準(K_id, No, T_id)と完全に一致させる。
# ────────────────────────────────────────────────────────────

def verify_tooling_nc(ss, pg, limit=None):
    log("② ツーリング 比較開始...")
    ssc = ss.cursor()
    pgc = pg.cursor()

    ssc.execute("""
        SELECT T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note
        FROM ACC_Tool
        ORDER BY K_id,
                 CASE WHEN No IS NULL THEN 1 ELSE 0 END,
                 No, T_id
    """)
    old_rows = ssc.fetchall()
    log(f"  旧DB取得: {len(old_rows)}件")
    if limit:
        old_rows = old_rows[:limit]

    old_by_kid = defaultdict(list)
    orphan_old_count = 0
    for row in old_rows:
        if row[1] is None:
            orphan_old_count += 1
            continue
        old_by_kid[row[1]].append(row)
    if orphan_old_count:
        log(f"  [WARN] 旧DB側でK_idがNULLの孤立行: {orphan_old_count}件（比較対象外として除外）")

    pgc.execute("""
        SELECT machining_id, sort_order, process_type, chip_model,
               holder_model, nose_r, t_number, note
        FROM nc_tools
        ORDER BY machining_id, sort_order
    """)
    new_by_kid = defaultdict(list)
    orphan_new_count = 0
    for row in pgc.fetchall():
        if row[0] is None:
            orphan_new_count += 1
            continue
        new_by_kid[row[0]].append(row)
    if orphan_new_count:
        log(f"  [WARN] 新DB側でmachining_idがNULLの孤立行: {orphan_new_count}件（比較対象外として除外）")

    results = []
    matched = mismatched = missing_in_new = row_count_mismatch = 0
    kids = sorted(old_by_kid.keys())

    for kid in kids:
        old_list = old_by_kid[kid]
        new_list = new_by_kid.get(kid)

        if new_list is None:
            missing_in_new += 1
            results.append({"kakoid": kid, "status": "MISSING_IN_NEW", "rows": []})
            continue

        if len(old_list) != len(new_list):
            row_count_mismatch += 1
            results.append({
                "kakoid": kid, "status": "ROW_COUNT_MISMATCH",
                "old_count": len(old_list), "new_count": len(new_list), "rows": [],
            })
            continue

        row_diffs = []
        for idx, (old_r, new_r) in enumerate(zip(old_list, new_list)):
            (o_tid, o_kid, o_no, o_shave1, o_shave2, o_chip, o_holder, o_norzr, o_note) = old_r
            (n_kid, n_sort, n_proc_type, n_chip, n_holder, n_nose_r, n_tno, n_note) = new_r

            # nc_full_import_v2.py PHASE2: process_type = "Shave1 / Shave2" 連結文字列
            o_proc_type = " / ".join([s for s in (
                str(o_shave1).strip() if o_shave1 else None,
                str(o_shave2).strip() if o_shave2 else None,
            ) if s]) or None

            field_checks = [
                ("No(T番号)",   o_no,     n_tno,       "str"),
                ("加工種別",    o_proc_type, n_proc_type, "str"),
                ("チップ",      o_chip,   n_chip,       "str"),
                ("ホルダー",    o_holder, n_holder,     "str"),
                ("ノーズR",     o_norzr,  n_nose_r,     "dvalue"),
                ("備考",        o_note,   n_note,       "str"),
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
            results.append({"kakoid": kid, "status": "MISMATCH", "rows": row_diffs})
        else:
            matched += 1

    summary = {
        "category": "ツーリング(NC)",
        "total": len(kids),
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_new": missing_in_new,
        "row_count_mismatch": row_count_mismatch,
    }
    log(f"  ② 完了: total={len(kids)} matched={matched} mismatched={mismatched} "
        f"row_count_mismatch={row_count_mismatch} missing={missing_in_new}")
    return summary, results


# ────────────────────────────────────────────────────────────
# ③ 履歴(変更履歴/印刷履歴/作業記録) 比較
#   旧ACC_HistoryはK_id単位の1レコード。nc_full_import_v2.py PHASE3の
#   3分岐ロジック(A:setup_sheet_logs/B:work_records/C:change_history)を
#   そのまま再現し、「K_idごとに旧側で予測される各テーブルの件数」と
#   「新側で、そのK_idに対応する全nc_programs.id群に実際に入っている件数の合計」
#   を比較する(MC側verify_historyのmcid_map方式をK_id基準に適用したもの)。
# ────────────────────────────────────────────────────────────

def verify_history_nc(ss, pg, limit=None):
    log("③ 履歴(変更/印刷/作業記録) 比較開始...")
    ssc = ss.cursor()
    pgc = pg.cursor()

    ssc.execute("""
        SELECT Hist_id, K_id, NC_id, Mc,
               Out_Ver, Out_Cont, Out_Op, Out_Date,
               In_Ver, In_Cont, In_Op, In_Date,
               Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P
        FROM ACC_History
        ORDER BY K_id, In_Date
    """)
    old_rows = ssc.fetchall()
    log(f"  旧DB取得: {len(old_rows)}件")
    if limit:
        old_rows = old_rows[:limit]

    # K_id → [nc_programs.id, ...] (共通部品で複数あり得る。nc_full_import_v2.py PHASE3と同じ構築方法)
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    kid_to_program_ids = defaultdict(list)
    for prog_id, machining_id in pgc.fetchall():
        kid_to_program_ids[machining_id].append(prog_id)

    # K_idごとに旧側で予測される各テーブルの件数を、
    # nc_full_import_v2.py PHASE3 A/B/C の判定ロジックをそのまま再現して集計する。
    expected = defaultdict(lambda: {"setup_sheet_logs": 0, "change_history": 0, "work_records": 0})

    for row in old_rows:
        (hist_id, k_id, nc_id_old, mc_raw,
         out_ver, out_cont, out_op, out_date,
         in_ver, in_cont, in_op, in_date,
         dan_op, dan_h, dan_m, la_op, la_h, la_m, p) = row

        if k_id is None:
            continue

        out_cont_s = str(out_cont or "").strip()
        in_cont_s = str(in_cont or "").strip()

        # A: setup_sheet_logs（Out_Cont = "印刷"、Out_Dateあり）
        if "印刷" in out_cont_s and out_date:
            expected[k_id]["setup_sheet_logs"] += 1

        # B: work_records（Dan_*/La_*/P に実データあり）
        dan_h_i = int(dan_h) if dan_h is not None else 0
        dan_m_i = int(dan_m) if dan_m is not None else 0
        la_h_i = int(la_h) if la_h is not None else 0
        la_m_i = int(la_m) if la_m is not None else 0
        p_i = int(p) if p is not None else 0
        dan_op_s = str(dan_op or "").strip()
        has_work_data = bool(dan_op_s) or dan_h_i > 0 or dan_m_i > 0 or la_h_i > 0 or la_m_i > 0 or p_i > 0
        if has_work_data:
            expected[k_id]["work_records"] += 1

        # C: change_history（In_Cont が新規登録/仮登録/変更/承認、In_Dateあり）
        is_nc_change = any(kw in in_cont_s for kw in ("新規登録", "仮登録", "変更", "承認"))
        if is_nc_change and in_date:
            expected[k_id]["change_history"] += 1

    # 新側の実際の件数を nc_program_id 単位で集計
    pgc.execute("SELECT nc_program_id, COUNT(*) FROM setup_sheet_logs GROUP BY nc_program_id")
    actual_sl = dict(pgc.fetchall())
    pgc.execute("SELECT nc_program_id, COUNT(*) FROM change_history GROUP BY nc_program_id")
    actual_ch = dict(pgc.fetchall())
    pgc.execute("SELECT nc_program_id, COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL GROUP BY nc_program_id")
    actual_wr = dict(pgc.fetchall())

    results = []
    matched = mismatched = missing_in_new = 0
    kids = sorted(expected.keys())
    if limit:
        kids = kids[:limit]

    for kid in kids:
        prog_ids = kid_to_program_ids.get(kid, [])
        if not prog_ids:
            missing_in_new += 1
            results.append({"kakoid": kid, "status": "MISSING_IN_NEW", "rows": []})
            continue

        exp = expected[kid]
        # 共通部品(同一K_idが複数nc_programsに展開)では、nc_full_import_v2.py PHASE3が
        # 1件のHist_id行を len(prog_ids) 件に複製してINSERTする。
        # そのため期待値側も同じ倍率(len(prog_ids))を乗じてから新側の合算値と比較する
        # (新側は既に複製後の実件数のため、複製しない場合の生件数のままでは
        #  共通部品の全K_idで必ず不一致になってしまっていたバグを修正)。
        dup_factor = len(prog_ids)
        exp_sl = exp["setup_sheet_logs"] * dup_factor
        exp_ch = exp["change_history"] * dup_factor
        exp_wr = exp["work_records"] * dup_factor
        act_sl = sum(actual_sl.get(pid, 0) for pid in prog_ids)
        act_ch = sum(actual_ch.get(pid, 0) for pid in prog_ids)
        act_wr = sum(actual_wr.get(pid, 0) for pid in prog_ids)

        field_checks = [
            ("印刷履歴件数", exp_sl, act_sl, "num"),
            ("変更履歴件数", exp_ch, act_ch, "num"),
            ("作業記録件数", exp_wr, act_wr, "num"),
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
                "kakoid": kid, "status": "MISMATCH",
                "rows": [{"row_index": 1, "fields": diffs}],
            })
        else:
            matched += 1

    summary = {
        "category": "履歴(NC: 変更/印刷/作業記録)",
        "total": len(kids),
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_new": missing_in_new,
    }
    log(f"  ③ 完了: total={len(kids)} matched={matched} mismatched={mismatched} missing={missing_in_new}")
    return summary, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="検証対象を先頭N件に制限(テスト用)")
    ap.add_argument("--out", default="/tmp/verify_nc_result.json")
    args = ap.parse_args()

    log("DB接続中...")
    ss = ss_connect()
    pg = pg_connect()
    log("接続完了")

    summary1, results1 = verify_basic_info_nc(ss, pg, args.limit)
    summary2, results2 = verify_tooling_nc(ss, pg, args.limit)
    summary3, results3 = verify_history_nc(ss, pg, args.limit)

    output = {
        "generated_at": datetime.now().isoformat(),
        "summaries": [summary1, summary2, summary3],
        # generate_verify_report.py(MC用に作られた既存レポート生成ツール)を
        # NC側でもそのまま再利用できるよう、MC側と同じキー名(basic_info/tooling/history)
        # を使う。ワークオフセット/インデックスプログラムに相当するNC概念は存在しないため、
        # 該当キー(work_offsets/index_programs)は空配列として埋めておく
        # (generate_verify_report.py側がdetails.get(...)で存在しないキーを
        #  想定していないケースに備えた安全策)。
        "details": {
            "basic_info":   results1,
            "tooling":      results2,
            "work_offsets": [],
            "index_programs": [],
            "history":      results3,
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"結果をJSON保存: {args.out}")

    ss.close()
    pg.close()
    log("完了")


if __name__ == "__main__":
    main()
