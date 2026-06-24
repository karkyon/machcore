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

import sys, os, re, shutil, argparse, traceback, subprocess
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
# d1共有(192.168.1.9/d1) → /mnt/mcfiles  ← 旧MC移行元
# d2共有(192.168.1.9/d2) → /mnt/mc_files ← 新システム格納先
# 構造: /mnt/mc_files/MC/files/{Drawings,Pictures,Programs,thumbnails}
SMB_MC_ROOT  = Path("/mnt/mcfiles/MC")
SRC_DRAW     = SMB_MC_ROOT / "図"
SRC_PHOTO    = SMB_MC_ROOT / "写真"
SRC_PRG      = SMB_MC_ROOT / "ﾌﾟﾛｸﾞﾗﾑ"
DST_ROOT     = Path("/mnt/mc_files/MC/files")
DST_DRAW     = DST_ROOT / "Drawings"
DST_PHOTO    = DST_ROOT / "Pictures"
DST_PRG      = DST_ROOT / "Programs"
UPLOAD_BASE  = Path("/mnt/mc_files")
UPLOAD_DRAW  = DST_DRAW
UPLOAD_PHOTO = DST_PHOTO
UPLOAD_PG    = DST_PRG
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
    mc  = ss_connect(SS_MC_DB)
    pb  = ss_connect(SS_PB_DB)
    mcc = mc.cursor()
    pbc = pb.cursor()
    pgc = pg.cursor()

    if not dry_run:
        log("既存データ全破棄...")
        pgc.execute("DELETE FROM mc_files")
        pgc.execute("DELETE FROM mc_change_history")
        pgc.execute("DELETE FROM mc_setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM operation_logs WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM work_sessions WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM mc_programs")
        pgc.execute("DELETE FROM mc_machining_details")
        pg.commit()
        log("全破棄完了")

    pbc.execute("SELECT 部品ID, 図面番号, 名称, 主機種型式, 納入先ID FROM v_旧部品マスタ")
    buhin_rows = pbc.fetchall()
    log(f"部品マスタ取得: {len(buhin_rows)}件")

    pbc.execute("SELECT 納入先ID, 会社名 FROM v_旧得意先マスタ")
    client_map = {r[0]: r[1] for r in pbc.fetchall()}

    pgc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pgc.fetchall()}

    parts_inserted = 0
    for buhin_id, drawing_no, name, main_model, client_id in buhin_rows:
        pid_str     = str(buhin_id)
        client_name = client_map.get(client_id, "")
        if pid_str not in parts_map:
            if not dry_run:
                pgc.execute("""
                    INSERT INTO parts (part_id, drawing_no, name, main_model, client_name, is_active, synced_at)
                    VALUES (%s,%s,%s,%s,%s,true,NOW())
                    ON CONFLICT (part_id) DO UPDATE SET
                        drawing_no=EXCLUDED.drawing_no, name=EXCLUDED.name,
                        main_model=EXCLUDED.main_model, client_name=EXCLUDED.client_name,
                        synced_at=NOW()
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

    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type='MC'")
    machines_map = {r[1]: r[0] for r in pgc.fetchall()}

    pgc.execute("SELECT id, name FROM users")
    users_map = {r[1]: r[0] for r in pgc.fetchall()}
    import re as _p1re
    _u_norm_p1 = {_p1re.sub(r'[\s\u3000]+', ' ', k).strip(): v for k, v in users_map.items()}
    def _p1_resolve(raw):
        if not raw: return None
        val = str(raw).strip()
        if val in users_map: return users_map[val]
        normed = _p1re.sub(r'[\s\u3000]+', ' ', val).strip()
        return _u_norm_p1.get(normed)

    # 機械: ACC_マシニングrawの「機械」列は文字列("MC5"等) → machines_mapから直引き
    ss_machine_map = dict(machines_map)  # machine_code → machines.id
    # "MC"プレフィックスなし対応
    for code, mid in list(machines_map.items()):
        if code.startswith("MC"):
            ss_machine_map[code[2:]] = mid

    # ACC_マシニングraw 確定カラム(ログより):
    # 加工ID, ﾊﾞｰｼﾞｮﾝ, [MC工程No,], ﾌｫﾙﾀﾞ1, ﾌｫﾙﾀﾞ2, ﾌｧｲﾙ名, [ﾒｲﾝﾌﾟﾛｸﾞﾗﾑNo,],
    # 機械, 加工時間H/M/S, 加工個数, ｸﾗﾝﾌﾟ, 備考, 氏名, 入力日,
    # [IP 有･無], [WD 有･無], 写真枚数, RC, 図枚数, ｵﾍﾟﾚｰﾀｰ,
    # IN_DATE, 作成, S_DATE, prg
    # ※ カンマ・スペース含むカラムは角括弧でエスケープ必須
    mcc.execute("""
        SELECT
            mc.部品ID, mc.MCID, mc.加工ID,
            m.ﾊﾞｰｼﾞｮﾝ, m.[MC工程No,], m.ﾌｫﾙﾀﾞ1, m.ﾌｫﾙﾀﾞ2, m.ﾌｧｲﾙ名,
            m.[ﾒｲﾝﾌﾟﾛｸﾞﾗﾑNo,], m.機械, m.加工時間H, m.加工時間M, m.加工時間S,
            m.加工個数, m.ｸﾗﾝﾌﾟ, m.備考,
            NULL, m.[IP 有･無], m.[WD 有･無],
            m.写真枚数, m.RC, m.図枚数,
            m.ｵﾍﾟﾚｰﾀｰ, m.IN_DATE,
            m.作成, m.S_DATE,
            m.氏名, m.入力日
        FROM ACC_MC mc
        INNER JOIN ACC_マシニングraw m ON mc.加工ID = m.加工ID
        ORDER BY mc.MCID
    """)
    rows = mcc.fetchall()
    log(f"旧DBマシニング取得: {len(rows)}件")

    ok = skip = err = 0
    for row in rows:
        try:
            # 列順(28列):
            # 部品ID, MCID, 加工ID,
            # ﾊﾞｰｼﾞｮﾝ, MC工程No, ﾌｫﾙﾀﾞ1, ﾌｫﾙﾀﾞ2, ﾌｧｲﾙ名,
            # ﾒｲﾝﾌﾟﾛｸﾞﾗﾑNo, 機械(文字列), 加工時間H, 加工時間M, 加工時間S,
            # 加工個数, ｸﾗﾝﾌﾟ, 備考,
            # NULL(担当者ID), IP有無, WD有無,
            # 写真枚数, RC, 図枚数,
            # ｵﾍﾟﾚｰﾀｰ(名前), IN_DATE,
            # 作成(シート作成者名), S_DATE(シート作成日),
            # 氏名(承認者名), 入力日(承認日)
            (buhin_id, mcid, kakoid,
             version, process_no, path1, path2, file_name,
             main_pg_no, machine_name, time_h, time_m, time_s,
             qty, clamp, note,
             _dummy, ip_umu, wd_umu,
             photo_cnt, rc, draw_cnt,
             operater_name, in_date,
             creator_name, sheet_created_at,
             approver_name, approved_date) = row

            part_db_id = parts_map.get(str(buhin_id))
            if not part_db_id: skip += 1; continue

            # 機械名文字列→machines.id
            machine_db_id = None
            if machine_name:
                mn = str(machine_name).strip()
                machine_db_id = ss_machine_map.get(mn)

            ct_sec = None
            if time_h is not None or time_m is not None or time_s is not None:
                ct_sec = int(time_h or 0)*3600 + int(time_m or 0)*60 + int(time_s or 0)

            has_ip = str(ip_umu or "").strip() not in ("ﾅｼ", "なし", "0", "")
            has_wd = str(wd_umu or "").strip() not in ("ﾅｼ", "なし", "0", "")

            # ① 作成者(シート): 作成列名前→ID (直接解決)
            cr_id           = _p1_resolve(creator_name)
            # ⑤ オペレーター: ｵﾍﾟﾚｰﾀｰ列名前→ID (直接解決、PHASE6Cで未解決分のみ上書き)
            reg_id          = _p1_resolve(operater_name) or ADMIN_ID
            # ③ 承認者: 氏名列名前→ID (PHASE6Dでも補完更新)
            approver_id     = _p1_resolve(approver_name)
            # ④ 承認日: 入力日列（マシニング）
            approved_at_v   = approved_date if approved_date else in_date
            # ⑥ 入力日: IN_DATE列
            registered_at_v = in_date if in_date else datetime.now()

            ver_str = str(version or "1.0001")

            if dry_run: ok += 1; continue

            pgc.execute("""
                INSERT INTO mc_machining_details (
                    machining_id, version, machine_id, o_number,
                    clamp_note, cycle_time_sec, mc_process_no,
                    folder1, folder2, file_name,
                    has_index_program, has_work_offset, rc,
                    creator_id, sheet_created_at,
                    legacy_kakoid, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (machining_id) DO UPDATE SET
                    version=EXCLUDED.version, machine_id=EXCLUDED.machine_id,
                    o_number=EXCLUDED.o_number, clamp_note=EXCLUDED.clamp_note,
                    cycle_time_sec=EXCLUDED.cycle_time_sec, mc_process_no=EXCLUDED.mc_process_no,
                    folder1=EXCLUDED.folder1, folder2=EXCLUDED.folder2, file_name=EXCLUDED.file_name,
                    has_index_program=EXCLUDED.has_index_program, has_work_offset=EXCLUDED.has_work_offset,
                    rc=EXCLUDED.rc, creator_id=EXCLUDED.creator_id,
                    sheet_created_at=EXCLUDED.sheet_created_at,
                    legacy_kakoid=EXCLUDED.legacy_kakoid, updated_at=NOW()
            """, (kakoid, ver_str, machine_db_id, main_pg_no,
                  clamp, ct_sec, process_no,
                  str(path1) if path1 is not None else None,
                  str(path2) if path2 is not None else None,
                  str(file_name) if file_name else None,
                  has_ip, has_wd, int(rc or 0),
                  cr_id, sheet_created_at, kakoid))

            pgc.execute("""
                INSERT INTO mc_programs (
                    part_id, machining_id, machining_qty, note, status,
                    registered_by, approved_by, approved_at,
                    registered_at, legacy_mcid, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,'APPROVED',%s,%s,%s,%s,%s,NOW(),NOW())
            """, (part_db_id, kakoid, qty or 1, note,
                  reg_id, approver_id, approved_at_v, registered_at_v, mcid))

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

    if not dry_run:
        pgc.execute("DELETE FROM mc_work_offsets")
        pg.commit()
        log("mc_work_offsets既存データ削除完了")

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
                    ON CONFLICT DO NOTHING
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

    if not dry_run:
        pgc.execute("DELETE FROM mc_index_programs")
        pg.commit()
        log("mc_index_programs既存データ削除完了")

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
                    ON CONFLICT DO NOTHING
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
# PHASE 6: ACC_変更履歴 → 3テーブル分離移行
#
# 旧 ACC_変更履歴 1レコードの構造（3アクティビティが混在）：
#   ① 段取シート印刷   : 内容 に "段取シート印刷" / "仮登録" / "印刷" を含む
#                         → mc_setup_sheet_logs
#   ② 作業実績         : TH/TM/TS > 0 or ﾜｰｸ数 > 0 or 段取開始 IS NOT NULL
#                         → work_records (mc_program_id, work_type='MC')
#   ③ マシニング変更    : 内容 が "新規登録" / "変更" / "承認" 等
#                         → mc_change_history
#
# ※ 1レコードが複数テーブルに書き込まれるケースあり
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase6(pg, dry_run=False):
    section("PHASE 6: ACC_変更履歴 → 3テーブル分離移行")
    import json as _json, re as _re2
    from datetime import timedelta as _td

    pgc = pg.cursor()

    # テーブルクリア
    if not dry_run:
        pgc.execute("DELETE FROM mc_change_history WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM mc_setup_sheet_logs WHERE mc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM work_records WHERE mc_program_id IS NOT NULL")
        pg.commit()
        log("mc_change_history / mc_setup_sheet_logs / work_records(MC分) 削除完了")

    # ユーザーマップ
    pgc.execute("SELECT id, name FROM users")
    _u_rows = pgc.fetchall()
    _u_exact = {r[1]: r[0] for r in _u_rows}
    _u_norm  = {_re2.sub(r"[\s\u3000]+", " ", r[1]).strip(): r[0] for r in _u_rows}

    def _resolve(raw_val):
        if not raw_val: return None
        val = str(raw_val).strip()
        if val in _u_exact: return _u_exact[val]
        normed = _re2.sub(r"[\s\u3000]+", " ", val).strip()
        if normed in _u_norm: return _u_norm[normed]
        return None

    def _resolve_multi(raw_val):
        if not raw_val: return []
        parts = _re2.split(r"[&\uff06,\u3001]", str(raw_val))
        ids = []
        for part in parts:
            part = part.strip()
            if not part: continue
            uid = _resolve(part)
            if uid:
                ids.append(uid)
                continue
            # スペース区切り複数名前方貪欲マッチ
            remaining = _re2.sub(r"[\s\u3000]+", " ", part).strip()
            while remaining:
                matched_id = None; matched_len = 0
                for nm, uid in _u_norm.items():
                    if remaining.startswith(nm) and len(nm) > matched_len:
                        matched_id = uid; matched_len = len(nm)
                if matched_id:
                    ids.append(matched_id); remaining = remaining[matched_len:].strip()
                else:
                    break
        return list(dict.fromkeys(ids))

    # 機械マップ (機械名→machines.id)
    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type='MC'")
    _machines_map = {r[1]: r[0] for r in pgc.fetchall()}

    # mcid_map (legacy_mcid → [mc_program_id,...])
    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_map = {}
    for mc_id, lmid in pgc.fetchall():
        mcid_map.setdefault(lmid, []).append(mc_id)

    # 旧DBから変更履歴全件取得
    ss_conn = ss_connect(SS_MC_DB)
    ss_cur  = ss_conn.cursor()

    # カラム確認
    try:
        ss_cur.execute("SELECT TOP 1 * FROM ACC_変更履歴")
        cols = [d[0] for d in ss_cur.description]
        log(f"ACC_変更履歴カラム: {cols}")
    except Exception as e:
        log(f"[WARN] ACC_変更履歴カラム確認失敗: {e}", "WARN")
        cols = []

    ss_cur.execute("""
        SELECT MCID, 加工ID, 内容, 内容区分ID, 内容区分, Ver,
               作成, 作成日, ｵﾍﾟﾚｰﾀｰ, 入力日,
               承認, 承認日,
               Prg, PrgPlas, PrgTimeH, PrgTimeM,
               段取, 作業者, 機械, TH, TM, TS,
               [1S_個数], R_IN_DATE, R_OP,
               段取開始, ﾁｪｯｸTime, ﾁｪｯｸMan, 加工終了,
               [段取_ﾜｰｸ数], [ﾜｰｸ数],
               段取時間, 加工時間, 総時間,
               [ｻｲｸﾙﾀｲﾑ/1P], [加工時間/1P], [総時間/1P]
        FROM ACC_変更履歴
        ORDER BY MCID, 入力日
    """)
    all_rows = ss_cur.fetchall()
    log(f"ACC_変更履歴取得: {len(all_rows)}件")

    COL_NAMES = [
        "MCID","加工ID","内容","内容区分ID","内容区分","Ver",
        "作成","作成日","ｵﾍﾟﾚｰﾀｰ","入力日",
        "承認","承認日",
        "Prg","PrgPlas","PrgTimeH","PrgTimeM",
        "段取","作業者","機械","TH","TM","TS",
        "1S_個数","R_IN_DATE","R_OP",
        "段取開始","ﾁｪｯｸTime","ﾁｪｯｸMan","加工終了",
        "段取_ﾜｰｸ数","ﾜｰｸ数",
        "段取時間","加工時間","総時間",
        "ｻｲｸﾙﾀｲﾑ/1P","加工時間/1P","総時間/1P"
    ]

    # ──────────────────────────────────────────────
    # 時間パース (HH:MM:SS または "3H 30M" テキスト形式)
    # ──────────────────────────────────────────────
    def _parse_hms_min(s):
        if not s: return None
        s = str(s).strip()
        mh = _re2.search(r"(\d+)H", s); mm = _re2.search(r"H\s*(\d+)M", s)
        if mh:
            h = int(mh.group(1)); m = int(mm.group(1)) if mm else 0
            return h * 60 + m if (h > 0 or m > 0) else None
        return None

    def _parse_hms_sec(s):
        if not s: return None
        s = str(s).strip()
        mh = _re2.search(r"(\d+)H", s)
        mm = _re2.search(r"H\s*(\d+)M", s)
        ms = _re2.search(r"M\s*(\d+)S", s)
        h = int(mh.group(1)) if mh else 0
        m = int(mm.group(1)) if mm else 0
        sc= int(ms.group(1)) if ms else 0
        return h*3600 + m*60 + sc if (h or m or sc) else None

    def _to_jst_utc(dt):
        """SQL Serverから来るJSTのnaive datetimeをUTCに変換（-9h）"""
        if dt is None: return None
        from datetime import timezone
        try:
            return dt - _td(hours=9)
        except Exception:
            return dt

    # カウンタ
    sl_ok = sl_skip = sl_err = 0
    ch_ok = ch_skip = ch_err = 0
    wr_ok = wr_skip = wr_err = 0
    err_msgs = []
    commit_every = 500
    row_count = 0

    for raw_row in all_rows:
        rd = dict(zip(COL_NAMES, raw_row))
        row_count += 1

        try:
            mcid = rd["MCID"]
            mc_db_ids = mcid_map.get(mcid, [])
            if not mc_db_ids:
                sl_skip += 1; continue

            nk = rd["内容区分ID"] or 0
            try: nk = int(nk)
            except: nk = 0

            content     = str(rd["内容"] or "").strip()
            input_dt    = _to_jst_utc(rd["入力日"])
            return_dt   = rd["R_IN_DATE"]   # 戻り日付（段取シートバック日）
            ver_str     = str(rd["Ver"] or "").strip() or None
            op_name     = str(rd["ｵﾍﾟﾚｰﾀｰ"] or "").strip()
            creator_name= str(rd["作成"]    or "").strip()
            approver_name=str(rd["承認"]    or "").strip()
            machine_name= str(rd["機械"]    or "").strip()

            op_id       = _resolve(op_name) or ADMIN_ID
            creator_id  = _resolve(creator_name) or ADMIN_ID
            approver_id = _resolve(approver_name) if approver_name else None
            machine_id  = _machines_map.get(machine_name)

            # ━━ work_collected 判定 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ストアド準拠:
            # 1) 内容に「済」含む → 回収済
            # 2) R_IN_DATE(戻り日付)がNULLでない → 回収済(usp_init_copy_mc_dataの補完と同等)
            has_zumi = "済" in content
            has_return_dt = return_dt is not None and str(return_dt).strip() != ""
            work_collected = has_zumi or has_return_dt

            # ━━ setup_sheet_type 判定 ━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 内容区分ID=3→NEW, 7→NEW, 1で参考含む→REFERENCE(is_reference=True), 1→REPEAT
            if nk in (3, 7):
                sheet_type  = "NEW"
                is_reference = False
            elif nk == 1:
                if "参考" in content:
                    sheet_type   = "REPEAT"
                    is_reference = True
                    work_collected = True  # 参考出力は回収済(setup_sheet_type_cd=9補完)
                else:
                    sheet_type   = "REPEAT"
                    is_reference = False
            else:
                sheet_type   = None
                is_reference = False

            for mc_db_id in mc_db_ids:

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # [1][3][7] → mc_setup_sheet_logs に INSERT
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                if nk in (1, 3, 7) and not dry_run:
                    try:
                        qty_val = rd["ﾜｰｸ数"]
                        qty = int(float(str(qty_val))) if qty_val else None
                        pgc.execute("""
                            INSERT INTO mc_setup_sheet_logs
                              (mc_program_id, operator_id, printed_at, version,
                               work_collected, is_reference, sheet_type,
                               quantity, machine_id_log)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (mc_db_id, op_id,
                              input_dt or datetime.now(),
                              ver_str,
                              work_collected,
                              is_reference,
                              sheet_type,
                              qty,
                              machine_id))
                        sl_ok += 1
                    except Exception as e2:
                        sl_err += 1
                        if sl_err <= 5: err_msgs.append(f"SL ERR mcid={mcid}: {e2}")

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # [2][4][5][6][8][9][10][11][13][14][15][16][99] → mc_change_history
                # 内容区分ID=1,3,7,12,17 は入れない
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                if nk in (2,4,5,6,8,9,10,11,13,14,15,16,99) and not dry_run:
                    if nk in (2, 8):
                        change_type = "NEW_REGISTRATION"
                        ch_op_id = creator_id
                    elif nk == 4:
                        change_type = "APPROVAL"
                        ch_op_id = approver_id or creator_id
                        # 承認時の入力日は承認日
                        input_dt_ch = _to_jst_utc(rd["承認日"]) if rd["承認日"] else input_dt
                    else:
                        change_type = "CHANGE"
                        ch_op_id = creator_id
                    if ch_op_id is None: ch_op_id = ADMIN_ID

                    changed_at_val = (input_dt_ch if nk == 4 else input_dt) or datetime.now()

                    try:
                        pgc.execute("""
                            INSERT INTO mc_change_history
                              (mc_program_id, change_type, operator_id,
                               version_after, content, changed_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (mc_db_id, change_type, ch_op_id,
                              ver_str, content[:500] if content else None,
                              changed_at_val))
                        ch_ok += 1
                    except Exception as e2:
                        ch_err += 1
                        if ch_err <= 5: err_msgs.append(f"CH ERR mcid={mcid} nk={nk}: {e2}")

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # [17] 作業記録 OR 総時間あり → work_records
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                has_work = (nk == 17) or (rd["総時間"] is not None and str(rd["総時間"]).strip() != "")
                if has_work and not dry_run:
                    wd_date = input_dt.date() if input_dt else datetime.now().date()

                    setup_min  = _parse_hms_min(rd["段取時間"])
                    mach_min   = _parse_hms_min(rd["加工時間"])
                    th = int(rd["TH"] or 0); tm = int(rd["TM"] or 0); ts = int(rd["TS"] or 0)
                    cycle_sec  = _parse_hms_sec(rd["ｻｲｸﾙﾀｲﾑ/1P"])
                    if cycle_sec is None and (th or tm or ts):
                        cycle_sec = th*3600 + tm*60 + ts

                    qty_val = rd["ﾜｰｸ数"]
                    work_qty = int(float(str(qty_val))) if qty_val else None
                    setup_qty_val = rd["段取_ﾜｰｸ数"]
                    setup_qty = int(float(str(setup_qty_val))) if setup_qty_val else None

                    # 担当者
                    setup_ids = _resolve_multi(rd["段取"])
                    prod_ids  = _resolve_multi(rd["作業者"])
                    work_op_id = _resolve(rd["ｵﾍﾟﾚｰﾀｰ"]) or ADMIN_ID

                    # 時刻 (SQL Serverから来るJSTのnaive datetime/varchar)
                    def _parse_dt(v):
                        if v is None: return None
                        if hasattr(v, "year"): return _to_jst_utc(v)
                        s = str(v).strip()
                        if not s: return None
                        for fmt in ["%Y/%m/%d", "%Y-%m-%d"]:
                            try: return datetime.strptime(s, fmt)
                            except: pass
                        return None

                    started_at  = _parse_dt(rd["段取開始"])
                    checked_at  = _parse_dt(rd["ﾁｪｯｸTime"])
                    finished_at = _parse_dt(rd["加工終了"])

                    # Prg
                    prg_man     = str(rd["Prg"] or "").strip() or None
                    prg_plas    = str(rd["PrgPlas"] or "").strip() or None
                    prg_h = int(rd["PrgTimeH"] or 0); prg_m = int(rd["PrgTimeM"] or 0)
                    prg_min = prg_h*60 + prg_m if (prg_h or prg_m) else None

                    try:
                        pgc.execute("""
                            INSERT INTO work_records
                              (mc_program_id, operator_id, machine_id,
                               work_date, setup_time_min, machining_time_min,
                               cycle_time_sec, quantity, started_at, checked_at, finished_at,
                               setup_work_count, prg_man, prg_time_min, prg_plas,
                               setup_operator_ids, production_operator_ids,
                               work_type, created_at)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'MC',NOW())
                        """, (mc_db_id, work_op_id, machine_id,
                              wd_date,
                              setup_min, mach_min, cycle_sec,
                              work_qty,
                              started_at, checked_at, finished_at,
                              setup_qty,
                              prg_man, prg_min, prg_plas,
                              _json.dumps(setup_ids),
                              _json.dumps(prod_ids)))
                        wr_ok += 1
                    except Exception as e2:
                        wr_err += 1
                        if wr_err <= 5: err_msgs.append(f"WR ERR mcid={mcid}: {e2}")

        except Exception as e:
            sl_err += 1
            if len(err_msgs) < 10: err_msgs.append(f"ERR MCID={rd.get('MCID')}: {e}")

        if row_count % commit_every == 0 and not dry_run:
            pg.commit()
            log(f"  進捗: {row_count}/{len(all_rows)} "
                f"SL={sl_ok} CH={ch_ok} WR={wr_ok} err={sl_err+ch_err+wr_err}")

    if not dry_run: pg.commit()
    ss_conn.close()

    for msg in err_msgs: log(f"  {msg}", "WARN")
    log(f"PHASE6完了: 入力={row_count} skip={sl_skip} SL_err={sl_err} CH_err={ch_err} WR_err={wr_err}")
    log(f"  [印刷履歴={sl_ok} / 変更履歴={ch_ok} / 作業実績={wr_ok}]")

    if not dry_run:
        # PHASE6B: registered_by/approved_by を変更履歴の新規登録・承認レコードで更新
        log("PHASE6B: registered_by/approved_by 更新...")
        pgc.execute("""
            UPDATE mc_programs p SET registered_by = ch.operator_id
            FROM (
                SELECT DISTINCT ON (mc_program_id) mc_program_id, operator_id
                FROM mc_change_history
                WHERE change_type = 'NEW_REGISTRATION'
                ORDER BY mc_program_id, changed_at ASC
            ) ch
            WHERE p.id = ch.mc_program_id AND ch.operator_id IS NOT NULL AND ch.operator_id != %s
        """, (ADMIN_ID,))
        pgc.execute("""
            UPDATE mc_programs p SET approved_by = ch.operator_id, approved_at = ch.changed_at
            FROM (
                SELECT DISTINCT ON (mc_program_id) mc_program_id, operator_id, changed_at
                FROM mc_change_history
                WHERE change_type = 'APPROVAL'
                ORDER BY mc_program_id, changed_at DESC
            ) ch
            WHERE p.id = ch.mc_program_id AND ch.operator_id IS NOT NULL
        """)
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE registered_by != %s", (ADMIN_ID,))
        log(f"  管理者以外のregistered_by: {pgc.fetchone()[0]}件")
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE approved_by IS NOT NULL AND approved_by != %s", (ADMIN_ID,))
        log(f"  管理者以外のapproved_by: {pgc.fetchone()[0]}件")

        # PHASE6C: registered_by を ACC_変更履歴 ｵﾍﾟﾚｰﾀｰ列最新から補完（ADMIN_IDのままのもの）
        log("PHASE6C: registered_by ｵﾍﾟﾚｰﾀｰ列最新から補完...")
        mc6c = ss_connect(SS_MC_DB)
        mc6c_c = mc6c.cursor()
        mc6c_c.execute("""
            SELECT MCID, ｵﾍﾟﾚｰﾀｰ, 入力日 FROM ACC_変更履歴
            WHERE ｵﾍﾟﾚｰﾀｰ IS NOT NULL AND LEN(RTRIM(ｵﾍﾟﾚｰﾀｰ)) > 0
            ORDER BY MCID, 入力日 DESC
        """)
        _op_map = {}
        for _mcid, _op_name, _ in mc6c_c.fetchall():
            if _mcid not in _op_map:
                _uid = _resolve(_op_name)
                if _uid and _uid != ADMIN_ID: _op_map[_mcid] = _uid
        _reg_ok = 0
        for _mcid, _uid in _op_map.items():
            for _mc_db_id in mcid_map.get(_mcid, []):
                pgc.execute("UPDATE mc_programs SET registered_by=%s WHERE id=%s AND registered_by=%s",
                            (_uid, _mc_db_id, ADMIN_ID))
                _reg_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE registered_by != %s", (ADMIN_ID,))
        log(f"  PHASE6C: registered_by補完={_reg_ok}件 管理者以外={pgc.fetchone()[0]}件")

        # PHASE6D: approved_by を ACC_変更履歴 承認カラムから補完
        log("PHASE6D: approved_by 承認カラムから補完...")
        mc6c_c.execute("""
            SELECT MCID, 承認, 承認日 FROM ACC_変更履歴
            WHERE 承認 IS NOT NULL AND LEN(RTRIM(承認)) > 0 AND 承認日 IS NOT NULL
            ORDER BY MCID, 承認日 DESC
        """)
        _seen = set(); _app_ok = 0
        for _mcid, _aname, _adate in mc6c_c.fetchall():
            if _mcid in _seen: continue
            _seen.add(_mcid)
            _uid = _resolve(_aname)
            if not _uid: continue
            for _mc_db_id in mcid_map.get(_mcid, []):
                pgc.execute("""
                    UPDATE mc_programs SET approved_by=%s, approved_at=%s
                    WHERE id=%s AND (approved_by IS NULL OR approved_by = %s)
                """, (_uid, _adate - _td(hours=9) if _adate else None, _mc_db_id, ADMIN_ID))
                _app_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE approved_by IS NOT NULL AND approved_by != %s", (ADMIN_ID,))
        log(f"  PHASE6D: approved_by補完={_app_ok}件 管理者以外={pgc.fetchone()[0]}件")

        # PHASE6E: work_records 段取/量産担当者の再名寄せ（既にINSERT時に処理済みだが補完）
        log("PHASE6E: work_records setup/production_operator_ids 確認...")
        pgc.execute("SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND setup_operator_ids != '[]'::jsonb")
        log(f"  setup_operator_ids設定済み: {pgc.fetchone()[0]}件")
        pgc.execute("SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND production_operator_ids != '[]'::jsonb")
        log(f"  production_operator_ids設定済み: {pgc.fetchone()[0]}件")

        # PHASE6F: sheet_created_at/creator_id を ACC_変更履歴の作成日/作成から更新（NULLのみ）
        log("PHASE6F: sheet_created_at/creator_id 更新...")
        mc6c_c.execute("""
            SELECT MCID, 加工ID, 作成, 作成日 FROM ACC_変更履歴
            WHERE 作成日 IS NOT NULL AND 作成 IS NOT NULL AND LEN(RTRIM(作成)) > 0
            ORDER BY MCID, 入力日 ASC
        """)
        _mach_sheet_map = {}
        for _mcid, _kakoid, _sakusha, _sakusha_date in mc6c_c.fetchall():
            if _kakoid and _kakoid not in _mach_sheet_map:
                _creator_id = _resolve(_sakusha)
                if _creator_id and _sakusha_date:
                    _mach_sheet_map[_kakoid] = (_sakusha_date, _creator_id)
        _sheet_ok = 0
        for _kakoid, (_sheet_date, _creator_id) in _mach_sheet_map.items():
            pgc.execute("""
                UPDATE mc_machining_details
                SET sheet_created_at = COALESCE(sheet_created_at, %s),
                    creator_id = COALESCE(creator_id, %s)
                WHERE machining_id = %s
            """, (_sheet_date - _td(hours=9) if _sheet_date else None,
                  _creator_id, _kakoid))
            if pgc.rowcount > 0: _sheet_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_machining_details WHERE sheet_created_at IS NOT NULL")
        log(f"  PHASE6F: sheet_created_at設定済み={pgc.fetchone()[0]}件 ok={_sheet_ok}件")

        mc6c.close()

    pgc.execute("SELECT COUNT(*) FROM mc_setup_sheet_logs WHERE mc_program_id IS NOT NULL")
    log(f"  mc_setup_sheet_logs(MC): {pgc.fetchone()[0]}")
    pgc.execute("SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL")
    log(f"  work_records(MC):        {pgc.fetchone()[0]}")
    pgc.execute("SELECT COUNT(*) FROM mc_change_history")
    log(f"  mc_change_history:       {pgc.fetchone()[0]}")




# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE7結果検証（読み取り専用・DB/FSへの書き込みなし）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _verify_program_files(pg, sample_n=10):
    pgc = pg.cursor()
    pgc.execute("""
        SELECT f.id, p.machining_id, f.stored_name, f.file_path, f.source_path, f.file_size
        FROM mc_files f
        JOIN mc_programs p ON p.id = f.mc_program_id
        WHERE f.file_type = 'PROGRAM' AND f.is_deleted = false
        ORDER BY f.id
    """)
    rows = pgc.fetchall()
    pgc.execute("SELECT machining_id, folder1, folder2 FROM mc_machining_details")
    fd_map = {r[0]: (r[1] or "", r[2] or "") for r in pgc.fetchall()}

    total = len(rows); ok = 0
    err_src = []; err_dst = []; err_size = []; err_fd = []; err_path = []
    for fid, mach_id, stored_name, file_path, source_path, file_size in rows:
        good = True
        src_exists = bool(source_path) and Path(source_path).exists()
        if not src_exists:
            err_src.append((fid, mach_id, source_path)); good = False
        dst_exists = bool(file_path) and Path(file_path).exists()
        if not dst_exists:
            err_dst.append((fid, mach_id, file_path)); good = False
        if src_exists and dst_exists:
            try:
                s_sz = Path(source_path).stat().st_size
                d_sz = Path(file_path).stat().st_size
                if s_sz != d_sz or d_sz != (file_size or -1):
                    err_size.append((fid, mach_id, s_sz, d_sz, file_size)); good = False
            except OSError as e:
                err_size.append((fid, mach_id, "STAT_ERROR", str(e), file_size)); good = False
        f1, f2 = fd_map.get(mach_id, ("", ""))
        expected_fd = f"{f1}{f2}"
        if source_path and expected_fd and expected_fd not in Path(source_path).parts:
            err_fd.append((fid, mach_id, expected_fd, source_path)); good = False
        if file_path:
            expected_suffix = f"Programs/{mach_id}/{stored_name}"
            if not str(file_path).replace("\\", "/").endswith(expected_suffix):
                err_path.append((fid, mach_id, file_path, expected_suffix)); good = False
        if good: ok += 1

    log(f"  PROGRAM検証: 対象={total}件 OK={ok}件")
    log(f"    ①source_path不在={len(err_src)} ②file_path不在={len(err_dst)} "
        f"③サイズ不一致={len(err_size)} ④FD名不整合={len(err_fd)} ⑤新パス規則違反={len(err_path)}")
    for label, lst in [("①source_path不在", err_src), ("②file_path不在", err_dst),
                        ("③サイズ不一致", err_size), ("④FD名不整合", err_fd),
                        ("⑤新パス規則違反", err_path)]:
        for item in lst[:sample_n]:
            log(f"      [{label}] {item}", "WARN")
    return total - ok


def _verify_image_files(pg, file_type, sample_n=10):
    pgc = pg.cursor()
    pgc.execute("""
        SELECT f.id, p.machining_id, f.stored_name, f.file_path, f.source_path, f.file_size
        FROM mc_files f
        JOIN mc_programs p ON p.id = f.mc_program_id
        WHERE f.file_type = %s AND f.is_deleted = false
        ORDER BY f.id
    """, (file_type,))
    rows = pgc.fetchall()

    total = len(rows); ok = 0
    err_src = []; err_dst = []; err_size = []; err_name = []; err_mismatch = []
    name_re = re.compile(r'^(\d+)-(\d+)\.[A-Za-z]+$')
    for fid, mach_id, stored_name, file_path, source_path, file_size in rows:
        good = True
        src_exists = bool(source_path) and Path(source_path).exists()
        if not src_exists:
            err_src.append((fid, mach_id, source_path)); good = False
        dst_exists = bool(file_path) and Path(file_path).exists()
        if not dst_exists:
            err_dst.append((fid, mach_id, file_path)); good = False
        if src_exists and dst_exists:
            try:
                s_sz = Path(source_path).stat().st_size
                d_sz = Path(file_path).stat().st_size
                if s_sz != d_sz or d_sz != (file_size or -1):
                    err_size.append((fid, mach_id, s_sz, d_sz, file_size)); good = False
            except OSError as e:
                err_size.append((fid, mach_id, "STAT_ERROR", str(e), file_size)); good = False
        m = name_re.match(stored_name or "")
        if not m:
            err_name.append((fid, mach_id, stored_name)); good = False
        elif int(m.group(1)) != mach_id:
            err_mismatch.append((fid, mach_id, int(m.group(1)), stored_name)); good = False
        if good: ok += 1

    log(f"  {file_type}検証: 対象={total}件 OK={ok}件")
    log(f"    ①source_path不在={len(err_src)} ②file_path不在={len(err_dst)} "
        f"③サイズ不一致={len(err_size)} ⑥命名規則違反={len(err_name)} ⑦ID取り違え={len(err_mismatch)}")
    for label, lst in [("①source_path不在", err_src), ("②file_path不在", err_dst),
                        ("③サイズ不一致", err_size), ("⑥命名規則違反", err_name),
                        ("⑦ID取り違え", err_mismatch)]:
        for item in lst[:sample_n]:
            log(f"      [{label}] {item}", "WARN")
    return total - ok


def verify_imported_files(pg, prg_only=False):
    """PHASE7直後に呼び出す検証関数（読み取り専用）。異常0件なら戻り値0。"""
    section("PHASE7結果検証（読み取り専用）")
    total_err = 0
    total_err += _verify_program_files(pg)
    if not prg_only:
        total_err += _verify_image_files(pg, "DRAWING")
        total_err += _verify_image_files(pg, "PHOTO")
    if total_err == 0:
        log("検証結果: 全件正常です ✅")
    else:
        log(f"検証結果: 異常 {total_err}件 見つかりました ⚠️ 上記サンプルを確認してください", "WARN")
    return total_err


def phase7(pg, dry_run=False, force_copy=False, prg_only=False):
    section("PHASE 7: 図・写真・プログラム ファイル移行" + ("（プログラムのみ）" if prg_only else ""))
    import shutil as _shutil

    # コピー先ディレクトリを必ず作成
    ensure_dirs(DST_DRAW, DST_PHOTO, DST_PRG)

    pgc = pg.cursor()

    if not dry_run:
        # mc_filesレコードは必ず全削除して再登録
        # ★prg_only指定時はPROGRAM分のみ削除（DRAWING/PHOTOのmc_filesは保持）
        if prg_only:
            pgc.execute("DELETE FROM mc_files WHERE file_type = 'PROGRAM'")
        else:
            pgc.execute("DELETE FROM mc_files")
        pg.commit()
        log("mc_files既存データ削除完了" + ("（PROGRAM分のみ）" if prg_only else ""))

        # --force-copy またはデフォルトでコピー先を全削除→再コピー
        # ※ コピー元(SRC_*) と コピー先(DST_*) は別マウント。必ず削除→再コピーが正しい動作
        import time as _time

        def _safe_rmtree_and_mkdir(dst_dir, label):
            """CIFS上でrmtree後makedirs失敗する問題をリトライで対処 (rm -rf使用)"""
            if dst_dir.exists():
                log(f"  {label}: コピー先クリア ({dst_dir})")
                # CIFS上ではshutil.rmtreeがos.rmdirで失敗するため subprocess rm -rf を使用
                _res = subprocess.run(["rm", "-rf", str(dst_dir)],
                                      capture_output=True, text=True)
                if _res.returncode != 0:
                    log(f"  [WARN] rm -rf failed: {_res.stderr}", "WARN")
            # CIFS遅延対応: 最大10回リトライ
            for _attempt in range(10):
                try:
                    os.makedirs(str(dst_dir), exist_ok=True)
                    break
                except OSError:
                    _time.sleep(1)
                    if _attempt == 9:
                        # 親ディレクトリから順に作成
                        os.makedirs(str(dst_dir.parent), exist_ok=True)
                        os.makedirs(str(dst_dir), exist_ok=True)

        _clear_targets = [("Programs", DST_PRG)] if prg_only else \
            [("Drawings", DST_DRAW), ("Pictures", DST_PHOTO), ("Programs", DST_PRG)]
        for label, dst_dir in _clear_targets:
            _safe_rmtree_and_mkdir(dst_dir, label)
        log("コピー先ディレクトリクリア完了" + ("（Programsのみ）" if prg_only else ""))

    pgc.execute("SELECT id, machining_id FROM mc_programs")
    machining_map: dict[int, list[int]] = {}
    for mc_id, mach_id in pgc.fetchall():
        machining_map.setdefault(mach_id, []).append(mc_id)
    log(f"machining_id種類: {len(machining_map)}件")

    # ── プログラムファイル取得元: 作成者(作成)/作成日(S_DATE)をACC_マシニングrawから取得 ──
    # PHASE1ではこの2列を mc_machining_details.creator_id / sheet_created_at（段取シート用）に
    # 流用しているため、PHASE7では別途SQL Serverへ直接問い合わせて
    # mc_files.uploaded_by / uploaded_at に正確な値を反映する。
    from datetime import timedelta as _td7
    log("プログラムファイル作成者・作成日（ACC_マシニングraw）取得中...")
    _mc_prg = ss_connect(SS_MC_DB)
    _mc_prg_c = _mc_prg.cursor()
    # ★訂正: PG作成者は [作成](段取シート作成者)ではなく [prg] 列が正しい。
    #   PG更新日時も固定列値ではなく実ファイルのファイルシステム更新日時(mtime)を使う
    #   仕様のため、ここでは prg(作成者名) のみ取得する。日付はコピー時にmtimeから取得する。
    _mc_prg_c.execute("""
        SELECT 加工ID, ﾌｫﾙﾀﾞ1, ﾌｫﾙﾀﾞ2, ﾌｧｲﾙ名, prg
        FROM ACC_マシニングraw
        WHERE ﾌｧｲﾙ名 IS NOT NULL AND ﾌｫﾙﾀﾞ1 IS NOT NULL AND ﾌｧｲﾙ名 != ''
    """)
    _prg_creator_rows = _mc_prg_c.fetchall()
    _mc_prg.close()
    log(f"  取得: {len(_prg_creator_rows)}件")

    # users.name → id 解決マップ（PHASE6と同じ正規化ロジック）
    pgc.execute("SELECT id, name FROM users")
    _u7_rows = pgc.fetchall()
    _u7_exact = {r[1]: r[0] for r in _u7_rows}
    _u7_norm  = {re.sub(r"[\s\u3000]+", " ", r[1]).strip(): r[0] for r in _u7_rows}
    def _resolve_pg_creator(raw_val):
        if not raw_val: return None
        val = str(raw_val).strip()
        if val in _u7_exact: return _u7_exact[val]
        normed = re.sub(r"[\s\u3000]+", " ", val).strip()
        return _u7_norm.get(normed)

    # 加工ID → PG作成者名 のマップ（日付はファイルmtimeから別途取得するためここでは持たない）
    pg_creator_map: dict[int, str] = {}
    for _kakoid7, _f1, _f2, _fname, _creator_raw in _prg_creator_rows:
        pg_creator_map[_kakoid7] = _creator_raw

    # ── (folder1, folder2) → 実ディレクトリパスを直接構築 ──
    # 旧VBA仕様: SSPrg & folder1 & "\" & folder1 & folder2
    # 例: folder1="森", folder2="F" → SRC_PRG/森/森F/
    pgc.execute("""
        SELECT DISTINCT folder1, folder2, file_name FROM mc_machining_details
        WHERE file_name IS NOT NULL AND folder1 IS NOT NULL AND file_name != ''
    """)
    combos = pgc.fetchall()

    log("プログラムファイルディレクトリ直接解決中...")
    folder_map: dict[tuple, object] = {}
    _dirmiss = 0
    for folder1, folder2, file_name in combos:
        key = (folder1, folder2)
        if key in folder_map: continue
        f1 = str(folder1).strip()
        f2 = str(folder2 or "").strip()
        candidate_dir = SRC_PRG / f1 / f"{f1}{f2}"
        if candidate_dir.exists() and candidate_dir.is_dir():
            folder_map[key] = candidate_dir
        else:
            _dirmiss += 1
    log(f"  ディレクトリ解決: {len(folder_map)}件 / 未解決: {_dirmiss}件")

    def insert_file(mc_id, ftype, orig, stored, mime, fpath, fsize, pg_role=None, sort_order=0, src_path=None):
        if dry_run: return
        pgc.execute("""
            INSERT INTO mc_files
              (mc_program_id, file_type, original_name, stored_name, mime_type,
               file_path, source_path, thumbnail_path, file_size, pg_role, sort_order,
               is_deleted, uploaded_by, uploaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,false,%s,NOW())
            ON CONFLICT DO NOTHING
        """, (mc_id, ftype, orig, stored, mime, str(fpath),
              str(src_path) if src_path else None,
              fsize, pg_role, sort_order, ADMIN_ID))

    # ── 7A: 図 (SRC_DRAW → DST_DRAW) ──────────────
    log("\n--- 7A: 図 (Drawings) ---" + ("[prg_onlyのためスキップ]" if prg_only else ""))
    ok = nomatch = err = 0
    if prg_only or not SRC_DRAW.exists():
        log(f"[WARN] SRC_DRAW が存在しない: {SRC_DRAW} - スキップ", "WARN")
    else:
        files = sorted(f for f in SRC_DRAW.rglob("*") if f.is_file())
        log(f"  コピー元: {SRC_DRAW} ({len(files)}件)")
        for i, f in enumerate(files):
            m = re.match(r'^(\d+)-(\d+)\.(tif|TIF|jpg|JPG|png|PNG)$', f.name)
            if not m: continue
            mach_id = int(m.group(1)); seq = int(m.group(2)); ext = f.suffix.lower()
            stored = f"{mach_id}-{seq}{ext}"
            if mach_id not in machining_map: nomatch += 1; continue
            dst = DST_DRAW / stored
            try:
                if not dry_run:
                    _shutil.copy2(f, dst)
                fsize = f.stat().st_size
                mime  = "image/tiff" if ext == ".tif" else "image/jpeg"
                for mc_id in machining_map[mach_id]:
                    insert_file(mc_id, "DRAWING", f.name, stored, mime, dst, fsize, sort_order=seq, src_path=f)
                ok += 1
            except Exception as e:
                err += 1
                if err <= 10: log(f"  ERR {f.name}: {e}", "WARN")
            if (i + 1) % 1000 == 0:
                if not dry_run: pg.commit()
                log(f"    {i+1}/{len(files)} ok={ok} nomatch={nomatch} err={err}")
        if not dry_run: pg.commit()
    log(f"7A完了: ok={ok} nomatch={nomatch} err={err}")

    # ── 7B: 写真 (SRC_PHOTO → DST_PHOTO) ──────────
    log("\n--- 7B: 写真 (Pictures) ---" + ("[prg_onlyのためスキップ]" if prg_only else ""))
    ok = nomatch = err = 0
    if prg_only or not SRC_PHOTO.exists():
        log(f"[WARN] SRC_PHOTO が存在しない: {SRC_PHOTO} - スキップ", "WARN")
    else:
        files = sorted(f for f in SRC_PHOTO.rglob("*") if f.is_file())
        log(f"  コピー元: {SRC_PHOTO} ({len(files)}件)")
        for i, f in enumerate(files):
            m = re.match(r'^(\d+)-(\d+)\.(jpg|jpeg|JPG|png|PNG)$', f.name)
            if not m: continue
            mach_id = int(m.group(1)); seq = int(m.group(2)); ext = f.suffix.lower()
            stored = f"{mach_id}-{seq}{ext}"
            if mach_id not in machining_map: nomatch += 1; continue
            dst = DST_PHOTO / stored
            try:
                if not dry_run:
                    _shutil.copy2(f, dst)
                fsize = f.stat().st_size
                for mc_id in machining_map[mach_id]:
                    insert_file(mc_id, "PHOTO", f.name, stored, "image/jpeg", dst, fsize, sort_order=seq, src_path=f)
                ok += 1
            except Exception as e:
                err += 1
                if err <= 10: log(f"  ERR {f.name}: {e}", "WARN")
            if (i + 1) % 1000 == 0:
                if not dry_run: pg.commit()
                log(f"    {i+1}/{len(files)} ok={ok} nomatch={nomatch} err={err}")
        if not dry_run: pg.commit()
    log(f"7B完了: ok={ok} nomatch={nomatch} err={err}")

    # ── 7C: プログラム (SRC_PRG → DST_PRG) ────────
    # 仕様: <FD名>=folder1+folder2 ディレクトリの中身を、加工IDのフォルダへ
    #       完全にそのまま（ファイル名・拡張子そのまま）コピーする。
    #       ファイルが1件でも複数でも同一ロジック（フォルダ単位コピー）。
    log("\n--- 7C: プログラム (Programs) ---")
    ok = nomatch = notfound = err = 0

    def _insert_program_file(mc_id, orig_name, stored_name, mime, fpath, fsize,
                              pg_role, sort_order, src_path, uploaded_by_id, uploaded_at_val):
        if dry_run: return
        pgc.execute("""
            INSERT INTO mc_files
              (mc_program_id, file_type, original_name, stored_name, mime_type,
               file_path, source_path, thumbnail_path, file_size, pg_role, sort_order,
               is_deleted, uploaded_by, uploaded_at)
            VALUES (%s,'PROGRAM',%s,%s,%s,%s,%s,NULL,%s,%s,%s,false,%s,%s)
            ON CONFLICT DO NOTHING
        """, (mc_id, orig_name, stored_name, mime, str(fpath),
              str(src_path) if src_path else None,
              fsize, pg_role, sort_order,
              uploaded_by_id, uploaded_at_val))

    pgc.execute("""
        SELECT d.machining_id, p.id, d.folder1, d.folder2, d.file_name
        FROM mc_machining_details d
        JOIN mc_programs p ON p.machining_id = d.machining_id
        WHERE d.file_name IS NOT NULL AND d.file_name != '' AND d.folder1 IS NOT NULL
    """)
    programs = pgc.fetchall()
    log(f"  対象: {len(programs)}件")
    for mach_id, mc_id, folder1, folder2, file_name in programs:
        key      = (folder1, folder2)
        src_dir  = folder_map.get(key)
        if not src_dir: nomatch += 1; continue

        src_item = src_dir / str(file_name).strip()
        if not src_item.exists():
            notfound += 1
            continue

        _creator_raw = pg_creator_map.get(mach_id)
        _uploaded_by = _resolve_pg_creator(_creator_raw) or ADMIN_ID

        dst_dir = DST_PRG / str(mach_id)
        dst_dir.mkdir(parents=True, exist_ok=True)

        if src_item.is_file():
            src_files = [src_item]
        elif src_item.is_dir():
            try:
                src_files = sorted(f for f in src_item.iterdir() if f.is_file())
            except Exception as e:
                err += 1
                if err <= 10: log(f"  ERR_LISTDIR {mach_id} dir={src_item}: {e}", "WARN")
                continue
        else:
            notfound += 1
            continue

        if not src_files:
            notfound += 1
            continue

        # ★PG更新日時: 固定列値ではなく実ファイルのファイルシステム更新日時(mtime)を使う。
        #   旧Access仕様: PrgDay.Caption = FileDateTime(Prgpath) と同等の取得方法。
        #   複数ファイルの場合はMAIN(.spf以外)優先、無ければ全体の最新mtimeを使う。
        _main_file = next((f for f in src_files if not f.name.lower().endswith(".spf")), src_files[0])
        try:
            _uploaded_at = datetime.fromtimestamp(_main_file.stat().st_mtime)
        except Exception:
            _uploaded_at = datetime.now()

        copied_any = False
        for sort_idx, src_file in enumerate(src_files):
            dst_file = dst_dir / src_file.name
            try:
                if not dry_run:
                    _shutil.copy2(src_file, dst_file)
                fsize   = src_file.stat().st_size
                pg_role = "SUB" if src_file.name.lower().endswith(".spf") else "MAIN"
                # ファイル個別のmtimeをuploaded_atとして使う（MAINファイルはdst_file側にも反映）
                try:
                    _file_mtime = datetime.fromtimestamp(src_file.stat().st_mtime)
                except Exception:
                    _file_mtime = _uploaded_at
                _insert_program_file(mc_id, src_file.name, src_file.name, "text/plain",
                                     dst_file, fsize, pg_role, sort_idx, src_file,
                                     _uploaded_by, _file_mtime)
                copied_any = True
            except Exception as e:
                err += 1
                if not dry_run:
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                if err <= 10: log(f"  ERR {mach_id}/{src_file.name}: {e}", "WARN")
        if copied_any:
            # ★編集モードの「PG作成者」「PG更新日時」欄が空欄になる問題を解消:
            #   mc_machining_details.pg_created_by / pg_updated_at に同期する。
            #   (mc_files.uploaded_by/uploaded_at とは別カラムで、編集モードが参照するのはこちら)
            if not dry_run:
                try:
                    pgc.execute("""
                        UPDATE mc_machining_details
                        SET pg_created_by = %s, pg_updated_at = %s
                        WHERE machining_id = %s
                    """, (_uploaded_by, _uploaded_at, mach_id))
                except Exception as e:
                    err += 1
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                    if err <= 10: log(f"  ERR_PGMETA {mach_id}: {e}", "WARN")
            if not dry_run: pg.commit()
            ok += 1
        if ok % 500 == 0 and ok > 0:
            if not dry_run: pg.commit()
            log(f"  {ok}件完了... nomatch={nomatch} notfound={notfound} err={err}")
    if not dry_run: pg.commit()
    log(f"7C完了: ok={ok} nomatch={nomatch} notfound={notfound} err={err}")
    pgc.execute("SELECT COUNT(*) FROM mc_machining_details WHERE pg_created_by IS NOT NULL")
    log(f"  mc_machining_details.pg_created_by設定済み: {pgc.fetchone()[0]}件")

    pgc.execute("SELECT file_type, COUNT(*) FROM mc_files GROUP BY file_type ORDER BY file_type")
    log("\n--- mc_files 集計 ---")
    for row in pgc.fetchall(): log(f"  {row[0]}: {row[1]}件")

    # ★追加: コピー直後に自動検証を実行（読み取り専用、DB/FSへの書き込みなし）
    if not dry_run:
        verify_imported_files(pg, prg_only=prg_only)



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
# PHASE 10: mc_programs.status 正規化
# 旧VBAクエリ条件（段取シート印刷/仮登録/仮試作/SP印刷/連続使用）で
# 各MCIDのstatusを正しく設定する
#
# 旧DB判定ロジック（access_MC_spec.html段取ｼｰﾄ戻り1フォームVBA参照）:
#   内容='仮登録' or '仮試作'   → status=NEW
#   内容='段取シート印刷'系     → status=APPROVED
#   上記なし + 承認レコードあり → status=APPROVED
#   上記なし + 承認なし         → status=NEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase10(pg, dry_run=False):
    section("PHASE 10: mc_programs.status 正規化")
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    # 旧VBAクエリ条件と同じKEYWORDS
    PRINT_CONTENTS = {
        "段取シート印刷",
        "段取シート印刷 ",        # 末尾スペース含む（旧DBの実データ）
        "段取シート印刷 連続使用",
        "SP段取シート印刷",
        "SP段取ｼｰﾄ印刷",
        "仮登録",
        "仮試作",
    }
    TENTATIVE_CONTENTS = {"仮登録", "仮試作"}
    APPROVAL_CONTENTS  = {"承認"}

    # 旧DB ACC_変更履歴 から MCID別に内容を集計
    mcc.execute("""
        SELECT MCID, 内容, 入力日
        FROM ACC_変更履歴
        WHERE 内容 IS NOT NULL
        ORDER BY MCID, 入力日 DESC
    """)
    rows = mcc.fetchall()
    log(f"ACC_変更履歴取得: {len(rows)}件")

    # MCID別に最新レコードとPRINT系有無・承認有無を集計
    from collections import defaultdict
    mcid_latest   = {}   # MCID → 最新内容（入力日DESC最初）
    mcid_has_print = set()  # PRINT_CONTENTS に該当するMCIDセット
    mcid_has_approval = set()

    for mcid, content, input_date in rows:
        if mcid is None: continue
        c = str(content).strip() if content else ""
        # 最新（DESC順なので最初に出たもの）
        if mcid not in mcid_latest:
            mcid_latest[mcid] = c
        # PRINT系判定（部分一致も含む）
        for kw in PRINT_CONTENTS:
            if c.startswith(kw) or c == kw:
                mcid_has_print.add(mcid)
                break
        # 承認判定
        for kw in APPROVAL_CONTENTS:
            if c.startswith(kw) or c == kw:
                mcid_has_approval.add(mcid)
                break

    log(f"PRINT系有りMCID: {len(mcid_has_print)}件")
    log(f"承認有りMCID: {len(mcid_has_approval)}件")

    # mc_programs から legacy_mcid 取得
    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mc_rows = pgc.fetchall()
    log(f"mc_programs取得: {len(mc_rows)}件")

    stat_new = stat_approved = stat_pending = 0

    if not dry_run:
        for mc_db_id, legacy_mcid in mc_rows:
            latest_content = mcid_latest.get(legacy_mcid, "")
            has_print = legacy_mcid in mcid_has_print
            has_approval = legacy_mcid in mcid_has_approval

            # status判定ロジック
            if has_print:
                # PRINT系あり
                is_tentative = any(
                    latest_content.startswith(kw) or latest_content == kw
                    for kw in TENTATIVE_CONTENTS
                )
                if is_tentative:
                    # 最新が仮登録/仮試作 → NEW
                    new_status = "NEW"
                    stat_new += 1
                else:
                    # 最新が印刷系 → APPROVED
                    new_status = "APPROVED"
                    stat_approved += 1
            else:
                # PRINT系なし
                if has_approval:
                    new_status = "APPROVED"
                    stat_approved += 1
                else:
                    # 変更履歴のみ（承認なし・印刷なし） → PENDING_APPROVAL
                    new_status = "PENDING_APPROVAL"
                    stat_pending += 1

            pgc.execute(
                "UPDATE mc_programs SET status = %s::mc_program_status WHERE id = %s",
                (new_status, mc_db_id)
            )

        pg.commit()

    log(f"status設定完了:")
    log(f"  APPROVED        : {stat_approved}件")
    log(f"  NEW             : {stat_new}件")
    log(f"  PENDING_APPROVAL: {stat_pending}件")

    # 確認サマリ
    pgc.execute("SELECT status, COUNT(*) FROM mc_programs GROUP BY status ORDER BY status")
    for row in pgc.fetchall():
        log(f"  DB確認 status={row[0]}: {row[1]}件")

    # ─────────────────────────────────────────────
    # PART2: mc_setup_sheet_logs.work_collected 正規化
    # 旧VBAクエリ（DISTINCTROW MCID+加工ID+入力日）をキーに完全一致更新
    # ─────────────────────────────────────────────
    log("\nPART2: mc_setup_sheet_logs.work_collected 正規化（旧VBAクエリキー完全一致）...")

    # Step1: 全件 work_collected = true にリセット
    if not dry_run:
        pgc.execute("UPDATE mc_setup_sheet_logs SET work_collected = true")
        pg.commit()
        log("  全件 work_collected=true にリセット完了")

    # Step2: 旧VBAクエリをそのまま実行
    # SELECT DISTINCTROW MC.MCID, 変更履歴.加工ID, 変更履歴.入力日
    # FROM MC INNER JOIN 変更履歴 ON MC.MCID = 変更履歴.MCID
    # WHERE 内容='段取シート印刷' OR '仮登録' OR '段取シート印刷 連続使用'
    #       OR 'SP段取シート印刷' OR '仮試作'
    # ※ RTRIMで末尾スペース除去、DISTINCT で重複排除
    mcc.execute("""
        SELECT DISTINCT
            MC.MCID,
            H.加工ID,
            H.入力日
        FROM ACC_MC MC
        INNER JOIN ACC_変更履歴 H ON MC.MCID = H.MCID
        WHERE RTRIM(H.内容) = '段取シート印刷'
           OR RTRIM(H.内容) = '段取シート印刷 連続使用'
           OR RTRIM(H.内容) = 'SP段取シート印刷'
           OR RTRIM(H.内容) = 'SP段取ｼｰﾄ印刷'
           OR RTRIM(H.内容) = '仮登録'
           OR RTRIM(H.内容) = '仮試作'
    """)
    vba_rows = mcc.fetchall()
    log(f"  旧VBAクエリ結果: {len(vba_rows)}件 (MCID+加工ID+印刷日時)")

    # Step3: MCID→legacy_mcid→mc_program_id のマップ構築
    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    legacy_to_dbid = {}
    for db_id, lmcid in pgc.fetchall():
        legacy_to_dbid[lmcid] = db_id  # MCID=legacy_mcid は1:1

    # Step4: mc_setup_sheet_logs を (mc_program_id, printed_at日付文字列) でインデックス化
    pgc.execute("""
        SELECT id, mc_program_id, printed_at
        FROM mc_setup_sheet_logs
    """)
    # キー: (mc_program_id, 日付10文字) → log_id リスト（同日に複数あり得る）
    from collections import defaultdict
    slogs_by_key = defaultdict(list)
    for log_id, mc_pid, printed_at in pgc.fetchall():
        date_str = str(printed_at)[:10] if printed_at else ''
        slogs_by_key[(mc_pid, date_str)].append((log_id, printed_at))

    # Step5: 旧VBAクエリ結果をキーにして未回収IDを特定
    # 旧DBの入力日はJST→PGのUTC変換で-9時間されているので照合時も変換
    from datetime import timedelta as _td2
    uncollected_ids = []
    not_found_list = []  # デバッグ用
    not_found = 0
    for mcid, kakoid, input_date in vba_rows:
        mc_db_id = legacy_to_dbid.get(mcid)
        if not mc_db_id:
            not_found += 1
            not_found_list.append((mcid, kakoid, input_date, 'NO_MC_DB_ID'))
            continue
        # JST→UTC変換（PHASE6でも同様に変換しているため）
        input_date_utc = (input_date - _td2(hours=9)) if input_date else None
        date_str = str(input_date_utc)[:10] if input_date_utc else ''
        candidates = slogs_by_key.get((mc_db_id, date_str), [])
        if candidates:
            # 同日に複数あれば印刷時刻が最も近いもの（UTC変換後の入力日時と一致）を選ぶ
            if input_date_utc and len(candidates) > 1:
                best = min(candidates, key=lambda x: abs(
                    (x[1] - input_date_utc).total_seconds() if x[1] and input_date_utc else 999999
                ))
                uncollected_ids.append(best[0])
            else:
                uncollected_ids.append(candidates[0][0])
        else:
            not_found += 1
            not_found_list.append((mcid, kakoid, input_date, date_str))

    log(f"  未回収ID特定: {len(uncollected_ids)}件 (未マッチ: {not_found}件)")
    for _nf in not_found_list:
        log(f"  未マッチ詳細: MCID={_nf[0]} 加工ID={_nf[1]} 入力日={_nf[2]} date_str={_nf[3]}", "WARN")

    if not dry_run and uncollected_ids:
        pgc.execute(
            "UPDATE mc_setup_sheet_logs SET work_collected = false WHERE id = ANY(%s)",
            (uncollected_ids,)
        )
        pg.commit()
        log(f"  work_collected=false 設定: {pgc.rowcount}件")

    # Step6: 仮登録/仮試作MCIDのsheet_typeをNEWに設定
    mcc.execute("""
        SELECT DISTINCT MC.MCID
        FROM ACC_MC MC
        INNER JOIN ACC_変更履歴 H ON MC.MCID = H.MCID
        WHERE RTRIM(H.内容) = '仮登録' OR RTRIM(H.内容) = '仮試作'
    """)
    tentative_mcids = list({row[0] for row in mcc.fetchall()})
    log(f"  仮登録/仮試作MCID: {len(tentative_mcids)}件")

    if not dry_run:
        pgc.execute("""
            UPDATE mc_setup_sheet_logs sl
            SET sheet_type = CASE
                WHEN p.legacy_mcid = ANY(%s) THEN 'NEW'
                ELSE 'MC'
            END
            FROM mc_programs p
            WHERE sl.mc_program_id = p.id
              AND sl.work_collected = false
        """, (tentative_mcids,))
        pg.commit()
        log(f"  sheet_type更新: {pgc.rowcount}件")

        # mc_programs.status: 仮登録MCIDをNEWに設定
        pgc.execute("""
            UPDATE mc_programs SET status = 'NEW'::mc_program_status
            WHERE legacy_mcid = ANY(%s) AND status != 'NEW'::mc_program_status
        """, (tentative_mcids,))
        pg.commit()
        log(f"  仮登録status=NEW設定: {pgc.rowcount}件")

        pgc.execute("SELECT COUNT(*) FROM mc_setup_sheet_logs WHERE work_collected = false")
        log(f"  ダッシュボード表示件数（未回収）: {pgc.fetchone()[0]}件")
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE status='NEW'::mc_program_status")
        log(f"  mc_programs status=NEW総数: {pgc.fetchone()[0]}件")

    mc.close()
    log("PHASE10完了")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    parser = argparse.ArgumentParser(description="MachCore MC完全移行スクリプト")
    parser.add_argument("--phase", type=int, default=0,
                        help="実行フェーズ (0=全, 1-9=個別)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DBへの書き込みなし")
    parser.add_argument("--force-copy", action="store_true",
                        help="PHASE7: コピー先ファイルを全削除してから再コピー")
    parser.add_argument("--skip-file-copy", action="store_true",
                        help="PHASE7をスキップ（ファイルコピーなし、データのみ移行）")
    parser.add_argument("--prg-only", action="store_true",
                        help="PHASE7: プログラムファイル(7C)のみ実行。図(7A)・写真(7B)はスキップ")
    args = parser.parse_args()

    dry = args.dry_run
    if dry: log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    pg = pg_connect()
    try:
        force_copy = args.force_copy
        skip_file  = args.skip_file_copy
        prg_only   = args.prg_only
        phases = {1:phase1, 2:phase2, 3:phase3, 4:phase4,
                  5:phase5, 6:phase6, 7:phase7, 8:phase8, 9:phase9, 10:phase10}
        if args.phase == 0:
            run = [p for p in range(1, 11) if not (skip_file and p == 7)]
        else:
            run = [args.phase]
        for p in run:
            try:
                if p == 7:
                    phases[p](pg, dry_run=dry, force_copy=force_copy, prg_only=prg_only)
                else:
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
