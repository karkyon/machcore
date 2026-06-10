#!/usr/bin/env python3
# coding: utf-8
"""
MachCore MC完全移行スクリプト (mc_full_import.py)
=================================================
実行方法:
  python3 mc_full_import.py [--phase N] [--dry-run]

フェーズ:
  0 = 全フェーズ一括実行（本番用）
  1 = mc_programs基本データ移行
  2 = mc_tooling移行
  3 = RC同期
  4 = mc_work_offsets移行
  5 = mc_index_programs移行
  6 = mc_change_history移行
  7 = 図・写真・プログラムファイル移行
  8 = drawing_count/photo_count更新

ソースDB: imotomc (192.168.1.9)
  - ACC_MC          : 部品ID, MCID, 加工ID
  - ACC_マシニング   : 加工ID, Version, MC工程No, パス1, パス2, ファイル名...
  - ACC_ツーリング   : 加工ID, 順番, 工具名, T, H, D, D値, SUB, コメント...
  - ACC_ワークオフセット / ACC_インデックスプログラム / ACC_変更履歴
部品/得意先: imotodb (192.168.1.9)
  - v_旧部品マスタ  : 部品ID, 図面番号, 名称, 主機種型式, 納入先ID
  - v_旧得意先マスタ : 納入先ID, 会社名
"""

import sys, os, re, shutil, argparse, traceback
from pathlib import Path
from datetime import datetime

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PG_DSN       = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
SS_MC_SERVER = "192.168.1.9"
SS_MC_USER   = "sa"
SS_MC_PASS   = "RTW65b"
SS_MC_DB     = "imotomc"    # マシニングデータ
SS_PB_DB     = "imotodb"    # 部品・得意先マスタ
ADMIN_ID     = 22           # ADMIN001 users.id

# ファイルパス
SMB_MC_ROOT  = Path("/mnt/mcfiles/MC")
SRC_DRAW     = SMB_MC_ROOT / "図"
SRC_PHOTO    = SMB_MC_ROOT / "写真"
SRC_PRG      = SMB_MC_ROOT / "ﾌﾟﾛｸﾞﾗﾑ"
DST_ROOT     = Path("/mnt/mcfiles/MC/files")
DST_DRAW     = DST_ROOT / "Drawings"
DST_PHOTO    = DST_ROOT / "Pictures"
DST_PRG      = DST_ROOT / "Programs"
UPLOAD_BASE  = Path("/mnt/ncfiles/mc_files")
UPLOAD_DRAW  = UPLOAD_BASE / "drawings"
UPLOAD_PHOTO = UPLOAD_BASE / "photos"
UPLOAD_PG    = UPLOAD_BASE / "pg"
LOG_FILE     = Path("/home/karkyon/projects/machcore/logs/mc_full_import.log")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーティリティ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_log_fh = open(LOG_FILE, "a", encoding="utf-8")

def log(msg, level="INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    _log_fh.write(line + "\n")
    _log_fh.flush()

def section(title):
    bar = "=" * 60
    log(f"\n{bar}\n  {title}\n{bar}")

def ensure_dirs(*dirs):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

def pg_connect():
    import psycopg2
    return psycopg2.connect(PG_DSN)

def ss_connect(db):
    import pymssql
    return pymssql.connect(server=SS_MC_SERVER, user=SS_MC_USER,
                           password=SS_MC_PASS, database=db, tds_version='7.4')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: mc_programs 基本データ移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase1(pg, dry_run=False):
    section("PHASE 1: mc_programs 基本データ移行")
    mc  = ss_connect(SS_MC_DB)   # imotomc
    pb  = ss_connect(SS_PB_DB)   # imotodb
    mcc = mc.cursor()
    pbc = pb.cursor()
    pgc = pg.cursor()

    # 既存データ全破棄
    if not dry_run:
        log("既存データ全破棄...")
        pgc.execute("DELETE FROM mc_files")
        pgc.execute("DELETE FROM mc_change_history")
        pgc.execute("DELETE FROM mc_setup_sheet_logs")
        pgc.execute("DELETE FROM operation_logs WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM work_sessions WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM mc_programs")
        # mc_machining_details削除でmc_tooling/mc_work_offsets/mc_index_programsもCASCADE
        pgc.execute("DELETE FROM mc_machining_details")
        pg.commit()
        log("全破棄完了")

    # 部品マスタ (imotodb.v_旧部品マスタ)
    pbc.execute("SELECT 部品ID, 図面番号, 名称, 主機種型式, 納入先ID FROM v_旧部品マスタ")
    buhin_rows = pbc.fetchall()
    log(f"部品マスタ取得: {len(buhin_rows)}件")

    # 得意先マスタ (imotodb.v_旧得意先マスタ)
    pbc.execute("SELECT 納入先ID, 会社名 FROM v_旧得意先マスタ")
    client_map = {r[0]: r[1] for r in pbc.fetchall()}

    # parts テーブルへ upsert
    pgc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pgc.fetchall()}  # part_id文字列 → DB id

    parts_inserted = 0
    for buhin_id, drawing_no, name, main_model, client_id in buhin_rows:
        pid_str    = str(buhin_id)
        client_name = client_map.get(client_id, "")
        if pid_str not in parts_map:
            if not dry_run:
                pgc.execute("""
                    INSERT INTO parts (part_id, drawing_no, name, main_model, client_name, is_active, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,true,NOW(),NOW())
                    ON CONFLICT (part_id) DO UPDATE SET
                        drawing_no=EXCLUDED.drawing_no, name=EXCLUDED.name,
                        main_model=EXCLUDED.main_model, client_name=EXCLUDED.client_name
                    RETURNING id
                """, (pid_str, drawing_no or "", name or "", main_model, client_name))
                new_id = pgc.fetchone()[0]
                parts_map[pid_str] = new_id
                parts_inserted += 1
        else:
            if not dry_run:
                pgc.execute("""
                    UPDATE parts SET drawing_no=%s, name=%s, main_model=%s, client_name=%s
                    WHERE part_id=%s
                """, (drawing_no or "", name or "", main_model, client_name, pid_str))
    if not dry_run:
        pg.commit()
    log(f"parts同期完了: 新規={parts_inserted}件, 総数={len(parts_map)}件")

    # 機械マスタ
    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type='MC'")
    machines_map = {r[1]: r[0] for r in pgc.fetchall()}

    # ユーザーマスタ
    pgc.execute("SELECT id, name FROM users")
    users_by_id  = {}
    users_by_name = {}
    for uid, uname in pgc.fetchall():
        users_by_id[uid]    = uname
        users_by_name[uname] = uid

    # 機械IDマスタ (imotomc)
    mcc.execute("SELECT 機械ID, 機械名 FROM ACC_機械")
    ss_machine_map = {}
    for mid, mname in mcc.fetchall():
        # 機械名→MachCoreのmachine_code変換
        code = str(mname).strip()
        if code in machines_map:
            ss_machine_map[mid] = machines_map[code]
        else:
            # "MC1"等に変換試行
            mc_code = f"MC{code}" if not code.startswith("MC") else code
            ss_machine_map[mid] = machines_map.get(mc_code)

    # ACC_MC × ACC_マシニング JOIN で全データ取得
    mcc.execute("""
        SELECT
            mc.部品ID, mc.MCID, mc.加工ID,
            m.Version, m.[MC工程No], m.パス1, m.パス2, m.ファイル名,
            m.メインPGNo, m.機械ID, m.加工時間H, m.加工時間M, m.加工時間S,
            m.加工個数, m.クランプ, m.備考,
            m.担当者ID, m.IP有無, m.WD有無,
            m.写真枚数, m.RC, m.図枚数,
            m.作成者ID, m.PG担当者ID,
            m.入力日付, m.登録日付
        FROM ACC_MC mc
        INNER JOIN ACC_マシニング m ON mc.加工ID = m.加工ID AND mc.MCID = m.MCID
        WHERE m.削除区分 = 0
        ORDER BY mc.MCID
    """)
    rows = mcc.fetchall()
    log(f"旧DBマシニング取得: {len(rows)}件")

    ok = skip = err = 0
    for row in rows:
        try:
            (buhin_id, mcid, kakoid,
             version, process_no, path1, path2, file_name,
             main_pg_no, machine_id_ss, time_h, time_m, time_s,
             qty, clamp, note,
             tanto_id, ip_umu, wd_umu,
             photo_cnt, rc, draw_cnt,
             sakusha_id, pg_tanto_id,
             input_date, reg_date) = row

            part_db_id = parts_map.get(str(buhin_id))
            if not part_db_id:
                skip += 1; continue

            # 機械
            machine_db_id = ss_machine_map.get(machine_id_ss)

            # 加工時間→秒
            ct_sec = None
            if time_h is not None or time_m is not None or time_s is not None:
                ct_sec = int(time_h or 0)*3600 + int(time_m or 0)*60 + int(time_s or 0)

            # IP/WD
            has_ip = str(ip_umu or "").strip() not in ("ﾅｼ", "なし", "0", "")
            has_wd = str(wd_umu or "").strip() not in ("ﾅｼ", "なし", "0", "")

            # 担当者（旧DBのIDはPGのusers.idと対応しないためADMINで統一）
            reg_id  = ADMIN_ID
            cr_id   = None
            pg_id   = None

            # バージョン
            ver_str = str(version or "1.0001")

            if dry_run:
                ok += 1; continue

            # STEP-A: mc_machining_details (加工詳細; machining_id=加工ID でUPSERT)
            pgc.execute("""
                INSERT INTO mc_machining_details (
                    machining_id, version, machine_id, o_number,
                    clamp_note, cycle_time_sec, mc_process_no,
                    folder1, folder2, file_name,
                    has_index_program, has_work_offset, rc,
                    legacy_kakoid, created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s,
                    %s,%s,%s,
                    %s,%s,%s,
                    %s,%s,%s,
                    %s,NOW(),NOW()
                )
                ON CONFLICT (machining_id) DO UPDATE SET
                    version=EXCLUDED.version,
                    machine_id=EXCLUDED.machine_id,
                    o_number=EXCLUDED.o_number,
                    clamp_note=EXCLUDED.clamp_note,
                    cycle_time_sec=EXCLUDED.cycle_time_sec,
                    mc_process_no=EXCLUDED.mc_process_no,
                    folder1=EXCLUDED.folder1,
                    folder2=EXCLUDED.folder2,
                    file_name=EXCLUDED.file_name,
                    has_index_program=EXCLUDED.has_index_program,
                    has_work_offset=EXCLUDED.has_work_offset,
                    rc=EXCLUDED.rc,
                    legacy_kakoid=EXCLUDED.legacy_kakoid,
                    updated_at=NOW()
            """, (
                kakoid, ver_str, machine_db_id, main_pg_no,
                clamp, ct_sec, process_no,
                str(path1) if path1 is not None else None,
                str(path2) if path2 is not None else None,
                str(file_name) if file_name else None,
                has_ip, has_wd, int(rc or 0),
                kakoid,
            ))
            # STEP-B: mc_programs (部品と加工の紐付けのみ)
            pgc.execute("""
                INSERT INTO mc_programs (
                    part_id, machining_id, machining_qty, note, status,
                    registered_by,
                    registered_at,
                    legacy_mcid,
                    created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s,'APPROVED',
                    %s,
                    %s,
                    %s,
                    NOW(),NOW()
                )
            """, (
                part_db_id, kakoid, qty or 1, note,
                reg_id,
                input_date or reg_date or datetime.now(),
                mcid,
            ))
            ok += 1
            if ok % 1000 == 0:
                pg.commit()
                log(f"  {ok}件挿入中... skip={skip} err={err}")
        except Exception as e:
            err += 1
            if not dry_run: pg.rollback()
            if err <= 10: log(f"  ERR MCID={row[1]}: {e}", "WARN")

    if not dry_run: pg.commit()
    pgc.execute("SELECT COUNT(*) FROM mc_programs")
    log(f"PHASE1完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    mc.close(); pb.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: mc_tooling 移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase2(pg, dry_run=False):
    section("PHASE 2: mc_tooling移行")
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    # 既存mc_toolingを全削除してから再挿入
    if not dry_run:
        pgc.execute("DELETE FROM mc_tooling")
        pg.commit()
        log("mc_tooling既存データ削除完了")

    # machining_id マップ（mc_machining_detailsの実在IDセット）
    pgc.execute("SELECT machining_id FROM mc_machining_details")
    valid_machining_ids: set[int] = {r[0] for r in pgc.fetchall()}

    mcc.execute("""
        SELECT 加工ID, 順番, N, 工具, T, H, D, D値, SUB, コメント, 工具名, ツーリングID
        FROM ACC_ツーリング
        ORDER BY 加工ID, ツーリングID
    """)
    rows = mcc.fetchall()
    log(f"ACC_ツーリング取得: {len(rows)}件")

    ok = skip = err = 0
    for row in rows:
        try:
            kakoid, order, n_no, tool_name, t_no, h_no, d_no, d_val, sub_pg, comment, tool_name2, tooling_id = row
            # 工具名: 「工具」列(切削条件/径)と「工具名」列(正式名)をマージ
            tool_name_merged = str(tool_name or "").strip() or None
            tool_name_full   = str(tool_name2 or "").strip() or None
            n_no_str         = str(n_no or "").strip() or None
            if kakoid not in valid_machining_ids: skip += 1; continue
            if not dry_run:
                pgc.execute("""
                    INSERT INTO mc_tooling (
                        machining_id, sort_order, tool_no, tool_name, t_no,
                        length_offset_no, dia_offset_no, d_value_content,
                        sub_pg_no, note, raw_program_line
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (kakoid,
                      int(float(order or 0)),
                      n_no_str,
                      tool_name_merged,
                      str(t_no).strip() if t_no else None,
                      str(h_no).strip() if h_no else None,
                      str(d_no).strip() if d_no else None,
                      str(d_val).strip() if d_val else None,
                      str(sub_pg).strip() if sub_pg else None,
                      str(comment).strip() if comment else None,
                      tool_name_full))
            ok += 1
            if ok % 5000 == 0:
                if not dry_run: pg.commit()
                log(f"  {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run: pg.rollback()
            if err <= 5: log(f"  ERR: {e}", "WARN")

    if not dry_run: pg.commit()
    pgc.execute("SELECT COUNT(*) FROM mc_tooling")
    log(f"PHASE2完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    mc.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3: RC同期
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase3(pg, dry_run=False):
    section("PHASE 3: RC同期")
    pgc = pg.cursor()
    if not dry_run:
        pgc.execute("""
            UPDATE mc_machining_details d
            SET rc = (SELECT COUNT(*) FROM mc_tooling t WHERE t.machining_id = d.machining_id)
        """)
        pg.commit()
    pgc.execute("SELECT SUM(rc) FROM mc_machining_details")
    log(f"PHASE3完了: RC総計={pgc.fetchone()[0]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: mc_work_offsets 移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase4(pg, dry_run=False):
    section("PHASE 4: mc_work_offsets移行")
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    pgc.execute("SELECT machining_id FROM mc_machining_details")
    valid_machining_ids: set[int] = {r[0] for r in pgc.fetchall()}

    # ACC_ワークオフセットのカラム確認して取得
    try:
        mcc.execute("SELECT TOP 1 * FROM ACC_ワークオフセット")
        cols = [d[0] for d in mcc.description]
        log(f"ACC_ワークオフセットカラム: {cols}")
    except Exception as e:
        log(f"ACC_ワークオフセット取得失敗: {e}", "WARN")
        mc.close(); return

    mcc.execute("SELECT * FROM ACC_ワークオフセット ORDER BY 加工ID, WOD_ID")
    rows = mcc.fetchall()
    log(f"ACC_ワークオフセット取得: {len(rows)}件")

    ok = skip = err = 0
    for row in rows:
        try:
            row_dict = dict(zip(cols, row))
            kakoid   = row_dict.get("加工ID")
            if kakoid not in valid_machining_ids: skip += 1; continue
            if not dry_run:
                pgc.execute("""
                    INSERT INTO mc_work_offsets
                      (machining_id, g_code, x_offset, y_offset, z_offset, a_offset, r_offset, note)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (kakoid,
                      str(row_dict.get("G") or ""),
                      row_dict.get("X"), row_dict.get("Y"),
                      row_dict.get("Z"), row_dict.get("A"),
                      row_dict.get("R"), None))
            ok += 1
        except Exception as e:
            err += 1
            if not dry_run: pg.rollback()
            if err <= 5: log(f"  ERR: {e}", "WARN")

    if not dry_run: pg.commit()
    pgc.execute("SELECT COUNT(*) FROM mc_work_offsets")
    log(f"PHASE4完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    mc.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 5: mc_index_programs 移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase5(pg, dry_run=False):
    section("PHASE 5: mc_index_programs移行")
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    pgc.execute("SELECT machining_id FROM mc_machining_details")
    valid_machining_ids: set[int] = {r[0] for r in pgc.fetchall()}

    try:
        mcc.execute("SELECT TOP 1 * FROM ACC_インデックスプログラム")
        cols = [d[0] for d in mcc.description]
        log(f"ACC_インデックスプログラムカラム: {cols}")
    except Exception as e:
        log(f"ACC_インデックスプログラム取得失敗: {e}", "WARN")
        mc.close(); return

    mcc.execute("SELECT * FROM ACC_インデックスプログラム ORDER BY 加工ID, IP_ID")
    rows = mcc.fetchall()
    log(f"ACC_インデックスプログラム取得: {len(rows)}件")

    ok = skip = err = 0
    for row in rows:
        try:
            row_dict = dict(zip(cols, row))
            kakoid   = row_dict.get("加工ID")
            if kakoid not in valid_machining_ids: skip += 1; continue
            if not dry_run:
                # STEP_Nは文字列（///はコメント）→ axis_0に格納、sort_orderはIP_ID昇順
                pgc.execute("""
                    INSERT INTO mc_index_programs
                      (machining_id, sort_order, axis_0, axis_1, axis_2, note)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (kakoid,
                      int(row_dict.get("IP_ID") or 0),
                      str(row_dict.get("STEP_N") or ""),
                      row_dict.get("第1軸"),
                      row_dict.get("第2軸"),
                      None))
            ok += 1
        except Exception as e:
            err += 1
            if not dry_run: pg.rollback()
            if err <= 5: log(f"  ERR: {e}", "WARN")

    if not dry_run: pg.commit()
    pgc.execute("SELECT COUNT(*) FROM mc_index_programs")
    log(f"PHASE5完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    mc.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 6: mc_change_history 移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase6(pg, dry_run=False):
    section("PHASE 6: mc_change_history移行")
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    pgc.execute("SELECT id, legacy_mcid FROM mc_programs")
    mcid_map: dict[int, int] = {r[1]: r[0] for r in pgc.fetchall()}

    pgc.execute("SELECT id, name FROM users")
    users_map = {r[1]: r[0] for r in pgc.fetchall()}

    try:
        mcc.execute("SELECT TOP 1 * FROM ACC_変更履歴")
        cols = [d[0] for d in mcc.description]
        log(f"ACC_変更履歴カラム: {cols}")
    except Exception as e:
        log(f"ACC_変更履歴取得失敗: {e}", "WARN")
        mc.close(); return

    mcc.execute("SELECT * FROM ACC_変更履歴 ORDER BY MCID, 作成日")
    rows = mcc.fetchall()
    log(f"ACC_変更履歴取得: {len(rows)}件")

    change_type_map = {
        "新規": "NEW_REGISTRATION", "新規登録": "NEW_REGISTRATION",
        "変更": "CHANGE", "編集": "CHANGE",
        "承認": "APPROVAL",
        "削除": "CHANGE", "復元": "CHANGE",
    }

    ok = skip = err = 0
    for row in rows:
        try:
            row_dict  = dict(zip(cols, row))
            mcid      = row_dict.get("MCID")
            mc_db_id  = mcid_map.get(mcid)
            if not mc_db_id: skip += 1; continue

            operator  = str(row_dict.get("作成") or row_dict.get("ｵﾍﾟﾚｰﾀｰ") or "").strip()
            op_id     = users_map.get(operator, ADMIN_ID)
            ct        = change_type_map.get(str(row_dict.get("内容区分") or "").strip(), "CHANGE")
            changed_at = row_dict.get("作成日") or row_dict.get("入力日")
            content    = row_dict.get("内容")
            ver_before = row_dict.get("Ver")
            ver_after  = row_dict.get("Ver")
            hist_id    = row_dict.get("加工ID")

            if not dry_run:
                pgc.execute("""
                    INSERT INTO mc_change_history
                      (mc_program_id, change_type, operator_id,
                       version_before, version_after, content,
                       changed_at, legacy_hist_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (mc_db_id, ct, op_id, ver_before, ver_after,
                      content, changed_at, hist_id))
            ok += 1
            if ok % 10000 == 0:
                if not dry_run: pg.commit()
                log(f"  {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run: pg.rollback()
            if err <= 5: log(f"  ERR: {e}", "WARN")

    if not dry_run: pg.commit()
    pgc.execute("SELECT COUNT(*) FROM mc_change_history")
    log(f"PHASE6完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    mc.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 7: 図・写真・プログラム ファイル移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase7(pg, dry_run=False):
    section("PHASE 7: 図・写真・プログラム ファイル移行")

    ensure_dirs(DST_DRAW, DST_PHOTO, DST_PRG,
                UPLOAD_DRAW, UPLOAD_PHOTO, UPLOAD_PG)

    pgc = pg.cursor()

    if not dry_run:
        pgc.execute("DELETE FROM mc_files")
        pg.commit()
        log("mc_files既存データ削除完了")

    pgc.execute("SELECT id, machining_id FROM mc_programs")
    machining_map: dict[int, list[int]] = {}
    for mc_id, mach_id in pgc.fetchall():
        machining_map.setdefault(mach_id, []).append(mc_id)
    log(f"machining_id種類: {len(machining_map)}件")

    # folder_map構築（プログラム用）— mc_machining_detailsから取得
    pgc.execute("""
        SELECT DISTINCT folder1, folder2, file_name FROM mc_machining_details
        WHERE file_name IS NOT NULL AND folder1 IS NOT NULL AND file_name != ''
    """)
    combos = pgc.fetchall()

    log("プログラムファイルインデックス構築中...")
    file_index: dict[str, list[Path]] = {}
    if SRC_PRG.exists():
        for top in SRC_PRG.iterdir():
            if not top.is_dir(): continue
            for sub in top.iterdir():
                if sub.is_dir():
                    for f in sub.iterdir():
                        if f.is_file():
                            file_index.setdefault(f.name, []).append(f)
                elif sub.is_file():
                    file_index.setdefault(sub.name, []).append(sub)
    log(f"インデックス: {len(file_index)}種類")

    folder_map: dict[tuple, Path] = {}
    for folder1, folder2, file_name in combos:
        key = (folder1, folder2)
        if key in folder_map: continue
        paths = file_index.get(file_name, [])
        if paths:
            folder_map[key] = paths[0].parent

    def insert_file(mc_id, ftype, orig, stored, mime, fpath, fsize, pg_role=None, sort_order=0):
        if dry_run: return
        pgc.execute("""
            INSERT INTO mc_files
              (mc_program_id, file_type, original_name, stored_name, mime_type,
               file_path, thumbnail_path, file_size, pg_role, sort_order,
               is_deleted, uploaded_by, uploaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,false,%s,NOW())
            ON CONFLICT DO NOTHING
        """, (mc_id, ftype, orig, stored, mime, str(fpath),
              fsize, pg_role, sort_order, ADMIN_ID))

    # ── 7A: 図 ─────────────────────────────────────
    log("\n--- 7A: 図 (Drawings) ---")
    ok=skip=nomatch=err=0
    processed = set()
    src_dirs = [d for d in [UPLOAD_DRAW, DST_DRAW, SRC_DRAW] if d.exists()]
    for src_dir in src_dirs:
        files = sorted(f for f in src_dir.iterdir() if f.is_file())
        log(f"  ソース: {src_dir} ({len(files)}件)")
        for i, f in enumerate(files):
            m = re.match(r'^(\d+)-(\d+)\.(tif|TIF|jpg|JPG|png|PNG)$', f.name)
            if not m: skip+=1; continue
            mach_id=int(m.group(1)); seq=int(m.group(2)); ext=f.suffix.lower()
            stored = f"{mach_id}-{seq}{ext}"
            if stored in processed: skip+=1; continue
            if mach_id not in machining_map: nomatch+=1; continue
            dst = UPLOAD_DRAW / stored
            try:
                if not dst.exists(): shutil.copy2(f, dst)
                files_dst = DST_DRAW / stored
                if not files_dst.exists() and src_dir != DST_DRAW:
                    shutil.copy2(f, files_dst)
                fsize = dst.stat().st_size
                mime  = "image/tiff" if ext == ".tif" else "image/jpeg"
                for mc_id in machining_map[mach_id]:
                    insert_file(mc_id, "DRAWING", f.name, stored, mime, dst, fsize, sort_order=seq)
                ok+=1; processed.add(stored)
            except Exception as e:
                err+=1
                if err<=10: log(f"  ERR {f.name}: {e}", "WARN")
            if (i+1)%1000==0:
                if not dry_run: pg.commit()
                log(f"    {i+1}/{len(files)} ok={ok} skip={skip} nomatch={nomatch} err={err}")
    if not dry_run: pg.commit()
    log(f"7A完了: ok={ok} skip={skip} nomatch={nomatch} err={err}")

    # ── 7B: 写真 ────────────────────────────────────
    log("\n--- 7B: 写真 (Pictures) ---")
    ok=skip=nomatch=err=0
    processed = set()
    src_dirs = [d for d in [UPLOAD_PHOTO, DST_PHOTO, SRC_PHOTO] if d.exists()]
    for src_dir in src_dirs:
        files = sorted(f for f in src_dir.iterdir() if f.is_file())
        log(f"  ソース: {src_dir} ({len(files)}件)")
        for i, f in enumerate(files):
            m = re.match(r'^(\d+)-(\d+)\.(jpg|jpeg|JPG|png|PNG)$', f.name)
            if not m: skip+=1; continue
            mach_id=int(m.group(1)); seq=int(m.group(2)); ext=f.suffix.lower()
            stored = f"{mach_id}-{seq}{ext}"
            if stored in processed: skip+=1; continue
            if mach_id not in machining_map: nomatch+=1; continue
            dst = UPLOAD_PHOTO / stored
            try:
                if not dst.exists(): shutil.copy2(f, dst)
                files_dst = DST_PHOTO / stored
                if not files_dst.exists() and src_dir != DST_PHOTO:
                    shutil.copy2(f, files_dst)
                fsize = dst.stat().st_size
                for mc_id in machining_map[mach_id]:
                    insert_file(mc_id, "PHOTO", f.name, stored, "image/jpeg", dst, fsize, sort_order=seq)
                ok+=1; processed.add(stored)
            except Exception as e:
                err+=1
                if err<=10: log(f"  ERR {f.name}: {e}", "WARN")
            if (i+1)%1000==0:
                if not dry_run: pg.commit()
                log(f"    {i+1}/{len(files)} ok={ok} skip={skip} nomatch={nomatch} err={err}")
    if not dry_run: pg.commit()
    log(f"7B完了: ok={ok} skip={skip} nomatch={nomatch} err={err}")

    # ── 7C: プログラム ──────────────────────────────
    log("\n--- 7C: プログラム (Programs) ---")
    ok=skip=nomatch=notfound=err=0
    pgc.execute("""
        SELECT d.machining_id, p.id, d.folder1, d.folder2, d.file_name
        FROM mc_machining_details d
        JOIN mc_programs p ON p.machining_id = d.machining_id
        WHERE d.file_name IS NOT NULL AND d.file_name != '' AND d.folder1 IS NOT NULL
    """)
    programs = pgc.fetchall()
    log(f"  対象: {len(programs)}件")
    for mach_id, mc_id, folder1, folder2, file_name in programs:
        key     = (folder1, folder2)
        src_dir = folder_map.get(key)
        if not src_dir: nomatch+=1; continue
        src_file = src_dir / file_name
        if not src_file.exists() or not src_file.is_file(): notfound+=1; continue
        dst_dir = UPLOAD_PG / str(mach_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_file = dst_dir / file_name
        files_dir = DST_PRG / str(mach_id)
        files_dir.mkdir(parents=True, exist_ok=True)
        files_dst = files_dir / file_name
        try:
            if not dst_file.exists(): shutil.copy2(src_file, dst_file)
            if not files_dst.exists(): shutil.copy2(src_file, files_dst)
            fsize   = dst_file.stat().st_size
            pg_role = "SUB" if str(file_name).lower().endswith(".spf") else "MAIN"
            insert_file(mc_id, "PROGRAM", file_name, file_name, "text/plain",
                        dst_file, fsize, pg_role=pg_role, sort_order=0)
            ok+=1
        except Exception as e:
            err+=1
            if err<=10: log(f"  ERR {mach_id}/{file_name}: {e}", "WARN")
        if ok%500==0 and ok>0:
            if not dry_run: pg.commit()
            log(f"  {ok}件完了... nomatch={nomatch} notfound={notfound} err={err}")
    if not dry_run: pg.commit()
    log(f"7C完了: ok={ok} skip={skip} nomatch={nomatch} notfound={notfound} err={err}")

    pgc.execute("SELECT file_type, COUNT(*) FROM mc_files GROUP BY file_type ORDER BY file_type")
    log("\n--- mc_files 集計 ---")
    for row in pgc.fetchall(): log(f"  {row[0]}: {row[1]}件")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 8: カウント更新
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase8(pg, dry_run=False):
    section("PHASE 8: RC/has_index_program/has_work_offset更新")
    pgc = pg.cursor()
    if not dry_run:
        pgc.execute("""
            UPDATE mc_machining_details d SET
              rc = (SELECT COUNT(*) FROM mc_tooling t WHERE t.machining_id=d.machining_id),
              has_index_program = (EXISTS(SELECT 1 FROM mc_index_programs i WHERE i.machining_id=d.machining_id)),
              has_work_offset   = (EXISTS(SELECT 1 FROM mc_work_offsets w WHERE w.machining_id=d.machining_id))
        """)
        pg.commit()
    pgc.execute("SELECT SUM(rc) FROM mc_machining_details")
    log(f"PHASE8完了: RC総計={pgc.fetchone()[0]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 最終レポート
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def final_report(pg):
    section("最終レポート")
    pgc = pg.cursor()
    items = [
        ("mc_machining_details","SELECT COUNT(*) FROM mc_machining_details"),
        ("mc_programs",       "SELECT COUNT(*) FROM mc_programs"),
        ("mc_tooling",        "SELECT COUNT(*) FROM mc_tooling"),
        ("mc_work_offsets",   "SELECT COUNT(*) FROM mc_work_offsets"),
        ("mc_index_programs", "SELECT COUNT(*) FROM mc_index_programs"),
        ("mc_change_history", "SELECT COUNT(*) FROM mc_change_history"),
        ("mc_files(DRAWING)", "SELECT COUNT(*) FROM mc_files WHERE file_type='DRAWING'"),
        ("mc_files(PHOTO)",   "SELECT COUNT(*) FROM mc_files WHERE file_type='PHOTO'"),
        ("mc_files(PROGRAM)", "SELECT COUNT(*) FROM mc_files WHERE file_type='PROGRAM'"),
        ("parts",             "SELECT COUNT(*) FROM parts"),
    ]
    for label, sql in items:
        pgc.execute(sql)
        log(f"  {label:25s}: {pgc.fetchone()[0]:>8,}件")
    log(f"\nログ: {LOG_FILE}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 9: 採番整合性確認・NULLレコード自動修復
# 旧システムのMCID採番ロジック継承を検証
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase9(pg, dry_run=False):
    section("PHASE 9: 採番整合性確認 + NULL自動修復")
    pgc = pg.cursor()
    pgc.execute("SELECT COALESCE(MAX(legacy_mcid),0) FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    max_legacy = pgc.fetchone()[0]
    pgc.execute("SELECT COALESCE(MAX(machining_id),0) FROM mc_machining_details")
    max_machining = pgc.fetchone()[0]
    next_id = max(max_legacy, max_machining) + 1
    log(f"MAX(legacy_mcid): {max_legacy}")
    log(f"MAX(machining_id) in mc_machining_details: {max_machining}")
    log(f"次回採番予定番号: {next_id}")
    pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE legacy_mcid IS NULL")
    null_cnt = pgc.fetchone()[0]
    log(f"legacy_mcid NULL レコード（要修復）: {null_cnt}件")
    if null_cnt > 0 and not dry_run:
        pgc.execute("SELECT id FROM mc_programs WHERE legacy_mcid IS NULL ORDER BY id")
        null_ids = [r[0] for r in pgc.fetchall()]
        pgc.execute("SELECT COALESCE(MAX(legacy_mcid),0) FROM mc_programs WHERE legacy_mcid IS NOT NULL")
        cur_max = pgc.fetchone()[0]
        for row_id in null_ids:
            cur_max += 1
            pgc.execute("UPDATE mc_programs SET legacy_mcid = %s WHERE id = %s", (cur_max, row_id))
        pg.commit()
        log(f"自動修復完了: {len(null_ids)}件 → legacy_mcid ~{cur_max}")
        next_id = cur_max + 1
    elif null_cnt > 0:
        log("[DRY-RUN] 修復スキップ")
    log(f"次回MCID採番: {next_id} から連番")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(description="MachCore MC完全移行スクリプト")
    parser.add_argument("--phase", type=int, default=0,
                        help="実行フェーズ (0=全, 1-9=個別)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DBへの書き込みなし")
    args = parser.parse_args()

    dry = args.dry_run
    if dry: log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    pg = pg_connect()
    try:
        phases = {1:phase1, 2:phase2, 3:phase3, 4:phase4,
                  5:phase5, 6:phase6, 7:phase7, 8:phase8, 9:phase9}
        run = list(range(1,10)) if args.phase == 0 else [args.phase]
        for p in run:
            try:
                phases[p](pg, dry_run=dry)
            except Exception as e:
                log(f"PHASE {p} エラー: {e}", "ERROR")
                log(traceback.format_exc(), "ERROR")
                raise
        final_report(pg)
    finally:
        pg.close()
        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n総実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        _log_fh.close()

if __name__ == "__main__":
    main()
