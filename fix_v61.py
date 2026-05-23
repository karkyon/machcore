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

# ── 1. page.tsx (ダッシュボード) — 「機械TC」→「機械タイムカード」へ変更 ──
PAGE = f"{ROOT}/apps/web/app/page.tsx"

patch(PAGE,
    '{ label: "機械TC",          href: "/mc/timecards", active: false },',
    '{ label: "機械タイムカード", href: "/mc/timecards", active: false },',
    "page.tsx ナビラベル 機械TC→機械タイムカード")

# ── 2. adminの全ページ共通サイドバーに「機械タイムカード」追加 ──────
ADMIN_PAGES = [
    f"{ROOT}/apps/web/app/admin/machines/page.tsx",
    f"{ROOT}/apps/web/app/admin/users/page.tsx",
    f"{ROOT}/apps/web/app/admin/settings/page.tsx",
    f"{ROOT}/apps/web/app/admin/raw/page.tsx",
    f"{ROOT}/apps/web/app/admin/logs/page.tsx",
]

OLD_SIDEBAR_ITEMS = '''    { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
            { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
            { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
            { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },'''

NEW_SIDEBAR_ITEMS = '''    { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
            { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
            { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
            { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
            { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },'''

# 定数配列パターン（raw/settings/logs）
OLD_CONST_ITEMS = '''  const SIDEBAR_ITEMS = [
    { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
    { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
    { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
    { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  ];'''

NEW_CONST_ITEMS = '''  const SIDEBAR_ITEMS = [
    { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
    { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
    { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
    { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
    { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  ];'''

for path in ADMIN_PAGES:
    if not os.path.exists(path):
        print(f"SKIP: {os.path.basename(path)} — ファイルなし")
        continue
    # まずSIDEBAR_ITEMS定数パターン（raw/settings/logs）
    ok = patch(path, OLD_CONST_ITEMS, NEW_CONST_ITEMS, f"{os.path.basename(path)} SIDEBAR_ITEMS定数")
    if not ok:
        # インライン配列パターン（machines）
        patch(path, OLD_SIDEBAR_ITEMS, NEW_SIDEBAR_ITEMS, f"{os.path.basename(path)} インライン配列")

# users/page.tsxはインラインパターン（href直接a要素）
USERS_PAGE = f"{ROOT}/apps/web/app/admin/users/page.tsx"
OLD_USERS_NAV = '''        <a href="/admin/users"
          className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm bg-sky-600 text-white font-bold">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          ユーザ管理
        </a>
        <a href="/admin/machines"
          className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          機械管理
        </a>
        <a href="/admin/settings"'''

NEW_USERS_NAV = '''        <a href="/admin/users"
          className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm bg-sky-600 text-white font-bold">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          ユーザ管理
        </a>
        <a href="/admin/machines"
          className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          機械管理
        </a>
        <a href="/mc/timecards"
          className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          機械タイムカード
        </a>
        <a href="/admin/settings"'''

patch(USERS_PAGE, OLD_USERS_NAV, NEW_USERS_NAV, "users/page.tsx サイドバーに機械タイムカード追加")

# ── 3. ビルド & デプロイ ────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: ダッシュボード機械TC→機械タイムカード + adminサイドバーに機械タイムカード追加 v61" && git push')
print("DONE")
