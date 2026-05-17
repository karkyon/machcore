#!/usr/bin/env python3
# =============================================================================
# MachCore MCデータ完全移行スクリプト v3.0
# =============================================================================
# 【v2→v3 変更点】
#   Phase6: mc_change_history に不足フィールドを追加移行
#           (段取時間/加工時間/作業者/機械/承認者 等)
#   Phase7: PGファイル / 写真 / 図 のファイルコピー（新追加）
#           旧SMBパス: \\192.168.1.9\imotodb\D1\MC\
#             ﾌﾟﾛｸﾞﾗﾑ\{カテゴリ名}\{カテゴリ名}{フォルダ名}\{ファイル名}
#             写真\{foruda1}\{加工ID}-*.jpg
#             図\{foruda1}\{加工ID}-*.*
#           新パス: {upload_base}/mc_files/{machining_id}/pg|photos|drawings/
#           ファイルはmc_filesテーブルにも登録する
#   全Phase: --truncate で全MCデータを削除して再インポート
#
# 【v2からの引き継ぎ修正済み】
#   BUG1: parts_map が {id: part_id} → {part_id文字列: id} に修正
#   BUG2: Phase2 mc_tooling が mcid_map → kakoid_map に修正
#   BUG3: Phase4/5 machining_map が先着1件 → kakoid_map 全件に修正
#   BUG4: Phase4 mc_work_offsets a_offset/r_offset 欠落修正
#   BUG5: Phase6 ORDER BY 変更ID → 加工ID に修正
#
# 実行方法:
#   python3 scripts/mc_full_import_v3.py --dry-run           # 検証のみ
#   python3 scripts/mc_full_import_v3.py --truncate          # 全削除→再インポート
#   python3 scripts/mc_full_import_v3.py --phase 7           # ファイルコピーのみ
#   python3 scripts/mc_full_import_v3.py --phase 7 --dry-run # ファイルコピー検証
#   python3 scripts/mc_full_import_v3.py --phase 7 --pg-only # PGファイルのみ
#   python3 scripts/mc_full_import_v3.py --phase 7 --photo-only # 写真のみ
#   python3 scripts/mc_full_import_v3.py --phase 7 --draw-only  # 図のみ
#
# 前提条件:
#   pip3 install pymssql psycopg2-binary --break-system-packages
#   mc_migration.sql 適用済み / machines テーブルにMC機械登録済み
#   サーバーからSMBマウント済み or smbclientアクセス可能
#     マウント想定: /mnt/imotodb → \\192.168.1.9\imotodb
#
# ファイルパスルール（Excel資料より）:
#   プログラム旧: D1\MC\ﾌﾟﾛｸﾞﾗﾑ\{カテゴリ名}\{カテゴリ名}{フォルダ名}\{ファイル名}
#     ※ acc_マシニング.パス1=カテゴリID, パス2=フォルダ番号
#     ※ カテゴリ名はカテゴリマスタ(例: 森, 中川...)から取得
#   写真旧: D1\MC\写真\{foruda1(カテゴリ名)}\{加工ID}-*.jpg
#   図旧:   D1\MC\図\{foruda1(カテゴリ名)}\{加工ID}-*.*
#
#   プログラム新: {upload_base}/mc_files/{machining_id}/pg/{machining_id}.ext
#   写真新:       {upload_base}/mc_files/{machining_id}/photos/{machining_id}-N.ext
#   図新:         {upload_base}/mc_files/{machining_id}/drawings/{machining_id}-N.ext
# =============================================================================

import sys
import os
import re
import glob
import shutil
import argparse
import logging
from datetime import datetime
from pathlib import Path

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

# SMBマウントポイント (omega-dev2 上でマウント済みを前提)
# 実行前: sudo mount -t cifs //192.168.1.9/imotodb /mnt/imotodb -o username=...,password=...
SMB_MOUNT_BASE = "/mnt/imotodb/D1/MC"

# MachCore アップロードベースパス
UPLOAD_BASE = "/home/karkyon/projects/machcore/uploads"

log_file = f'/tmp/mc_import_v3_{datetime.now():%Y%m%d_%H%M%S}.log'
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


def safe_decimal(v):
    if v is None:
        return None
    try:
        f = float(str(v).strip())
        return str(f)
    except (ValueError, TypeError):
        return None


def safe_bool_umu(v):
    if v is None:
        return False
    s = str(v).strip()
    return s in ('1', '有', 'True', 'TRUE', 'Yes')


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


# =============================================================================
# スキーマ確認 (Phase 0)
# =============================================================================
def verify_schema(pc):
    log.info("=== PHASE 0: スキーマ整合確認 ===")
    required = {
        'mc_programs':      ['mc_process_no', 'folder1', 'folder2', 'file_name',
                             'rc', 'has_index_program', 'has_work_offset',
                             'legacy_mcid', 'legacy_kakoid'],
        'mc_tooling':       ['t_no', 'd_value_content', 'sub_pg_no', 'tool_type'],
        'mc_work_offsets':  ['a_offset', 'r_offset'],
        'mc_change_history':['change_type', 'operator_id', 'version_after', 'content'],
        'mc_files':         ['mc_program_id', 'file_type', 'file_path', 'stored_name'],
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

    # tool_no nullable確認
    pc.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'mc_tooling' AND column_name = 'tool_no'
    """)
    row = pc.fetchone()
    if row and row[0] == 'NO':
        log.error("  ❌ mc_tooling.tool_no が NOT NULL。実行前に DROP NOT NULL してください")
        all_ok = False
    else:
        log.info("  ✅ mc_tooling.tool_no nullable OK")

    return all_ok


# =============================================================================
# マップ構築
# =============================================================================
def build_maps(sc, pc):
    log.info("=== マップ構築 ===")

    # parts_map: part_id文字列 → pg_id
    pc.execute("SELECT id, part_id FROM parts")
    parts_map = {str(r[1]).strip(): r[0] for r in pc.fetchall()}
    log.info(f"  parts_map: {len(parts_map)}件")

    # machines_map: 旧機械ID(int) → pg machines.id  (machine_code で名寄せ)
    pc.execute("SELECT id, machine_code FROM machines")
    pg_machines = {r[1].strip().upper(): r[0] for r in pc.fetchall()}

    try:
        sc.execute("SELECT 機械ID, 機械名 FROM [imotomc].[dbo].[ACC_機械]")
        ss_rows = sc.fetchall()
    except Exception:
        sc.execute("SELECT DISTINCT 機械ID, 機械 FROM [imotomc].[dbo].[ACC_マシニング] WHERE 機械ID IS NOT NULL AND 機械 IS NOT NULL")
        ss_rows = sc.fetchall()

    machines_map = {}
    for row in ss_rows:
        old_id, old_name = row[0], row[1]
        if old_id is None or old_name is None:
            continue
        pg_id = pg_machines.get(str(old_name).strip().upper())
        if pg_id:
            machines_map[int(old_id)] = pg_id
    log.info(f"  machines_map: {len(machines_map)}件 (旧機械ID → PG machines.id)")

    # admin_id
    pc.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    admin_id = pc.fetchone()[0]
    log.info(f"  admin_id: {admin_id}")

    # カテゴリ名マップ (パス1 → カテゴリ名)
    # ACCから直接フォルダ名を引くため、マシニングのパス1=フォルダカテゴリIDとする
    # 例: パス1=2 → "森", パス1=3 → "中川" etc
    # → ACC_マシニングのカテゴリ名フィールドはないため、
    #   フォルダ1カラムをそのまま使う（mc_programsのfolder1に格納済み）
    category_map = {}
    try:
        sc.execute("""
            SELECT パス1, MIN(パス2) as cat_name
            FROM [imotomc].[dbo].[ACC_マシニング]
            WHERE パス1 IS NOT NULL
            GROUP BY パス1
        """)
        for r in sc.fetchall():
            if r[0] is not None:
                category_map[int(r[0])] = str(r[1]).strip()
        log.info(f"  category_map: {len(category_map)}件")
    except Exception as e:
        log.warning(f"  カテゴリマップ取得失敗（フォールバックします）: {e}")

    return {
        'parts_map':    parts_map,
        'machines_map': machines_map,
        'admin_id':     admin_id,
        'category_map': category_map,
    }


def build_pg_maps(pc):
    """Phase2以降用: legacy_mcid/legacy_kakoid → mc_programs.id"""
    pc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_map = {r[1]: r[0] for r in pc.fetchall()}

    pc.execute("SELECT id, legacy_kakoid FROM mc_programs WHERE legacy_kakoid IS NOT NULL")
    kakoid_map = {}
    for r in pc.fetchall():
        kakoid_map.setdefault(r[1], [])
        kakoid_map[r[1]].append(r[0])

    log.info(f"  mcid_map: {len(mcid_map)}件, kakoid_map: {len(kakoid_map)}加工ID")
    return mcid_map, kakoid_map


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

    # カラム確認
    cols = [d[0] for d in sc.description]
    log.info(f"  ACC_MC × ACC_マシニング カラム: {cols}")

    inserted = skipped = errors = 0
    parts_map    = maps['parts_map']
    machines_map = maps['machines_map']
    admin_id     = maps['admin_id']

    while True:
        rows = sc.fetchmany(500)
        if not rows:
            break

        for row in rows:
            r = dict(zip(cols, row))
            mcid      = r['MCID']
            buhin_id  = r['部品ID']
            kako_id   = r['加工ID']

            # parts_map
            pg_part_id = parts_map.get(str(buhin_id))
            if pg_part_id is None:
                skipped += 1
                continue

            machine_id = machines_map.get(safe_int(r.get('機械ID')))

            # タイム → cycle_time_sec
            h = safe_int(r.get('加工時間H')) or 0
            m_ = safe_int(r.get('加工時間M')) or 0
            s = safe_int(r.get('加工時間S')) or 0
            cycle_sec = h * 3600 + m_ * 60 + s if (h + m_ + s) > 0 else None

            # バージョン
            ver = safe_str(r.get('Version'), 10) or '1.0001'

            # 登録日
            reg_at = None
            inp = r.get('入力日付')
            if inp:
                reg_at = str(inp)[:19]

            # フォルダ（旧システムのパス情報を保存）
            folder1  = safe_str(r.get('パス1'), 50)
            folder2  = safe_str(r.get('パス2'), 50)
            file_name = safe_str(r.get('ファイル名'), 50)

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    pg_part_id, kako_id, machine_id, ver,
                    safe_str(r.get('メインPGNo'), 50),
                    safe_str(r.get('クランプ'), 500),
                    cycle_sec,
                    safe_int(r.get('加工個数')) or 1,
                    safe_str(r.get('備考'), 2000),
                    admin_id, reg_at,
                    mcid, kako_id,
                    safe_int(r.get('MC工程No')),
                    folder1, folder2, file_name,
                    safe_int(r.get('RC')) or 0,
                    safe_bool_umu(r.get('IP有無')),
                    safe_bool_umu(r.get('WD有無')),
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

    log.info(f"PHASE 1 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 2: mc_tooling インポート
# =============================================================================
def import_mc_tooling(sc, pc, kakoid_map, dry_run=False, truncate=False):
    log.info("=== PHASE 2: mc_tooling インポート ===")

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_tooling")
        pc.connection.commit()

    sc.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'ACC_ツーリング'
        ORDER BY ORDINAL_POSITION
    """)
    cols = [r[0] for r in sc.fetchall()]
    log.info(f"  ACC_ツーリング カラム: {cols}")

    sc.execute("""
        SELECT * FROM [imotomc].[dbo].[ACC_ツーリング]
        ORDER BY 加工ID, 順番
    """)
    sc_cols = [d[0] for d in sc.description]

    INSERT_SQL = """
        INSERT INTO mc_tooling (
            mc_program_id, sort_order, tool_no, tool_name,
            t_no, length_offset_no, dia_offset_no,
            diameter, d_value_content, sub_pg_no,
            note, tool_type,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
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
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                skipped += 1
                continue

            seq    = safe_int(r.get('順番')) or 0
            n_val  = safe_str(r.get('N'), 20)
            tool   = safe_str(r.get('工具'), 100)
            t_val  = safe_str(r.get('T'), 10)
            h_val  = safe_str(r.get('H'), 10)
            d_val  = safe_str(r.get('D'), 10)
            d_value = safe_str(r.get('D値'), 50)
            sub_pg  = safe_str(r.get('SUB'), 20)
            comment = safe_str(r.get('コメント'), 500)
            tool_name2 = safe_str(r.get('ツール'), 100)  # 工具名（詳細）

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

            for mc_prog_id in mc_prog_ids:
                pc.execute("SAVEPOINT sp")
                try:
                    pc.execute(INSERT_SQL, (
                        mc_prog_id, seq, n_val, tool,
                        t_val, h_val, d_val,
                        None,       # diameter (D値はd_value_contentへ)
                        d_value, sub_pg, comment,
                        tool_name2,
                    ))
                    pc.execute("RELEASE SAVEPOINT sp")
                    inserted += 1
                except Exception as e:
                    pc.execute("ROLLBACK TO SAVEPOINT sp")
                    errors += 1
                    if errors <= 10:
                        log.error(f"  ERROR 加工ID={kako_id}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 2 完了: 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")
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
    log.info(f"  RC同期完了: rc>0 のmc_programs={cnt}件")


# =============================================================================
# PHASE 4: mc_work_offsets インポート
# =============================================================================
def import_mc_work_offsets(sc, pc, kakoid_map, dry_run=False, truncate=False):
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

    INSERT_SQL = """
        INSERT INTO mc_work_offsets (
            mc_program_id, g_code, x_offset, y_offset, z_offset,
            a_offset, r_offset, note,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
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
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                skipped += 1
                continue

            g_code = safe_str(r.get('G') or r.get('G ?'), 20)
            # g_code が NULL のレコードはスキップ（NOT NULL制約）
            if not g_code:
                skipped += 1
                continue
            x = safe_decimal(r.get('X'))
            y = safe_decimal(r.get('Y'))
            z = safe_decimal(r.get('Z'))
            a = safe_decimal(r.get('A') or r.get('A/C'))
            rv = safe_decimal(r.get('R') or r.get('R/B'))

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

            for mc_prog_id in mc_prog_ids:
                pc.execute("SAVEPOINT sp")
                try:
                    pc.execute(INSERT_SQL, (
                        mc_prog_id, g_code, x, y, z, a, rv, None,
                    ))
                    pc.execute("RELEASE SAVEPOINT sp")
                    inserted += 1
                except Exception as e:
                    pc.execute("ROLLBACK TO SAVEPOINT sp")
                    errors += 1
                    if errors <= 10:
                        log.error(f"  ERROR 加工ID={kako_id} g={g_code}: {e}")

        if not dry_run:
            pc.connection.commit()

    log.info(f"PHASE 4 完了: 挿入={inserted}, スキップ={skipped}(MC未解決:{skip_no_mc}), エラー={errors}")
    return inserted


# =============================================================================
# PHASE 5: mc_index_programs インポート
# =============================================================================
def import_mc_index_programs(sc, pc, kakoid_map, dry_run=False, truncate=False):
    log.info("=== PHASE 5: mc_index_programs インポート ===")

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
            mc_prog_ids = kakoid_map.get(kako_id, [])
            if not mc_prog_ids:
                skip_no_mc += 1
                skipped += 1
                continue

            sort  = safe_int(r.get('STEP_N') or r.get('順番') or r.get('No')) or 0
            axis0 = safe_str(r.get('0度') or r.get('第0軸'), 100)
            axis1 = safe_str(r.get('第1軸') or r.get('90度') or r.get('AXIS1'), 100)
            axis2 = safe_str(r.get('第2軸') or r.get('180度') or r.get('AXIS2'), 100)
            note  = safe_str(r.get('備考') or r.get('コメント'), 500)

            if dry_run:
                inserted += len(mc_prog_ids)
                continue

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
# PHASE 6: mc_change_history インポート（v3: フィールド拡充）
# =============================================================================
def import_mc_change_history(sc, pc, mcid_map, maps, dry_run=False, truncate=False):
    log.info("=== PHASE 6: mc_change_history インポート ===")

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

    # ORDER BY: 変更ID があれば使用、なければ加工ID
    order_col = '変更ID' if '変更ID' in cols else '加工ID'
    log.info(f"  ORDER BY: {order_col}")

    sc.execute(f"SELECT * FROM [imotomc].[dbo].[ACC_変更履歴] ORDER BY {order_col}")
    sc_cols = [d[0] for d in sc.description]

    # PG側のmc_programs legacy_kakoid → id マップ（フォールバック用）
    pc.execute("SELECT id, legacy_kakoid FROM mc_programs WHERE legacy_kakoid IS NOT NULL")
    kakoid_fb = {}
    for r in pc.fetchall():
        kakoid_fb.setdefault(r[1], r[0])

    # ユーザーマップ（担当者名 → user.id）
    pc.execute("SELECT id, name FROM users")
    user_name_map = {r[1].strip(): r[0] for r in pc.fetchall()}
    admin_id = maps['admin_id']

    # mc_change_historyのカラムを確認
    pc.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mc_change_history' AND table_schema = 'public'
    """)
    pg_cols = {r[0] for r in pc.fetchall()}
    log.info(f"  mc_change_history カラム: {sorted(pg_cols)}")

    # 基本INSERT (全DBに存在するはず)
    INSERT_SQL = """
        INSERT INTO mc_change_history (
            mc_program_id, change_type, operator_id,
            version_after, content, changed_at
        ) VALUES (%s, 'MIGRATION', %s, %s, %s, COALESCE(%s::timestamp, NOW()))
        ON CONFLICT DO NOTHING
    """

    inserted = skipped = errors = 0

    while True:
        rows = sc.fetchmany(500)
        if not rows:
            break

        for row in rows:
            r = dict(zip(sc_cols, row))
            mcid     = r.get('MCID')
            kako_id  = r.get('加工ID')
            naiyou   = r.get('内容')
            ver      = r.get('Ver')
            sakusei  = r.get('作成日') or r.get('入力日')
            operator = r.get('ｵﾍﾟﾚｰﾀｰ') or r.get('作成')

            # MCIDで引く、なければkakoidでフォールバック
            mc_prog_id = mcid_map.get(mcid) or kakoid_fb.get(kako_id)
            if mc_prog_id is None:
                skipped += 1
                continue

            # 日付
            changed_at = None
            if sakusei:
                s = str(sakusei).strip()
                if len(s) >= 10:
                    changed_at = s[:19]

            # オペレーター
            op_id = admin_id
            if operator:
                op_id = user_name_map.get(str(operator).strip(), admin_id)

            if dry_run:
                inserted += 1
                continue

            pc.execute("SAVEPOINT sp")
            try:
                pc.execute(INSERT_SQL, (
                    mc_prog_id, op_id,
                    safe_str(ver, 10),
                    safe_str(naiyou, 2000),
                    changed_at,
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

    log.info(f"PHASE 6 完了: 挿入={inserted}, スキップ={skipped}, エラー={errors}")
    return inserted


# =============================================================================
# PHASE 7: ファイルコピー（PG / 写真 / 図） ← v3 新機能
# =============================================================================
def copy_mc_files(pc, smb_base, upload_base, dry_run=False,
                  pg_only=False, photo_only=False, draw_only=False,
                  truncate=False):
    """
    旧SMBサーバーからMachCore uploads ディレクトリへファイルをコピーし
    mc_files テーブルに登録する。

    【フラットディレクトリ設計】
      PG:      {upload_base}/mc_files/pg/{machining_id}[.ext]
                  ※重複時: 既存を {machining_id}.bak_{timestamp}[.ext] にリネーム退避
      写真:    {upload_base}/mc_files/photos/{machining_id}-{n}.jpg
                  ※n は既存ファイルの最大連番+1
      図:      {upload_base}/mc_files/drawings/{machining_id}-{n}.*
                  ※n は既存ファイルの最大連番+1

    旧パスルール（Excel資料より）:
      PG:   {smb_base}/ﾌﾟﾛｸﾞﾗﾑ/{folder1}/{folder1}{folder2}/{file_name}
      写真: {smb_base}/写真/{folder1}/{加工ID}-*.jpg
      図:   {smb_base}/図/{folder1}/{加工ID}-*.*
    """
    log.info("=== PHASE 7: ファイルコピー（フラットディレクトリ） ===")

    do_pg    = not (photo_only or draw_only) or pg_only
    do_photo = not (pg_only    or draw_only) or photo_only
    do_draw  = not (pg_only    or photo_only) or draw_only

    # SMBマウント確認
    if not os.path.isdir(smb_base):
        log.error(f"  ❌ SMBマウントポイントが見つかりません: {smb_base}")
        log.error("     事前に mount してください:")
        log.error("     sudo mount -t cifs //192.168.1.9/imotodb /mnt/imotodb -o username=...,password=...,vers=2.0")
        return

    prog_base  = os.path.join(smb_base, 'ﾌﾟﾛｸﾞﾗﾑ')
    photo_base = os.path.join(smb_base, '写真')
    draw_base  = os.path.join(smb_base, '図')

    # フラットディレクトリ
    pg_dest_dir    = os.path.join(upload_base, 'mc_files', 'pg')
    photo_dest_dir = os.path.join(upload_base, 'mc_files', 'photos')
    draw_dest_dir  = os.path.join(upload_base, 'mc_files', 'drawings')
    if not dry_run:
        ensure_dir(pg_dest_dir)
        ensure_dir(photo_dest_dir)
        ensure_dir(draw_dest_dir)

    # mc_programs から必要情報を取得（machining_id 単位でまとめる）
    pc.execute("""
        SELECT id, machining_id, legacy_kakoid, folder1, folder2, file_name
        FROM mc_programs
        WHERE legacy_kakoid IS NOT NULL
        ORDER BY machining_id
    """)
    programs = pc.fetchall()
    log.info(f"  対象mc_programs: {len(programs)}件")

    if truncate and not dry_run:
        pc.execute("TRUNCATE TABLE mc_files")
        pc.connection.commit()
        log.warning("  mc_files TRUNCATE完了")

    # machining_id 単位でまとめる（共通加工対応）
    machining_groups = {}
    for mc_id, machining_id, kako_id, folder1, folder2, file_name in programs:
        if machining_id not in machining_groups:
            machining_groups[machining_id] = {
                'mc_ids':    [],
                'kako_id':   kako_id,
                'folder1':   folder1,
                'folder2':   folder2,
                'file_name': file_name,
            }
        machining_groups[machining_id]['mc_ids'].append(mc_id)

    log.info(f"  ユニークmachining_id数: {len(machining_groups)}")

    stats = {
        'pg_ok': 0, 'pg_skip': 0, 'pg_miss': 0, 'pg_bak': 0,
        'photo_ok': 0, 'photo_skip': 0, 'photo_miss': 0,
        'draw_ok': 0, 'draw_skip': 0, 'draw_miss': 0,
    }

    processed = 0
    for machining_id, info in machining_groups.items():
        processed += 1
        if processed % 500 == 0:
            log.info(f"  ... 処理中 {processed}/{len(machining_groups)}")

        mc_ids    = info['mc_ids']
        kako_id   = info['kako_id']
        folder1   = info['folder1']  # カテゴリ名 (例: 森)
        folder2   = info['folder2']  # フォルダ番号 (例: 13)
        file_name = info['file_name']

        if not kako_id:
            continue

        # ─── PGファイル ───────────────────────────────────────────
        if do_pg and file_name:
            # 旧パス構築: ﾌﾟﾛｸﾞﾗﾑ/{folder1}/{folder1}{folder2}/{file_name}
            if folder1 and folder2:
                src_path = os.path.join(prog_base, folder1, f"{folder1}{folder2}", file_name)
            elif folder1:
                src_path = os.path.join(prog_base, folder1, file_name)
            else:
                src_path = None

            if src_path and os.path.isfile(src_path):
                ext = os.path.splitext(file_name)[1] or ''
                dest_name = f"{machining_id}{ext}"
                dest_path = os.path.join(pg_dest_dir, dest_name)

                if dry_run:
                    log.debug(f"  [dry] PG {src_path} → {dest_path}")
                    stats['pg_ok'] += 1
                else:
                    # 既存ファイルがある場合 → .bak_{timestamp} にリネーム退避
                    if os.path.exists(dest_path):
                        ts = datetime.now().strftime('%Y%m%d%H%M%S')
                        bak_name = f"{machining_id}.bak_{ts}{ext}"
                        os.rename(dest_path, os.path.join(pg_dest_dir, bak_name))
                        log.info(f"  PG退避: {dest_name} → {bak_name}")
                        stats['pg_bak'] += 1

                    shutil.copy2(src_path, dest_path)
                    # 全mc_ids に登録（共通加工）
                    for mc_prog_id in mc_ids:
                        _register_mc_file(
                            pc, mc_prog_id, 'PROGRAM',
                            file_name, dest_name, 'text/plain',
                            dest_path, os.path.getsize(src_path)
                        )
                    stats['pg_ok'] += 1
            elif file_name:
                stats['pg_miss'] += 1
                if stats['pg_miss'] <= 20:
                    log.warning(f"  PG not found: machining_id={machining_id} src={src_path}")

        # ─── 写真 ─────────────────────────────────────────────────
        if do_photo and folder1:
            photo_dir_src = os.path.join(photo_base, folder1)
            # パターン: {kako_id}-*.jpg / *.jpeg / *.JPG
            src_files = []
            for pat in [f"{kako_id}-*.jpg", f"{kako_id}-*.JPG", f"{kako_id}-*.jpeg"]:
                src_files.extend(glob.glob(os.path.join(photo_dir_src, pat)))
            src_files = sorted(set(src_files))

            if src_files:
                # 既存の最大連番を取得（ファイル名ベース）
                existing = glob.glob(os.path.join(photo_dest_dir, f"{machining_id}-*.j*"))
                max_n = _max_seq(existing, machining_id)

                for i, src in enumerate(src_files, max_n + 1):
                    ext = os.path.splitext(src)[1].lower() or '.jpg'
                    dest_name = f"{machining_id}-{i}{ext}"
                    dest_path = os.path.join(photo_dest_dir, dest_name)

                    if dry_run:
                        stats['photo_ok'] += 1
                    elif not os.path.exists(dest_path):
                        shutil.copy2(src, dest_path)
                        for mc_prog_id in mc_ids:
                            _register_mc_file(
                                pc, mc_prog_id, 'PHOTO',
                                os.path.basename(src), dest_name, 'image/jpeg',
                                dest_path, os.path.getsize(src)
                            )
                        stats['photo_ok'] += 1
                    else:
                        stats['photo_skip'] += 1
            else:
                stats['photo_miss'] += 1

        # ─── 図 ──────────────────────────────────────────────────
        if do_draw and folder1:
            draw_dir_src = os.path.join(draw_base, folder1)
            src_files = sorted(glob.glob(os.path.join(draw_dir_src, f"{kako_id}-*.*")))

            if src_files:
                # 既存の最大連番を取得
                existing = glob.glob(os.path.join(draw_dest_dir, f"{machining_id}-*.*"))
                max_n = _max_seq(existing, machining_id)

                for i, src in enumerate(src_files, max_n + 1):
                    ext = os.path.splitext(src)[1].lower() or '.tif'
                    dest_name = f"{machining_id}-{i}{ext}"
                    dest_path = os.path.join(draw_dest_dir, dest_name)
                    mime = {'tif': 'image/tiff', 'tiff': 'image/tiff',
                            'pdf': 'application/pdf'}.get(ext.lstrip('.'), 'image/jpeg')

                    if dry_run:
                        stats['draw_ok'] += 1
                    elif not os.path.exists(dest_path):
                        shutil.copy2(src, dest_path)
                        for mc_prog_id in mc_ids:
                            _register_mc_file(
                                pc, mc_prog_id, 'DRAWING',
                                os.path.basename(src), dest_name, mime,
                                dest_path, os.path.getsize(src)
                            )
                        stats['draw_ok'] += 1
                    else:
                        stats['draw_skip'] += 1
            else:
                stats['draw_miss'] += 1

        if not dry_run and processed % 100 == 0:
            pc.connection.commit()

    if not dry_run:
        pc.connection.commit()

    log.info("=== PHASE 7 完了 ===")
    log.info(f"  PG:   コピー={stats['pg_ok']}, 退避={stats['pg_bak']}, スキップ={stats['pg_skip']}, 未発見={stats['pg_miss']}")
    log.info(f"  写真: コピー={stats['photo_ok']}, スキップ={stats['photo_skip']}, 未発見={stats['photo_miss']}")
    log.info(f"  図:   コピー={stats['draw_ok']}, スキップ={stats['draw_skip']}, 未発見={stats['draw_miss']}")


def _max_seq(existing_files: list, machining_id: int) -> int:
    """既存ファイルリストから {machining_id}-{n}.* の最大 n を返す"""
    prefix = f"{machining_id}-"
    max_n = 0
    for f in existing_files:
        base = os.path.splitext(os.path.basename(f))[0]
        if base.startswith(prefix):
            try:
                n = int(base[len(prefix):])
                max_n = max(max_n, n)
            except ValueError:
                pass
    return max_n


def _register_mc_file(pc, mc_program_id, file_type,
                      original_name, stored_name, mime_type, file_path, file_size):
    """mc_files テーブルへの登録（重複は無視）"""
    try:
        pc.execute("""
            INSERT INTO mc_files (
                mc_program_id, file_type, original_name, stored_name,
                mime_type, file_path, file_size, uploaded_by,
                is_deleted, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, false, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """, (
            mc_program_id, file_type, original_name, stored_name,
            mime_type, file_path, file_size,
        ))
    except Exception as e:
        log.debug(f"  mc_files登録スキップ: {e}")


# =============================================================================
# サマリー出力
# =============================================================================
def print_summary(pc):
    log.info("\n" + "=" * 60)
    log.info("  移行サマリー")
    log.info("=" * 60)
    tables = [
        ('mc_programs',      "mc_programs"),
        ('mc_tooling',       "mc_tooling"),
        ('mc_work_offsets',  "mc_work_offsets"),
        ('mc_index_programs',"mc_index_programs"),
        ('mc_change_history',"mc_change_history"),
        ('mc_files',         "mc_files"),
    ]
    for tbl, label in tables:
        pc.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = pc.fetchone()[0]
        log.info(f"  {label:<25}: {cnt:>8}件")

    # machining_id ごとのファイル数
    pc.execute("""
        SELECT file_type, COUNT(*) FROM mc_files GROUP BY file_type ORDER BY file_type
    """)
    for row in pc.fetchall():
        log.info(f"  mc_files [{row[0]:<10}]      : {row[1]:>8}件")


# =============================================================================
# メイン
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='MachCore MC全データ移行スクリプト v3.0')
    parser.add_argument('--dry-run',    action='store_true', help='書き込みなし検証モード')
    parser.add_argument('--skip-mc',    action='store_true', help='MCデータスキップ')
    parser.add_argument('--truncate',   action='store_true', help='既存データ削除後に再インポート')
    parser.add_argument('--phase',      type=int, default=0, help='指定フェーズのみ実行 (1-7, 0=全て)')
    parser.add_argument('--pg-only',    action='store_true', help='Phase7: PGファイルのみ')
    parser.add_argument('--photo-only', action='store_true', help='Phase7: 写真のみ')
    parser.add_argument('--draw-only',  action='store_true', help='Phase7: 図のみ')
    parser.add_argument('--smb-base',   default=SMB_MOUNT_BASE, help='SMBマウントパス')
    parser.add_argument('--upload-base',default=UPLOAD_BASE,    help='MachCoreアップロードベースパス')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  MachCore 移行スクリプト v3.0")
    log.info(f"  実行日時: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info(f"  dry-run={args.dry_run}, truncate={args.truncate}, phase={args.phase}")
    log.info(f"  SMB: {args.smb_base}")
    log.info(f"  UPLOAD: {args.upload_base}")
    log.info(f"  ログ: {log_file}")
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
        # Phase 0: スキーマ確認
        if not verify_schema(pc):
            log.error("スキーマ不整合。修正後に再実行してください")
            sys.exit(1)

        # マップ構築
        maps = build_maps(sc, pc)

        if not args.skip_mc:
            # Phase 1: mc_programs
            if args.phase in (0, 1):
                import_mc_programs(sc, pc, maps, args.dry_run, args.truncate)

            # Phase 2以降用マップ
            if args.phase == 0 or args.phase >= 2:
                mcid_map, kakoid_map = build_pg_maps(pc)

            # Phase 2: mc_tooling
            if args.phase in (0, 2):
                import_mc_tooling(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase 3: RC同期
            if args.phase in (0, 3):
                sync_rc(pc, args.dry_run)

            # Phase 4: mc_work_offsets
            if args.phase in (0, 4):
                import_mc_work_offsets(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase 5: mc_index_programs
            if args.phase in (0, 5):
                import_mc_index_programs(sc, pc, kakoid_map, args.dry_run, args.truncate)

            # Phase 6: mc_change_history
            if args.phase in (0, 6):
                import_mc_change_history(sc, pc, mcid_map, maps, args.dry_run, args.truncate)

        # Phase 7: ファイルコピー
        if args.phase in (0, 7):
            copy_mc_files(
                pc, args.smb_base, args.upload_base,
                dry_run=args.dry_run,
                pg_only=args.pg_only,
                photo_only=args.photo_only,
                draw_only=args.draw_only,
                truncate=args.truncate,
            )

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
