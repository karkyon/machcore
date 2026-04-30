#!/usr/bin/env python3
# =============================================================================
# MachCore MCデータ完全移行スクリプト v2.0
# =============================================================================
# 【重要変更点 v1→v2】
#   BUG1: parts_map が {id: part_id} (逆) だったのを {part_id文字列: id} に修正
#   BUG2: Phase2 mc_tooling が mcid_map(legacy_mcid) でlookupしていた
#         → 正しくは kakoid_map(legacy_kakoid) で全MCIDに紐付け
#   BUG3: Phase4/5 で machining_map が先着1件のみだった
#         → kakoid_map で全該当MCIDに紐付け（共通加工対応）
#   BUG4: Phase4 mc_work_offsets で a_offset / r_offset が欠落
#   BUG5: Phase6 ORDER BY 変更ID → ORDER BY 加工ID に修正
#
# 実行方法:
#   python3 scripts/mc_full_import_v2.py --dry-run     # 検証のみ
#   python3 scripts/mc_full_import_v2.py --truncate    # 本番移行（既存削除）
#   python3 scripts/mc_full_import_v2.py --phase 2     # 指定フェーズのみ
#
# 前提条件:
#   pip3 install pymssql psycopg2-binary --break-system-packages
#   mc_migration.sql 適用済み
#   machines テーブルにMC機械登録済み
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
SS_CONFIG = dict(
    server='192.168.1.9', user='sa', password='RTW65b',
    database='imotomc', tds_version='7.4'
)
PG_DSN = (
    "host=localhost port=5440 dbname=machcore_dev "
    "user=machcore password=machcore_pass_change_me"
)

log_file = f'/tmp/mc_import_v2_{datetime.now():%Y%m%d_%H%M%S}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
log = logging.getLogger(__name__)


# =============================================================================
# ユーティリティ
# =============================================================================
def safe_str(v, maxlen=None):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def safe_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def safe_float(v):
    if v is None:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def safe_decimal(v):
    """文字列・数値 → Decimal互換の文字列（None if 変換不可）"""
    if v is None:
        return None
    try:
        f = float(str(v).strip())
        return str(f)
    except (ValueError, TypeError):
        return None


def safe_bool_umu(v):
    """有無フィールド → boolean"""
    if v is None:
        return False
    return str(v).strip() not in ('', '無', 'None', '0')


def buhin_id_to_str(v):
    """
    ACC_MC.部品ID (INT or Decimal) → parts.part_id 照合用文字列
    例: 1482 → "1482"  /  1482.0 → "1482"
    """
    if v is None:
        return None
    try:
        return str(int(float(str(v).strip())))
    except (ValueError, TypeError):
        return str(v).strip()


# =============================================================================
# PHASE 0: 事前マップ構築
# =============================================================================
def build_maps(sc, pc):
    log.info("=== PHASE 0: 事前マップ構築 ===")

    # --------------------------------------------------------
    # [FIX BUG1] parts_map: part_id文字列 → parts.id整数
    # 旧スクリプトは {r[0]: r[1]} (id→part_id) で逆だった
    # --------------------------------------------------------
    pc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pc.fetchall()}  # "1482" → 30
    log.info(f"  parts_map: {len(parts_map)}件 (key=part_id文字列)")

    # machines: machine_code → id
    pc.execute("SELECT id, machine_code FROM machines")
    machine_code_map = {r[1]: r[0] for r in pc.fetchall()}
    log.info(f"  machines: {len(machine_code_map)}件")

    # SQL Server: ACC_機械.機械ID → 機械名
    sc.execute("SELECT 機械ID, 機械名 FROM [imotomc].[dbo].[ACC_機械]")
    ss_machine_name = {r[0]: r[1] for r in sc.fetchall()}
    log.info(f"  SS機械マスタ: {len(ss_machine_name)}件")

    def resolve_mc_machine(ss_id):
        if ss_id is None:
            return None
        name = ss_machine_name.get(ss_id)
        if name is None:
            return None
        return machine_code_map.get(name)

    # users: ADMIN001のid
    pc.execute("SELECT id FROM users WHERE employee_code = 'ADMIN001'")
    row = pc.fetchone()
    if row is None:
        raise RuntimeError("ADMIN001ユーザーが存在しません")
    admin_id = row[0]
    log.info(f"  admin_id: {admin_id}")

    return {
        'parts': parts_map,
        'machine_code': machine_code_map,
        'ss_machine_name': ss_machine_name,
        'resolve_mc_machine': resolve_mc_machine,
        'admin_id': admin_id,
    }


def build_pg_maps(pc):
    """
    Phase1完了後に呼ぶ。mc_programs から2種類のマップを構築。

    [FIX BUG2/BUG3]
    kakoid_map: legacy_kakoid → [mc_programs.id, ...] (リスト)
      共通加工では同一kako_idに複数mc_programs行が存在するため、
      全IDをリストで保持する。

    mcid_map: legacy_mcid → mc_programs.id (1:1)
      変更履歴のMCID→mc_programs.id解決に使う。
    """
    pc.execute("""
        SELECT id, legacy_mcid, legacy_kakoid
        FROM mc_programs
        WHERE legacy_mcid IS NOT NULL OR legacy_kakoid IS NOT NULL
    """)
    rows = pc.fetchall()

    # legacy_mcid → mc_programs.id (1:1)
    mcid_map = {}
    # legacy_kakoid → [mc_programs.id, ...] (1:N)
    kakoid_map = {}

    for (pg_id, legacy_mcid, legacy_kakoid) in rows:
        if legacy_mcid is not None:
            mcid_map[legacy_mcid] = pg_id
        if legacy_kakoid is not None:
            kakoid_map.setdefault(legacy_kakoid, []).append(pg_id)

    # 共通加工の統計
    multi_count = sum(1 for ids in kakoid_map.values() if len(ids) > 1)
    log.info(f"  pg_maps構築: mcid_map={len(mcid_map)}件, kakoid_map={len(kakoid_map)}件 (共通加工:{multi_count}件)")

    return mcid_map, kakoid_map


# =============================================================================
# スキーマ整合確認
# =============================================================================
def verify_schema(pc):
    log.info("=== スキーマ整合確認 ===")
    required = {
        'mc_programs': [
            'mc_process_no', 'folder1', 'folder2', 'file_name',
            'rc', 'has_index_program', 'has_work_offset',
            'legacy_mcid', 'legacy_kakoid'
        ],
        'mc_tooling': ['t_no', 'd_value_content', 'sub_pg_no'],
        'mc_work_offsets': ['g_code', 'x_offset', 'y_offset', 'z_offset', 'a_offset', 'r_offset'],
        'mc_index_programs': ['sort_order', 'axis_0', 'axis_1', 'axis_2'],
        'mc_change_history': ['mc_program_id', 'change_type', 'changed_at'],
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

    # tool_no の nullable確認
    pc.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'mc_tooling' AND column_name = 'tool_no'
    """)
    row = pc.fetchone()
    if row and row[0] == 'NO':
        log.error("  ❌ mc_tooling.tool_no が NOT NULL です。DROP NOT NULL が必要です。")
        log.error("     ALTER TABLE mc_tooling ALTER COLUMN tool_no DROP NOT NULL;")
        all_ok = False
    else:
        log.info("  ✅ mc_tooling.tool_no nullable OK")

    return all_ok


# =============================================================================
# PHASE 1: mc_programs インポート
# =============================================================================
def import_mc_programs(sc, pc, maps, dry_run=False, truncate=False):
    log.info("=== PHASE 1: mc_programs インポート ===")

    if truncate and not dry_run:
        log.warning("  mc_programs TRUNCATE (CASCADE)...")
        pc.execute("TRUNCATE TABLE mc_programs CASCADE")
        pc.connection.commit()

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
    skip_no_part = 0
    BATCH = 500

    while True:
        rows = sc.fetchmany(BATCH)
        if not rows:
            break

        for row in rows:
            (mcid, buhin_id, kako_id,
             version, mc_process_no, main_pgno, kikai_id,
             h, m_val, s_val, qty,
             clamp, note, tanto_id, nyuryoku_bi, rc,
             path1, path2, filename, ip_umu, wd_umu) = row

            # [FIX BUG1] buhin_idをstr変換してparts_mapを引く
            part_key = buhin_id_to_str(buhin_id)
            pg_part_id = maps['parts'].get(part_key)
            if pg_part_id is None:
                skip_no_part += 1
                if skip_no_part <= 10:
                    log.warning(f"  SKIP: 部品ID={buhin_id}(key={part_key}) がpartsに存在しない")
                skipped += 1
                continue

            pg_machine_id = maps['resolve_mc_machine'](kikai_id)
            cycle_sec = int(safe_float(h) * 3600 + safe_float(m_val) * 60 + safe_float(s_val)) or None
            mq = safe_int(qty) or 1
            rc_val = safe_int(rc)
            reg_at = f"{nyuryoku_bi} 00:00:00" if nyuryoku_bi else None
            has_ip = safe_bool_umu(ip_umu)
            has_wd = safe_bool_umu(wd_umu)

            try:
                proc_no = int(mc_process_no) if mc_process_no is not None else None
            except (ValueError, TypeError):
                proc_no = None

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
                if errors <= 10:
                    log.error(f"  ERROR MCID={mcid}: {e}")

        if not dry_run:
            pc.connection.commit()
        log.info(f"  ... 挿入={inserted}, スキップ={skipped}(部品未解決:{skip_no_part}), エラー={errors}")

    log.info(f"PHASE 1 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 2: mc_tooling インポート
# =============================================================================
def import_mc_tooling(sc, pc, kakoid_map, dry_run=False, truncate=False):
    """
    [FIX BUG2]
    旧: mcid_map.get(kako_id) → MCID=加工IDの通常ケースのみ正しく動作
    新: kakoid_map.get(kako_id) → 全該当mc_programs.idに挿入（共通加工対応）
    """
    log.info("=== PHASE 2: mc_tooling インポート ===")

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_tooling")
        pc.connection.commit()

    # カラム存在確認
    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_ツーリング'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_ツーリング カラム: {cols}")

    has_d_value = 'D値' in cols
    has_sub = 'SUB' in cols

    select_cols = "加工ID, N, 工具, T, H, D, コメント, 順番"
    if has_d_value:
        select_cols += ", D値"
    if has_sub:
        select_cols += ", SUB"

    sc.execute(f"""
        SELECT {select_cols}
        FROM [imotomc].[dbo].[ACC_ツーリング]
        ORDER BY 加工ID, 順番
    """)

    INSERT_SQL = """
        INSERT INTO mc_tooling (
            mc_program_id, sort_order, tool_no, tool_name,
            t_no, length_offset_no, dia_offset_no,
            d_value_content, sub_pg_no, note,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    skip_no_mc = 0
    BATCH = 1000

    while True:
        rows = sc.fetchmany(BATCH)
        if not rows:
            break

        for row in rows:
            kako_id = row[0]
            n_val = safe_str(row[1], 20)
            tool = safe_str(row[2], 100)
            t_val = safe_str(row[3], 10)
            h_val = safe_str(row[4], 10)
            d_val = safe_str(row[5], 10)
            comment = safe_str(row[6], 500)
            seq = safe_int(row[7]) or 0
            d_value = safe_str(row[8], 50) if has_d_value and len(row) > 8 else None
            sub_pg = safe_str(row[9], 20) if has_sub and len(row) > 9 else None

            # [FIX BUG2] kakoid_mapで全該当mc_programs.idを取得
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                if skip_no_mc <= 10:
                    log.warning(f"  SKIP: 加工ID={kako_id} がmc_programsに存在しない")
                skipped += 1
                continue

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

            # 共通加工: 全mc_prog_idに同じツーリングを挿入
            for mc_prog_id in mc_prog_ids:
                pc.execute("SAVEPOINT sp")
                try:
                    pc.execute(INSERT_SQL, (
                        mc_prog_id, seq, n_val or '', tool,
                        t_val, h_val, d_val,
                        d_value, sub_pg, comment,
                    ))
                    pc.execute("RELEASE SAVEPOINT sp")
                    inserted += 1
                except Exception as e:
                    pc.execute("ROLLBACK TO SAVEPOINT sp")
                    errors += 1
                    if errors <= 10:
                        log.error(f"  ERROR 加工ID={kako_id} mc_prog_id={mc_prog_id} seq={seq}: {e}")

        if not dry_run:
            pc.connection.commit()
        log.info(f"  ... 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")

    log.info(f"PHASE 2 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 3: RC同期
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
    pc.execute("SELECT COUNT(*) FROM mc_programs WHERE rc > 0")
    cnt = pc.fetchone()[0]
    log.info(f"  RC同期完了: rc>0のmc_programs={cnt}件")


# =============================================================================
# PHASE 4: mc_work_offsets インポート
# =============================================================================
def import_mc_work_offsets(sc, pc, kakoid_map, dry_run=False, truncate=False):
    """
    [FIX BUG3] kakoid_mapで全mc_programs.idに紐付け
    [FIX BUG4] a_offset / r_offset を追加
    """
    log.info("=== PHASE 4: mc_work_offsets インポート ===")

    sc.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = 'ACC_ワークオフセット'
    """)
    if sc.fetchone()[0] == 0:
        log.warning("  ACC_ワークオフセット テーブルなし、スキップ")
        return 0

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_work_offsets")
        pc.connection.commit()

    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_ワークオフセット'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_ワークオフセット カラム: {cols}")

    sc.execute("SELECT * FROM [imotomc].[dbo].[ACC_ワークオフセット] ORDER BY 加工ID")
    sc_cols = [d[0] for d in sc.description]

    # a_offset / r_offset カラムの存在確認
    pc.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mc_work_offsets' AND table_schema = 'public'
    """)
    pg_cols = {r[0] for r in pc.fetchall()}
    has_a_offset = 'a_offset' in pg_cols
    has_r_offset = 'r_offset' in pg_cols

    if has_a_offset and has_r_offset:
        INSERT_SQL = """
            INSERT INTO mc_work_offsets (
                mc_program_id, g_code, x_offset, y_offset, z_offset,
                a_offset, r_offset, note, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (mc_program_id, g_code) DO NOTHING
        """
    else:
        log.warning("  a_offset / r_offset カラムなし。x/y/z/noteのみ挿入")
        INSERT_SQL = """
            INSERT INTO mc_work_offsets (
                mc_program_id, g_code, x_offset, y_offset, z_offset, note, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (mc_program_id, g_code) DO NOTHING
        """

    inserted = skipped = errors = 0
    skip_no_mc = 0

    while True:
        rows = sc.fetchmany(500)
        if not rows:
            break

        for row in rows:
            r = dict(zip(sc_cols, row))
            kako_id = r.get('加工ID')

            # Gコードの解決（カラム名揺れ対応）
            g_code = safe_str(r.get('Gコード') or r.get('G_CODE') or r.get('G') or r.get('Ｇコード'), 10)
            if not g_code:
                skipped += 1
                continue

            # [FIX BUG3] kakoid_mapで全mc_programs.idを取得
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                skipped += 1
                continue

            x = safe_decimal(r.get('X') or r.get('X_OFFSET') or r.get('Ｘ'))
            y = safe_decimal(r.get('Y') or r.get('Y_OFFSET') or r.get('Ｙ'))
            z = safe_decimal(r.get('Z') or r.get('Z_OFFSET') or r.get('Ｚ'))
            a = safe_decimal(r.get('A') or r.get('A_OFFSET') or r.get('Ａ'))
            rr = safe_decimal(r.get('R') or r.get('R_OFFSET') or r.get('Ｒ'))
            note = safe_str(r.get('備考') or r.get('コメント'), 100)

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

            for mc_prog_id in mc_prog_ids:
                pc.execute("SAVEPOINT sp")
                try:
                    if has_a_offset and has_r_offset:
                        pc.execute(INSERT_SQL, (mc_prog_id, g_code, x, y, z, a, rr, note))
                    else:
                        pc.execute(INSERT_SQL, (mc_prog_id, g_code, x, y, z, note))
                    pc.execute("RELEASE SAVEPOINT sp")
                    inserted += 1
                except Exception as e:
                    pc.execute("ROLLBACK TO SAVEPOINT sp")
                    errors += 1
                    if errors <= 10:
                        log.error(f"  ERROR 加工ID={kako_id} g_code={g_code}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 4 完了: 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")
    return inserted


# =============================================================================
# PHASE 5: mc_index_programs インポート
# =============================================================================
def import_mc_index_programs(sc, pc, kakoid_map, dry_run=False, truncate=False):
    """[FIX BUG3] kakoid_mapで全mc_programs.idに紐付け"""
    log.info("=== PHASE 5: mc_index_programs インポート ===")

    # テーブル名確定
    tname = None
    for candidate in ['ACC_インデックスプログラム', 'ACC_インデックス']:
        sc.execute(f"""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{candidate}'
        """)
        if sc.fetchone()[0] > 0:
            tname = candidate
            break

    if tname is None:
        log.warning("  インデックスプログラムテーブル なし、スキップ")
        return 0

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_index_programs")
        pc.connection.commit()

    sc.execute(f"""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tname}'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  {tname} カラム: {cols}")

    sc.execute(f"SELECT * FROM [imotomc].[dbo].[{tname}] ORDER BY 加工ID")
    sc_cols = [d[0] for d in sc.description]

    INSERT_SQL = """
        INSERT INTO mc_index_programs (
            mc_program_id, sort_order, axis_0, axis_1, axis_2, note,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    skip_no_mc = 0

    while True:
        rows = sc.fetchmany(500)
        if not rows:
            break

        for row in rows:
            r = dict(zip(sc_cols, row))
            kako_id = r.get('加工ID')

            # [FIX BUG3] kakoid_mapで全mc_programs.idを取得
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                skipped += 1
                continue

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

            sort = safe_int(r.get('順番') or r.get('No') or r.get('INDEX_NO') or r.get('STEP_N')) or 0
            axis0 = safe_str(r.get('0度') or r.get('AXIS0') or r.get('第0軸'), 100)
            axis1 = safe_str(r.get('90度') or r.get('AXIS1') or r.get('第1軸'), 100)
            axis2 = safe_str(r.get('180度') or r.get('AXIS2') or r.get('第2軸'), 100)
            note = safe_str(r.get('備考') or r.get('コメント'), 500)

            for mc_prog_id in mc_prog_ids:
                pc.execute("SAVEPOINT sp")
                try:
                    pc.execute(INSERT_SQL, (mc_prog_id, sort, axis0, axis1, axis2, note))
                    pc.execute("RELEASE SAVEPOINT sp")
                    inserted += 1
                except Exception as e:
                    pc.execute("ROLLBACK TO SAVEPOINT sp")
                    errors += 1
                    if errors <= 10:
                        log.error(f"  ERROR 加工ID={kako_id}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 5 完了: 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")
    return inserted


# =============================================================================
# PHASE 6: MC変更履歴 インポート
# =============================================================================
def import_mc_change_history(sc, pc, mcid_map, maps, dry_run=False, truncate=False):
    """
    [FIX BUG5] ORDER BY 変更ID → ORDER BY 加工ID に修正
    変更履歴はMCIDベースで1:1マッピング（mcid_map使用）
    """
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
        pc.connection.commit()

    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_変更履歴'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_変更履歴 カラム: {cols}")

    # [FIX BUG5] 変更IDが存在しない場合は加工IDでORDER BY
    order_col = '変更ID' if '変更ID' in cols else '加工ID'
    log.info(f"  ORDER BY: {order_col}")

    sc.execute(f"SELECT * FROM [imotomc].[dbo].[ACC_変更履歴] ORDER BY {order_col}")
    sc_cols = [d[0] for d in sc.description]

    INSERT_SQL = """
        INSERT INTO mc_change_history (
            mc_program_id, change_type, operator_id,
            version_before, version_after, content, changed_at, legacy_hist_id,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::timestamp, NOW()), %s, NOW(), NOW())
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0
    skip_no_mc = 0

    while True:
        rows = sc.fetchmany(500)
        if not rows:
            break

        for row in rows:
            r = dict(zip(sc_cols, row))
            mcid = r.get('MCID') or r.get('MC_ID') or r.get('MCＩＤ')
            mc_prog_id = mcid_map.get(mcid)

            if mc_prog_id is None:
                skip_no_mc += 1
                skipped += 1
                continue

            content = safe_str(r.get('変更内容') or r.get('備考'), 1000)
            changed_at_raw = str(r.get('変更日') or r.get('入力日付') or '').strip()
            changed_at = None
            if changed_at_raw and len(changed_at_raw) >= 8:
                changed_at = f"{changed_at_raw[:10]} 00:00:00"

            hist_id = safe_int(r.get('変更ID'))
            ver_before = safe_str(r.get('変更前Ver') or r.get('変更前VERSION'), 10)
            ver_after = safe_str(r.get('変更後Ver') or r.get('Version') or r.get('変更後VERSION'), 10)

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    mc_prog_id, 'MIGRATION', maps['admin_id'],
                    ver_before, ver_after, content, changed_at, hist_id,
                ))
                pc.execute("RELEASE SAVEPOINT sp")
                inserted += 1
            except Exception as e:
                pc.execute("ROLLBACK TO SAVEPOINT sp")
                errors += 1
                if errors <= 10:
                    log.error(f"  ERROR MCID={mcid}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 6 完了: 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")
    return inserted


# =============================================================================
# 最終サマリー
# =============================================================================
def print_summary(pc):
    log.info("=== 最終サマリー ===")
    queries = [
        ("mc_programs",       "SELECT COUNT(*) FROM mc_programs"),
        ("mc_tooling",        "SELECT COUNT(*) FROM mc_tooling"),
        ("mc_work_offsets",   "SELECT COUNT(*) FROM mc_work_offsets"),
        ("mc_index_programs", "SELECT COUNT(*) FROM mc_index_programs"),
        ("mc_change_history", "SELECT COUNT(*) FROM mc_change_history"),
    ]
    for name, q in queries:
        try:
            pc.execute(q)
            cnt = pc.fetchone()[0]
            log.info(f"  {name:<25}: {cnt:>8,}件")
        except Exception as e:
            log.warning(f"  {name}: {e}")

    # 機械別内訳
    pc.execute("""
        SELECT COALESCE(m.machine_code, 'NULL') AS mc, COUNT(*) as cnt
        FROM mc_programs mp
        LEFT JOIN machines m ON mp.machine_id = m.id
        GROUP BY m.machine_code
        ORDER BY cnt DESC
        LIMIT 10
    """)
    log.info("  --- 機械別件数（上位10）---")
    for r in pc.fetchall():
        log.info(f"    {r[0]:<15}: {r[1]:>6,}件")

    # 共通加工統計
    pc.execute("""
        SELECT machining_id, COUNT(*) as cnt
        FROM mc_programs
        GROUP BY machining_id
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 5
    """)
    rows = pc.fetchall()
    if rows:
        log.info("  --- 共通加工（同一machining_id複数件, 上位5）---")
        for r in rows:
            log.info(f"    machining_id={r[0]}: {r[1]}件のMCが共有")


# =============================================================================
# メイン
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='MachCore MC全データ移行スクリプト v2.0')
    parser.add_argument('--dry-run',  action='store_true', help='書き込みなし検証モード')
    parser.add_argument('--skip-mc', action='store_true', help='MCデータスキップ')
    parser.add_argument('--truncate', action='store_true', help='既存データ削除後に再インポート')
    parser.add_argument('--phase',    type=int, default=0, help='指定フェーズのみ実行 (1-6)')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  MachCore 本番移行スクリプト v2.0")
    log.info(f"  実行日時: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info(f"  dry-run={args.dry_run}, truncate={args.truncate}, phase={args.phase}")
    log.info(f"  ログファイル: {log_file}")
    log.info("=" * 60)

    if args.truncate and not args.dry_run:
        ans = input("⚠️  既存データをTRUNCATEします。続行しますか？ (yes/no): ")
        if ans.strip().lower() != 'yes':
            log.info("中止しました")
            sys.exit(0)

    sql = pymssql.connect(**SS_CONFIG)
    pg = psycopg2.connect(PG_DSN)
    sc = sql.cursor()
    pc = pg.cursor()

    try:
        # スキーマ確認
        if not verify_schema(pc):
            log.error("スキーマ不整合があります。修正してから再実行してください")
            sys.exit(1)

        # マップ構築
        maps = build_maps(sc, pc)

        if not args.skip_mc:
            # Phase1: mc_programs
            if args.phase in (0, 1):
                import_mc_programs(sc, pc, maps, args.dry_run, args.truncate)

            # Phase1完了後にpg_mapsを構築（Phase2以降で使用）
            if not args.dry_run or args.phase in (0, 2, 3, 4, 5, 6):
                if args.phase == 0 or args.phase >= 2:
                    mcid_map, kakoid_map = build_pg_maps(pc)

            # Phase2: mc_tooling (kakoid_map使用)
            if args.phase in (0, 2):
                import_mc_tooling(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase3: RC同期
            if args.phase in (0, 3):
                sync_rc(pc, args.dry_run)

            # Phase4: mc_work_offsets (kakoid_map使用)
            if args.phase in (0, 4):
                import_mc_work_offsets(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase5: mc_index_programs (kakoid_map使用)
            if args.phase in (0, 5):
                import_mc_index_programs(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase6: mc_change_history (mcid_map使用)
            if args.phase in (0, 6):
                import_mc_change_history(sc, pc, mcid_map, maps, args.dry_run, args.truncate)

        if not args.dry_run:
            pg.commit()

        print_summary(pc)
        log.info("=" * 60)
        log.info("  🎉 移行完了！")
        log.info(f"  ログ: {log_file}")
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
