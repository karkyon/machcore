#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
緊急診断専用(読み取りのみ、一切のデータ変更を行わない)

【発生事象】
  nc_full_import.py本番実行で、PHASE1の全INSERT(8797件)が
  "constraint "unique_part_process" for table "nc_programs" does not exist"
  で全件エラーとなり、nc_programs等のNC関連データが全件0になった。

  既存データは全破棄(DELETE)済みのため、現在NC側データが空の状態である。

【原因の仮説】
  Prismaスキーマファイル(schema.prisma)には
  @@unique([partId, processL], name: "unique_part_process")
  が定義されているが、実際のPostgreSQL DBにはこの制約(または
  対応するUNIQUE INDEX)が一度も作成されていない可能性が高い。

【確認項目(読み取りのみ)】
  [1] nc_programsテーブルの全制約一覧(制約名・種別・対象カラム)
  [2] nc_programsテーブルの全インデックス一覧
  [3] part_id, process_l の組み合わせで重複が実際に存在するか
      (重複があれば、UNIQUE制約をこれから追加する際にエラーになるため
       先に確認が必要)
  [4] 現在のnc_programsの件数(0件であることの再確認)
"""
import subprocess

CONTAINER = "machcore-postgres"
DB = "machcore_dev"
DB_USER = "machcore"


def psql(sql, label=None):
    if label:
        print(f"\n--- {label} ---")
    cmd = [
        "docker", "exec", "-i", CONTAINER,
        "psql", "-U", DB_USER, "-d", DB, "-c", sql
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"[ERROR] {result.stderr}")
    return result.stdout.strip()


print("=" * 70)
print("【緊急診断】nc_programsテーブルの実際の制約状態を確認")
print("=" * 70)

print("\n=== [1] nc_programsテーブルの全制約一覧 ===")
psql("""
SELECT conname AS constraint_name, contype AS constraint_type,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'nc_programs'::regclass
ORDER BY conname;
""", "nc_programs 制約一覧")

print("\n=== [2] nc_programsテーブルの全インデックス一覧 ===")
psql("""
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'nc_programs'
ORDER BY indexname;
""", "nc_programs インデックス一覧")

print("\n=== [3] part_id + process_l の重複確認(現在0件のはずだが念のため) ===")
psql("""
SELECT part_id, process_l, COUNT(*)
FROM nc_programs
GROUP BY part_id, process_l
HAVING COUNT(*) > 1;
""", "重複行(0件であるはず)")

print("\n=== [4] nc_programs現在の件数 ===")
psql("SELECT COUNT(*) FROM nc_programs;", "nc_programs件数")

print("\n=== [5] 他の主要テーブルの制約有無も横断確認(同様の問題が他にもあるか) ===")
for tbl in ["mc_programs", "machine_timecards", "users", "machines"]:
    psql(f"""
    SELECT conname, contype, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = '{tbl}'::regclass AND contype = 'u';
    """, f"{tbl} のUNIQUE制約")

print("\n" + "=" * 70)
print("【診断完了】")
print("[1]に unique_part_process が無ければ、制約未作成が確定。")
print("[3]が0件であれば、安全にUNIQUE制約を追加できる。")
print("=" * 70)
