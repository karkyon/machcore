#!/usr/bin/env python3
# =============================================================================
# MachCore 本番移行スクリプト — NC + MC 全データ一括コンバート＆インポート
# =============================================================================
# 対象: SQL Server (192.168.1.9/imotomc) → PostgreSQL (machcore_dev)
#
# 実行方法:
#   python3 scripts/mc_full_import.py [--dry-run] [--skip-nc] [--skip-mc]
#
# オプション:
#   --dry-run  : DBへの書き込みを行わず検証のみ実施
#   --skip-nc  : NC旋盤データのインポートをスキップ
#   --skip-mc  : MCマシニングデータのインポートをスキップ
#   --truncate : 既存データを全削除してから再インポート（本番移行時）
#   --phase N  : 指定フェーズのみ実行 (1-6)
#
# 前提条件:
#   pip3 install pymssql psycopg2-binary --break-system-packages
#   PostgreSQL側にmc_migration.sqlが適用済みであること
#   machines テーブルにMC機械が登録済みであること
#   mc_tooling.tool_no が nullable であること:
#     ALTER TABLE mc_tooling ALTER COLUMN tool_no DROP NOT NULL;
#
# フェーズ構成:
#   Phase 0: スキーマ整合確認 (必須カラム + nullable確認)
#   Phase 1: mc_programs    — ACC_MC × ACC_マシニング (約15,681件想定)
#   Phase 2: mc_tooling     — ACC_ツーリング (約127,235件想定)
#   Phase 3: RC同期         — ツーリング件数 → mc_programs.rc
#   Phase 4: mc_work_offsets — ACC_ワークオフセット
#   Phase 5: mc_index_programs — ACC_インデックスプログラム
#   Phase 6: mc_change_history — ACC_変更履歴
#
# 重要な実装メモ (開発時の調査結果):
#   - ACC_マシニング実カラム名: Version(英字), 機械ID(int), 入力日付, パス1/パス2, 担当者ID
#   - ACC_MC.MCID がユニークキー (9,539), 加工IDは共通加工で複数MCIDが共有 (7,895)
#   - mc_tooling の加工ID紐づけは legacy_kakoid ベースで解決
#   - SP_Sheet(機械ID=1)はPGに存在しないためmachine_id=NULLになる (正常)
#   - tool_no(Nカラム)はNULLデータが多数存在するためNOT NULL制約を外す必要あり
#   - fetchall()は大量データで遅延するためfetchmany(500)を使用
# =============================================================================

import sys
import argparse
import logging
from datetime import datetime

import pymssql
import psycopg2
import psycopg2.extras

# =============================================================================
# 設定
# =============================================================================
SS_CONFIG = dict(server='192.168.1.9', user='sa', password='RTW65b',
                 database='imotomc', tds_version='7.4')

PG_DSN = ("host=localhost port=5440 dbname=machcore_dev "
          "user=machcore password=machcore_pass_change_me")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'/tmp/mc_import_{datetime.now():%Y%m%d_%H%M%S}.log')
    ]
)
log = logging.getLogger(__name__)

# =============================================================================
# ユーティリティ
# =============================================================================
def safe_str(v, maxlen=None):
    if v is None: return None
    s = str(v).strip()
    if not s: return None
    return s[:maxlen] if maxlen else s

def safe_int(v):
    if v is None: return None
    try: return int(v)
    except: return None

def safe_float(v):
    if v is None: return 0.0
    try: return float(v)
    except: return 0.0

def safe_bool_umu(v):
    """有無フィールド → boolean"""
    if v is None: return False
    return str(v).strip() not in ('', '無', 'None')


# =============================================================================
# PHASE 0: 事前マップ構築
# =============================================================================
def build_maps(sc, pc):
    log.info("=== PHASE 0: 事前マップ構築 ===")

    # parts: part_id(文字列) → id
    pc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pc.fetchall()}   # "1482" → 30
    log.info(f"  parts: {len(parts_map)}件")

    # machines: machine_code → id (全system_type)
    pc.execute("SELECT id, machine_code FROM machines")
    machine_code_map = {r[1]: r[0] for r in pc.fetchall()}
    log.info(f"  machines: {len(machine_code_map)}件")

    # SQL Server: ACC_機械.機械ID → 機械名
    sc.execute("SELECT 機械ID, 機械名 FROM [imotomc].[dbo].[ACC_機械]")
    ss_machine_name = {r[0]: r[1] for r in sc.fetchall()}

    def resolve_mc_machine(ss_id):
        if ss_id is None: return None
        name = ss_machine_name.get(ss_id)
        return machine_code_map.get(name) if name else None

    # users: ADMIN001のid
    pc.execute("SELECT id FROM users WHERE employee_code = 'ADMIN001'")
    admin_id = pc.fetchone()[0]
    log.info(f"  admin_id: {admin_id}")

    # NC旋盤: machines (system_type='NC') machine_code → id
    pc.execute("SELECT id, machine_code FROM machines WHERE system_type = 'NC'")
    nc_machine_map = {r[1]: r[0] for r in pc.fetchall()}
    log.info(f"  NC machines: {len(nc_machine_map)}件")

    return {
        'parts': parts_map,
        'machine_code': machine_code_map,
        'nc_machine': nc_machine_map,
        'ss_machine_name': ss_machine_name,
        'resolve_mc_machine': resolve_mc_machine,
        'admin_id': admin_id,
    }


# =============================================================================
# PHASE 1: mc_programs インポート (ACC_MC × ACC_マシニング)
# =============================================================================
def import_mc_programs(sc, pc, maps, dry_run=False, truncate=False):
    log.info("=== PHASE 1: mc_programs インポート ===")

    if truncate and not dry_run:
        log.warning("  mc_programs TRUNCATE (CASCADE)...")
        pc.execute("TRUNCATE TABLE mc_programs CASCADE")
        pc.execute("ROLLBACK TO SAVEPOINT sp") if False else None

    INSERT_SQL = """
        INSERT INTO mc_programs (
            part_id, machining_id, machine_id, status, version,
            o_number, clamp_note, cycle_time_sec, machining_qty,
            note, registered_by, registered_at,
            legacy_mcid, legacy_kakoid,
            mc_process_no, folder1, folder2, file_name,
            rc, has_index_program, has_work_offset,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, 'APPROVED', %s,
            %s, %s, %s, %s,
            %s, %s, COALESCE(%s::timestamp, NOW()),
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            NOW(), NOW()
        )
        ON CONFLICT DO NOTHING
    """

    sc.execute("""
        SELECT mc.MCID, mc.部品ID, mc.加工ID,
               m.Version, m.MC工程No, m.メインPGNo, m.機械ID,
               m.加工時間H, m.加工時間M, m.加工時間S, m.加工個数,
               m.クランプ, m.備考, m.担当者ID, m.入力日付, m.RC,
               m.パス1, m.パス2, m.ファイル名, m.IP有無, m.WD有無
        FROM [imotomc].[dbo].[ACC_MC] mc
        INNER JOIN [imotomc].[dbo].[ACC_マシニング] m ON mc.加工ID = m.加工ID
        WHERE m.削除区分 = 0
        ORDER BY mc.MCID
    """)

    inserted = skipped = errors = 0
    BATCH = 500

    while True:
        rows = sc.fetchmany(BATCH)
        if not rows: break

        for row in rows:
            (mcid, buhin_id, kako_id,
             version, mc_process_no, main_pgno, kikai_id,
             h, m_val, s_val, qty,
             clamp, note, tanto_id, nyuryoku_bi, rc,
             path1, path2, filename, ip_umu, wd_umu) = row

            pg_part_id = maps['parts'].get(str(buhin_id))
            if pg_part_id is None:
                skipped += 1
                continue

            pg_machine_id = maps['resolve_mc_machine'](kikai_id)
            cycle_sec = int(safe_float(h)*3600 + safe_float(m_val)*60 + safe_float(s_val)) or None
            mq = safe_int(qty) or 1
            rc_val = safe_int(rc)
            reg_at = f"{nyuryoku_bi} 00:00:00" if nyuryoku_bi else None
            has_ip = safe_bool_umu(ip_umu)
            has_wd = safe_bool_umu(wd_umu)
            try: proc_no = int(mc_process_no) if mc_process_no is not None else None
            except: proc_no = None

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    pg_part_id, kako_id, pg_machine_id,
                    safe_str(version) or '1.0001',
                    safe_str(main_pgno, 50),
                    safe_str(clamp, 2000),
                    cycle_sec, mq,
                    safe_str(note, 2000),
                    maps['admin_id'], reg_at,
                    mcid, kako_id,
                    proc_no,
                    safe_str(path1, 50), safe_str(path2, 50), safe_str(filename, 50),
                    rc_val, has_ip, has_wd,
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 5:
                    log.error(f"  ERROR MCID={mcid}: {e}")

        if not dry_run:
            pc.connection.commit()
        log.info(f"  ... 挿入={inserted}, スキップ={skipped}, エラー={errors}")

    log.info(f"PHASE 1 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 2: mc_tooling インポート (ACC_ツーリング)
# =============================================================================
def import_mc_tooling(sc, pc, dry_run=False, truncate=False):
    log.info("=== PHASE 2: mc_tooling インポート ===")

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_tooling")

    # ── マップ構築: legacy_kakoid(加工ID) → mc_programs.id ──────────────
    # ツーリングはACC_ツーリング.加工ID = ACC_マシニング.加工ID で紐づく。
    # mc_programsのlegacy_kakoidに加工IDが格納されている。
    # 同一加工IDに複数のMCIDが存在する（共通加工）場合は先頭のmc_programs.idを使用。
    pc.execute("SELECT id, legacy_kakoid FROM mc_programs WHERE legacy_kakoid IS NOT NULL")
    kakoid_map = {}
    for r in pc.fetchall():
        kakoid_map.setdefault(r[1], r[0])  # 同一kakoidは最初のidを採用
    log.info(f"  kakoidマップ: {len(kakoid_map)}件")

    # ── ACC_ツーリング カラム動的確認 ──────────────────────────────────
    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_ツーリング'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_ツーリング カラム: {cols}")

    # カラム存在フラグ
    has_d_value  = 'D値' in cols
    has_sub      = 'SUB' in cols
    has_tool_col = 'ツール' in cols   # tool_type相当

    # SELECT文を動的構築（ツーリングIDを先頭に）
    select_cols = "ツーリングID, 加工ID, 順番, N, 工具, T, H, D, コメント"
    if has_d_value:  select_cols += ", D値"
    if has_sub:      select_cols += ", SUB"
    if has_tool_col: select_cols += ", ツール"

    sc.execute(f"""
        SELECT {select_cols}
        FROM [imotomc].[dbo].[ACC_ツーリング]
        ORDER BY 加工ID, 順番
    """)

    # ── tool_no は nullable (本番DBでALTER済み) ──────────────────────
    # DB側: ALTER TABLE mc_tooling ALTER COLUMN tool_no DROP NOT NULL;
    # Prisma: toolNo String? に変更済み
    INSERT_SQL = """
        INSERT INTO mc_tooling (
            mc_program_id, sort_order, tool_no, tool_name,
            t_no, length_offset_no, dia_offset_no,
            d_value_content, sub_pg_no, note, tool_type,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    BATCH = 500

    while True:
        rows = sc.fetchmany(BATCH)
        if not rows: break

        for row in rows:
            idx = 0
            tid      = row[idx]; idx += 1
            kako_id  = row[idx]; idx += 1
            junban   = row[idx]; idx += 1
            n_val    = safe_str(row[idx], 20);  idx += 1
            tool     = safe_str(row[idx], 100); idx += 1
            t_val    = safe_str(row[idx], 10);  idx += 1
            h_val    = safe_str(row[idx], 10);  idx += 1
            d_val    = safe_str(row[idx], 10);  idx += 1
            comment  = safe_str(row[idx], 500); idx += 1
            d_value  = safe_str(row[idx], 50)  if has_d_value  else None; idx += (1 if has_d_value  else 0)
            sub_pg   = safe_str(row[idx], 20)  if has_sub      else None; idx += (1 if has_sub      else 0)
            tool_typ = safe_str(row[idx], 50)  if has_tool_col else None

            try:
                seq = int(float(junban)) if junban is not None else 0
            except:
                seq = 0

            # D値をfloat→文字列変換
            if d_value is not None:
                try:
                    d_value = str(round(float(d_value), 3))
                except:
                    pass

            mc_prog_id = kakoid_map.get(kako_id)
            if mc_prog_id is None:
                skipped += 1
                continue

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    mc_prog_id, seq,
                    n_val,      # tool_no — NULL許容
                    tool,
                    t_val, h_val, d_val,
                    d_value, sub_pg, comment, tool_typ,
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 5:
                    log.error(f"  ERROR tid={tid} 加工ID={kako_id} seq={seq}: {e}")

        if not dry_run:
            pc.connection.commit()
        log.info(f"  ... 挿入={inserted}, スキップ={skipped}, エラー={errors}")

    log.info(f"PHASE 2 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 3: RC同期 (mc_tooling件数 → mc_programs.rc)
# =============================================================================
def sync_rc(pc, dry_run=False):
    log.info("=== PHASE 3: RC同期 ===")
    if dry_run:
        log.info("  [dry-run] スキップ")
        return
    pc.execute("""
        UPDATE mc_programs mp
        SET rc = sub.cnt
        FROM (
            SELECT mc_program_id, COUNT(*) AS cnt
            FROM mc_tooling
            GROUP BY mc_program_id
        ) sub
        WHERE mp.id = sub.mc_program_id
    """)
    pc.connection.commit()
    log.info("  RC同期完了")


# =============================================================================
# PHASE 4: mc_work_offsets インポート (ACC_ワークオフセット)
# =============================================================================
def import_mc_work_offsets(sc, pc, dry_run=False, truncate=False):
    log.info("=== PHASE 4: mc_work_offsets インポート ===")

    # テーブル存在確認
    sc.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = 'ACC_ワークオフセット'
    """)
    if sc.fetchone()[0] == 0:
        log.warning("  ACC_ワークオフセット テーブルなし、スキップ")
        return 0

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_work_offsets")

    # machining_id → mc_programs.id
    pc.execute("SELECT id, machining_id FROM mc_programs")
    machining_map = {}
    for r in pc.fetchall():
        if r[1] not in machining_map:
            machining_map[r[1]] = r[0]

    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_ワークオフセット'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_ワークオフセット カラム: {cols}")

    sc.execute("SELECT * FROM [imotomc].[dbo].[ACC_ワークオフセット] ORDER BY 加工ID")

    INSERT_SQL = """
        INSERT INTO mc_work_offsets (mc_program_id, g_code, x_offset, y_offset, z_offset, note)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (mc_program_id, g_code) DO NOTHING
    """

    inserted = skipped = errors = 0
    sc_cols = [d[0] for d in sc.description]

    while True:
        rows = sc.fetchmany(500)
        if not rows: break
        for row in rows:
            r = dict(zip(sc_cols, row))
            kako_id = r.get('加工ID')
            mc_prog_id = machining_map.get(kako_id)
            if mc_prog_id is None:
                skipped += 1
                continue

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    mc_prog_id,
                    safe_str(r.get('Gコード') or r.get('G_CODE') or r.get('G'), 10),
                    r.get('X') or r.get('X_OFFSET'),
                    r.get('Y') or r.get('Y_OFFSET'),
                    r.get('Z') or r.get('Z_OFFSET'),
                    safe_str(r.get('備考') or r.get('コメント'), 100),
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 5:
                    log.error(f"  ERROR 加工ID={kako_id}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 4 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 5: mc_index_programs インポート (ACC_インデックスプログラム)
# =============================================================================
def import_mc_index_programs(sc, pc, dry_run=False, truncate=False):
    log.info("=== PHASE 5: mc_index_programs インポート ===")

    sc.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = 'ACC_インデックスプログラム'
    """)
    if sc.fetchone()[0] == 0:
        sc.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'ACC_インデックス'
        """)
        if sc.fetchone()[0] == 0:
            log.warning("  ACC_インデックスプログラム/ACC_インデックス テーブルなし、スキップ")
            return 0

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_index_programs")

    pc.execute("SELECT id, machining_id FROM mc_programs")
    machining_map = {}
    for r in pc.fetchall():
        if r[1] not in machining_map:
            machining_map[r[1]] = r[0]

    # テーブル名確定
    tname = 'ACC_インデックスプログラム'
    sc.execute(f"""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tname}'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  {tname} カラム: {cols}")

    sc.execute(f"SELECT * FROM [imotomc].[dbo].[{tname}] ORDER BY 加工ID")

    INSERT_SQL = """
        INSERT INTO mc_index_programs (mc_program_id, sort_order, axis_0, axis_1, axis_2, note)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    sc_cols = [d[0] for d in sc.description]

    while True:
        rows = sc.fetchmany(500)
        if not rows: break
        for row in rows:
            r = dict(zip(sc_cols, row))
            kako_id = r.get('加工ID')
            mc_prog_id = machining_map.get(kako_id)
            if mc_prog_id is None:
                skipped += 1
                continue

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                sort = safe_int(r.get('順番') or r.get('No') or r.get('INDEX_NO')) or 0
                pc.execute(INSERT_SQL, (
                    mc_prog_id, sort,
                    safe_str(r.get('0度') or r.get('AXIS0'), 100),
                    safe_str(r.get('90度') or r.get('AXIS1'), 100),
                    safe_str(r.get('180度') or r.get('AXIS2'), 100),
                    safe_str(r.get('備考') or r.get('コメント'), 500),
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 5:
                    log.error(f"  ERROR 加工ID={kako_id}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 5 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 6: MC変更履歴 インポート (ACC_変更履歴 → mc_change_history)
# =============================================================================
def import_mc_change_history(sc, pc, maps, dry_run=False, truncate=False):
    log.info("=== PHASE 6: MC変更履歴 インポート ===")

    sc.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = 'ACC_変更履歴'
    """)
    if sc.fetchone()[0] == 0:
        log.warning("  ACC_変更履歴 テーブルなし、スキップ")
        return 0

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_change_history")

    # legacy_mcid → mc_programs.id
    pc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    legacy_map = {r[1]: r[0] for r in pc.fetchall()}

    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_変更履歴'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_変更履歴 カラム: {cols}")

    sc.execute("SELECT * FROM [imotomc].[dbo].[ACC_変更履歴] ORDER BY 変更ID")

    INSERT_SQL = """
        INSERT INTO mc_change_history (
            mc_program_id, change_type, operator_id,
            version_before, version_after, content, changed_at, legacy_hist_id
        ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::timestamp, NOW()), %s)
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    sc_cols = [d[0] for d in sc.description]

    while True:
        rows = sc.fetchmany(500)
        if not rows: break
        for row in rows:
            r = dict(zip(sc_cols, row))
            mcid = r.get('MCID') or r.get('MC_ID')
            mc_prog_id = legacy_map.get(mcid)
            if mc_prog_id is None:
                skipped += 1
                continue

            change_type = 'MIGRATION'
            content = safe_str(r.get('変更内容') or r.get('備考'), 1000)
            changed_at = str(r.get('変更日') or r.get('入力日付') or '')
            changed_at = f"{changed_at} 00:00:00" if changed_at and len(changed_at) == 10 else None
            hist_id = safe_int(r.get('変更ID'))

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    mc_prog_id, change_type, maps['admin_id'],
                    safe_str(r.get('変更前Ver'), 10),
                    safe_str(r.get('変更後Ver') or r.get('Version'), 10),
                    content, changed_at, hist_id,
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 5:
                    log.error(f"  ERROR MCID={mcid}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 6 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 7: スキーマ追加カラム整合確認
# =============================================================================
def verify_schema(pc):
    log.info("=== PHASE 7: スキーマ整合確認 ===")
    required = {
        'mc_programs': ['mc_process_no', 'folder1', 'folder2', 'file_name',
                        'rc', 'has_index_program', 'has_work_offset',
                        'legacy_mcid', 'legacy_kakoid'],
        'mc_tooling':  ['t_no', 'd_value_content', 'sub_pg_no', 'tool_type'],
    }
    all_ok = True
    for table, cols in required.items():
        pc.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
        """, (table,))
        existing = {r[0] for r in pc.fetchall()}
        for col in cols:
            if col not in existing:
                log.error(f"  ❌ {table}.{col} が存在しません")
                all_ok = False
            else:
                log.info(f"  ✅ {table}.{col}")

    # tool_no の nullable 確認
    pc.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'mc_tooling' AND column_name = 'tool_no'
    """)
    r = pc.fetchone()
    if r and r[0] == 'YES':
        log.info("  ✅ mc_tooling.tool_no: nullable (正常)")
    else:
        log.error("  ❌ mc_tooling.tool_no が NOT NULL のままです")
        log.error("     ALTER TABLE mc_tooling ALTER COLUMN tool_no DROP NOT NULL; を実行してください")
        all_ok = False

    return all_ok


# =============================================================================
# 最終サマリー
# =============================================================================
def print_summary(pc):
    log.info("=== 最終サマリー ===")
    queries = [
        ("mc_programs", "SELECT COUNT(*) FROM mc_programs"),
        ("mc_tooling",  "SELECT COUNT(*) FROM mc_tooling"),
        ("mc_work_offsets",   "SELECT COUNT(*) FROM mc_work_offsets"),
        ("mc_index_programs", "SELECT COUNT(*) FROM mc_index_programs"),
        ("mc_change_history", "SELECT COUNT(*) FROM mc_change_history"),
    ]
    for name, q in queries:
        try:
            pc.execute(q)
            cnt = pc.fetchone()[0]
            log.info(f"  {name:<25}: {cnt:>7,}件")
        except Exception as e:
            log.warning(f"  {name}: {e}")

    # 機械別内訳
    pc.execute("""
        SELECT m.machine_code, COUNT(*) as cnt
        FROM mc_programs mp
        LEFT JOIN machines m ON mp.machine_id = m.id
        GROUP BY m.machine_code
        ORDER BY cnt DESC
        LIMIT 10
    """)
    log.info("  --- 機械別件数（上位10）---")
    for r in pc.fetchall():
        log.info(f"    {(r[0] or 'NULL'):<15}: {r[1]:>5,}件")


# =============================================================================
# メイン
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='MachCore MC全データ移行スクリプト')
    parser.add_argument('--dry-run',   action='store_true', help='書き込みなし検証モード')
    parser.add_argument('--skip-nc',   action='store_true', help='NC旋盤データスキップ')
    parser.add_argument('--skip-mc',   action='store_true', help='MCマシニングデータスキップ')
    parser.add_argument('--truncate',  action='store_true', help='既存データ削除後に再インポート')
    parser.add_argument('--phase',     type=int, default=0, help='指定フェーズのみ実行 (1-6)')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  MachCore 本番移行スクリプト")
    log.info(f"  実行日時: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info(f"  dry-run={args.dry_run}, truncate={args.truncate}")
    log.info("=" * 60)

    if args.truncate and not args.dry_run:
        ans = input("⚠️  既存データをTRUNCATEします。続行しますか？ (yes/no): ")
        if ans.strip().lower() != 'yes':
            log.info("中止しました")
            sys.exit(0)

    sql = pymssql.connect(**SS_CONFIG)
    pg  = psycopg2.connect(PG_DSN)
    sc  = sql.cursor()
    pc  = pg.cursor()

    try:
        # スキーマ確認
        if not verify_schema(pc):
            log.error("スキーマ不整合があります。mc_migration.sqlを先に実行してください")
            sys.exit(1)

        # マップ構築
        maps = build_maps(sc, pc)

        if not args.skip_mc:
            if args.phase in (0, 1):
                import_mc_programs(sc, pc, maps, args.dry_run, args.truncate)
            if args.phase in (0, 2):
                import_mc_tooling(sc, pc, args.dry_run, args.truncate)
            if args.phase in (0, 3):
                sync_rc(pc, args.dry_run)
            if args.phase in (0, 4):
                import_mc_work_offsets(sc, pc, args.dry_run, args.truncate)
            if args.phase in (0, 5):
                import_mc_index_programs(sc, pc, args.dry_run, args.truncate)
            if args.phase in (0, 6):
                import_mc_change_history(sc, pc, maps, args.dry_run, args.truncate)

        if not args.dry_run:
            pg.commit()

        print_summary(pc)
        log.info("=" * 60)
        log.info("  🎉 移行完了！")
        log.info("=" * 60)

    except Exception as e:
        log.exception(f"移行中に予期しないエラー: {e}")
        pg.rollback()
        sys.exit(1)
    finally:
        sc.close()
        pc.close()
        sql.close()
        pg.close()


if __name__ == '__main__':
    main()
