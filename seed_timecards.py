#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_timecards.py
4/1以降（土日除く）のダミータイムカードレコードを登録
既存データは削除してから再登録
"""
import subprocess, datetime

DB_CMD = ["docker", "exec", "machcore-postgres", "psql", "-U", "machcore", "-d", "machcore_dev", "-c"]

def run_sql(sql):
    r = subprocess.run(DB_CMD + [sql], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"SQL Error: {r.stderr.strip()[:200]}")
    return r

# 既存データ削除（4/1以降）
run_sql("DELETE FROM machine_timecards WHERE work_date >= \'2026-04-01\';")
print("✅ 既存タイムカードデータ削除（4/1以降）")

# 有効機械取得
r = subprocess.run(DB_CMD + ["SELECT id, machine_code FROM machines WHERE is_active = true ORDER BY sort_order;"],
    capture_output=True, text=True)
lines = r.stdout.strip().split("\n")
machines = []
for line in lines:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) == 2:
        try:
            machines.append((int(parts[0]), parts[1]))
        except ValueError:
            pass
print(f"✅ 有効機械: {len(machines)}台 {[m[1] for m in machines]}")

# 4/1〜今日の平日ループ
start = datetime.date(2026, 4, 1)
end   = datetime.date.today()
cur   = start
inserted = 0
skipped  = 0

while cur <= end:
    dow = cur.weekday()  # 0=月 〜 6=日
    if dow >= 5:  # 土日スキップ
        skipped += 1
        cur += datetime.timedelta(days=1)
        continue

    dt_str = cur.strftime("%Y-%m-%d")
    for machine_id, machine_code in machines:
        sql = f"""INSERT INTO machine_timecards (machine_id, operator_id, work_date, start_time, end_time, note)
VALUES ({machine_id}, 1, \'{dt_str}\', \'{dt_str}T08:00:00\', \'{dt_str}T17:00:00\', \'自動生成ダミーデータ\')
ON CONFLICT DO NOTHING;"""
        run_sql(sql)
        inserted += 1

    cur += datetime.timedelta(days=1)

print(f"✅ 登録完了: {inserted}件 / スキップ(土日): {skipped}日")
