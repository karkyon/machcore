#!/usr/bin/env python3
"""
fix_mc_pg_photos_v1b.py
edit/page.tsx: 基本情報タブのJSX構造エラー修正
PG情報ブロックをmax-w-2xl divの中に正しく収める
"""
import subprocess, sys

BASE      = "/home/karkyon/projects/machcore"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 現在の壊れた構造を修正
# 問題: </div> で max-w-2xl を閉じた後に {/* PG情報 */}ブロックが来ている
# 解決: max-w-2xl を space-y-4 のまま維持し、PG情報をその中に入れる

OLD_BASIC = '''            {/* 基本情報 */}
            {activeSection === "basic" && (
              <div className="max-w-2xl space-y-4">'''

# 末尾の壊れた閉じ方
OLD_BASIC_END = '''              </div>

              {/* PG情報 */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-600">プログラム情報</span>
                  <button onClick={async () => {
                    setPgLoading(true);
                    try {
                      const r = await mcApi.getPgFile(mcId);
                      const data = (r as any).data ?? r;
                      setPgContent(data.content ?? "");
                      setPgOrigName(data.originalName ?? "");
                      setPgEditorOpen(true);
                    } catch { showToast("PGファイルが見つかりません"); }
                    finally { setPgLoading(false); }
                  }} disabled={pgLoading}
                    className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                    {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                  </button>
                </div>
                <div className="px-4 py-3 grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">PG作成者</label>
                    <select value={pgCreatedBy} onChange={e => setPgCreatedBy(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {users.filter(u => u.isActive).map(u => (
                        <option key={u.id} value={String(u.id)}>{u.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">PG更新日時</label>
                    <div className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-600 font-mono">
                      {pgUpdatedAtDisp || "—"}
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">※ PGアップロード時に自動更新</p>
                  </div>
                </div>
              </div>
            </div>
            )}'''

NEW_BASIC_END = '''
                {/* PG情報 */}
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">プログラム情報</span>
                    <button onClick={async () => {
                      setPgLoading(true);
                      try {
                        const r = await mcApi.getPgFile(mcId);
                        const data = (r as any).data ?? r;
                        setPgContent(data.content ?? "");
                        setPgOrigName(data.originalName ?? "");
                        setPgEditorOpen(true);
                      } catch { showToast("PGファイルが見つかりません"); }
                      finally { setPgLoading(false); }
                    }} disabled={pgLoading}
                      className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                    </button>
                  </div>
                  <div className="px-4 py-3 grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">PG作成者</label>
                      <select value={pgCreatedBy} onChange={e => setPgCreatedBy(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                        <option value="">— 選択 —</option>
                        {users.filter(u => u.isActive).map(u => (
                          <option key={u.id} value={String(u.id)}>{u.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">PG更新日時</label>
                      <div className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-600 font-mono">
                        {pgUpdatedAtDisp || "—"}
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5">※ PGアップロード時に自動更新</p>
                    </div>
                  </div>
                </div>
              </div>
            )}'''

if OLD_BASIC_END in src:
    src = src.replace(OLD_BASIC_END, NEW_BASIC_END, 1)
    print("  OK: 基本情報タブ JSX構造修正")
else:
    print("  WARN: パターン不一致 — コンテキスト確認")
    idx = src.find("PG情報 */}")
    if idx != -1:
        print(repr(src[max(0,idx-100):idx+200]))
    sys.exit(1)

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

print("=== Web ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -15",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr[-300:])
    sys.exit(1)

print("=== PM2 再起動 ===")
subprocess.run("pm2 restart machcore-web", shell=True)

print("=== git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: pg_photos v1b - fix basic tab JSX structure" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
