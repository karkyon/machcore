#!/usr/bin/env python3
import subprocess, sys, os

REPO = "/home/karkyon/projects/machcore"
WEB  = f"{REPO}/apps/web"

# 1) 現在のsettings/page.tsxの該当箇所を確認
TARGET = f"{WEB}/app/admin/settings/page.tsx"
with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

# cronTime の存在確認
if "cronTime" in content:
    print("OK cronTime exists in settings page")
else:
    print("ERROR cronTime NOT found - cron_time_input fix was not applied")
    sys.exit(1)

# 実行時刻（24時間表記）の存在確認
if "24時間表記" in content:
    print("OK 24時間表記 label found")
else:
    print("WARNING: 24時間表記 label not found")

# 2) .next キャッシュ削除
print("--- clearing .next cache ---")
r = subprocess.run(
    f"rm -rf {WEB}/.next",
    shell=True, capture_output=True, text=True
)
print("OK .next deleted")

# 3) 強制 next build
print("--- next build (clean) ---")
r2 = subprocess.run(
    f"export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && cd {REPO} && npm run build --workspace=apps/web 2>&1",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
out = r2.stdout + r2.stderr
if "Build error" in out or "Type error" in out or "SyntaxError" in out:
    print("ERROR build:"); print(out[-3000:]); sys.exit(1)
print("OK next build")

# 4) pm2 delete + start (キャッシュ完全クリア)
print("--- pm2 delete + start machcore-web ---")
subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 delete machcore-web 2>&1",
    shell=True, executable="/bin/bash"
)
r3 = subprocess.run(
    f"export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && cd {REPO} && pm2 start ecosystem.config.js --only machcore-web 2>&1",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r3.stdout[-500:])
print("OK pm2 machcore-web restarted")

# git push (fix_pm2_restart.py が未コミットなら)
r4 = subprocess.run(
    f"cd {REPO} && git status --short 2>&1",
    shell=True, capture_output=True, text=True
)
if r4.stdout.strip():
    subprocess.run(
        f"cd {REPO} && git add -A && git commit -m 'fix: force rebuild web after cron time input change' && git push 2>&1",
        shell=True
    )
    print("OK git push")
else:
    print("INFO git: nothing to commit")

print("DONE")
print("ブラウザで Ctrl+Shift+R (強制リロード) してください")
