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
    mc  = ss_connect(SS_MC_DB)
    mcc = mc.cursor()
    pgc = pg.cursor()

    if not dry_run:
        pgc.execute("DELETE FROM mc_change_history")
        pgc.execute("DELETE FROM mc_setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE mc_program_id IS NOT NULL")
        pg.commit()
        log("mc_change_history / mc_setup_sheet_logs / work_records(MC分) 削除完了")

    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_map: dict[int, list[int]] = {}
    for mc_id, lmid in pgc.fetchall():
        mcid_map.setdefault(lmid, []).append(mc_id)

    pgc.execute("SELECT id, name FROM users")
    users_map = {r[1]: r[0] for r in pgc.fetchall()}

    pgc.execute("SELECT id, machine_code FROM machines WHERE system_type='MC'")
    machines_map = {r[1]: r[0] for r in pgc.fetchall()}

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

    PRINT_KEYWORDS = ["段取シート印刷", "SP段取シート印刷", "段取シート　印刷", "仮登録", "印刷"]
    CHANGE_KEYWORDS = [
        ("NEW_REGISTRATION", ["新規登録", "新規"]),
        ("APPROVAL",         ["承認"]),
        ("CHANGE",           ["大変更", "小変更", "変更", "修正", "編集", "削除", "復元", "更新"]),
    ]

    def classify(content_str):
        if not content_str:
            return False, True, "CHANGE"
        s = str(content_str).strip()
        is_print  = any(s.startswith(kw) or kw in s for kw in PRINT_KEYWORDS)
        is_change = False; change_type = "CHANGE"
        for ct, kws in CHANGE_KEYWORDS:
            if any(s.startswith(kw) for kw in kws):
                is_change = True; change_type = ct; break
        if not is_print and not is_change:
            is_change = True
        return is_print, is_change, change_type

    def toint(v):
        try: return int(v or 0)
        except: return 0

    sl_ok = wr_ok = ch_ok = skip = err = 0
    batch = 0
    for row in rows:
        try:
            row_dict  = dict(zip(cols, row))
            mcid      = row_dict.get("MCID")
            mc_db_ids = mcid_map.get(mcid, [])
            if not mc_db_ids: skip += 1; continue

            op_name   = str(row_dict.get("作成") or row_dict.get("ｵﾍﾟﾚｰﾀｰ") or "").strip()
            op_id     = users_map.get(op_name, ADMIN_ID)
            content   = str(row_dict.get("内容") or "").strip()
            ver_after = str(row_dict.get("Ver") or "").strip() or None
            ver_before= row_dict.get("旧Ver") or row_dict.get("OldVer") or None
            created_at= row_dict.get("作成日") or row_dict.get("入力日")
            hist_id   = row_dict.get("加工ID")

            is_print, is_change, change_type = classify(content)

            th = toint(row_dict.get("TH")); tm = toint(row_dict.get("TM")); ts = toint(row_dict.get("TS"))
            work_cnt  = toint(row_dict.get("ﾜｰｸ数"))
            setup_cnt = toint(row_dict.get("段取_ﾜｰｸ数") or row_dict.get("段取ﾜｰｸ数") or 0)
            ichi_s    = toint(row_dict.get("1S_個数") or row_dict.get("1S個数") or 0)
            dan_start = row_dict.get("段取開始"); work_end = row_dict.get("加工終了")
            total_min = th * 60 + tm + (1 if ts >= 30 else 0)
            has_work  = (total_min > 0 or work_cnt > 0 or dan_start is not None)

            machine_name_val = str(row_dict.get("機械") or "").strip()
            machine_db_id = machines_map.get(machine_name_val) if machine_name_val else None

            prg_man_val  = str(row_dict.get("Prg") or "").strip() or None
            prg_time_min = toint(row_dict.get("PrgTimeH")) * 60 + toint(row_dict.get("PrgTimeM"))

            # 旧DB時間フォーマット: "3H 30M" or "0H 9M 6S" → 分/秒に変換
            def parse_hms_to_min(s):
                if not s: return None
                s = str(s).strip()
                h = m = 0
                mh = re.search(r'(\d+)H', s)
                mm = re.search(r'H\s*(\d+)M', s)
                if mh: h = int(mh.group(1))
                if mm: m = int(mm.group(1))
                return h * 60 + m if (h > 0 or m > 0) else None
            def parse_hms_to_sec(s):
                if not s: return None
                s = str(s).strip()
                h = m = sc = 0
                mh = re.search(r'(\d+)H', s)
                mm = re.search(r'H\s*(\d+)M', s)
                ms = re.search(r'M\s*(\d+)S', s)
                if mh: h = int(mh.group(1))
                if mm: m = int(mm.group(1))
                if ms: sc = int(ms.group(1))
                return h * 3600 + m * 60 + sc if (h > 0 or m > 0 or sc > 0) else None

            setup_time_min = parse_hms_to_min(row_dict.get("段取時間"))
            mach_time_min  = parse_hms_to_min(row_dict.get("加工時間"))
            total_hms_min  = parse_hms_to_min(row_dict.get("総時間"))
            if mach_time_min is None and total_min > 0:
                mach_time_min = total_min

            cycle_sec = parse_hms_to_sec(row_dict.get("ｻｲｸﾙﾀｲﾑ/1P") or row_dict.get("サイクルタイム/1P"))
            # TH/TM/TSからサイクル秒を計算（旧DBのサイクルタイムは加工時間H/M/S）
            if cycle_sec is None and (th > 0 or tm > 0 or ts > 0):
                cycle_sec = th * 3600 + tm * 60 + ts

            sheet_type_val = "SP" if is_print and ("SP" in content or "特殊" in content) else ("MC" if is_print else None)

            if not dry_run:
                for mc_db_id in mc_db_ids:
                    if is_print:
                        pgc.execute("""
                            INSERT INTO mc_setup_sheet_logs
                              (mc_program_id, operator_id, printed_at, version,
                               work_collected, sheet_type, quantity, machine_id_log)
                            VALUES (%s,%s,%s,%s,false,%s,%s,%s)
                        """, (mc_db_id, op_id, created_at or datetime.now(),
                              ver_after, sheet_type_val,
                              ichi_s if ichi_s > 0 else None, machine_db_id))
                        sl_ok += 1
                    if has_work:
                        wd = created_at
                        if wd and hasattr(wd, 'date'): wd = wd.date()
                        # 段取担当者・量産担当者 名前→ID解決
                        tanto_name   = str(row_dict.get('段取')    or '').strip()
                        sagyosha_name= str(row_dict.get('作業者')   or '').strip()
                        check_man    = str(row_dict.get('ﾁｪｯｸMan') or '').strip()
                        setup_op_id  = users_map.get(tanto_name)
                        prod_op_id   = users_map.get(sagyosha_name)
                        setup_op_ids = [setup_op_id] if setup_op_id else []
                        prod_op_ids  = [prod_op_id]  if prod_op_id  else []
                        import json as _json
                        # ﾁｪｯｸTime → checked_at
                        chk_time = row_dict.get('ﾁｪｯｸTime')
                        pgc.execute("""
                            INSERT INTO work_records
                              (mc_program_id, operator_id, machine_id,
                               work_date, setup_time_min, machining_time_min,
                               cycle_time_sec, quantity, started_at, checked_at, finished_at,
                               setup_work_count, prg_man, prg_time_min, prg_plas,
                               setup_operator_ids, production_operator_ids,
                               work_type, created_at)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'MC',NOW())
                        """, (mc_db_id, op_id, machine_db_id,
                              wd or datetime.now().date(),
                              setup_time_min, mach_time_min, cycle_sec,
                              work_cnt if work_cnt > 0 else None,
                              dan_start, chk_time, work_end,
                              setup_cnt if setup_cnt > 0 else None,
                              prg_man_val,
                              prg_time_min if prg_time_min > 0 else None,
                              str(row_dict.get('PrgPlas') or '') or None,
                              _json.dumps(setup_op_ids),
                              _json.dumps(prod_op_ids)))
                        wr_ok += 1
                    if is_change:
                        # 承認レコードは承認列から承認者IDを解決
                        import re as _ch_re
                        def _ch_resolve(raw):
                            if not raw: return None
                            v = str(raw).strip()
                            if v in users_map: return users_map[v]
                            n = _ch_re.sub(r'[\s\u3000]+', ' ', v).strip()
                            return next((uid for nm, uid in users_map.items()
                                         if _ch_re.sub(r'[\s\u3000]+', ' ', nm).strip() == n), None)
                        if change_type == 'APPROVAL':
                            _approver_op = _ch_resolve(row_dict.get('承認')) or op_id
                        else:
                            _approver_op = op_id
                        pgc.execute("""
                            INSERT INTO mc_change_history
                              (mc_program_id, change_type, operator_id,
                               version_before, version_after, content,
                               changed_at, legacy_hist_id)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (mc_db_id, change_type, _approver_op, ver_before, ver_after,
                              content or None, created_at or datetime.now(), hist_id))
                        ch_ok += 1
            else:
                if is_print: sl_ok += 1
                if has_work: wr_ok += 1
                if is_change: ch_ok += 1

            batch += 1
            if batch % 5000 == 0:
                if not dry_run: pg.commit()
                log(f"  {batch}件処理... sl={sl_ok} wr={wr_ok} ch={ch_ok} skip={skip} err={err}")

        except Exception as e:
            err += 1
            if not dry_run:
                try: pg.rollback()
                except: pass
            if err <= 10: log(f"  ERR MCID={row_dict.get('MCID')}: {e}", "WARN")

    if not dry_run:
        pg.commit()
        # PHASE6B: registered_by/approved_by を変更履歴の新規登録・承認レコードで更新
        log("PHASE6B: registered_by/approved_by 更新...")
        # 新規登録の作成者→registered_by
        pgc.execute("""
            UPDATE mc_programs p SET registered_by = ch.operator_id
            FROM (
                SELECT DISTINCT ON (mc_program_id) mc_program_id, operator_id
                FROM mc_change_history
                WHERE change_type = 'NEW_REGISTRATION'
                ORDER BY mc_program_id, changed_at ASC
            ) ch
            WHERE p.id = ch.mc_program_id AND ch.operator_id IS NOT NULL
        """)
        # 承認の作成者→approved_by/approved_at
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
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE registered_by != 22")
        log(f"  管理者以外のregistered_by: {pgc.fetchone()[0]}件")
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE approved_by IS NOT NULL AND approved_by != 22")
        log(f"  管理者以外のapproved_by: {pgc.fetchone()[0]}件")

        # PHASE6C: registered_by を ｵﾍﾟﾚｰﾀｰ列（最古）から正しく更新
        log("PHASE6C: registered_by をｵﾍﾟﾚｰﾀｰ列から更新...")
        mc6c = ss_connect(SS_MC_DB)
        mc6c_c = mc6c.cursor()
        def _resolve_one(raw_val, u_exact, u_norm):
            if not raw_val: return None
            import re as _re
            val = str(raw_val).strip()
            if val in u_exact: return u_exact[val]
            normed = _re.sub(r'[\s\u3000]+', ' ', val).strip()
            if normed in u_norm: return u_norm[normed]
            return None
        pgc.execute("SELECT id, name FROM users WHERE employee_code LIKE 'MC%' OR employee_code = 'ADMIN001'")
        _pg_users = pgc.fetchall()
        _u_exact = {u[1]: u[0] for u in _pg_users}
        _u_norm  = {__import__('re').sub(r'[\s\u3000]+', ' ', u[1]).strip(): u[0] for u in _pg_users}
        mc6c_c.execute("""
            SELECT MCID, ｵﾍﾟﾚｰﾀｰ, 入力日 FROM ACC_変更履歴
            WHERE ｵﾍﾟﾚｰﾀｰ IS NOT NULL AND LEN(RTRIM(ｵﾍﾟﾚｰﾀｰ)) > 0
            ORDER BY MCID, 入力日 DESC
        """)
        _op_map = {}
        for _mcid, _op_name, _ in mc6c_c.fetchall():
            if _mcid not in _op_map:
                _uid = _resolve_one(_op_name, _u_exact, _u_norm)
                if _uid and _uid != ADMIN_ID: _op_map[_mcid] = _uid
        _reg_ok = 0
        for _mcid, _uid in _op_map.items():
            for _mc_db_id in mcid_map.get(_mcid, []):
                # ADMIN_IDのもののみ上書き（PHASE1で既設定のものは保持）
                pgc.execute("UPDATE mc_programs SET registered_by=%s WHERE id=%s AND registered_by=%s",
                            (_uid, _mc_db_id, ADMIN_ID))
                if pgc.rowcount > 0: _reg_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE registered_by != %s", (ADMIN_ID,))
        log(f"  PHASE6C: registered_by更新={_reg_ok}件 管理者以外={pgc.fetchone()[0]}件")

        # PHASE6D: approved_by/approved_at を ACC_変更履歴の承認カラムから更新
        log("PHASE6D: approved_by を承認カラムから更新...")
        mc6c_c.execute("""
            SELECT MCID, 承認, 承認日 FROM ACC_変更履歴
            WHERE 承認 IS NOT NULL AND LEN(RTRIM(承認)) > 0 AND 承認日 IS NOT NULL
            ORDER BY MCID, 承認日 DESC
        """)
        _seen = set(); _app_ok = 0
        for _mcid, _aname, _adate in mc6c_c.fetchall():
            if _mcid in _seen: continue
            _seen.add(_mcid)
            _uid = _resolve_one(_aname, _u_exact, _u_norm)
            if not _uid: continue
            for _mc_db_id in mcid_map.get(_mcid, []):
                pgc.execute("UPDATE mc_programs SET approved_by=%s, approved_at=%s WHERE id=%s",
                            (_uid, _adate, _mc_db_id))
                _app_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_programs WHERE approved_by IS NOT NULL AND approved_by != %s", (ADMIN_ID,))
        log(f"  PHASE6D: approved_by更新={_app_ok}件 管理者以外={pgc.fetchone()[0]}件")

        # PHASE6E: work_records setup_operator_ids/production_operator_ids を名寄せで更新
        log("PHASE6E: work_records 段取/量産担当者 名寄せ更新...")
        import json as _json, re as _re2
        def _resolve_names(raw_val, u_exact, u_norm):
            if not raw_val: return []
            val = str(raw_val).strip()
            parts = _re2.split(r'[&＆,、]', val)
            ids = []
            for part in parts:
                part = part.strip()
                if not part: continue
                if part in u_exact: ids.append(u_exact[part]); continue
                normed = _re2.sub(r'[\s\u3000]+', ' ', part).strip()
                if normed in u_norm: ids.append(u_norm[normed]); continue
                remaining = normed
                while remaining:
                    matched_id = None; matched_len = 0
                    for nm, uid in u_norm.items():
                        if remaining.startswith(nm) and len(nm) > matched_len:
                            matched_id = uid; matched_len = len(nm)
                    if matched_id: ids.append(matched_id); remaining = remaining[matched_len:].strip()
                    else: break
            return list(dict.fromkeys(ids))
        mc6c_c.execute("""
            SELECT MCID, 入力日, 段取, 作業者 FROM ACC_変更履歴
            WHERE (TH > 0 OR TM > 0 OR TS > 0 OR ﾜｰｸ数 > 0 OR 段取開始 IS NOT NULL)
            ORDER BY MCID, 入力日
        """)
        pgc.execute("SELECT id, mc_program_id, work_date FROM work_records WHERE mc_program_id IS NOT NULL")
        _wr_map = {}
        for _wrid, _mc_pid, _wd in pgc.fetchall():
            _wr_map[(_mc_pid, str(_wd))] = _wrid
        _wr_ok = 0
        for _mcid, _input_date, _dandori, _sagyosha in mc6c_c.fetchall():
            _setup_ids = _resolve_names(_dandori, _u_exact, _u_norm)
            _prod_ids  = _resolve_names(_sagyosha, _u_exact, _u_norm)
            _wd_str = str(_input_date)[:10] if _input_date else ''
            for _mc_db_id in mcid_map.get(_mcid, []):
                _wrid = _wr_map.get((_mc_db_id, _wd_str))
                if not _wrid: continue
                pgc.execute("UPDATE work_records SET setup_operator_ids=%s, production_operator_ids=%s WHERE id=%s",
                            (_json.dumps(_setup_ids), _json.dumps(_prod_ids), _wrid))
                _wr_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND setup_operator_ids != '[]'::jsonb")
        log(f"  PHASE6E: work_records担当者更新={_wr_ok}件 setup設定済み={pgc.fetchone()[0]}件")

        # PHASE6F: sheet_created_at/creator_id を変更履歴の作成日/作成から更新
        log("PHASE6F: sheet_created_at/creator_id 更新...")
        mc6c_c.execute("""
            SELECT MCID, 加工ID, 作成, 作成日 FROM ACC_変更履歴
            WHERE 作成日 IS NOT NULL AND 作成 IS NOT NULL AND LEN(RTRIM(作成)) > 0
            ORDER BY MCID, 入力日 ASC
        """)
        _mach_sheet_map = {}
        for _mcid, _kakoid, _sakusha, _sakusha_date in mc6c_c.fetchall():
            if _kakoid and _kakoid not in _mach_sheet_map:
                _creator_id = _resolve_one(_sakusha, _u_exact, _u_norm)
                if _creator_id and _sakusha_date:
                    _mach_sheet_map[_kakoid] = (_sakusha_date, _creator_id)
        _sheet_ok = 0
        for _kakoid, (_sheet_date, _creator_id) in _mach_sheet_map.items():
            # NULLのもののみ上書き（PHASE1でACC_マシニングrawから設定済みのものは保持）
            pgc.execute("""
                UPDATE mc_machining_details
                SET sheet_created_at=COALESCE(sheet_created_at, %s),
                    creator_id=COALESCE(creator_id, %s)
                WHERE machining_id=%s
            """, (_sheet_date, _creator_id, _kakoid))
            if pgc.rowcount > 0: _sheet_ok += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_machining_details WHERE sheet_created_at IS NOT NULL")
        log(f"  PHASE6F: sheet_created_at設定済み={pgc.fetchone()[0]}件 ok={_sheet_ok}件")

        # PHASE6G: mc_setup_sheet_logs operator_id/machine_id_log 更新
        log("PHASE6G: setup_sheet_logs operator_id/machine_id_log 更新...")
        _machines_map_local = machines_map
        pgc.execute("SELECT id, mc_program_id, printed_at FROM mc_setup_sheet_logs")
        _sl_map = {}
        for _slid, _mc_pid, _pat in pgc.fetchall():
            _sl_map[(_mc_pid, str(_pat)[:10] if _pat else '')] = _slid
        mc6c_c.execute("""
            SELECT MCID, ｵﾍﾟﾚｰﾀｰ, 入力日, 機械 FROM ACC_変更履歴
            WHERE 内容 LIKE '%段取シート%' OR 内容 LIKE '%仮登録%' OR 内容 LIKE '%印刷%'
            ORDER BY MCID, 入力日
        """)
        _sl_ok2 = 0
        for _mcid, _op_name, _input_date, _machine_name in mc6c_c.fetchall():
            _op_id2 = _resolve_one(_op_name, _u_exact, _u_norm)
            _mach_id2 = _machines_map_local.get(str(_machine_name).strip()) if _machine_name else None
            if not _op_id2 and not _mach_id2: continue
            _wd_str2 = str(_input_date)[:10] if _input_date else ''
            for _mc_db_id in mcid_map.get(_mcid, []):
                _slid = _sl_map.get((_mc_db_id, _wd_str2))
                if not _slid: continue
                _upd = []; _prm = []
                if _op_id2: _upd.append("operator_id=%s"); _prm.append(_op_id2)
                if _mach_id2: _upd.append("machine_id_log=%s"); _prm.append(_mach_id2)
                if _upd:
                    _prm.append(_slid)
                    pgc.execute(f"UPDATE mc_setup_sheet_logs SET {chr(44).join(_upd)} WHERE id=%s", _prm)
                    _sl_ok2 += 1
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM mc_setup_sheet_logs WHERE machine_id_log IS NOT NULL")
        log(f"  PHASE6G: setup_sheet_logs更新={_sl_ok2}件 machine設定済み={pgc.fetchone()[0]}件")
        mc6c.close()

    pgc.execute("SELECT COUNT(*) FROM mc_setup_sheet_logs WHERE mc_program_id IS NOT NULL")
    log(f"  mc_setup_sheet_logs(MC): {pgc.fetchone()[0]}")
    pgc.execute("SELECT COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL")
    log(f"  work_records(MC):        {pgc.fetchone()[0]}")
    pgc.execute("SELECT COUNT(*) FROM mc_change_history")
    log(f"  mc_change_history:       {pgc.fetchone()[0]}")
    log(f"PHASE6完了: 入力={len(rows)} skip={skip} err={err}")
    log(f"  [印刷履歴={sl_ok} / 作業実績={wr_ok} / 変更履歴={ch_ok}]")
    mc.close()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 7: 図・写真・プログラム ファイル移行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase7(pg, dry_run=False, force_copy=False):
    section("PHASE 7: 図・写真・プログラム ファイル移行")
    import shutil as _shutil

    # コピー先ディレクトリを必ず作成
    ensure_dirs(DST_DRAW, DST_PHOTO, DST_PRG)

    pgc = pg.cursor()

    if not dry_run:
        # mc_filesレコードは必ず全削除して再登録
        pgc.execute("DELETE FROM mc_files")
        pg.commit()
        log("mc_files既存データ削除完了")

        # --force-copy またはデフォルトでコピー先を全削除→再コピー
        # ※ コピー元(SRC_*) と コピー先(DST_*) は別マウント。必ず削除→再コピーが正しい動作
        for label, dst_dir in [("Drawings", DST_DRAW), ("Pictures", DST_PHOTO)]:
            if dst_dir.exists():
                log(f"  {label}: コピー先クリア ({dst_dir})")
                _shutil.rmtree(dst_dir)
            os.makedirs(str(dst_dir), exist_ok=True)
        # Programs は machining_id サブディレクトリ構造のため個別削除
        if DST_PRG.exists():
            log(f"  Programs: コピー先クリア ({DST_PRG})")
            _shutil.rmtree(DST_PRG)
        # rmtree後に os.makedirs で強制再作成（Pathのmkdirは親が消えると失敗する）
        for _d in [str(DST_ROOT), str(DST_DRAW), str(DST_PHOTO), str(DST_PRG)]:
            os.makedirs(_d, exist_ok=True)
        log("コピー先ディレクトリクリア完了")

    pgc.execute("SELECT id, machining_id FROM mc_programs")
    machining_map: dict[int, list[int]] = {}
    for mc_id, mach_id in pgc.fetchall():
        machining_map.setdefault(mach_id, []).append(mc_id)
    log(f"machining_id種類: {len(machining_map)}件")

    # folder_map構築（プログラム用）
    pgc.execute("""
        SELECT DISTINCT folder1, folder2, file_name FROM mc_machining_details
        WHERE file_name IS NOT NULL AND folder1 IS NOT NULL AND file_name != ''
    """)
    combos = pgc.fetchall()

    log("プログラムファイルインデックス構築中...")
    file_index: dict[str, list] = {}
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
    else:
        log(f"[WARN] SRC_PRG が存在しない: {SRC_PRG}", "WARN")
    log(f"インデックス: {len(file_index)}種類")

    folder_map: dict[tuple, object] = {}
    for folder1, folder2, file_name in combos:
        key = (folder1, folder2)
        if key in folder_map: continue
        paths = file_index.get(file_name, [])
        if paths:
            folder_map[key] = paths[0].parent

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
    log("\n--- 7A: 図 (Drawings) ---")
    ok = nomatch = err = 0
    if not SRC_DRAW.exists():
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
    log("\n--- 7B: 写真 (Pictures) ---")
    ok = nomatch = err = 0
    if not SRC_PHOTO.exists():
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
    log("\n--- 7C: プログラム (Programs) ---")
    ok = nomatch = notfound = err = 0
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
        src_file = src_dir / file_name
        if not src_file.exists() or not src_file.is_file(): notfound += 1; continue
        dst_dir  = DST_PRG / str(mach_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_file = dst_dir / file_name
        try:
            if not dry_run:
                _shutil.copy2(src_file, dst_file)
            fsize   = src_file.stat().st_size
            pg_role = "SUB" if str(file_name).lower().endswith(".spf") else "MAIN"
            insert_file(mc_id, "PROGRAM", file_name, file_name, "text/plain",
                        dst_file, fsize, pg_role=pg_role, sort_order=0, src_path=src_file)
            ok += 1
        except Exception as e:
            err += 1
            if err <= 10: log(f"  ERR {mach_id}/{file_name}: {e}", "WARN")
        if ok % 500 == 0 and ok > 0:
            if not dry_run: pg.commit()
            log(f"  {ok}件完了... nomatch={nomatch} notfound={notfound} err={err}")
    if not dry_run: pg.commit()
    log(f"7C完了: ok={ok} nomatch={nomatch} notfound={notfound} err={err}")

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
    parser.add_argument("--force-copy", action="store_true",
                        help="PHASE7: コピー先ファイルを全削除してから再コピー")
    parser.add_argument("--skip-file-copy", action="store_true",
                        help="PHASE7をスキップ（ファイルコピーなし、データのみ移行）")
    args = parser.parse_args()

    dry = args.dry_run
    if dry: log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    pg = pg_connect()
    try:
        force_copy = args.force_copy
        skip_file  = args.skip_file_copy
        phases = {1:phase1, 2:phase2, 3:phase3, 4:phase4,
                  5:phase5, 6:phase6, 7:phase7, 8:phase8, 9:phase9}
        if args.phase == 0:
            run = [p for p in range(1, 10) if not (skip_file and p == 7)]
        else:
            run = [args.phase]
        for p in run:
            try:
                if p == 7:
                    phases[p](pg, dry_run=dry, force_copy=force_copy)
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
