#!/usr/bin/env python3
"""fix_v88.py
問題: AuthContextのtokenはlocalStorage残存トークンで初期化されるため
      isAuthenticated=trueになり仮登録ボタンが有効になる。
解決: operatorオブジェクトの有無で認証状態を判定する。
      operatorはAuthModal認証成功時にのみセットされ、
      ページリロード時はnullにリセットされる。
"""
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

# mc/new/page.tsx の canSubmit と ボタン分岐を修正
# authOperator（operatorオブジェクト）の有無で認証済みを判定
# operatorはAuthModal成功時にのみセットされ、ページロード時はnull

patch(f"{WEB}/app/mc/new/page.tsx",
    "  // 認証済み + 部品選択済み + 加工ID取得済み の場合のみ登録可\n  const canSubmit = !!(authToken && isAuthenticated && selectedPart && machiningId);",
    "  // authOperatorがセットされている = AuthModalで実際に認証済み（localStorage残存トークンは除外）\n  // authOperatorはページリロードでnullになるのでlocalStorage残存tokenの誤認証を防ぐ\n  const actuallyAuthenticated = !!(authToken && authOperator);\n  const canSubmit = !!(actuallyAuthenticated && selectedPart && machiningId);",
    "mc/new/page.tsx canSubmitをauthOperator判定に変更"
)

patch(f"{WEB}/app/mc/new/page.tsx",
    "    {!authToken ? (",
    "    {!actuallyAuthenticated ? (",
    "mc/new/page.tsx ボタン分岐をactuallyAuthenticated判定に変更"
)

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v88): authOperator判定でlocalStorage残存token誤認証を防ぐ' && git push", cwd=ROOT)
print("DONE v88")
