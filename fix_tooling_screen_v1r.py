#!/usr/bin/env python3
"""fix_tooling_screen_v1r.py
コメント列=工具列と同幅(210px)。
テーブルはw-autoで内容幅のみ。外側divをinline-blockで右空白なし。
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT, "r") as f:
    esrc = f.read()

# 1. w-full → w-auto
OLD1 = '<table className="text-xs w-full border-collapse">'
NEW1 = '<table className="text-xs border-collapse">'
c1 = esrc.count(OLD1)
if c1:
    esrc = esrc.replace(OLD1, NEW1)
    print(f"OK: {c1}箇所 w-full除去")

# w-auto残っていれば除去
OLD1b = '<table className="text-xs w-auto border-collapse">'
c1b = esrc.count(OLD1b)
if c1b:
    esrc = esrc.replace(OLD1b, NEW1)
    print(f"OK: {c1b}箇所 w-auto除去")

# 2. コメント列 col → 210px
OLD2 = '                        <col/>\n'
NEW2 = '                        <col style={{width:"210px"}}/>\n'
c2 = esrc.count(OLD2)
if c2:
    esrc = esrc.replace(OLD2, NEW2)
    print(f"OK: {c2}箇所 コメント列 210px")
else:
    # 300pxの場合
    OLD2b = '                        <col style={{width:"300px"}}/>\n'
    c2b = esrc.count(OLD2b)
    if c2b:
        esrc = esrc.replace(OLD2b, NEW2)
        print(f"OK: {c2b}箇所 コメント列 300px→210px")

# 3. overflow-y-auto div を inline-block ラッパーで囲む
OLD3 = '                  <div className="overflow-y-auto max-h-[55vh]">'
NEW3 = '                  <div className="overflow-y-auto max-h-[55vh]" style={{display:"inline-block",minWidth:"100%"}}>'
c3 = esrc.count(OLD3)
if c3:
    esrc = esrc.replace(OLD3, NEW3)
    print(f"OK: {c3}箇所 inline-block追加")

with open(EDIT, "w") as f:
    f.write(esrc)

res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -6"],
    capture_output=True, text=True)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:", res.stderr[-400:]); sys.exit(1)

subprocess.run(["pm2", "restart", "machcore-web"], check=True)
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1r - comment 210px, table no w-full, no right gap" && '
    'git push origin main'], check=True)
print("=== 完了 ===")
