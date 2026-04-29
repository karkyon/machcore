#!/usr/bin/env python3
# =============================================================================
# MachCore MCデータ整合性確認スクリプト v1.0
# =============================================================================
# 【確認レベル】
#   L1: 件数確認（各テーブルの総件数）
#   L2: サンプル確認（任意MCIDで旧DB・新DBのデータ比較）
#   L3: 参照整合性（FKが全て有効、孤立レコードなし）
#   L4: 共通加工確認（共通加工IDの全MCにツーリングが紐付いているか）
#   L5: ビジネスロジック（RC値 = ツーリング件数）
#
# 実行方法:
#   python3 scripts/mc_verify.py --full-report
#   python3 scripts/mc_verify.py --mcid 100 --mcid 500
#   python3 scripts/mc_verify.py --level 1 2 3
# =============================================================================

import sys
import argparse
import logging
from datetime import datetime

import pymssql
import psycopg2

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

log_file = f'/tmp/mc_verify_{datetime.now():%Y%m%d_%H%M%S}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
log = logging.getLogger(__name__)

OK = "✅"
NG = "❌"
WARN = "⚠️ "


# =============================================================================
# L1: 件数確認
# =============================================================================
def check_l1_counts(sc, pc):
    log.info("\n" + "="*60)
    log.info("L1: 件数確認")
    log.info("="*60)

    results = []

    # PostgreSQL側件数
    pg_counts = {}
    for table in ['mc_programs', 'mc_tooling', 'mc_work_offsets',
                  'mc_index_programs', 'mc_change_history']:
        pc.execute(f"SELECT COUNT(*) FROM {table}")
        pg_counts[table] = pc.fetchone()[0]

    # SQL Server側件数（元データ）
    ss_counts = {}
    queries = {
        'ACC_MC × ACC_マシニング': """
            SELECT COUNT(*)
            FROM [imotomc].[dbo].[ACC_MC] mc
            INNER JOIN [imotomc].[dbo].[ACC_マシニング] m ON mc.加工ID = m.加工ID
            WHERE m.削除区分 = 0
        """,
        'ACC_ツーリング': "SELECT COUNT(*) FROM [imotomc].[dbo].[ACC_ツーリング]",
        'ACC_ワークオフセット': "SELECT COUNT(*) FROM [imotomc].[dbo].[ACC_ワークオフセット]",
        'ACC_インデックスプログラム': """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME IN ('ACC_インデックスプログラム', 'ACC_インデックス')
        """,
        'ACC_変更履歴': "SELECT COUNT(*) FROM [imotomc].[dbo].[ACC_変更履歴]",
    }

    for name, q in queries.items():
        try:
            sc.execute(q)
            ss_counts[name] = sc.fetchone()[0]
        except Exception as e:
            ss_counts[name] = f"エラー: {e}"

    log.info(f"\n  {'テーブル':<30} {'新DB(PG)':<12} {'旧DB(SS)':<12} {'判定'}")
    log.info(f"  {'-'*70}")

    checks = [
        ('mc_programs',       'ACC_MC × ACC_マシニング', 15681),
        ('mc_tooling',        'ACC_ツーリング',          127235),
        ('mc_work_offsets',   'ACC_ワークオフセット',    5134),
        ('mc_index_programs', 'ACC_インデックスプログラム', 7213),
        ('mc_change_history', 'ACC_変更履歴',            60259),
    ]

    all_ok = True
    for pg_tbl, ss_tbl, expected in checks:
        pg_cnt = pg_counts.get(pg_tbl, 0)
        ss_cnt = ss_counts.get(ss_tbl, '?')
        # 共通加工分は複製されるのでpg_cnt >= ss_cnt が正常
        if isinstance(ss_cnt, int):
            ok = pg_cnt >= ss_cnt * 0.95  # 5%以内の誤差は許容
        else:
            ok = pg_cnt > 0
        status = OK if ok else NG
        if not ok:
            all_ok = False
        log.info(f"  {pg_tbl:<30} {pg_cnt:<12,} {str(ss_cnt):<12} {status}")
        results.append({'table': pg_tbl, 'pg': pg_cnt, 'ss': ss_cnt, 'ok': ok})

    return all_ok, results


# =============================================================================
# L2: サンプル確認（指定MCIDで旧DB・新DBのデータ比較）
# =============================================================================
def check_l2_sample(sc, pc, mcids):
    log.info("\n" + "="*60)
    log.info(f"L2: サンプル確認 (MCID: {mcids})")
    log.info("="*60)

    all_ok = True

    for mcid in mcids:
        log.info(f"\n  --- MCID={mcid} ---")

        # 旧DB: ACC_MC + ACC_マシニング
        sc.execute("""
            SELECT mc.MCID, mc.部品ID, mc.加工ID,
                   m.Version, m.MC工程No, m.メインPGNo, m.加工個数
            FROM [imotomc].[dbo].[ACC_MC] mc
            INNER JOIN [imotomc].[dbo].[ACC_マシニング] m ON mc.加工ID = m.加工ID
            WHERE mc.MCID = %s AND m.削除区分 = 0
        """, (mcid,))
        ss_row = sc.fetchone()

        if ss_row is None:
            log.warning(f"  {WARN} MCID={mcid} が旧DBに存在しません")
            continue

        ss_mcid, ss_buhin_id, ss_kako_id, ss_ver, ss_proc_no, ss_pgno, ss_qty = ss_row
        log.info(f"  旧DB: 部品ID={ss_buhin_id}, 加工ID={ss_kako_id}, Ver={ss_ver}, PGNo={ss_pgno}, 個数={ss_qty}")

        # 新DB: mc_programs
        pc.execute("""
            SELECT mp.id, mp.part_id, mp.machining_id, mp.version, mp.o_number,
                   mp.machining_qty, mp.legacy_mcid, mp.legacy_kakoid,
                   p.part_id as part_code
            FROM mc_programs mp
            LEFT JOIN parts p ON mp.part_id = p.id
            WHERE mp.legacy_mcid = %s
        """, (mcid,))
        pg_row = pc.fetchone()

        if pg_row is None:
            log.error(f"  {NG} MCID={mcid} が新DB(mc_programs)に存在しません！")
            all_ok = False
            continue

        (pg_id, pg_part_id, pg_machining_id, pg_ver, pg_pgno,
         pg_qty, pg_legacy_mcid, pg_legacy_kakoid, pg_part_code) = pg_row

        log.info(f"  新DB: id={pg_id}, part_id={pg_part_id}(code={pg_part_code}), "
                 f"machining_id={pg_machining_id}, ver={pg_ver}, pgno={pg_pgno}, 個数={pg_qty}")

        # 整合性確認
        ok = True

        # machining_id一致確認
        if pg_machining_id != ss_kako_id:
            log.error(f"  {NG} machining_id不一致: 旧={ss_kako_id}, 新={pg_machining_id}")
            ok = False
        else:
            log.info(f"  {OK} machining_id一致: {pg_machining_id}")

        # legacy_kakoid = machining_id確認
        if pg_legacy_kakoid != ss_kako_id:
            log.error(f"  {NG} legacy_kakoid不一致: 旧={ss_kako_id}, 新={pg_legacy_kakoid}")
            ok = False
        else:
            log.info(f"  {OK} legacy_kakoid一致: {pg_legacy_kakoid}")

        # 部品ID確認（旧DB部品ID文字列 == 新DB parts.part_id）
        if pg_part_code != str(int(float(str(ss_buhin_id).strip()))):
            log.warning(f"  {WARN} 部品ID確認: 旧={ss_buhin_id}, 新parts.part_id={pg_part_code}")
        else:
            log.info(f"  {OK} 部品ID一致: {pg_part_code}")

        # ツーリング件数確認
        sc.execute("SELECT COUNT(*) FROM [imotomc].[dbo].[ACC_ツーリング] WHERE 加工ID = %s", (ss_kako_id,))
        ss_tool_cnt = sc.fetchone()[0]

        pc.execute("SELECT COUNT(*) FROM mc_tooling WHERE mc_program_id = %s", (pg_id,))
        pg_tool_cnt = pc.fetchone()[0]

        if ss_tool_cnt > 0 and pg_tool_cnt == 0:
            log.error(f"  {NG} ツーリング件数: 旧={ss_tool_cnt}, 新={pg_tool_cnt} (0件になっている！)")
            ok = False
        elif ss_tool_cnt != pg_tool_cnt:
            log.warning(f"  {WARN} ツーリング件数差: 旧={ss_tool_cnt}, 新={pg_tool_cnt} "
                        f"(共通加工の場合は正常)")
        else:
            log.info(f"  {OK} ツーリング件数一致: {pg_tool_cnt}件")

        if not ok:
            all_ok = False

    return all_ok


# =============================================================================
# L3: 参照整合性確認
# =============================================================================
def check_l3_referential(pc):
    log.info("\n" + "="*60)
    log.info("L3: 参照整合性確認")
    log.info("="*60)

    all_ok = True
    checks = [
        # (説明, クエリ, 期待件数)
        ("mc_programsの孤立part_id",
         "SELECT COUNT(*) FROM mc_programs mp WHERE NOT EXISTS (SELECT 1 FROM parts p WHERE p.id = mp.part_id)",
         0),
        ("mc_toolingの孤立mc_program_id",
         "SELECT COUNT(*) FROM mc_tooling mt WHERE NOT EXISTS (SELECT 1 FROM mc_programs mp WHERE mp.id = mt.mc_program_id)",
         0),
        ("mc_work_offsetsの孤立mc_program_id",
         "SELECT COUNT(*) FROM mc_work_offsets wo WHERE NOT EXISTS (SELECT 1 FROM mc_programs mp WHERE mp.id = wo.mc_program_id)",
         0),
        ("mc_index_programsの孤立mc_program_id",
         "SELECT COUNT(*) FROM mc_index_programs ip WHERE NOT EXISTS (SELECT 1 FROM mc_programs mp WHERE mp.id = ip.mc_program_id)",
         0),
        ("mc_change_historyの孤立mc_program_id",
         "SELECT COUNT(*) FROM mc_change_history ch WHERE NOT EXISTS (SELECT 1 FROM mc_programs mp WHERE mp.id = ch.mc_program_id)",
         0),
        ("legacy_mcidがNULLのmc_programs",
         "SELECT COUNT(*) FROM mc_programs WHERE legacy_mcid IS NULL",
         0),
        ("legacy_kakoidがNULLのmc_programs",
         "SELECT COUNT(*) FROM mc_programs WHERE legacy_kakoid IS NULL",
         0),
    ]

    for desc, q, expected in checks:
        try:
            pc.execute(q)
            cnt = pc.fetchone()[0]
            ok = cnt == expected
            status = OK if ok else NG
            if not ok:
                all_ok = False
            log.info(f"  {status} {desc}: {cnt}件 (期待: {expected}件)")
        except Exception as e:
            log.error(f"  {NG} {desc}: クエリエラー {e}")
            all_ok = False

    return all_ok


# =============================================================================
# L4: 共通加工確認
# =============================================================================
def check_l4_common_machining(sc, pc):
    log.info("\n" + "="*60)
    log.info("L4: 共通加工確認")
    log.info("="*60)

    # 同一machining_idを持つmc_programsを抽出
    pc.execute("""
        SELECT machining_id, COUNT(*) as cnt
        FROM mc_programs
        GROUP BY machining_id
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 20
    """)
    common_rows = pc.fetchall()

    if not common_rows:
        log.info(f"  {WARN} 共通加工レコードが見つかりません（正常移行されていれば複数件あるはず）")
        return False

    log.info(f"  共通加工グループ数: {len(common_rows)}件（上位20件表示）")
    all_ok = True

    for (machining_id, mc_count) in common_rows[:10]:
        # このmachining_idに紐付くmcid一覧
        pc.execute("""
            SELECT id, legacy_mcid FROM mc_programs
            WHERE machining_id = %s
            ORDER BY legacy_mcid
        """, (machining_id,))
        pg_mcs = pc.fetchall()

        # 各MCのツーリング件数
        tooling_counts = []
        for (pg_id, legacy_mcid) in pg_mcs:
            pc.execute("SELECT COUNT(*) FROM mc_tooling WHERE mc_program_id = %s", (pg_id,))
            t_cnt = pc.fetchone()[0]
            tooling_counts.append(t_cnt)

        # 共通加工では全MCが同じツーリング件数を持つべき
        if len(set(tooling_counts)) == 1:
            log.info(f"  {OK} machining_id={machining_id}: {mc_count}件のMCが各{tooling_counts[0]}件ツーリングを共有")
        elif all(c == 0 for c in tooling_counts):
            log.warning(f"  {WARN} machining_id={machining_id}: 全MCのツーリングが0件")
        else:
            log.error(f"  {NG} machining_id={machining_id}: ツーリング件数が不均一 {tooling_counts}")
            all_ok = False

    return all_ok


# =============================================================================
# L5: ビジネスロジック確認（RC値）
# =============================================================================
def check_l5_rc(pc):
    log.info("\n" + "="*60)
    log.info("L5: ビジネスロジック確認（RC値 vs ツーリング件数）")
    log.info("="*60)

    pc.execute("""
        SELECT COUNT(*) FROM mc_programs
        WHERE rc IS NOT NULL AND rc > 0
    """)
    rc_set_cnt = pc.fetchone()[0]
    log.info(f"  rc>0のmc_programs: {rc_set_cnt}件")

    # RC値 ≠ ツーリング件数の件数を確認
    pc.execute("""
        SELECT COUNT(*) FROM mc_programs mp
        WHERE mp.rc IS NOT NULL
          AND mp.rc != (
              SELECT COUNT(*) FROM mc_tooling mt
              WHERE mt.mc_program_id = mp.id
          )
    """)
    mismatch_cnt = pc.fetchone()[0]

    if mismatch_cnt == 0:
        log.info(f"  {OK} RC値とツーリング件数が全件一致")
        return True
    else:
        log.warning(f"  {WARN} RC値とツーリング件数が不一致: {mismatch_cnt}件")
        # 上位件数表示
        pc.execute("""
            SELECT mp.id, mp.legacy_mcid, mp.rc,
                   (SELECT COUNT(*) FROM mc_tooling mt WHERE mt.mc_program_id = mp.id) as actual_cnt
            FROM mc_programs mp
            WHERE mp.rc IS NOT NULL
              AND mp.rc != (
                  SELECT COUNT(*) FROM mc_tooling mt
                  WHERE mt.mc_program_id = mp.id
              )
            ORDER BY ABS(mp.rc - (
                SELECT COUNT(*) FROM mc_tooling mt WHERE mt.mc_program_id = mp.id
            )) DESC
            LIMIT 10
        """)
        for r in pc.fetchall():
            log.info(f"    mc_id={r[0]} legacy_mcid={r[1]} rc={r[2]} actual={r[3]}")
        return mismatch_cnt < 100  # 100件未満なら警告止まり


# =============================================================================
# 追加確認: MCIDで検索の再現テスト
# =============================================================================
def check_mcid_search(sc, pc, mcids):
    """
    「MCIDで検索すると関係ないMC情報が表示される」バグの再現確認。
    旧DB(MCID) → 新DB(mc_programs.legacy_mcid) の対応確認。
    """
    log.info("\n" + "="*60)
    log.info("追加確認: MCIDによる検索結果の正確性確認")
    log.info("="*60)

    all_ok = True

    for mcid in mcids:
        # 旧DBの正解
        sc.execute("""
            SELECT mc.MCID, mc.部品ID, mc.加工ID, m.メインPGNo
            FROM [imotomc].[dbo].[ACC_MC] mc
            INNER JOIN [imotomc].[dbo].[ACC_マシニング] m ON mc.加工ID = m.加工ID
            WHERE mc.MCID = %s AND m.削除区分 = 0
        """, (mcid,))
        ss_row = sc.fetchone()

        if ss_row is None:
            log.warning(f"  MCID={mcid} は旧DBに存在しません")
            continue

        # 新DBの検索結果
        pc.execute("""
            SELECT mp.id, mp.legacy_mcid, mp.machining_id, mp.o_number,
                   p.part_id as part_code, p.drawing_no
            FROM mc_programs mp
            LEFT JOIN parts p ON mp.part_id = p.id
            WHERE mp.legacy_mcid = %s
        """, (mcid,))
        pg_rows = pc.fetchall()

        if len(pg_rows) == 0:
            log.error(f"  {NG} MCID={mcid}: 新DBに存在しない")
            all_ok = False
        elif len(pg_rows) > 1:
            log.error(f"  {NG} MCID={mcid}: 新DBに{len(pg_rows)}件ある（重複）")
            all_ok = False
        else:
            pg_row = pg_rows[0]
            pg_machining = pg_row[2]
            ss_kako = ss_row[2]

            if pg_machining == ss_kako:
                log.info(f"  {OK} MCID={mcid}: 旧加工ID={ss_kako} == 新machining_id={pg_machining} "
                         f"部品={pg_row[4]} 図面={pg_row[5]}")
            else:
                log.error(f"  {NG} MCID={mcid}: 旧加工ID={ss_kako} != 新machining_id={pg_machining}")
                all_ok = False

    return all_ok


# =============================================================================
# フルレポート生成
# =============================================================================
def full_report(sc, pc, sample_mcids):
    log.info("\n" + "="*60)
    log.info(f"  MachCore MC データ整合性確認レポート")
    log.info(f"  実行日時: {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info("="*60)

    results = {}

    ok1, counts = check_l1_counts(sc, pc)
    results['L1_件数'] = OK if ok1 else NG

    ok2 = check_l2_sample(sc, pc, sample_mcids)
    results['L2_サンプル'] = OK if ok2 else NG

    ok3 = check_l3_referential(pc)
    results['L3_参照整合性'] = OK if ok3 else NG

    ok4 = check_l4_common_machining(sc, pc)
    results['L4_共通加工'] = OK if ok4 else NG

    ok5 = check_l5_rc(pc)
    results['L5_RC値'] = OK if ok5 else NG

    ok6 = check_mcid_search(sc, pc, sample_mcids)
    results['追加_MCID検索'] = OK if ok6 else NG

    log.info("\n" + "="*60)
    log.info("  最終判定サマリー")
    log.info("="*60)
    all_pass = True
    for check, status in results.items():
        log.info(f"  {status} {check}")
        if status == NG:
            all_pass = False

    if all_pass:
        log.info("\n  🎉 全チェック合格！移行データは正常です。")
    else:
        log.error("\n  ⚠️  問題が検出されました。ログを確認し、再移行を検討してください。")

    log.info(f"\n  ログファイル: {log_file}")
    return all_pass


# =============================================================================
# メイン
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='MachCore MC整合性確認スクリプト v1.0')
    parser.add_argument('--full-report', action='store_true', help='全レベル確認レポート')
    parser.add_argument('--mcid', type=int, action='append', default=[], help='確認するMCID（複数指定可）')
    parser.add_argument('--level', type=int, nargs='+', help='確認レベル指定 (1-5)')
    args = parser.parse_args()

    # デフォルトサンプルMCID
    sample_mcids = args.mcid if args.mcid else [7, 100, 500, 1000, 5000, 8964]

    sql = pymssql.connect(**SS_CONFIG)
    pg = psycopg2.connect(PG_DSN)
    sc = sql.cursor()
    pc = pg.cursor()

    try:
        if args.full_report or not args.level:
            result = full_report(sc, pc, sample_mcids)
            sys.exit(0 if result else 1)
        else:
            for level in args.level:
                if level == 1:
                    check_l1_counts(sc, pc)
                elif level == 2:
                    check_l2_sample(sc, pc, sample_mcids)
                elif level == 3:
                    check_l3_referential(pc)
                elif level == 4:
                    check_l4_common_machining(sc, pc)
                elif level == 5:
                    check_l5_rc(pc)

    except Exception as e:
        log.exception(f"確認中にエラー: {e}")
        sys.exit(1)
    finally:
        sc.close()
        pc.close()
        sql.close()
        pg.close()


if __name__ == '__main__':
    main()
