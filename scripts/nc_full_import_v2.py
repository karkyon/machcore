#!/usr/bin/env python3
# coding: utf-8
"""
MachCore NC完全移行スクリプト (nc_full_import.py) — v2 (新スキーマ対応版)
========================================================================
v038で導入された新スキーマ(NcMachiningDetail + NcProgram)に対応する。

【v1からの変更点】
  旧ACC_NC(NC_id, B_id, K_id)は、MC側ACC_MC(MCID, 部品ID, 加工ID)と同じ構造の
  「部品ID×加工データの対応表」であり、同一K_id(加工データ)が複数のB_id(部品ID)
  から共有される「共通部品」パターンが旧データに実在する(診断v035/v036/v037で確認済み)。
  v1は(part_id, process_l)にunique制約をかけ、これを後勝ち上書きで1レコードに
  集約していたため、共通部品の一方の情報が失われる欠陥があった。

  v2では mc_full_import.py PHASE1/PHASE6 と完全に同じ設計方針を採用する:
    - NcMachiningDetail: PKに旧K_idをそのまま使用(ON CONFLICT(k_id) DO UPDATE)。
      加工データ本体は1K_idにつき1レコードのみ。
    - NcProgram: ACC_NCの行ごとに無条件INSERT(unique制約なし)。
      同一K_idに複数のB_id行があれば、複数のNcProgramレコードが作られ、
      全てが同じNcMachiningDetail(machining_id)を参照する。
    - nc_tools: ncProgramId参照 → machiningId(=K_id)参照に変更。
      K_id自体が新PKなので、旧kid_mapとnew_idの対応が単純化される。
    - change_history/setup_sheet_logs/work_records: 旧ACC_HistoryはK_id単位の
      レコードなので、mc_full_import.py PHASE6と同じく「1件の旧履歴行を、
      そのK_idに対応する全NcProgram行に複製してINSERTする」方式を採用する。

実行方法:
  python3 nc_full_import.py [--phase N] [--dry-run]

フェーズ:
  0 = 全フェーズ一括実行（本番用）
  1 = nc_machining_details + nc_programs 基本データ移行（ACC_NC × ACC_Lathe）
  2 = nc_tools移行（ACC_Tool、machining_id参照）
  3 = ACC_History → 3テーブル分離移行（setup_sheet_logs/work_records/change_history、
      K_id→全対応NcProgramへ複製）
  4 = nc_programs.status 正規化（K_id単位の判定をその全対応NcProgramへ展開）
  5 = NCプログラムファイル移行（folder_name配下→K_idフォルダへ。図・写真は対象外）

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

import sys, os, re, argparse, traceback, subprocess
from pathlib import Path
from datetime import datetime, timedelta

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PG_DSN       = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
SS_SERVER    = "192.168.1.9"
SS_USER      = "sa"
SS_PASS      = "RTW65b"
SS_DB        = "imotomc"   # NC側ビューもMC側と同じDB内に存在(diag_v017/v018bで確認済み)
LOG_FILE     = Path("/home/karkyon/projects/machcore/logs/nc_full_import.log")

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


ADMIN_FALLBACK_ID = 22  # メモリ記載のADMIN_ID(MC側と共通)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: nc_machining_details + nc_programs 基本データ移行
#   (ACC_NC × ACC_Lathe)
#   mc_full_import.py PHASE1と同じ2段階方式:
#     ① K_id単位でnc_machining_details(加工データ本体)を1件だけUPSERT
#     ② ACC_NCの行ごとに(B_id単位で)nc_programsを無条件INSERT
#        → 同一K_idが複数のB_idから参照されれば、複数のnc_programs行が作られ、
#          全てが同じnc_machining_details.k_idを指す(共通部品の正しい表現)。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase1(pg, dry_run=False):
    section("PHASE 1: nc_machining_details + nc_programs 基本データ移行")
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
        pgc.execute("DELETE FROM nc_machining_details")
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
    machine_id_map = {}
    machine_unmatched = 0
    for m_id, model in acc_machine_rows:
        model_str = str(model or "").strip()
        if model_str in machine_code_map:
            machine_id_map[m_id] = machine_code_map[model_str]
        else:
            machine_unmatched += 1
    log(f"ACC_Machine取得: {len(acc_machine_rows)}件, machines対応: {len(machine_id_map)}件, 未対応: {machine_unmatched}件")

    # ACC_FD: 参考情報のみ(folder_name解決には未使用、v1から継続)
    ssc.execute("SELECT FD_id, FD_name FROM ACC_FD")
    fd_map = {r[0]: (r[1] or "").strip() for r in ssc.fetchall()}
    log(f"ACC_FD取得: {len(fd_map)}件 (参考情報として取得のみ。folder_name解決には未使用)")

    # ACC_Staff: St_id → employee_code "STAFF{:03d}" → users.id 解決
    pgc.execute("SELECT id, employee_code FROM users")
    code_to_userid = {r[1]: r[0] for r in pgc.fetchall()}
    ssc.execute("SELECT St_id, S_name FROM ACC_Staff")
    staff_rows = ssc.fetchall()
    staff_id_map = {}
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

    # ── ① ACC_Lathe単位(K_id単位)でnc_machining_detailsを構築 ──
    ssc.execute("""
        SELECT l.K_id, l.L, l.Clamp, l.Machine, l.Tm, l.Ts, l.FD_name, l.F_name,
               l.oNo, l.Note, l.Fig, l.Photo, l.Ver
        FROM ACC_Lathe l
        ORDER BY l.K_id
    """)
    lathe_rows = ssc.fetchall()
    log(f"旧DB ACC_Lathe取得: {len(lathe_rows)}件 (K_id単位、加工データ本体)")

    detail_ok = detail_skip = detail_err = 0
    kid_set = set()  # 正常に登録できたK_idの集合(PHASE1②での参照整合性チェック用)

    for row in lathe_rows:
        try:
            (kid, l_no, clamp, machine_raw, tm, ts, fd_name_raw, f_name,
             ono, note, fig, photo, ver) = row

            machine_db_id = machine_id_map.get(machine_raw) if machine_raw is not None else None

            # FD_name: ACC_Lathe.FD_name列の値をそのままfolder_nameとして使用する。
            # (ACC_FD経由の逆引きは未確証のため今回は採用しない。v1から継続)
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
            ver_str = str(int(ver)) if ver is not None else "0"

            if dry_run:
                kid_set.add(int(kid))
                detail_ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_machining_details (
                    k_id, process_l, machine_id, machining_time, setup_time_ref,
                    folder_name, file_name, o_number, version, clamp_note,
                    drawing_count, photo_count, legacy_ver, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (k_id) DO UPDATE SET
                    process_l=EXCLUDED.process_l, machine_id=EXCLUDED.machine_id,
                    machining_time=EXCLUDED.machining_time, setup_time_ref=EXCLUDED.setup_time_ref,
                    folder_name=EXCLUDED.folder_name, file_name=EXCLUDED.file_name,
                    o_number=EXCLUDED.o_number, version=EXCLUDED.version,
                    clamp_note=EXCLUDED.clamp_note, drawing_count=EXCLUDED.drawing_count,
                    photo_count=EXCLUDED.photo_count, legacy_ver=EXCLUDED.legacy_ver,
                    updated_at=NOW()
            """, (int(kid), process_l, machine_db_id, machining_time, setup_time_ref,
                  folder_name, str(f_name) if f_name is not None else "",
                  str(ono) if ono is not None else None, ver_str, clamp_note,
                  int(fig or 0), int(photo or 0), str(ver) if ver is not None else None))
            kid_set.add(int(kid))
            detail_ok += 1
            if detail_ok % 2000 == 0:
                pg.commit()
                log(f"  nc_machining_details {detail_ok}件挿入中...")
        except Exception as e:
            detail_err += 1
            if not dry_run:
                pg.rollback()
            if detail_err <= 5:
                log(f"  ERR(detail): K_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_machining_details")
        log(f"nc_machining_details完了: ok={detail_ok} err={detail_err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"nc_machining_details完了(dry-run): ok={detail_ok} err={detail_err}")

    # ── ② ACC_NC単位(B_id×K_id単位)でnc_programsを無条件INSERT ──
    # 1つのK_idに複数のNC_id(=B_id行)が存在する場合、その全件がnc_programsとして
    # 個別にINSERTされる(unique制約なし、MC側mc_programs方式と同じ)。
    #
    # 登録者(Reco_P)・登録日(Reco_D)はACC_Lathe側のカラム(=加工データ本体側の情報)。
    # mc_full_import.py PHASE1でも同様に、登録者情報はACC_マシニングraw(加工データ本体)
    # 側から取得しており、共通部品(複数mc_programs)では同じ値が複製される設計になっている。
    # NC側もこれに合わせ、ACC_Lathe.Reco_P/Reco_Dを全NC_id行に対して共通で適用する。
    ssc.execute("""
        SELECT K_id, Reco_P, Reco_D
        FROM ACC_Lathe
    """)
    lathe_reco = {int(r[0]): (r[1], r[2]) for r in ssc.fetchall() if r[0] is not None}
    log(f"ACC_Lathe Reco_P/Reco_D取得: {len(lathe_reco)}件(K_id単位)")

    ssc.execute("""
        SELECT NC_id, B_id, K_id
        FROM ACC_NC
        ORDER BY NC_id
    """)
    nc_rows = ssc.fetchall()
    log(f"旧DB ACC_NC取得: {len(nc_rows)}件 (部品×加工の対応行)")

    ok = skip = err = 0
    nc_id_map = {}   # 旧NC_id(int) → nc_programs.id
    kid_to_dbid = {}  # 旧K_id(int) → nc_machining_details.k_id (=そのままK_id)

    for row in nc_rows:
        try:
            (ncid, bid, kid) = row
            kid_i = int(kid)

            if kid_i not in kid_set:
                # ACC_Lathe側に対応するK_idが存在しない(孤立NC_id行)
                skip += 1
                continue

            part_db_id = parts_map.get(str(bid))
            if not part_db_id:
                skip += 1
                continue

            rp, rd_ = lathe_reco.get(kid_i, (None, None))

            registered_by = staff_id_map.get(rp, ADMIN_FALLBACK_ID)
            registered_at = to_jst_utc(rd_) if rd_ else datetime(2005, 1, 1)

            if dry_run:
                virtual_id = -int(ncid)
                nc_id_map[ncid] = virtual_id
                kid_to_dbid[kid_i] = kid_i
                ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_programs (
                    part_id, machining_id, registered_by, registered_at,
                    legacy_nc_id, status, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,'APPROVED'::nc_program_status,NOW(),NOW())
                RETURNING id
            """, (part_db_id, kid_i, registered_by, registered_at, int(ncid)))
            new_id = pgc.fetchone()[0]
            nc_id_map[ncid] = new_id
            kid_to_dbid[kid_i] = kid_i
            ok += 1
            if ok % 2000 == 0:
                pg.commit()
                log(f"  nc_programs {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run:
                pg.rollback()
            if err <= 5:
                log(f"  ERR(program): NC_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_programs")
        log(f"PHASE1(nc_programs)完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE1(nc_programs)完了(dry-run): ok={ok} skip={skip} err={err}")

    ss.close()
    return nc_id_map, kid_to_dbid, staff_id_map, machine_id_map


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: nc_tools 移行 (ACC_Tool)
#   machining_id(=K_id)参照に変更。K_id自体が新PKのため、
#   旧kid_mapのような変換マッピングは不要(K_idがそのままmachining_idとして使える)。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase2(pg, dry_run=False, kid_to_dbid=None):
    section("PHASE 2: nc_tools 移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    if not kid_to_dbid:
        # phase1を経ずに--phase 2単独実行された場合に備え、DBから再構築する。
        pgc.execute("SELECT k_id FROM nc_machining_details")
        kid_to_dbid = {r[0]: r[0] for r in pgc.fetchall()}
        log(f"kid_to_dbid再構築: {len(kid_to_dbid)}件")

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
            kid_i = int(k_id) if k_id is not None else None
            if kid_i is None or kid_i not in kid_to_dbid:
                skip += 1
                continue
            machining_id = kid_to_dbid[kid_i]

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
                    machining_id, sort_order, process_type, chip_model,
                    holder_model, nose_r, t_number, note, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            """, (machining_id, sort_order, process_type,
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
#   旧ACC_Historyの1レコードはK_id単位。K_idに複数のnc_programs(共通部品)が
#   対応する場合、mc_full_import.py PHASE6と同じく、その全てに履歴を複製してINSERTする。
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
    section("PHASE 3: ACC_History 完全分離移行(K_id→全対応NcProgramへ複製)")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    # K_id → [nc_programs.id, ...] (共通部品で複数あり得る)。DBから再構築する。
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    kid_to_program_ids = {}
    for prog_id, machining_id in pgc.fetchall():
        kid_to_program_ids.setdefault(machining_id, []).append(prog_id)
    log(f"kid_to_program_ids構築: {len(kid_to_program_ids)}件のK_idに対応するNcProgram群")

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
    # 共通部品で複製INSERTされた件数をカウント(参考値)
    sl_dup = wr_dup = ch_dup = 0

    for row in rows:
        try:
            (hist_id, k_id, nc_id_old, mc_raw,
             out_ver, out_cont, out_op, out_date,
             in_ver, in_cont, in_op, in_date,
             dan_op, dan_h, dan_m, la_op, la_h, la_m, p) = row

            kid_i = int(k_id) if k_id is not None else None
            program_ids = kid_to_program_ids.get(kid_i, []) if kid_i is not None else []
            if not program_ids:
                sl_skip += 1
                wr_skip += 1
                ch_skip += 1
                continue

            out_cont_s = str(out_cont or "").strip()
            in_cont_s = str(in_cont or "").strip()
            out_date_utc = to_jst_utc(out_date)
            in_date_utc = to_jst_utc(in_date)

            # ── A: setup_sheet_logs（Out_Cont = "印刷"）→ 対応する全NcProgramに複製 ──
            if "印刷" in out_cont_s and out_date_utc:
                op_id = staff_id_map.get(out_op, ADMIN_FALLBACK_ID)
                out_ver_str = str(int(out_ver)) if out_ver is not None else None
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO setup_sheet_logs (
                                    nc_program_id, operator_id, printed_at, version,
                                    pdf_path, session_id, work_collected
                                ) VALUES (%s,%s,%s,%s,NULL,NULL,true)
                            """, (prog_id, op_id, out_date_utc, out_ver_str))
                        sl_ok += 1
                        if idx > 0:
                            sl_dup += 1
                    except Exception:
                        sl_err += 1
                        if not dry_run:
                            pg.rollback()

            # ── B: work_records（Dan_*/La_*/P に実データあり）→ 対応する全NcProgramに複製 ──
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
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO work_records (
                                    nc_program_id, operator_id, machine_id, work_date,
                                    setup_time_min, machining_time_min, quantity, note, created_at
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                            """, (prog_id, work_op_id, work_machine_id, work_date,
                                  setup_min, mach_min, p_i if p_i > 0 else None, note_str))
                        wr_ok += 1
                        if idx > 0:
                            wr_dup += 1
                    except Exception:
                        wr_err += 1
                        if not dry_run:
                            pg.rollback()

            # ── C: change_history（In_Cont が新規登録/仮登録/変更/承認）→ 対応する全NcProgramに複製 ──
            is_nc_change = any(kw in in_cont_s for kw in ("新規登録", "仮登録", "変更", "承認"))
            if is_nc_change and in_date_utc:
                op_id = staff_id_map.get(in_op, ADMIN_FALLBACK_ID)
                ver_before = str(int(out_ver)) if out_ver is not None else None
                ver_after = str(int(in_ver)) if in_ver is not None else None
                field_changes = None
                if out_cont_s and "印刷" not in out_cont_s:
                    import json as _json
                    field_changes = _json.dumps({"out_content": out_cont_s})
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO change_history (
                                    nc_program_id, change_type, operator_id,
                                    version_before, version_after, content,
                                    field_changes, changed_at, legacy_hist_id
                                ) VALUES (%s,%s::change_type,%s,%s,%s,%s,%s,%s,%s)
                            """, (prog_id, guess_change_type(in_cont_s), op_id,
                                  ver_before, ver_after, in_cont_s or None,
                                  field_changes, in_date_utc, int(hist_id)))
                        ch_ok += 1
                        if idx > 0:
                            ch_dup += 1
                    except Exception:
                        ch_err += 1
                        if not dry_run:
                            pg.rollback()

            if not dry_run and (sl_ok + wr_ok + ch_ok) % 5000 == 0:
                pg.commit()
        except Exception as e:
            log(f"  ERR: Hist_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()

    log(f"PHASE3完了: setup_sheet_logs ok={sl_ok}(共通部品複製分={sl_dup}) skip={sl_skip} err={sl_err}")
    log(f"            work_records     ok={wr_ok}(共通部品複製分={wr_dup}) skip={wr_skip} err={wr_err}")
    log(f"            change_history   ok={ch_ok}(共通部品複製分={ch_dup}) skip={ch_skip} err={ch_err}")
    log(f"  【内訳】ACC_History {len(rows)}件 → 最大 {sl_ok + wr_ok + ch_ok} レコードに展開")
    log("  ※ legacy_hist_idは複製元の旧Hist_idをそのまま保持するため、共通部品では")
    log("    同一legacy_hist_idを持つchange_history行が複数件(NcProgram数分)存在しうる。")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: nc_programs.status 正規化
#   K_id単位で判定したstatusを、そのK_idに対応する全NcProgram行に同一適用する。
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

    # K_id(=machining_id)単位で、その全NcProgram行(id一覧)を取得
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    program_rows = pgc.fetchall()
    log(f"nc_programs取得: {len(program_rows)}件")

    stat_new = stat_approved = stat_pending = 0

    if not dry_run:
        for nc_db_id, kid in program_rows:
            latest_in = kid_latest_in.get(kid, "")
            has_print = kid in kid_has_print
            has_approval = kid in kid_has_approval

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
        ("nc_machining_details", "SELECT COUNT(*) FROM nc_machining_details"),
        ("nc_programs", "SELECT COUNT(*) FROM nc_programs"),
        ("nc_tools", "SELECT COUNT(*) FROM nc_tools"),
        ("change_history(NC)", "SELECT COUNT(*) FROM change_history"),
        ("setup_sheet_logs", "SELECT COUNT(*) FROM setup_sheet_logs"),
        ("work_records(NC)", "SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL"),
        ("nc_files(PROGRAM)", "SELECT COUNT(*) FROM nc_files WHERE file_type='PROGRAM'"),
    ]:
        pgc.execute(sql)
        log(f"  {label}: {pgc.fetchone()[0]}件")

    # 共通部品(1つのK_idに複数nc_programsが対応)の件数を参考表示
    pgc.execute("""
        SELECT COUNT(*) FROM (
            SELECT machining_id FROM nc_programs GROUP BY machining_id HAVING COUNT(*) > 1
        ) t
    """)
    log(f"  共通部品(1つのK_idを複数部品で共有)のK_id数: {pgc.fetchone()[0]}件")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ----------------------------------------------------------------
# PHASE 5: NCプログラムファイル移行
#   mc_full_import.py PHASE7(7C: プログラム)と同じ考え方。
#   旧サーバ上のプログラム保存場所は nc_machining_details.folder_name
#   (=ACC_Lathe.FD_name)で、E:\imotodb\D1\NC\プログラム\ 配下のフォルダ名
#   (A, B, C...)と完全一致することを現地確認済み(2026-06-30, KARKYONさん確認)。
#   NC側はfolder1+folder2のような2階層構成ではなくfolder_name1本の単一階層
#   構成のため、MC側PHASE7Cより単純な1階層直下コピーで表現できる。
#   写真・図(MC側7A/7B相当)は旧サーバ上で実質1枚ずつしか存在せず運用実態が
#   ないため、本フェーズの対象外とする(現地確認結果を踏まえた判断)。
# ----------------------------------------------------------------
SRC_NC_ROOT = Path("/mnt/mcfiles/NC")
SRC_NC_PRG  = SRC_NC_ROOT / "ﾌﾟﾛｸﾞﾗﾑ"  # NC側プログラムフォルダ(半角ｶﾅ、MC側SRC_PRGと同じ表記)
DST_NC_ROOT = Path("/mnt/mc_files/NC/files")
DST_NC_PRG  = DST_NC_ROOT / "Programs"
NC_FILE_ADMIN_FALLBACK_ID = 22  # ADMIN001 users.id (MC側ADMIN_IDと共通)


def _nc_safe_rmtree_and_mkdir(dst_dir, label):
    """CIFS上でrmtree後mkdir失敗する問題をリトライで対処(mc_full_import.pyと同方式、rm -rf使用)。"""
    import time as _time
    if dst_dir.exists():
        log(f"  {label}: コピー先クリア ({dst_dir})")
        _res = subprocess.run(["rm", "-rf", str(dst_dir)], capture_output=True, text=True)
        if _res.returncode != 0:
            log(f"  [WARN] rm -rf failed: {_res.stderr}", "WARN")
    for _attempt in range(10):
        try:
            os.makedirs(str(dst_dir), exist_ok=True)
            return
        except OSError:
            _time.sleep(1)
    os.makedirs(str(dst_dir), exist_ok=True)


def phase5(pg, dry_run=False):
    section("PHASE 5: NCプログラムファイル移行 (folder_name配下 -> K_idフォルダへ)")
    import shutil as _shutil
    import mimetypes

    pgc = pg.cursor()

    if not SRC_NC_PRG.exists():
        log(f"[WARN] SRC_NC_PRG が存在しない: {SRC_NC_PRG} - PHASE5をスキップします", "WARN")
        return

    if not dry_run:
        log("nc_files(PROGRAM分)既存データ削除...")
        pgc.execute("DELETE FROM nc_files WHERE file_type = 'PROGRAM'")
        pg.commit()
        _nc_safe_rmtree_and_mkdir(DST_NC_PRG, "プログラム(NC)")
    else:
        os.makedirs(str(DST_NC_PRG), exist_ok=True)

    # K_id -> [(nc_programs.id, registered_by, registered_at), ...]
    # (共通部品で複数あり得る。phase3と同じ構築方法)
    pgc.execute("SELECT id, machining_id, registered_by, registered_at FROM nc_programs")
    kid_to_programs = {}
    for prog_id, machining_id, registered_by, registered_at in pgc.fetchall():
        kid_to_programs.setdefault(machining_id, []).append((prog_id, registered_by, registered_at))
    log(f"kid_to_programs構築: {len(kid_to_programs)}件のK_idに対応するNcProgram群")

    pgc.execute("""
        SELECT k_id, folder_name, file_name
        FROM nc_machining_details
        WHERE file_name IS NOT NULL AND file_name != ''
          AND folder_name IS NOT NULL AND folder_name != '' AND folder_name != '(未設定)'
        ORDER BY k_id
    """)
    details = pgc.fetchall()
    log(f"  対象K_id: {len(details)}件")

    ok = nomatch = notfound = err = 0

    def _insert_nc_program_file(nc_program_id, orig_name, stored_name, mime, fpath, fsize,
                                 uploaded_by_id, uploaded_at_val):
        if dry_run:
            return
        pgc.execute("""
            INSERT INTO nc_files
              (nc_program_id, file_type, original_name, stored_name, mime_type,
               file_path, thumbnail_path, file_size, uploaded_by, uploaded_at)
            VALUES (%s,'PROGRAM',%s,%s,%s,%s,NULL,%s,%s,%s)
        """, (nc_program_id, orig_name, stored_name, mime, str(fpath), fsize,
              uploaded_by_id, uploaded_at_val))

    for i, (kid, folder_name, file_name) in enumerate(details):
        # ★v053修正: フォルダ全件ではなく file_name で指定された1ファイルのみコピー。
        #   folder_name(A,B,C...)は複数K_idが共有する親フォルダ。
        #   各K_idが使うファイルはnc_machining_details.file_nameで一意に特定できる。
        src_file = SRC_NC_PRG / str(folder_name).strip() / str(file_name).strip()
        if not src_file.exists():
            notfound += 1
            if notfound <= 10:
                log(f"  [WARN] notfound: K_id={kid} folder={folder_name} file={file_name}", "WARN")
            continue
        if kid not in kid_to_programs:
            nomatch += 1
            continue

        dst_dir = DST_NC_PRG / str(kid)
        try:
            if not dry_run:
                os.makedirs(str(dst_dir), exist_ok=True)
            dst = dst_dir / src_file.name
            if not dry_run:
                _shutil.copy2(src_file, dst)
            fsize = src_file.stat().st_size
            mime = mimetypes.guess_type(src_file.name)[0] or "application/octet-stream"
            for prog_id, registered_by, registered_at in kid_to_programs[kid]:
                _insert_nc_program_file(
                    prog_id, src_file.name, src_file.name, mime, dst, fsize,
                    registered_by or NC_FILE_ADMIN_FALLBACK_ID,
                    registered_at,
                )
            ok += 1
        except Exception as e:
            err += 1
            if err <= 10:
                log(f"  ERR K_id={kid} folder={folder_name} file={file_name}: {e}", "WARN")

        if (i + 1) % 500 == 0:
            if not dry_run:
                pg.commit()
            log(f"    {i+1}/{len(details)} ok={ok} nomatch={nomatch} notfound={notfound} err={err}")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_files WHERE file_type='PROGRAM'")
        log(f"PHASE5完了: ok(K_id)={ok} nomatch={nomatch} notfound={notfound} err={err} "
            f"nc_files(PROGRAM)総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE5完了(dry-run): ok(K_id)={ok} nomatch={nomatch} notfound={notfound} err={err}")


def main():
    parser = argparse.ArgumentParser(description="MachCore NC完全移行スクリプト v2(新スキーマ対応)")
    parser.add_argument("--phase", type=int, default=0, help="実行フェーズ (0=全, 1-5=個別)")
    parser.add_argument("--dry-run", action="store_true", help="DBへの書き込みなし")
    parser.add_argument("--skip-file-copy", action="store_true",
                        help="PHASE5をスキップ（プログラムファイルコピーなし、データのみ移行）")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    pg = pg_connect()
    try:
        nc_id_map = kid_to_dbid = staff_id_map = machine_id_map = None

        if args.phase in (0, 1):
            nc_id_map, kid_to_dbid, staff_id_map, machine_id_map = phase1(pg, dry_run=dry)
        if args.phase in (0, 2):
            phase2(pg, dry_run=dry, kid_to_dbid=kid_to_dbid)
        if args.phase in (0, 3):
            phase3(pg, dry_run=dry, nc_id_map=nc_id_map, staff_id_map=staff_id_map, machine_id_map=machine_id_map)
        if args.phase in (0, 4):
            phase4(pg, dry_run=dry)
        if args.phase == 5 or (args.phase == 0 and not args.skip_file_copy):
            phase5(pg, dry_run=dry)

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
