#!/usr/bin/env python3
"""fix_v51b.py — mc/page.tsxのalt属性の??演算子を修正"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)

DETAIL = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/page.tsx")

# alt属性に入った??演算子を修正（alt={f.stored_name ?? f.original_name} → alt={f.stored_name ?? f.original_name ?? ""}）
# ただしalt属性は文字列型のみ許可なので三項演算子でstring確定にする
content = read(DETAIL)
# alt={f.stored_name ?? f.original_name} は型エラー → alt={f.stored_name ?? f.original_name ?? ""}でも同じ
# 正しくはalt属性以外に??を残し、alt属性は元のoriginal_nameのままにする
# テキスト表示部分の??はそのままでOK、alt属性のみ元に戻す
content = content.replace(
    'alt={f.stored_name ?? f.original_name}\n                        className="w-full h-full object-contain"',
    'alt={f.original_name}\n                        className="w-full h-full object-contain"'
)
write(DETAIL, content)
print("OK: mc/page.tsx alt属性をoriginal_nameに戻す（表示テキストはstored_nameのまま）")

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
    'cd ~/projects/machcore && git add -A && git commit -m "fix: alt属性をoriginal_nameに戻す v51b" && git push',
    shell=True
)
print("DONE")
