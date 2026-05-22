#!/usr/bin/env python3
"""fix_v51.py — ファイル表示名をoriginal_name→stored_nameに変更"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

EDIT = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/edit/page.tsx")
DETAIL = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/page.tsx")

# edit/page.tsx: ファイル一覧のoriginal_name → stored_name
patch(EDIT,
    "<p className=\"text-[11px] text-slate-600 truncate flex-1\">{f.original_name}</p>",
    "<p className=\"text-[11px] text-slate-600 truncate flex-1\">{f.stored_name ?? f.original_name}</p>",
    "edit/page.tsx ファイル表示名 stored_nameに変更"
)

# mc/page.tsx（MC詳細）: 写真・図タブのファイル名表示も確認・修正
content = read(DETAIL)
if "f.original_name" in content and "写真" in content:
    # 詳細ページのファイル名表示をstored_nameに
    new_content = content.replace(
        "{f.original_name}",
        "{f.stored_name ?? f.original_name}"
    )
    if new_content != content:
        write(DETAIL, new_content)
        print("OK: mc/page.tsx ファイル表示名 stored_nameに変更")
    else:
        print("INFO: mc/page.tsx 変更なし")

print("\n--- npm run build ---")
r = subprocess.run("cd ~/projects/machcore/apps/web && npm run build", shell=True, capture_output=True, text=True)
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
stderr_clean = "\n".join(l for l in r.stderr.split("\n") if "react-pdf" not in l)
if stderr_clean.strip():
    print("STDERR:", stderr_clean[-500:])

if r.returncode != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

print("\n--- pm2 restart web ---")
subprocess.run("pm2 restart machcore-web --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "fix: ファイル表示名をoriginal_name→stored_nameに変更 v51" && git push',
    shell=True
)
print("DONE")
