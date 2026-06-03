#!/usr/bin/env python3
"""
fix_mc_pg_photos_v1d.py
pgContent.split の改行文字問題修正
"""
import subprocess, sys

BASE      = "/home/karkyon/projects/machcore"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 壊れた split('\n') を修正 - 実際の改行になっている
# pgContent.split(' (実際の改行) ').length を pgContent.split('\n').length に修正
bad = "pgContent.split('\n').length"
good = "pgContent.split('\\n').length"

# ファイル内の実際の文字列を確認
idx = src.find("pgContent.split(")
if idx != -1:
    print("  CONTEXT:", repr(src[idx:idx+50]))

# 壊れているパターン: split(' + 実際改行 + ')
import re
# 実際の改行を含むsplit呼び出しを検索・置換
pattern = "pgContent.split('\n').length"
# Pythonの文字列では \n は実際の改行
actual_bad = "pgContent.split('" + chr(10) + "').length"
actual_good = "pgContent.split('\\n').length"

if actual_bad in src:
    src = src.replace(actual_bad, actual_good, 1)
    print("  OK: split改行文字修正")
elif bad in src:
    src = src.replace(bad, good, 1)
    print("  OK: split文字修正（通常パターン）")
else:
    # より広い検索
    idx2 = src.find("pgContent.split(")
    if idx2 != -1:
        snippet = src[idx2:idx2+40]
        print("  WARN: 別パターン:", repr(snippet))
    # 直接置換
    src = re.sub(r"pgContent\.split\('[^']*'\)\.length", "pgContent.split('\\n').length", src)
    print("  OK: regex置換で修正")

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
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: pg_photos v1d - fix split newline literal" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
