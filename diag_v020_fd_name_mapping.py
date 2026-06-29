#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診断専用(読み取りのみ)

目的:
  nc_full_import.py(PHASE1)の folder_name 解決ロジックを正確に実装するため、
  ACC_Lathe.FD_name 列の実際の意味を確認する。

  migrate_v2.ts (旧CSVベース移行スクリプト)では、
  fdMap.set(FD_id, FD_name) というマップを作り、
  fdMap.get(t2_Lathe.FD_name) でフォルダ名を解決していた。
  つまり t2_Lathe.FD_name 列は実は「FD_idへの参照値」であるという想定だった。

  しかし v018b診断結果では ACC_Lathe.FD_name の実データは 'A' のような
  1文字のアルファベットであり、ACC_FD.FD_id は整数(1,2,3...)、
  ACC_FD.FD_name は「森精機　Ｎｏ１」のような正式名称だった。
  'A'が整数IDの文字列表現とは考えにくいため、本当に migrate_v2.ts の
  ロジックが正しいのか、確実な根拠を持って判断する必要がある。

確認項目:
  [1] ACC_Lathe.FD_name の値の分布(全パターンと件数)
  [2] ACC_FD の全件(FD_id, FD_name)
  [3] [1]の値が[2]のFD_idの文字列表現と一致するものがあるか
  [4] ACC_Lathe.FD_name が ACC_FD.FD_name と直接一致するものがあるか(逆の可能性)
  [5] 結論: どちらの対応関係が正しいかを件数で判定
"""
import pymssql

SS_SERVER = "192.168.1.9"
SS_USER = "sa"
SS_PASS = "RTW65b"
SS_DB = "imotomc"


def connect():
    return pymssql.connect(server=SS_SERVER, user=SS_USER, password=SS_PASS,
                            database=SS_DB, tds_version='7.4')


print("=" * 70)
print("【診断】ACC_Lathe.FD_name の実際の意味を確認(読み取りのみ)")
print("=" * 70)

conn = connect()
cur = conn.cursor()

print("\n=== [1] ACC_Lathe.FD_name の値の分布(全パターン、上位30件) ===")
cur.execute("""
    SELECT TOP 30 FD_name, COUNT(*) AS cnt
    FROM ACC_Lathe
    GROUP BY FD_name
    ORDER BY cnt DESC
""")
for fd_name, cnt in cur.fetchall():
    print(f"  '{fd_name}': {cnt}件")

print("\n=== [2] ACC_FD 全件 ===")
cur.execute("SELECT FD_id, FD_name FROM ACC_FD ORDER BY FD_id")
fd_all = cur.fetchall()
for fd_id, fd_name in fd_all:
    print(f"  FD_id={fd_id}: '{fd_name}'")

print("\n=== [3] ACC_Lathe.FD_name の値が ACC_FD.FD_id(整数)の文字列表現と一致するか ===")
fd_ids_str = {str(r[0]) for r in fd_all}
cur.execute("SELECT DISTINCT FD_name FROM ACC_Lathe")
lathe_fd_names = [r[0] for r in cur.fetchall()]
match_as_id = [v for v in lathe_fd_names if v is not None and str(v).strip() in fd_ids_str]
print(f"  ACC_Lathe.FD_nameの値の種類: {len(lathe_fd_names)}種類")
print(f"  そのうちFD_id文字列と一致: {len(match_as_id)}種類 -> {match_as_id[:20]}")

print("\n=== [4] ACC_Lathe.FD_name の値が ACC_FD.FD_name(正式名称)と直接一致するか ===")
fd_names_set = {r[1] for r in fd_all}
match_as_name = [v for v in lathe_fd_names if v is not None and v in fd_names_set]
print(f"  ACC_FD.FD_nameと直接一致: {len(match_as_name)}種類 -> {match_as_name[:20]}")

print("\n=== [5] 結論用データ: ACC_Lathe.FD_nameの値とその件数を全部表示 ===")
cur.execute("""
    SELECT FD_name, COUNT(*) AS cnt
    FROM ACC_Lathe
    GROUP BY FD_name
    ORDER BY FD_name
""")
all_patterns = cur.fetchall()
for fd_name, cnt in all_patterns:
    print(f"  '{fd_name}': {cnt}件")

conn.close()

print("\n" + "=" * 70)
print("【診断完了】")
print("[3]の一致件数が多ければ FD_id参照説(migrate_v2.ts方式)が正しい。")
print("[4]の一致件数が多ければ ACC_Lathe.FD_name自体が既にフォルダ名(直接使用)説が正しい。")
print("両方0件、または[5]の値が'A'等の単純な記号であれば、第3の可能性")
print("(機械の設置場所や系列を表す独自コードで、フォルダ名とは無関係)を検討する必要がある。")
print("=" * 70)
