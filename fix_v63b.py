import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

MACHINES_PAGE = f"{ROOT}/apps/web/app/admin/machines/page.tsx"

# machineType/maker を (m as any) でアクセスするよう修正
patch(MACHINES_PAGE,
    "    if (fltType   && m.machineType !== fltType)             return false;\n"
    "    if (fltMaker  && !m.maker?.includes(fltMaker))         return false;",
    "    if (fltType   && (m as any).machineType !== fltType)    return false;\n"
    "    if (fltMaker  && !(m as any).maker?.includes(fltMaker)) return false;",
    "machines/page.tsx filter (m as any)修正")

# openEdit内のmachineTypeとmakerも修正済みだが念のため確認
patch(MACHINES_PAGE,
    "setFCode(m.machineCode); setFName(m.machineName ?? \"\"); setFType((m as any).machineType ?? \"MC\");\n"
    "    setFMaker((m as any).maker ?? \"\");",
    "setFCode(m.machineCode); setFName(m.machineName ?? \"\"); setFType((m as any).machineType ?? \"MC\");\n"
    "    setFMaker((m as any).maker ?? \"\");",
    "machines/page.tsx openEdit (m as any)確認")

# ── users/page.tsx — WARNになったヘッダー/サイドバーを直接文字列置換で対応 ──
USERS_PAGE = f"{ROOT}/apps/web/app/admin/users/page.tsx"
c = read(USERS_PAGE)

# ヘッダー: bg-slate-900 → bg-white
c = c.replace(
    'className="bg-slate-900 text-white px-5 py-2.5 flex items-center gap-3 shrink-0 border-b border-slate-800"',
    'className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0"'
)
# 管理パネル文字色
c = c.replace(
    '<span className="text-sm font-bold tracking-wide">MachCore 管理パネル</span>',
    '<span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>'
)
# ←NC画面リンク → ←ダッシュボード
c = c.replace(
    'href="/nc/search"\n            className="text-xs bg-slate-600 hover:bg-slate-500 text-slate-200 px-3 py-1.5 rounded transition-colors">\n            ← NC画面',
    'href="/"\n            className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">\n            ← ダッシュボード'
)
# ログアウトボタン
c = c.replace(
    'className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded transition-colors">\n            ログアウト',
    'className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">\n            ログアウト'
)
# サイドバー背景
c = c.replace(
    'className="w-48 shrink-0 bg-slate-800 flex flex-col py-4 gap-1 border-r border-slate-700"',
    'className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5"'
)
# サイドバーメニューラベル
c = c.replace(
    '"px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider"',
    '"px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider"'
)
# サイドバーリンクのアクティブ/非アクティブスタイル（users）
c = c.replace(
    '"bg-sky-600 text-white font-bold"',
    '"bg-sky-50 text-sky-700 font-bold border border-sky-200"'
)
c = c.replace(
    '"text-slate-300 hover:bg-slate-700 hover:text-white"',
    '"text-slate-600 hover:bg-slate-50 hover:text-slate-900"'
)
write(USERS_PAGE, c)
print("OK: users/page.tsx ヘッダー・サイドバーをライトモードに")

# フィルタ行のHTMLをmainコンテンツの先頭に追加
# タイトル「ユーザ一覧」の後にフィルタUIを挿入
c2 = read(USERS_PAGE)
OLD_TITLE = '''          <div className="flex items-center justify-between mb-6">
            <h1 className="text-xl font-bold text-slate-800">ユーザ一覧</h1>
            <button onClick={openCreate}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg transition-colors">
              ＋ 新規ユーザ追加
            </button>
          </div>'''
NEW_TITLE = '''          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-slate-800">ユーザ一覧</h1>
            <button onClick={openCreate}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg transition-colors">
              ＋ 新規ユーザ追加
            </button>
          </div>
          {/* フィルタ */}
          <div className="flex flex-wrap gap-2 mb-4 bg-white p-3 rounded-xl border border-slate-200">
            <input type="text" value={fltCode} onChange={e => setFltCode(e.target.value)} placeholder="社員コードでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-44" />
            <input type="text" value={fltName2} onChange={e => setFltName2(e.target.value)} placeholder="氏名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-44" />
            <select value={fltRole} onChange={e => setFltRole(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">ロール: すべて</option>
              <option value="ADMIN">管理者</option>
              <option value="OPERATOR">作業者</option>
              <option value="VIEWER">閲覧者</option>
            </select>
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option>
              <option value="active">有効のみ</option>
              <option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filteredUsers.length}/{users.length}件</span>
          </div>'''

if OLD_TITLE in c2:
    c2 = c2.replace(OLD_TITLE, NEW_TITLE, 1)
    write(USERS_PAGE, c2)
    print("OK: users/page.tsx フィルタ行追加")
else:
    print("WARN: users/page.tsx フィルタ行 — パターン不一致（手動確認必要）")

# fltName2 stateを追加（既にfltNameがfilteredUsersで使われているため名前変更）
c3 = read(USERS_PAGE)
c3 = c3.replace(
    '  const [fltCode,   setFltCode]   = useState("");\n'
    '  const [fltName,   setFltName]   = useState("");\n'
    '  const [fltRole,   setFltRole]   = useState("");\n'
    '  const [fltStatus, setFltStatus] = useState("");',
    '  const [fltCode,   setFltCode]   = useState("");\n'
    '  const [fltName,   setFltName]   = useState("");\n'
    '  const [fltName2,  setFltName2]  = useState("");\n'
    '  const [fltRole,   setFltRole]   = useState("");\n'
    '  const [fltStatus, setFltStatus] = useState("");'
)
# filteredUsersのfltNameをfltName2に統一
c3 = c3.replace(
    '    if (fltName   && !u.name?.includes(fltName))         return false;',
    '    if (fltName2  && !u.name?.includes(fltName2))         return false;'
)
write(USERS_PAGE, c3)
print("OK: users/page.tsx fltName2追加・filteredUsers修正")

# raw/page.tsx サイドバーライトモード（WARNだった箇所）
RAW_PAGE = f"{ROOT}/apps/web/app/admin/raw/page.tsx"
cr = read(RAW_PAGE)
cr = cr.replace(
    'className="w-48 shrink-0 bg-slate-800 flex flex-col py-4 gap-1 border-r border-slate-700"',
    'className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5"'
)
cr = cr.replace(
    '"px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider"',
    '"px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider"'
)
cr = cr.replace(
    '"bg-sky-600 text-white font-bold"',
    '"bg-sky-50 text-sky-700 font-bold border border-sky-200"'
)
cr = cr.replace(
    '"text-slate-300 hover:bg-slate-700 hover:text-white"',
    '"text-slate-600 hover:bg-slate-50 hover:text-slate-900"'
)
write(RAW_PAGE, cr)
print("OK: raw/page.tsx サイドバーライトモード")

# ── ビルド & デプロイ ────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: admin全ページライトモード+フィルタ型エラー修正 v63b" && git push')
print("DONE")
