#!/usr/bin/env python3
"""fix_v97c: print/page copy.tsx 削除してビルド通す"""
import subprocess, sys, os, glob

ROOT = os.path.expanduser("~/projects/machcore")

# 不要なコピーファイルを全削除
patterns = [
    f"{ROOT}/apps/web/app/mc/[mc_id]/print/page copy.tsx",
    f"{ROOT}/apps/web/app/mc/[mc_id]/print/page copy*.tsx",
    f"{ROOT}/apps/web/**/*copy*.tsx",
    f"{ROOT}/apps/web/**/*.bak",
]
deleted = []
for pat in patterns:
    for f in glob.glob(pat, recursive=True):
        os.remove(f)
        deleted.append(f)
        print(f"DELETED: {f}")

if not deleted:
    print("INFO: 削除対象ファイルなし — 直接パス削除試行")
    target = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page copy.tsx"
    if os.path.exists(target):
        os.remove(target)
        print(f"DELETED: {target}")

# mc/[mc_id] ディレクトリ内のコピー系ファイルを確認
import subprocess as sp
r = sp.run(["find", f"{ROOT}/apps/web/app/mc", "-name", "* *", "-o", "-name", "*.bak"],
           capture_output=True, text=True)
if r.stdout.strip():
    for f in r.stdout.strip().split('\n'):
        if f and os.path.exists(f):
            os.remove(f)
            print(f"DELETED: {f}")

print("\n--- build web ---")
r = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-3000:])
if r.stderr: print("STDERR:", r.stderr[-2000:])
if r.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-2000:])
if r.stderr: print("STDERR:", r.stderr[-1000:])
if r.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v97c): page copy.tsx削除 ビルドエラー解消"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v97c")
