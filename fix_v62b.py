import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    content = read(path)
    if old not in content:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, content.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

NEW_PAGE = f"{ROOT}/apps/web/app/mc/new/page.tsx"

# ── 1. useAuthからisAuthenticatedも取得するよう修正 ──────────────────
OLD_USE_AUTH = '''  const { token: authToken, operator: authOperator } = useAuth();'''

NEW_USE_AUTH = '''  const { token: authToken, operator: authOperator, isAuthenticated } = useAuth();'''

patch(NEW_PAGE, OLD_USE_AUTH, NEW_USE_AUTH, "mc/new/page.tsx useAuthにisAuthenticated追加")

# ── 2. ビルド & デプロイ ────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: mc/new useAuthにisAuthenticated追加 未認証時仮登録ブロック v62b" && git push')
print("DONE")
