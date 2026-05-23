import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# RAWデータ: main の overflow-auto → overflow-y-auto（flex-1と組み合わせで固定）
RAW = f"{ROOT}/apps/web/app/admin/raw/page.tsx"
c = read(RAW)
c = c.replace(
    '<main className="flex-1 overflow-auto px-4 py-6">',
    '<main className="flex-1 overflow-y-auto px-4 py-6">'
)
write(RAW, c)
print("OK: raw/page.tsx main overflow-auto→overflow-y-auto")

# settings: main の overflow-y-auto を確認して flex-1を付ける
SETTINGS = f"{ROOT}/apps/web/app/admin/settings/page.tsx"
c = read(SETTINGS)
# mainタグを探して確認・修正
if '<main className="flex-1 overflow-y-auto' not in c:
    c = c.replace(
        '<main className="flex-1 overflow-y-auto p-6 max-w-2xl">',
        '<main className="flex-1 overflow-y-auto p-6 max-w-2xl">'
    )
    # mainが別パターンの場合
    c = c.replace(
        '<main className="',
        '<main className="flex-1 overflow-y-auto '
    )
    write(SETTINGS, c)
    print("OK: settings/page.tsx main flex-1 overflow-y-auto追加")
else:
    print("OK: settings/page.tsx mainは既に正しい")

# logs: main確認・修正
LOGS = f"{ROOT}/apps/web/app/admin/logs/page.tsx"
c = read(LOGS)
c = c.replace(
    '<main className="flex-1 p-5 overflow-y-auto">',
    '<main className="flex-1 overflow-y-auto p-5">'
)
c = c.replace(
    '<main className="p-5 flex-1 overflow-y-auto">',
    '<main className="flex-1 overflow-y-auto p-5">'
)
write(LOGS, c)
print("OK: logs/page.tsx main確認")

# 全ページのmainタグを統一：flex-1 overflow-y-auto
for fname, fpath in [
    ("raw",      RAW),
    ("settings", SETTINGS),
    ("logs",     LOGS),
]:
    c = read(fpath)
    # mainの古いパターンを全部統一
    for old, new in [
        ('<main className="flex-1 overflow-y-auto p-5 overflow-y-auto">', '<main className="flex-1 overflow-y-auto p-5">'),
        ('<main className="flex-1 overflow-y-auto flex-1 overflow-y-auto ', '<main className="flex-1 overflow-y-auto '),
    ]:
        c = c.replace(old, new)
    write(fpath, c)

print("OK: 全ページmain className重複除去")

rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: admin全画面main overflow-y-auto統一 ヘッダー・サイドバー完全固定 v68" && git push')
print("DONE")
