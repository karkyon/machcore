#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_order_distribution.py
=============================
ACC_ツーリング.順番列の実データ分布を正確に調査する。
今回の smallint out of range (786件) の原因を確証込みで特定するため、
①順番列の最大値・分布 ②10倍後にsmallint上限(32767)を超える件数とその実値
③順番列がNULL/異常値のケースの内訳 を出力する。

実行方法:
  python3 diag_order_distribution.py
"""
import pymssql

SS_MC_SERVER = "192.168.1.9"
SS_MC_USER   = "sa"
SS_MC_PASS   = "RTW65b"
SS_MC_DB     = "imotomc"


def main():
    conn = pymssql.connect(server=SS_MC_SERVER, user=SS_MC_USER, password=SS_MC_PASS,
                           database=SS_MC_DB, tds_version="7.4")
    cur = conn.cursor()

    print("=== ① 順番列の基本統計 ===")
    cur.execute("SELECT MIN(順番), MAX(順番), COUNT(*), COUNT(順番) FROM ACC_ツーリング")
    row = cur.fetchone()
    print(f"  MIN={row[0]} MAX={row[1]} 全件数={row[2]} 順番NOT NULL件数={row[3]}")

    print("\n=== ② 10倍後にsmallint上限(32767)を超える行 (順番 > 3276.7) ===")
    cur.execute("""
        SELECT 加工ID, 順番, N, ツーリングID
        FROM ACC_ツーリング
        WHERE 順番 > 3276.7
        ORDER BY 順番 DESC
    """)
    over_rows = cur.fetchall()
    print(f"  該当件数: {len(over_rows)}件")
    for r in over_rows[:30]:
        print(f"    加工ID={r[0]} 順番={r[1]} N={r[2]} ツーリングID={r[3]}")

    print("\n=== ③ 順番列の値の桁数別分布 ===")
    cur.execute("""
        SELECT
            CASE
                WHEN 順番 IS NULL THEN 'NULL'
                WHEN 順番 < 0 THEN '負数'
                WHEN 順番 < 100 THEN '0-99'
                WHEN 順番 < 1000 THEN '100-999'
                WHEN 順番 < 3277 THEN '1000-3276'
                WHEN 順番 < 10000 THEN '3277-9999(10倍超え)'
                ELSE '10000以上(10倍超え)'
            END AS bucket,
            COUNT(*) AS cnt
        FROM ACC_ツーリング
        GROUP BY
            CASE
                WHEN 順番 IS NULL THEN 'NULL'
                WHEN 順番 < 0 THEN '負数'
                WHEN 順番 < 100 THEN '0-99'
                WHEN 順番 < 1000 THEN '100-999'
                WHEN 順番 < 3277 THEN '1000-3276'
                WHEN 順番 < 10000 THEN '3277-9999(10倍超え)'
                ELSE '10000以上(10倍超え)'
            END
        ORDER BY cnt DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}件")

    print("\n=== ④ 加工IDごとの順番最大値TOP10(異常に大きい加工IDを特定) ===")
    cur.execute("""
        SELECT TOP 10 加工ID, MAX(順番) AS max_order, COUNT(*) AS cnt
        FROM ACC_ツーリング
        WHERE 加工ID IS NOT NULL
        GROUP BY 加工ID
        ORDER BY MAX(順番) DESC
    """)
    for r in cur.fetchall():
        print(f"  加工ID={r[0]} 順番最大値={r[1]} 行数={r[2]}")

    conn.close()
    print("\n=== 診断完了 ===")


if __name__ == "__main__":
    main()
