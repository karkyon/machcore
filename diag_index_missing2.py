#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_index_missing2.py
=========================
検証レポートの「インデックスプログラム_新システムにレコード無し」2件
(加工ID512・513)について、KARKYONさんの分析通り
「ACC_MCに加工IDレコード自体が存在しない孤立データ」であり、
前回確証済みのツーリング側11件と同根で対応不要かを確証する。

実行方法:
  python3 diag_index_missing2.py
"""
import pymssql
import psycopg2

PG_DSN       = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
SS_MC_SERVER = "192.168.1.9"
SS_MC_USER   = "sa"
SS_MC_PASS   = "RTW65b"
SS_MC_DB     = "imotomc"

TARGET_KAKOIDS = [512, 513]


def main():
    pg = psycopg2.connect(PG_DSN)
    pgc = pg.cursor()
    ss = pymssql.connect(server=SS_MC_SERVER, user=SS_MC_USER, password=SS_MC_PASS,
                         database=SS_MC_DB, tds_version="7.4")
    mcc = ss.cursor()

    for kakoid in TARGET_KAKOIDS:
        print(f"--- 加工ID={kakoid} ---")

        mcc.execute("SELECT 部品ID, MCID FROM ACC_MC WHERE 加工ID = %s", (kakoid,))
        mc_rows = mcc.fetchall()
        print(f"  ACC_MC: {len(mc_rows)}件 {mc_rows[:3]}")
        if not mc_rows:
            print("  → ACC_MCに加工IDのレコード自体が無い(前回確証済みのツーリング11件と同根)")

        pgc.execute("SELECT machining_id FROM mc_machining_details WHERE machining_id = %s", (kakoid,))
        mmd_row = pgc.fetchone()
        print(f"  mc_machining_details存在: {'YES' if mmd_row else 'NO'}")

        mcc.execute("SELECT COUNT(*) FROM ACC_インデックスプログラム WHERE 加工ID = %s", (kakoid,))
        ip_count = mcc.fetchone()[0]
        print(f"  ACC_インデックスプログラム行数: {ip_count}件")

        mcc.execute("SELECT COUNT(*) FROM ACC_ツーリング WHERE 加工ID = %s", (kakoid,))
        tooling_count = mcc.fetchone()[0]
        print(f"  ACC_ツーリング行数(前回確証分との重複確認): {tooling_count}件")
        print()

    ss.close()
    pg.close()
    print("=== 診断完了 ===")
    print("両方ともACC_MCにレコードが無ければ、KARKYONさんの分析通り")
    print("「旧システム上に加工IDの母体となるマシニング情報がない」ことが確定し、")
    print("対応不要(調査対象外)で確定します。")


if __name__ == "__main__":
    main()
