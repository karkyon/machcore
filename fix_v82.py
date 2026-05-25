#!/usr/bin/env python3
"""fix_v82.py - canSubmitのpartApproved条件を === true に修正"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"

def read(p):
    with open(p,"r",encoding="utf-8") as f: return f.read()
def write(p,c):
    with open(p,"w",encoding="utf-8") as f: f.write(c)
def patch(p,old,new,label):
    c=read(p)
    if old not in c: print(f"WARN: {label} — 不一致"); return False
    write(p,c.replace(old,new,1)); print(f"OK: {label}"); return True
def run(cmd,cwd=ROOT):
    r=subprocess.run(cmd,shell=True,cwd=cwd,capture_output=True,text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:",r.stderr[-2000:])
    return r.returncode

# 問題: partApproved !== false → null(確認中)もtrueになる
# 修正: partApproved === true の場合のみ登録可能
patch(
    f"{WEB}/app/mc/new/page.tsx",
    "  const canSubmit = !!(authToken && isAuthenticated && selectedPart && machiningId && partApproved !== false);",
    "  // partApproved === true の場合のみ登録可（null=確認中はNG、false=未承認はNG）\n  const canSubmit = !!(authToken && isAuthenticated && selectedPart && machiningId && partApproved === true);",
    "mc/new/page.tsx canSubmit: partApproved === true のみ通す"
)

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v82): canSubmit partApproved===trueのみ通す（null確認中はブロック）' && git push", cwd=ROOT)
print("DONE v82")
