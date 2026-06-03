#!/usr/bin/env python3
"""
fix_mc_pg_photos_v1c.py
正規表現エスケープ文字列の修正
"""
import subprocess, sys

BASE      = "/home/karkyon/projects/machcore"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 壊れた正規表現を修正
OLD_RE = r"const count = (pgContent.match(new RegExp(pgEditorSearch.replace(/[.*+?^${}()|[\]\]/g,'\$&'), 'g')) ?? []).length;"
NEW_RE = r"const escaped = pgEditorSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); const count = (pgContent.match(new RegExp(escaped, 'g')) ?? []).length;"

if OLD_RE in src:
    src = src.replace(OLD_RE, NEW_RE, 1)
    print("  OK: 正規表現エスケープ修正")
else:
    # 別パターン確認
    idx = src.find("pgEditorSearch.replace")
    if idx != -1:
        print("  CONTEXT:", repr(src[max(0,idx-20):idx+120]))
    print("  WARN: パターン不一致")
    sys.exit(1)

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

print("=== Web ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -15",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr[-300:])
    sys.exit(1)

print("=== PM2 再起動 ===")
subprocess.run("pm2 restart machcore-web && pm2 ls", shell=True)

print("=== git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: pg_photos v1c - fix regex escape in PG editor" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
