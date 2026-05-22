#!/usr/bin/env python3
"""
fix_v54.py
1. page.tsx: sessionType="WORK_RECORD" → "work_record"
2. record/page.tsx: sessionType="MC_WORK_RECORD" → "work_record"
3. DBマイグレーション: mc_setup_sheet_logs.work_collected カラム追加
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

PAGE   = os.path.join(ROOT, "apps/web/app/page.tsx")
RECORD = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/record/page.tsx")

# 1. page.tsx: WORK_RECORD → work_record
patch(PAGE,
    'sessionType="WORK_RECORD"',
    'sessionType="work_record"',
    "page.tsx sessionType WORK_RECORD → work_record"
)

# 2. record/page.tsx: MC_WORK_RECORD → work_record
patch(RECORD,
    'sessionType="MC_WORK_RECORD"',
    'sessionType="work_record"',
    "record/page.tsx sessionType MC_WORK_RECORD → work_record"
)

# 3. DBマイグレーション: work_collected カラム追加（IF NOT EXISTS で冪等）
print("\n--- DB マイグレーション ---")
sql = """
ALTER TABLE mc_setup_sheet_logs
  ADD COLUMN IF NOT EXISTS work_collected BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE mc_setup_sheet_logs
  ADD COLUMN IF NOT EXISTS work_collected_at TIMESTAMP WITH TIME ZONE;
"""
r = subprocess.run(
    f'docker exec machcore-postgres psql -U machcore -d machcore_dev -c "{sql}"',
    shell=True, capture_output=True, text=True
)
print(r.stdout.strip())
if r.stderr.strip():
    print("STDERR:", r.stderr.strip())
if r.returncode != 0:
    print("DB migration FAILED — abort"); sys.exit(1)

print("\n--- npm run build ---")
r = subprocess.run("cd ~/projects/machcore/apps/web && npm run build", shell=True, capture_output=True, text=True)
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
stderr_clean = "\n".join(l for l in r.stderr.split("\n") if "react-pdf" not in l)
if stderr_clean.strip():
    print("STDERR:", stderr_clean[-500:])

if r.returncode != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

print("\n--- pm2 restart web ---")
subprocess.run("pm2 restart machcore-web --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "fix: sessionType WORK_RECORD→work_record + work_collected DBカラム追加 v54" && git push',
    shell=True
)
print("DONE")
