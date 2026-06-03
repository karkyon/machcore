#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
REPO = "/home/karkyon/projects/machcore"

TC = f"{WEB}/app/mc/timecards/page.tsx"
with open(TC, "r", encoding="utf-8") as f:
    src = f.read()

# 現在の壊れた状態を確認してから修正
idx = src.find("function fmtMin")
end = src.find("\n}\n", idx) + 3
print("current fmtMin block:", repr(src[idx:end]))

# 壊れたブロック全体を正しいものに置換
broken = src[idx:end]
correct = 'function fmtMin(min: number): string {\n  if (min <= 0) return "—";\n  return `${min}m`;\n}\n'

src = src[:idx] + correct + src[end:]
with open(TC, "w", encoding="utf-8") as f:
    f.write(src)
print("OK fmtMin fixed -> 480m format")

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
subprocess.run(["git", "commit", "-m", "fix: timecards fmtMin correct 480m"], cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
