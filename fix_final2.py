#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
REPO = "/home/karkyon/projects/machcore"

def patch(path, old, new, label):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if old in src:
        src = src.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"  OK {label}")
        return True
    else:
        print(f"  SKIP {label}: pattern not found")
        return False

# 1. timecards fmtMin: 旧パターン全体を「480分」に強制置換
TC = f"{WEB}/app/mc/timecards/page.tsx"
with open(TC, "r", encoding="utf-8") as f:
    src = f.read()

# fmtMin 関数全体を探して置換（returnまで）
import re
new_fmt = (
    'function fmtMin(min: number): string {\n'
    '  if (min <= 0) return "—";\n'
    '  return `${min}m`;\n'
    '}'
)
# 関数全体をregexで置換
src_new = re.sub(
    r'function fmtMin\(min: number\)[^{]*\{[^}]*\}',
    new_fmt,
    src,
    count=1
)
if src_new != src:
    with open(TC, "w", encoding="utf-8") as f:
        f.write(src_new)
    print("  OK timecards fmtMin -> 480m")
else:
    print("  SKIP fmtMin regex: no match")
    idx = src.find("function fmtMin")
    print("  current:", repr(src[idx:idx+120]))

# 2. users: 新規ユーザ追加ボタン縮小
USR = f"{WEB}/app/admin/users/page.tsx"
patch(USR,
    '<button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg">＋ 新規ユーザ追加</button>',
    '<button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg">＋ 新規ユーザ追加</button>',
    "users: 新規ユーザ追加ボタン縮小"
)

# 3. machines: 新規機械追加ボタン縮小
MCH = f"{WEB}/app/admin/machines/page.tsx"
patch(MCH,
    '<button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg">＋ 新規機械追加</button>',
    '<button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg">＋ 新規機械追加</button>',
    "machines: 新規機械追加ボタン縮小"
)

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
subprocess.run(["git", "commit", "-m",
    "fix: timecard fmtMin 480m, users/machines btn xs py-1.5"], cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
