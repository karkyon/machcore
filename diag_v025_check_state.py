# -*- coding: utf-8 -*-
"""
v025診断: 次回セッション開始時の状態確認(読み取り専用)
- unique_part_process制約がDBに実在するか
- 現在のNCデータ件数(ハンドオフ記載の7,852件等と一致するか)
- PM2プロセスの稼働状態
"""
import subprocess

DB_USER = "machcore"
DB_NAME = "machcore_dev"
CONTAINER = "machcore-postgres"

def psql(sql):
    cmd = ["docker", "exec", "-i", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-F", "|", "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] {r.stderr.strip()}")
        return None
    return r.stdout.strip()

print("=" * 70)
print("【v025診断】次回セッション開始時の状態確認")
print("=" * 70)

print("\n=== [1] unique_part_process制約の存在確認 ===")
out = psql("""
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'nc_programs'::regclass
  AND conname = 'unique_part_process';
""")
print(out if out else "(該当なし＝制約が存在しません)")

print("\n=== [2] nc_programs等の現在件数(ハンドオフ記載値との比較) ===")
for tbl in ["nc_programs", "nc_tools", "change_history", "setup_sheet_logs", "work_records"]:
    out = psql(f"SELECT COUNT(*) FROM {tbl} WHERE 1=1;" if tbl in ("nc_programs","nc_tools") else f"SELECT COUNT(*) FROM {tbl};")
    print(f"  {tbl}: {out}")

print("\n=== [2b] change_history/work_records のNC分のみ件数 ===")
out = psql("SELECT COUNT(*) FROM change_history WHERE nc_program_id IS NOT NULL;")
print(f"  change_history(NC分): {out}")
out = psql("SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL;")
print(f"  work_records(NC分): {out}")

print("\n=== [3] nc_programs.status分布 ===")
out = psql("SELECT status, COUNT(*) FROM nc_programs GROUP BY status ORDER BY status;")
print(out)

print("\n=== [4] machines件数(MC/NC/BOTH分布) ===")
out = psql("SELECT system_type, COUNT(*) FROM machines GROUP BY system_type ORDER BY system_type;")
print(out)

print("\n=== [5] users件数(MC/NC/BOTH分布) ===")
out = psql("SELECT system_type, COUNT(*) FROM users GROUP BY system_type ORDER BY system_type;")
print(out)

print("\n" + "=" * 70)
print("【診断完了】")
print("=" * 70)
