#!/usr/bin/env python3
"""
fix_v95:
① mc/new/print/page.tsx ボタン間余白追加
② mc/[mc_id]/print/page.tsx 認証前オプションチェックボックス削除
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def rep(content, old, new, label):
    if old not in content:
        print(f"WARN: {label} — 不一致"); return content
    print(f"OK: {label}"); return content.replace(old, new, 1)

# ① mc/new/print/page.tsx ボタン間余白
NEW_PRINT = f"{ROOT}/apps/web/app/mc/new/print/page.tsx"
p = read(NEW_PRINT)
p = rep(p,
    '            <button onClick={handlePreview} disabled={previewing || printing}\n              className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm">',
    '            <button onClick={handlePreview} disabled={previewing || printing}\n              className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm mt-2">',
    "new/print: プレビューボタン上余白")
p = rep(p,
    '            <button onClick={handleDirectPrint} disabled={printing || previewing}\n              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">',
    '            <button onClick={handleDirectPrint} disabled={printing || previewing}\n              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm mt-3">',
    "new/print: 直接印刷ボタン上余白")
p = rep(p,
    '            <button onClick={() => { logout(); if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending"); router.push("/"); }}\n              disabled={printing || previewing}\n              className="w-full bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-600 font-bold py-3 rounded-xl text-sm transition-colors">',
    '            <button onClick={() => { logout(); if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending"); router.push("/"); }}\n              disabled={printing || previewing}\n              className="w-full bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-600 font-bold py-3 rounded-xl text-sm transition-colors mt-3">',
    "new/print: キャンセルボタン上余白")
write(NEW_PRINT, p)

# ② mc/[mc_id]/print/page.tsx 認証前オプションブロック削除
# 認証前（!isAuthenticated）の中にあるオプションチェックブロックを削除
PRINT = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page.tsx"
p = read(PRINT)

# 認証前ブロック内のオプション（機械/主Oナンバ/ツーリング情報の下にあるチェックボックス群）を削除
# 現在のコードで !isAuthenticated ブロック内に残っているオプション部分を特定
import re

# 認証前ブロック全体を見つけて、その中のオプション部分だけ削除
# 「この作業を開始する」ボタンの上にあるオプションブロックを削除
OLD_PRE_AUTH_OPTS = '''              {/* オプション */}
              <div className="mb-5 border border-slate-100 rounded-xl overflow-hidden">
                <div className="px-5 py-3 bg-slate-50 border-b border-slate-100">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">段取シート発行オプション</span>
                </div>
                <div className="px-5 py-4 space-y-3">
                  <label className="flex items-center gap-3 text-sm cursor-pointer">
                    <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">図を含める</span>
                  </label>
                  {!isNew && (
                    <>
                      {([
                        ["ツーリングリストを含める", includeTooling, setIncludeTooling],
                        ["クランプ情報を含める",     includeClamp,   setIncludeClamp],
                        ["ワークオフセットを含める", includeWorkOffsets, setIncludeWorkOffsets],
                        ["インデックスプログラムを含める", includeIndexPrograms, setIncludeIndexPrograms],
                      ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
                        <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                          <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                            className="accent-teal-600 w-4 h-4" />
                          <span className="text-slate-700">{label}</span>
                        </label>
                      ))}
                    </>
                  )}
                </div>
              </div>'''

p = rep(p, OLD_PRE_AUTH_OPTS, '', "print: 認証前オプションブロック削除")

# 万一上記パターンが不一致の場合、「段取シート発行オプション」が2箇所あるか確認
count = p.count("段取シート発行オプション")
print(f"INFO: 認証前削除後 「段取シート発行オプション」残存: {count}箇所")

write(PRINT, p)

print("\n--- build web ---")
r = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-3000:])
if r.stderr: print("STDERR:", r.stderr[-2000:])
if r.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-2000:])
if r.stderr: print("STDERR:", r.stderr[-1500:])
if r.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v95): ボタン余白調整+認証前オプション削除"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v95")
