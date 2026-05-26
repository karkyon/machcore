#!/usr/bin/env python3
"""fix_v98b: record/page.tsx に StatusBadge import追加（正確なパターン）"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def rep(content, old, new, label):
    if old not in content:
        print(f"WARN: {label} — 不一致"); return content
    print(f"OK: {label}"); return content.replace(old, new, 1)

RECORD = f"{ROOT}/apps/web/app/mc/[mc_id]/record/page.tsx"
r = read(RECORD)

# StatusBadge import追加（正確なパターン）
r = rep(r,
    'import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";\nimport { useAuth } from "@/contexts/AuthContext";',
    'import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";\nimport { StatusBadge } from "@/components/nc/StatusBadge";\nimport { useAuth } from "@/contexts/AuthContext";',
    "record: StatusBadge import追加")

write(RECORD, r)

# edit の部品情報バーも確認して修正（WARN だったので現在のパターンを探す）
EDIT = f"{ROOT}/apps/web/app/mc/[mc_id]/edit/page.tsx"
e = read(EDIT)

# 現在のeditの部品情報バーのパターンを確認
if 'py-2.5 shrink-0' in e:
    e = rep(e,
        'py-2.5 shrink-0',
        'py-3 shrink-0',
        "edit: 部品情報バー py調整")
elif 'py-2 shrink-0' in e:
    e = rep(e,
        'py-2 shrink-0',
        'py-3 shrink-0',
        "edit: 部品情報バー py調整")

# drawingNoのフォントサイズをtext-2xlに
if 'text-teal-600 font-bold text-xl leading-none">{d.part.drawingNo}' in e:
    e = rep(e,
        'text-teal-600 font-bold text-xl leading-none">{d.part.drawingNo}',
        'text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}',
        "edit: 図番フォント text-2xl統一")

if 'text-slate-800 text-xl leading-none">{d.part.name}' in e:
    e = rep(e,
        'text-slate-800 text-xl leading-none">{d.part.name}',
        'text-slate-800 text-xl leading-none">{d.part.name}',
        "edit: 部品名フォント確認（変更なし）")

write(EDIT, e)

print("\n--- build web ---")
r2 = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r2.stdout[-3000:])
if r2.stderr: print("STDERR:", r2.stderr[-2000:])
if r2.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r2 = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r2.stdout[-2000:])
if r2.stderr: print("STDERR:", r2.stderr[-1000:])
if r2.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v98b): record StatusBadge import追加 ヘッダ統一"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v98b")
