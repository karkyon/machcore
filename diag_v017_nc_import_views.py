#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診断専用(読み取りのみ、一切のデータ変更を行わない)

目的:
  NC側データインポート(nc_full_import.py新規作成)に必要な、
  SQL Server側のリンクサーバビュー(ACCESSのRAWテーブルを直結したVIEW)が
  実際に作成されているかを確認する。

背景:
  リポジトリには既に apps/api/migrate_v2.ts という、CSVファイルベースの
  NC移行スクリプトが存在していた(過去のセッションで見落とされていた)。
  このスクリプトが要求するデータソースは以下9種類:
    - buhin.csv        → 部品マスタ          (MC側は v_旧部品マスタ で代替済み、parts共通)
    - nonyusaki.csv     → 得意先マスタ        (MC側は v_旧得意先マスタ で代替済み、parts共通)
    - t1_nc.csv         → t1_NC   (NC_id, B_id, K_id)
    - t2_lathe.csv      → t2_Lathe(K_id, L, Clamp, Machine, Tm, Ts, FD_name, F_name, oNo, Note,
                                    Fig, Photo, Ver, Reco_P, Reco_D)
    - t3_tool.csv       → t3_Tool (T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note)
    - t_d_fd.csv        → t_d_FD  (FD_id, FD_name) フォルダ名マスタ
    - t_d_machine.csv   → t_d_Machine (m_id, Model)
    - t_d_staff.csv     → t_d_Staff   (St_id, S_name, Password)
    - t_k_history.csv   → t_k_History (Hist_id, K_id, NC_id, Mc,
                                        Out_Ver/Out_Cont/Out_Op/Out_Date,
                                        In_Ver/In_Cont/In_Op/In_Date,
                                        Dan_Op/Dan_H/Dan_M, La_Op/La_H/La_M, P)

  parts/clients は既存の parts テーブル(MC側で既に同期済み)を再利用するため、
  NC側で新たに用意する必要があるのは t1_nc 〜 t_k_history の7種類。

  MC側は imotomc データベース内のビュー(ACC_MC, ACC_マシニングraw, ACC_ツーリング,
  ACC_変更履歴)を使っている。NC側は別データベース(例: imotodb 内、または新規
  imotonc 等)に作られている可能性があるため、複数のDBを横断して確認する。

確認項目:
  [1] SQL Serverへの接続確認
  [2] 接続可能な全データベース一覧
  [3] 各DB内で「NC」「ﾌｧｲﾙ」「鍒ｶ」等のNC関連と思われるテーブル/ビュー名を検索
  [4] migrate_v2.ts が期待する7種のテーブル名(t1_NC, t2_Lathe, t3_Tool, t_d_FD,
      t_d_Machine, t_d_Staff, t_k_History)そのものの名前のオブジェクトがどこかに
      存在するか、ピンポイントで検索
  [5] 見つかったオブジェクトのカラム一覧(あれば)
"""
import sys

try:
    import pymssql
except ImportError:
    print("[ERROR] pymssql がインストールされていません。")
    print("  pip install pymssql --break-system-packages")
    sys.exit(1)

SS_SERVER = "192.168.1.9"
SS_USER = "sa"
SS_PASS = "RTW65b"

# まず接続を試す候補データベース(MC側で使われている2つ + 推測される命名)
CANDIDATE_DBS = ["imotomc", "imotodb", "imotonc", "master"]

TARGET_TABLES = [
    "t1_NC", "t2_Lathe", "t3_Tool",
    "t_d_FD", "t_d_Machine", "t_d_Staff", "t_k_History",
]


def connect(db):
    return pymssql.connect(server=SS_SERVER, user=SS_USER, password=SS_PASS,
                            database=db, tds_version='7.4')


print("=" * 70)
print("【診断】NCインポート用 SQL Serverビュー存在確認(読み取りのみ)")
print("=" * 70)

print("\n=== [1] SQL Server接続確認 ===")
conn = None
connected_db = None
for db in CANDIDATE_DBS:
    try:
        conn = connect(db)
        connected_db = db
        print(f"[OK] {db} への接続成功")
        break
    except Exception as e:
        print(f"[INFO] {db} への接続失敗: {e}")

if not conn:
    print("[FAIL] どのデータベースにも接続できませんでした。診断を中止します。")
    sys.exit(1)

print("\n=== [2] サーバ上の全データベース一覧 ===")
cur = conn.cursor()
try:
    cur.execute("SELECT name FROM sys.databases ORDER BY name;")
    all_dbs = [r[0] for r in cur.fetchall()]
    for d in all_dbs:
        print(f"  - {d}")
except Exception as e:
    print(f"[WARN] データベース一覧取得失敗: {e}")
    all_dbs = [connected_db]
conn.close()

# user databaseのみ(システムDB除外)を対象にテーブル探索
SYSTEM_DBS = {"master", "model", "msdb", "tempdb"}
scan_dbs = [d for d in all_dbs if d not in SYSTEM_DBS] or [connected_db]

print(f"\n=== [3] 各DBで NC関連テーブル/ビュー名を検索 (対象DB: {scan_dbs}) ===")
found_locations = {}  # table_name -> [(db, schema, name, type), ...]

for db in scan_dbs:
    try:
        c = connect(db)
    except Exception as e:
        print(f"  [SKIP] {db}: 接続不可 ({e})")
        continue
    cu = c.cursor()
    try:
        cu.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            ORDER BY TABLE_NAME;
        """)
        rows = cu.fetchall()
        print(f"\n  --- DB: {db} (全オブジェクト数: {len(rows)}) ---")
        for schema, name, ttype in rows:
            # NC関連の可能性があるものだけ表示(t1,t2,t3,t_d,t_k, NC, ACC等を含む)
            lname = name.lower()
            if (lname.startswith('t1_') or lname.startswith('t2_') or lname.startswith('t3_')
                    or lname.startswith('t_d_') or lname.startswith('t_k_')
                    or 'nc' in lname or 'acc_' in lname.replace('acc_', 'acc_')):
                print(f"    {schema}.{name} [{ttype}]")
    except Exception as e:
        print(f"  [WARN] {db} のテーブル一覧取得失敗: {e}")
    c.close()

print(f"\n=== [4] migrate_v2.ts が期待する7テーブル名そのものの存在確認 ===")
for target in TARGET_TABLES:
    found = False
    for db in scan_dbs:
        try:
            c = connect(db)
            cu = c.cursor()
            cu.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = %s;
            """, (target,))
            rows = cu.fetchall()
            for schema, name, ttype in rows:
                print(f"  [FOUND] {target} -> {db}.{schema}.{name} [{ttype}]")
                found = True
                found_locations[target] = (db, schema, name)
            c.close()
        except Exception:
            continue
    if not found:
        print(f"  [NOT FOUND] {target}")

print("\n=== [5] 見つかったオブジェクトのカラム一覧 ===")
for target, (db, schema, name) in found_locations.items():
    try:
        c = connect(db)
        cu = c.cursor()
        cu.execute("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """, (schema, name))
        cols = cu.fetchall()
        print(f"\n  --- {db}.{schema}.{name} ---")
        for cname, ctype in cols:
            print(f"    {cname} ({ctype})")
        c.close()
    except Exception as e:
        print(f"  [WARN] {target} のカラム取得失敗: {e}")

print("\n" + "=" * 70)
print("【診断完了】")
print("[4]で7テーブル全てが[FOUND]になっていれば、nc_full_import.pyの")
print("本実装に進めます。[NOT FOUND]がある場合は、該当ビューの作成を")
print("お願いするか、ビュー名・スキーマ名を教えてください。")
print("=" * 70)
