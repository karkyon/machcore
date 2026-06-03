#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
REPO = "/home/karkyon/projects/machcore"

TC = f"{WEB}/app/mc/timecards/page.tsx"
with open(TC, "r", encoding="utf-8") as f:
    src = f.read()

# 8H0M -> 480分 表示
OLD = (
    'function fmtMin(min: number): string {\n'
    '  if (min <= 0) return "—";\n'
    '  const h = Math.floor(min / 60), m = min % 60;\n'
    '  return `${h}H${m}M`;\n'
    '}'
)
NEW = (
    'function fmtMin(min: number): string {\n'
    '  if (min <= 0) return "—";\n'
    '  return `${min}分`;\n'
    '}'
)

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    with open(TC, "w", encoding="utf-8") as f:
        f.write(src)
    print("OK fmtMin: 8H0M -> 480分")
else:
    # 前回スクリプト前の古い形式も試みる
    OLD2 = (
        'function fmtMin(min: number) {\n'
        '  if (min <= 0) return "—";\n'
        '  const h = Math.floor(min / 60), m = min % 60;\n'
        '  return h > 0 ? `${h}h${m > 0 ?'
    )
    if OLD2 in src:
        idx = src.find(OLD2)
        end = src.find('\n}', idx) + 2
        old_block = src[idx:end]
        new_block = (
            'function fmtMin(min: number): string {\n'
            '  if (min <= 0) return "—";\n'
            '  return `${min}分`;\n'
            '}'
        )
        src = src[:idx] + new_block + src[end:]
        with open(TC, "w", encoding="utf-8") as f:
            f.write(src)
        print("OK fmtMin: old format -> 480分")
    else:
        idx = src.find("function fmtMin")
        print("SKIP: pattern not found, current:", repr(src[idx:idx+150]))

print("\n--- next build ---")
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx next build",
    shell=True, cwd=WEB, capture_output=True, text=True
)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-2000:]); sys.exit(1)
print("OK next build")

subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-web",
    shell=True, capture_output=True)
print("OK pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "fix: timecard fmtMin -> 480分 format"], cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
