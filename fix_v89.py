#!/usr/bin/env python3
"""fix_v89.py - mc/[mc_id]/print/page.tsx: isNew時にタブ・MC詳細ボタンを不活性化"""
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

f = f"{WEB}/app/mc/[mc_id]/print/page.tsx"

# 1. ヘッダーの「← MC詳細」ボタン: isNew時は不活性
patch(f,
    """        <button
          onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>""",
    """        <button
          onClick={() => !isNew && router.push(`/mc/${mcId}`)}
          disabled={isNew}
          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${isNew ? "bg-slate-600 border-slate-600 text-slate-400 opacity-40 cursor-not-allowed pointer-events-none" : "bg-slate-700 hover:bg-slate-600 border-slate-600 text-white"}`}
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>""",
    "print/page.tsx ヘッダーMC詳細ボタン: isNew時不活性"
)

# 2. タブナビ: MC詳細・変更登録・作業記録 の3つを isNew時不活性化
# 現在のタブ部分（タブナビ全体を置換）
old_nav = """      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push"""

new_nav = """      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !isNew && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push"""

patch(f, old_nav, new_nav, "print/page.tsx タブナビMC詳細ボタン: isNew時不活性")

# 3. 変更・登録タブ と 作業記録タブ を isNew時不活性化
# 変更・登録タブ
old_edit_tab = """        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>"""

new_edit_tab = """        <button onClick={() => !isNew && router.push(`/mc/${mcId}/edit`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>"""

patch(f, old_edit_tab, new_edit_tab, "print/page.tsx 変更・登録タブ: isNew時不活性")

# 作業記録タブ
old_rec_tab = """        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>"""

new_rec_tab = """        <button onClick={() => !isNew && router.push(`/mc/${mcId}/record`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>"""

patch(f, old_rec_tab, new_rec_tab, "print/page.tsx 作業記録タブ: isNew時不活性")

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v89): print/page isNew時MC詳細/変更登録/作業記録タブ不活性化' && git push", cwd=ROOT)
print("DONE v89")
