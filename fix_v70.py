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

# ═══════════════════════════════════════════
# 1. RAWデータ — sticky thead方式に変更（列幅が揃う）
# ═══════════════════════════════════════════
RAW = f"{ROOT}/apps/web/app/admin/raw/page.tsx"

# テーブルエリアを単一overflow-autoコンテナ + sticky thead に変更
OLD_TABLE = '''        {/* テーブル: カラムヘッダー固定・明細スクロール */}
        <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
          {loading ? (
            <div className="py-20 text-center text-slate-400">読み込み中…</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-slate-400">データなし</div>
          ) : (<>
            {/* 固定ヘッダー */}
            <div className="shrink-0 overflow-x-auto border-b border-slate-200">
              <table className="text-xs whitespace-nowrap">
                <thead className="bg-slate-50">
                  <tr>
                    {cols.map(col => (
                      <th key={col} className="px-3 py-2 text-left text-slate-500 font-bold">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
              </table>
            </div>
            {/* スクロール明細 */}
            <div className="flex-1 overflow-auto">
              <table className="text-xs whitespace-nowrap">
                <tbody className="divide-y divide-slate-50">
                  {filtered.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      {cols.map(col => (
                        <td key={col} className="px-3 py-1.5 font-mono text-slate-700 max-w-[200px] truncate"
                          title={String(row[col] ?? "")}>
                          {row[col] === null ? <span className="text-slate-300">NULL</span>
                            : typeof row[col] === "object" ? JSON.stringify(row[col])
                            : String(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>)}
        </div>'''

NEW_TABLE = '''        {/* テーブル: stickyヘッダー方式（列幅が揃う） */}
        <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200">
          {loading ? (
            <div className="py-20 text-center text-slate-400">読み込み中…</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-slate-400">データなし</div>
          ) : (
            <table className="text-xs whitespace-nowrap w-full">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr>
                  {cols.map(col => (
                    <th key={col} className="px-3 py-2 text-left text-slate-500 font-bold border-b border-slate-200">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    {cols.map(col => (
                      <td key={col} className="px-3 py-1.5 font-mono text-slate-700 max-w-[200px] truncate"
                        title={String(row[col] ?? "")}>
                        {row[col] === null ? <span className="text-slate-300">NULL</span>
                          : typeof row[col] === "object" ? JSON.stringify(row[col])
                          : String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>'''

patch(RAW, OLD_TABLE, NEW_TABLE, "raw テーブルをsticky thead方式に変更")

# ═══════════════════════════════════════════
# 2. システム設定 — mainのmax-w-2xlを除去してh-screen固定を確実に
# ═══════════════════════════════════════════
SETTINGS = f"{ROOT}/apps/web/app/admin/settings/page.tsx"
patch(SETTINGS,
    '<main className="flex-1 overflow-y-auto p-6 max-w-2xl">',
    '<main className="flex-1 overflow-y-auto p-6">',
    "settings main max-w-2xl除去")

# ═══════════════════════════════════════════
# 3. 機械タイムカード — タイトル行追加
# ═══════════════════════════════════════════
TC = f"{ROOT}/apps/web/app/mc/timecards/page.tsx"
patch(TC,
    '''        <main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">
          {/* ツールバー固定 */}''',
    '''        <main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">
          {/* タイトル */}
          <div className="shrink-0">
            <h1 className="text-xl font-bold text-slate-800">機械タイムカード</h1>
          </div>
          {/* ツールバー固定 */}''',
    "timecards タイトル行追加")

# ビルド & デプロイ
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: RAWstickyヘッダー+settings固定+TCタイトル追加 v70" && git push')
print("DONE")
