#!/usr/bin/env python3
# coding: utf-8
"""
MachCore NC完全移行スクリプト (nc_full_import.py)
=================================================
mc_full_import.py と同じ枠組み(SQL Serverリンクサーバビュー経由・pymssql直接取得)で
NC側データを移行する。

実行方法:
  python3 nc_full_import.py [--phase N] [--dry-run]

フェーズ:
  0 = 全フェーズ一括実行（本番用）
  1 = nc_programs基本データ移行（ACC_NC × ACC_Lathe）
  2 = nc_tools移行（ACC_Tool）
  3 = ACC_History → 3テーブル分離移行（setup_sheet_logs/work_records/change_history）
  4 = nc_programs.status 正規化

ソースDB: imotomc (192.168.1.9) ※NC側ビューもMC側と同じimotomc DB内に存在
  - ACC_NC      : NC_id, B_id, K_id
  - ACC_Lathe   : K_id, L, Clamp, Machine, Tm, Ts, FD_name, F_name, oNo, Note,
                  Fig, Photo, Ver, Reco_P, Reco_D
  - ACC_Tool    : T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note
  - ACC_FD      : FD_id, FD_name
  - ACC_Machine : m_id, Model
  - ACC_Staff   : St_id, S_name, Password
  - ACC_History : Hist_id, K_id, NC_id, Mc, Out_Ver, Out_Cont, Out_Op, Out_Date,
                  In_Ver, In_Cont, In_Op, In_Date, Dan_Op, Dan_H, Dan_M,
                  La_Op, La_H, La_M, P

部品/得意先: parts テーブルは MC側で既に sync_parts.py により同期済みの
            既存資産を再利用する（imotodb 経由の新規移行は行わない）。

machines テーブルも既存資産を再利用する。ACC_Machine の Model(機械コード文字列)を
machines.machine_code に対して直引きする(MC方式と同じ)。
ACC_FD は nc_programs.folder_name の補完にのみ使う(FD_name→FD_idの逆引き)。

ユーザー: ACC_Staff の St_id → employee_code "STAFF{St_id:03d}" で users.id に解決する
         (migrate_v2.ts と同じ命名規則。既存usersデータが既にこの規則で作成済みのため
          新規ユーザー作成は行わない)。
"""

import sys, os, re, argparse, traceback
from pathlib import Path
from datetime import datetime, timedelta

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _load_pg_dsn():
    import re as _re
    _env = Path(__file__).resolve().parent.parent / "apps" / "api" / ".env"
    with open(_env, encoding="utf-8") as _f:
        for _line in _f:
            _m = _re.match(r'^DATABASE_URL="?([^"\n]*)"?$', _line.strip())
            if _m:
                _url = _m.group(1)
                # psycopg2はPrisma固有のクエリパラメータ(?schema=public等)を
                # 解釈できずinvalid dsnエラーになるため、クエリ部分を除去する。
                _url = _url.split("?", 1)[0]
                return _url
    raise RuntimeError(f"DATABASE_URL not found in {_env}")
PG_DSN = _load_pg_dsn()
SS_SERVER    = "192.168.1.9"
SS_USER      = "sa"
SS_PASS      = "RTW65b"
SS_DB        = "imotomc"   # NC側ビューもMC側と同じDB内に存在(diag_v017/v018bで確認済み)
LOG_FILE     = Path("/home/karkyon/projects/machcore-internal/logs/nc_full_import.log")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーティリティ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_log_fh = open(LOG_FILE, "a", encoding="utf-8")


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    _log_fh.write(line + "\n")
    _log_fh.flush()


def section(title):
    bar = "=" * 60
    log(f"\n{bar}\n  {title}\n{bar}")


def pg_connect():
    import psycopg2
    return psycopg2.connect(PG_DSN)


def ss_connect():
    import pymssql
    return pymssql.connect(server=SS_SERVER, user=SS_USER,
                            password=SS_PASS, database=SS_DB, tds_version='7.4')


def to_jst_utc(dt):
    """SQL Serverから来るJSTのnaive datetimeをUTCに変換（-9h）。mc_full_import.pyと同じ規則。"""
    if dt is None:
        return None
    try:
        return dt - timedelta(hours=9)
    except Exception:
        return dt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: nc_programs 基本データ移行 (ACC_NC × ACC_Lathe)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase1(pg, dry_run=False):
    section("PHASE 1: nc_programs 基本データ移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    if not dry_run:
        log("既存NC関連データ全破棄...")
        pgc.execute("DELETE FROM nc_files")
        pgc.execute("DELETE FROM change_history")
        pgc.execute("DELETE FROM setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM operation_logs WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM work_sessions WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM nc_tools")  # onDelete:Cascadeだが明示削除して件数を見える化
        pgc.execute("DELETE FROM nc_programs")
        pg.commit()
        log("全破棄完了")

    # parts は既存資産を再利用(MC側 sync_parts.py で同期済み)
    pgc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pgc.fetchall()}
    log(f"parts既存件数: {len(parts_map)}件（新規移行は行わない）")

    # machines は既存資産を再利用。ACC_Machine.Model(文字列) → machines.machine_code 直引き
    ssc.execute("SELECT m_id, Model FROM ACC_Machine")
    acc_machine_rows = ssc.fetchall()
    pgc.execute("SELECT id, machine_code FROM machines")
    machine_code_map = {r[1]: r[0] for r in pgc.fetchall()}
    # m_id(整数) → machines.id のマップを構築(ACC_Lathe.Machineが指すキー)
    machine_id_map = {}
    machine_unmatched = 0
    for m_id, model in acc_machine_rows:
        model_str = str(model or "").strip()
        if model_str in machine_code_map:
            machine_id_map[m_id] = machine_code_map[model_str]
        else:
            machine_unmatched += 1
    log(f"ACC_Machine取得: {len(acc_machine_rows)}件, machines対応: {len(machine_id_map)}件, 未対応: {machine_unmatched}件")

    # ACC_FD: FD_id → FD_name (folder_name補完用)
    # 注意: ACC_Lathe.FD_name列の実際の意味(ACC_FD.FD_idへの参照値なのか、
    #       それ自体が既にフォルダ識別コードなのか)は diag_v020_fd_name_mapping.py
    #       の確認結果を踏まえて確定させる。確証が取れるまでは、安全側として
    #       ACC_Lathe.FD_nameの値をそのままfolder_nameとして使用する
    #       (migrate_v2.tsのFD_id逆引きロジックは未確証のため今回は採用しない)。
    ssc.execute("SELECT FD_id, FD_name FROM ACC_FD")
    fd_map = {r[0]: (r[1] or "").strip() for r in ssc.fetchall()}
    log(f"ACC_FD取得: {len(fd_map)}件 (参考情報として取得のみ。folder_name解決には未使用)")

    # ACC_Staff: St_id → employee_code "STAFF{:03d}" → users.id 解決
    pgc.execute("SELECT id, employee_code FROM users")
    code_to_userid = {r[1]: r[0] for r in pgc.fetchall()}
    ssc.execute("SELECT St_id, S_name FROM ACC_Staff")
    staff_rows = ssc.fetchall()
    staff_id_map = {}  # St_id(int) → users.id
    staff_unmatched = 0
    for st_id, s_name in staff_rows:
        code = f"STAFF{int(st_id):03d}"
        if code in code_to_userid:
            staff_id_map[st_id] = code_to_userid[code]
        else:
            staff_unmatched += 1
    log(f"ACC_Staff取得: {len(staff_rows)}件, users対応: {len(staff_id_map)}件, 未対応: {staff_unmatched}件")
    if staff_unmatched > 0:
        log(f"  [WARN] 未対応St_idが{staff_unmatched}件あります。registered_byはADMIN(id=22)にフォールバックします。", "WARN")

    ADMIN_FALLBACK_ID = 22  # メモリ記載のADMIN_ID(MC側と共通)

    # ACC_NC × ACC_Lathe を K_id で結合
    ssc.execute("""
        SELECT n.NC_id, n.B_id, n.K_id,
               l.L, l.Clamp, l.Machine, l.Tm, l.Ts, l.FD_name, l.F_name,
               l.oNo, l.Note, l.Fig, l.Photo, l.Ver, l.Reco_P, l.Reco_D
        FROM ACC_NC n
        INNER JOIN ACC_Lathe l ON n.K_id = l.K_id
        ORDER BY n.NC_id
    """)
    rows = ssc.fetchall()
    log(f"旧DB ACC_NC×ACC_Lathe取得: {len(rows)}件")

    ok = skip = err = 0
    nc_id_map = {}   # 旧NC_id(int) → nc_programs.id
    kid_map = {}     # 旧K_id(int) → nc_programs.id (PHASE2/3で使用)

    for row in rows:
        try:
            (ncid, bid, kid,
             l_no, clamp, machine_raw, tm, ts, fd_name_raw, f_name,
             ono, note, fig, photo, ver, reco_p, reco_d) = row

            part_db_id = parts_map.get(str(bid))
            if not part_db_id:
                skip += 1
                continue

            machine_db_id = machine_id_map.get(machine_raw) if machine_raw is not None else None

            # FD_name: ACC_Lathe.FD_name列の値をそのままfolder_nameとして使用する。
            # (ACC_FD経由の逆引きは diag_v020 の確認結果が出るまで保留。詳細はPHASE1冒頭コメント参照)
            folder_name = str(fd_name_raw or "").strip() or "(未設定)"

            clamp_str = str(clamp or "").strip() or None
            note_str = str(note or "").strip() or None
            clamp_note = "\n".join([s for s in (
                (f"クランプ: {clamp_str}" if clamp_str else None),
                note_str,
            ) if s]) or None

            machining_time = int(tm) if tm is not None else None
            setup_time_ref = int(ts) if ts is not None else None
            process_l = int(l_no) if l_no is not None else 1

            registered_by = staff_id_map.get(reco_p, ADMIN_FALLBACK_ID)
            registered_at = to_jst_utc(reco_d) if reco_d else datetime(2005, 1, 1)

            ver_str = str(int(ver)) if ver is not None else "0"

            if dry_run:
                # dry-run時もPHASE2/3の検証のため、仮想ID(負数、実DBには存在しない)で
                # マッピングだけ構築する。これにより後続フェーズのskip/ok集計が
                # 本番実行時の挙動を正しく模擬できる。
                virtual_id = -int(kid)
                nc_id_map[ncid] = virtual_id
                kid_map[int(kid)] = virtual_id
                ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_programs (
                    part_id, process_l, machine_id, machining_time, setup_time_ref,
                    folder_name, file_name, o_number, version, clamp_note,
                    drawing_count, photo_count, status, registered_by, registered_at,
                    legacy_ver, legacy_kid, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'APPROVED'::nc_program_status,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT ON CONSTRAINT unique_part_process DO UPDATE SET
                    machine_id=EXCLUDED.machine_id, machining_time=EXCLUDED.machining_time,
                    setup_time_ref=EXCLUDED.setup_time_ref, folder_name=EXCLUDED.folder_name,
                    file_name=EXCLUDED.file_name, o_number=EXCLUDED.o_number,
                    version=EXCLUDED.version, clamp_note=EXCLUDED.clamp_note,
                    drawing_count=EXCLUDED.drawing_count, photo_count=EXCLUDED.photo_count,
                    legacy_ver=EXCLUDED.legacy_ver, legacy_kid=EXCLUDED.legacy_kid,
                    updated_at=NOW()
                RETURNING id
            """, (part_db_id, process_l, machine_db_id, machining_time, setup_time_ref,
                  folder_name, str(f_name) if f_name is not None else "", str(ono) if ono is not None else None,
                  ver_str, clamp_note,
                  int(fig or 0), int(photo or 0), registered_by, registered_at,
                  str(ver) if ver is not None else None, int(kid)))
            new_id = pgc.fetchone()[0]
            nc_id_map[ncid] = new_id
            kid_map[int(kid)] = new_id
            ok += 1
            if ok % 2000 == 0:
                pg.commit()
                log(f"  {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run:
                pg.rollback()
            if err <= 5:
                log(f"  ERR: NC_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_programs")
        log(f"PHASE1完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE1完了(dry-run): ok={ok} skip={skip} err={err}")

    ss.close()
    return nc_id_map, kid_map, staff_id_map, machine_id_map


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: nc_tools 移行 (ACC_Tool)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase2(pg, dry_run=False, kid_map=None):
    section("PHASE 2: nc_tools 移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    if not kid_map:
        # phase1を経ずに--phase 2単独実行された場合、またはdry-run時に
        # kid_mapが空(None/{})だった場合に備え、legacy_kidから再構築する。
        # 本番実行後のDBにはlegacy_kidが入っているため、ここでの再構築は
        # 「PHASE1を本番実行済みの状態でPHASE2だけ再実行する」場合に正しく機能する。
        # (dry-run単体で--phase 2のみ実行した場合はDBにデータが無く0件になる点に注意)
        pgc.execute("SELECT id, legacy_kid FROM nc_programs WHERE legacy_kid IS NOT NULL")
        kid_map = {r[1]: r[0] for r in pgc.fetchall()}
        log(f"kid_map再構築: {len(kid_map)}件")

    if not dry_run:
        pgc.execute("DELETE FROM nc_tools")
        pg.commit()
        log("nc_tools既存データ削除完了")

    ssc.execute("""
        SELECT T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note
        FROM ACC_Tool
        ORDER BY K_id,
                 CASE WHEN No IS NULL THEN 1 ELSE 0 END,
                 No, T_id
    """)
    rows = ssc.fetchall()
    log(f"ACC_Tool取得: {len(rows)}件")

    ok = skip = err = 0
    reseq_prev_kid = None
    reseq_counter = 0

    for row in rows:
        try:
            t_id, k_id, no, shave1, shave2, chip, holder, nose_r, note = row
            new_nc_id = kid_map.get(k_id)
            if not new_nc_id:
                skip += 1
                continue

            if k_id != reseq_prev_kid:
                reseq_prev_kid = k_id
                reseq_counter = 0
            reseq_counter += 1
            sort_order = reseq_counter * 10

            process_type = " / ".join([s for s in (
                str(shave1).strip() if shave1 else None,
                str(shave2).strip() if shave2 else None,
            ) if s]) or None

            if dry_run:
                ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_tools (
                    nc_program_id, sort_order, process_type, chip_model,
                    holder_model, nose_r, t_number, note, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            """, (new_nc_id, sort_order, process_type,
                  str(chip).strip() if chip else None,
                  str(holder).strip() if holder else None,
                  str(nose_r) if nose_r is not None else None,
                  str(no).strip() if no is not None else None,
                  str(note).strip() if note else None))
            ok += 1
            if ok % 5000 == 0:
                pg.commit()
                log(f"  {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run:
                pg.rollback()
            if err <= 5:
                log(f"  ERR: T_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_tools")
        log(f"PHASE2完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE2完了(dry-run): ok={ok} skip={skip} err={err}")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3: ACC_History → 3テーブル分離移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#   migrate_v2.ts の設計方針をそのまま継承:
#     Out_Cont に "印刷" を含む           → setup_sheet_logs
#     Dan_Op/Dan_H/Dan_M/La_Op/La_H/La_M/P あり → work_records
#     In_Cont が "新規登録"/"仮登録"/"変更"/"承認" 等 → change_history
#   1レコードが複数テーブルに分かれる場合あり
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def guess_change_type(in_cont):
    if not in_cont:
        return "CHANGE"
    s = str(in_cont)
    if "新規" in s or "仮登録" in s:
        return "NEW_REGISTRATION"
    if "承認" in s:
        return "APPROVAL"
    if "移行" in s or "migration" in s.lower():
        return "MIGRATION"
    return "CHANGE"


def phase3(pg, dry_run=False, nc_id_map=None, staff_id_map=None, machine_id_map=None):
    section("PHASE 3: ACC_History 完全分離移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    # kid_to_dbid は常にDB(nc_programs.legacy_kid)から再構築する。
    # PHASE1から引数で渡されたnc_id_map/kid_mapは(dry-run時は仮想IDのため)
    # ここでは使用しない。本番実行後のDBが正であることを前提にする。
    pgc.execute("SELECT id, legacy_kid FROM nc_programs WHERE legacy_kid IS NOT NULL")
    kid_to_dbid = {r[1]: r[0] for r in pgc.fetchall()}
    log(f"kid_to_dbid構築: {len(kid_to_dbid)}件")
    if dry_run and kid_to_dbid:
        log("  [NOTICE] dry-run中ですが、DBに既存のnc_programsデータが残っているため、"
            "PHASE3/PHASE4の件数は新規インポート内容ではなく既存データに対する参考値です。"
            "PHASE1の本番実行(--dry-run無し)後に改めてPHASE3/4を確認してください。", "WARN")

    if staff_id_map is None:
        pgc.execute("SELECT id, employee_code FROM users")
        code_to_userid = {r[1]: r[0] for r in pgc.fetchall()}
        ssc.execute("SELECT St_id, S_name FROM ACC_Staff")
        staff_id_map = {}
        for st_id, s_name in ssc.fetchall():
            code = f"STAFF{int(st_id):03d}"
            if code in code_to_userid:
                staff_id_map[st_id] = code_to_userid[code]

    # 氏名文字列(Dan_Op/La_Op)逆引き用: users.name → id
    pgc.execute("SELECT id, name FROM users")
    name_to_userid = {}
    for uid, name in pgc.fetchall():
        normed = re.sub(r"[\s\u3000]+", " ", name or "").strip()
        name_to_userid[normed] = uid
        name_to_userid[name] = uid

    if machine_id_map is None:
        ssc.execute("SELECT m_id, Model FROM ACC_Machine")
        acc_rows = ssc.fetchall()
        pgc.execute("SELECT id, machine_code FROM machines")
        code_map = {r[1]: r[0] for r in pgc.fetchall()}
        machine_id_map = {}
        for m_id, model in acc_rows:
            model_str = str(model or "").strip()
            if model_str in code_map:
                machine_id_map[m_id] = code_map[model_str]

    ADMIN_FALLBACK_ID = 22

    if not dry_run:
        pgc.execute("DELETE FROM change_history")
        pgc.execute("DELETE FROM setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE nc_program_id IS NOT NULL")
        pg.commit()
        log("change_history / setup_sheet_logs / work_records(NC分) 削除完了")

    ssc.execute("""
        SELECT Hist_id, K_id, NC_id, Mc,
               Out_Ver, Out_Cont, Out_Op, Out_Date,
               In_Ver, In_Cont, In_Op, In_Date,
               Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P
        FROM ACC_History
        ORDER BY K_id, In_Date
    """)
    rows = ssc.fetchall()
    log(f"ACC_History取得: {len(rows)}件")

    sl_ok = sl_skip = sl_err = 0
    wr_ok = wr_skip = wr_err = 0
    ch_ok = ch_skip = ch_err = 0

    for row in rows:
        try:
            (hist_id, k_id, nc_id_old, mc_raw,
             out_ver, out_cont, out_op, out_date,
             in_ver, in_cont, in_op, in_date,
             dan_op, dan_h, dan_m, la_op, la_h, la_m, p) = row

            new_nc_id = kid_to_dbid.get(k_id)
            if not new_nc_id:
                sl_skip += 1
                wr_skip += 1
                ch_skip += 1
                continue

            out_cont_s = str(out_cont or "").strip()
            in_cont_s = str(in_cont or "").strip()
            out_date_utc = to_jst_utc(out_date)
            in_date_utc = to_jst_utc(in_date)

            # ── A: setup_sheet_logs（Out_Cont = "印刷"）
            if "印刷" in out_cont_s and out_date_utc:
                op_id = staff_id_map.get(out_op, ADMIN_FALLBACK_ID)
                try:
                    if not dry_run:
                        out_ver_str = str(int(out_ver)) if out_ver is not None else None
                        pgc.execute("""
                            INSERT INTO setup_sheet_logs (
                                nc_program_id, operator_id, printed_at, version,
                                pdf_path, session_id, work_collected
                            ) VALUES (%s,%s,%s,%s,NULL,NULL,true)
                        """, (new_nc_id, op_id, out_date_utc, out_ver_str))
                    sl_ok += 1
                except Exception as e:
                    sl_err += 1
                    if not dry_run:
                        pg.rollback()

            # ── B: work_records（Dan_*/La_*/P に実データあり）
            dan_h_i = int(dan_h) if dan_h is not None else 0
            dan_m_i = int(dan_m) if dan_m is not None else 0
            la_h_i = int(la_h) if la_h is not None else 0
            la_m_i = int(la_m) if la_m is not None else 0
            p_i = int(p) if p is not None else 0
            dan_op_s = str(dan_op or "").strip()
            la_op_s = str(la_op or "").strip()
            has_work_data = bool(dan_op_s) or dan_h_i > 0 or dan_m_i > 0 or la_h_i > 0 or la_m_i > 0 or p_i > 0

            if has_work_data:
                setup_min = (dan_h_i * 60 + dan_m_i) or None
                mach_min = (la_h_i * 60 + la_m_i) or None
                dan_norm = re.sub(r"[\s\u3000]+", " ", dan_op_s).strip()
                la_norm = re.sub(r"[\s\u3000]+", " ", la_op_s).strip()
                work_op_id = (name_to_userid.get(dan_op_s) or name_to_userid.get(dan_norm)
                              or name_to_userid.get(la_op_s) or name_to_userid.get(la_norm)
                              or staff_id_map.get(in_op, ADMIN_FALLBACK_ID))
                work_machine_id = machine_id_map.get(mc_raw) if mc_raw is not None else None
                work_date = in_date_utc or out_date_utc or datetime(2005, 1, 1)
                note_parts = [s for s in (
                    f"段取: {dan_op_s}" if dan_op_s else None,
                    f"加工: {la_op_s}" if la_op_s and la_op_s != dan_op_s else None,
                ) if s]
                note_str = ", ".join(note_parts) or None
                try:
                    if not dry_run:
                        pgc.execute("""
                            INSERT INTO work_records (
                                nc_program_id, operator_id, machine_id, work_date,
                                setup_time_min, machining_time_min, quantity, note, created_at
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        """, (new_nc_id, work_op_id, work_machine_id, work_date,
                              setup_min, mach_min, p_i if p_i > 0 else None, note_str))
                    wr_ok += 1
                except Exception as e:
                    wr_err += 1
                    if not dry_run:
                        pg.rollback()

            # ── C: change_history（In_Cont が新規登録/仮登録/変更/承認）
            is_nc_change = any(kw in in_cont_s for kw in ("新規登録", "仮登録", "変更", "承認"))
            if is_nc_change and in_date_utc:
                op_id = staff_id_map.get(in_op, ADMIN_FALLBACK_ID)
                try:
                    if not dry_run:
                        ver_before = str(int(out_ver)) if out_ver is not None else None
                        ver_after = str(int(in_ver)) if in_ver is not None else None
                        field_changes = None
                        if out_cont_s and "印刷" not in out_cont_s:
                            import json as _json
                            field_changes = _json.dumps({"out_content": out_cont_s})
                        pgc.execute("""
                            INSERT INTO change_history (
                                nc_program_id, change_type, operator_id,
                                version_before, version_after, content,
                                field_changes, changed_at, legacy_hist_id
                            ) VALUES (%s,%s::change_type,%s,%s,%s,%s,%s,%s,%s)
                        """, (new_nc_id, guess_change_type(in_cont_s), op_id,
                              ver_before, ver_after, in_cont_s or None,
                              field_changes, in_date_utc, int(hist_id)))
                    ch_ok += 1
                except Exception as e:
                    ch_err += 1
                    if not dry_run:
                        pg.rollback()

            if not dry_run and (sl_ok + wr_ok + ch_ok) % 5000 == 0:
                pg.commit()
        except Exception as e:
            log(f"  ERR: Hist_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()

    log(f"PHASE3完了: setup_sheet_logs ok={sl_ok} skip={sl_skip} err={sl_err}")
    log(f"            work_records     ok={wr_ok} skip={wr_skip} err={wr_err}")
    log(f"            change_history   ok={ch_ok} skip={ch_skip} err={ch_err}")
    log(f"  【内訳】ACC_History {len(rows)}件 → 最大 {sl_ok + wr_ok + ch_ok} レコードに展開")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: nc_programs.status 正規化
#   mc_full_import.py PHASE10と同じ判定ロジックをNC側に適用
#   旧VBA判定: In_Cont/Out_Cont の内容に基づきstatusを決定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase4(pg, dry_run=False):
    section("PHASE 4: nc_programs.status 正規化")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    PRINT_CONTENTS = {"印刷"}
    TENTATIVE_CONTENTS = {"仮登録", "仮試作"}
    APPROVAL_CONTENTS = {"承認"}

    ssc.execute("""
        SELECT K_id, In_Cont, Out_Cont, In_Date
        FROM ACC_History
        WHERE In_Cont IS NOT NULL OR Out_Cont IS NOT NULL
        ORDER BY K_id, In_Date DESC
    """)
    rows = ssc.fetchall()
    log(f"ACC_History取得: {len(rows)}件")

    kid_latest_in = {}
    kid_has_print = set()
    kid_has_approval = set()

    for k_id, in_cont, out_cont, in_date in rows:
        if k_id is None:
            continue
        ic = str(in_cont or "").strip()
        oc = str(out_cont or "").strip()
        if k_id not in kid_latest_in:
            kid_latest_in[k_id] = ic
        if any(kw in oc for kw in PRINT_CONTENTS):
            kid_has_print.add(k_id)
        if any(kw in ic for kw in APPROVAL_CONTENTS):
            kid_has_approval.add(k_id)

    log(f"PRINT系有りK_id: {len(kid_has_print)}件")
    log(f"承認有りK_id: {len(kid_has_approval)}件")

    pgc.execute("SELECT id, legacy_kid FROM nc_programs WHERE legacy_kid IS NOT NULL")
    nc_rows = pgc.fetchall()
    log(f"nc_programs取得: {len(nc_rows)}件")

    stat_new = stat_approved = stat_pending = 0

    if not dry_run:
        for nc_db_id, legacy_kid in nc_rows:
            latest_in = kid_latest_in.get(legacy_kid, "")
            has_print = legacy_kid in kid_has_print
            has_approval = legacy_kid in kid_has_approval

            is_tentative = any(kw in latest_in for kw in TENTATIVE_CONTENTS)

            if has_print:
                if is_tentative:
                    new_status = "NEW"
                    stat_new += 1
                else:
                    new_status = "APPROVED"
                    stat_approved += 1
            else:
                if has_approval:
                    new_status = "APPROVED"
                    stat_approved += 1
                else:
                    new_status = "PENDING_APPROVAL"
                    stat_pending += 1

            pgc.execute(
                "UPDATE nc_programs SET status = %s::nc_program_status WHERE id = %s",
                (new_status, nc_db_id)
            )
        pg.commit()
        log(f"status更新: NEW={stat_new} APPROVED={stat_approved} PENDING_APPROVAL={stat_pending}")

        pgc.execute("SELECT status, COUNT(*) FROM nc_programs GROUP BY status ORDER BY status")
        for row in pgc.fetchall():
            log(f"  DB確認 status={row[0]}: {row[1]}件")
    else:
        log("(dry-run のため status 更新はスキップ)")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 最終レポート
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def final_report(pg):
    section("最終レポート")
    pgc = pg.cursor()
    for label, sql in [
        ("nc_programs", "SELECT COUNT(*) FROM nc_programs"),
        ("nc_tools", "SELECT COUNT(*) FROM nc_tools"),
        ("change_history(NC)", "SELECT COUNT(*) FROM change_history"),
        ("setup_sheet_logs", "SELECT COUNT(*) FROM setup_sheet_logs"),
        ("work_records(NC)", "SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL"),
    ]:
        pgc.execute(sql)
        log(f"  {label}: {pgc.fetchone()[0]}件")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(description="MachCore NC完全移行スクリプト")
    parser.add_argument("--phase", type=int, default=0, help="実行フェーズ (0=全, 1-4=個別)")
    parser.add_argument("--dry-run", action="store_true", help="DBへの書き込みなし")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    pg = pg_connect()
    try:
        nc_id_map = kid_map = staff_id_map = machine_id_map = None

        if args.phase in (0, 1):
            nc_id_map, kid_map, staff_id_map, machine_id_map = phase1(pg, dry_run=dry)
        if args.phase in (0, 2):
            phase2(pg, dry_run=dry, kid_map=kid_map)
        if args.phase in (0, 3):
            phase3(pg, dry_run=dry, nc_id_map=nc_id_map, staff_id_map=staff_id_map, machine_id_map=machine_id_map)
        if args.phase in (0, 4):
            phase4(pg, dry_run=dry)

        if args.phase == 0:
            final_report(pg)
    except Exception as e:
        log(f"エラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        raise
    finally:
        pg.close()
        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n総実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        _log_fh.close()


if __name__ == "__main__":
    main()
