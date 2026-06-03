#!/usr/bin/env python3
"""
fix_tooling_screen_v1p.py
- テーブルを w-full → w-auto に変更（内容合計幅で収まるようにする）
- 削除ボタン文字化け修正（删除→削除）
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT, "r") as f:
    esrc = f.read()

# テーブル w-full → w-auto
OLD_TBL = '<table className="text-xs w-full border-collapse">'
NEW_TBL = '<table className="text-xs w-auto border-collapse">'
count = esrc.count(OLD_TBL)
if count > 0:
    esrc = esrc.replace(OLD_TBL, NEW_TBL)
    print(f"OK: {count}箇所 w-full → w-auto")
else:
    print("SKIP: w-full テーブルが見つからない")

# 削除ボタン文字化け修正
OLD_DEL = '>\u5220\u9664</button>'  # 删除
NEW_DEL = '>\u524a\u9664</button>'  # 削除
count2 = esrc.count(OLD_DEL)
if count2 > 0:
    esrc = esrc.replace(OLD_DEL, NEW_DEL)
    print(f"OK: {count2}箇所 削除ボタン文字修正")

with open(EDIT, "w") as f:
    f.write(esrc)
print("SAVED:", EDIT)

res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -8"],
    capture_output=True, text=True)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:", res.stderr[-400:]); sys.exit(1)

subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("OK: pm2 restart")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1p - table w-auto, delete button kanji" && '
    'git push origin main'], check=True)
print("=== 完了 ===")
