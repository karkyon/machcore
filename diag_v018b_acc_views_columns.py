#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診断専用(読み取りのみ)

目的:
  diag_v017の結果、imotomc データベース内に以下のビューが
  MC側と同じ命名規則(ACC_*)で既に存在することが判明した:
    ACC_NC, ACC_Lathe, ACC_Tool, ACC_FD, ACC_Machine, ACC_Staff, ACC_History
  (imotomc2 にも同名ビューが存在するが、MC側が imotomc を使っているため
   まず imotomc を優先して確認する)

  nc_full_import.py を正確に実装するため、これら7ビューの
  カラム名・型・サンプルデータを確認する。
  migrate_v2.ts が前提としていたCSVのカラム名(NC_id, B_id, K_id, L, Clamp,
  Machine, Tm, Ts, FD_name, F_name, oNo, Note, Fig, Photo, Ver, Reco_P, Reco_D,
  T_id, No, Shave1, Shave2, Chip, Holder, NorzR, m_id, Model, St_id, S_name,
  Password, Hist_id, Mc, Out_Ver, Out_Cont, Out_Op, Out_Date, In_Ver, In_Cont,
  In_Op, In_Date, Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P)
  とビュー側のカラム名が一致するとは限らないため、推測せず実際のビュー定義から
  確認する。
"""
import sys

try:
    import pymssql
except ImportError:
    print("[ERROR] pymssql がインストールされていません。")
    sys.exit(1)

SS_SERVER = "192.168.1.9"
SS_USER = "sa"
SS_PASS = "RTW65b"
SS_DB = "imotomc"

TARGET_VIEWS = ["ACC_NC", "ACC_Lathe", "ACC_Tool", "ACC_FD", "ACC_Machine", "ACC_Staff", "ACC_History"]


def connect():
    return pymssql.connect(server=SS_SERVER, user=SS_USER, password=SS_PASS,
                            database=SS_DB, tds_version='7.4')


print("=" * 70)
print(f"【診断】{SS_DB} 内の7ビューのカラム構造・サンプルデータ確認")
print("=" * 70)

conn = connect()
cur = conn.cursor()

for view in TARGET_VIEWS:
    print(f"\n{'='*60}\n  VIEW: {view}\n{'='*60}")
    try:
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """, (view,))
        cols = cur.fetchall()
        if not cols:
            print(f"  [WARN] カラム情報が取得できませんでした(ビューが存在しないか権限不足)")
            continue
        print("  カラム一覧:")
        for cname, ctype, clen in cols:
            len_str = f"({clen})" if clen else ""
            print(f"    {cname:30s} {ctype}{len_str}")
    except Exception as e:
        print(f"  [ERROR] カラム取得失敗: {e}")
        continue

    # サンプルデータ取得(角括弧でエスケープして安全に)
    try:
        cur.execute(f"SELECT TOP 3 * FROM [{view}]")
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]
        print(f"\n  サンプルデータ(先頭3件):")
        print(f"    カラム順: {col_names}")
        for i, row in enumerate(rows):
            print(f"    行{i+1}: {row}")
    except Exception as e:
        print(f"  [ERROR] サンプルデータ取得失敗: {e}")

    # 件数確認
    try:
        cur.execute(f"SELECT COUNT(*) FROM [{view}]")
        cnt = cur.fetchone()[0]
        print(f"\n  総件数: {cnt}")
    except Exception as e:
        print(f"  [ERROR] 件数取得失敗: {e}")

conn.close()

print("\n" + "=" * 70)
print("【診断完了】")
print("各ビューのカラム名を確認し、migrate_v2.ts のCSVカラム名と対応付けてください。")
print("対応が取れれば nc_full_import.py の本実装に進めます。")
print("=" * 70)
