#!/usr/bin/env python3
"""fix_v96: mc/[mc_id]/print/page.tsx 認証前オプション削除（正確なパターン）"""
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

PRINT = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page.tsx"
p = read(PRINT)

# 認証前ブロック内のオプションを削除
# 現在のコード: 機械/主Oナンバ/CT/ツーリング情報の後にチェックボックス群がある
OLD = """              {/* 印刷オプション */}
              <div className="space-y-2 mb-6">
                {[
                  [includeTooling,       setIncludeTooling,       "ツーリングリストを含める"],
                  [includeClamp,         setIncludeClamp,         "クランプ情報を含める"],
                  [includeDrawings,      setIncludeDrawings,      "図を含める"],
                  [includeWorkOffsets,   setIncludeWorkOffsets,   "ワークオフセットを含める"],
                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],
                ].map(([val, setter, label]: any) => (
                  <label key={label} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">{label}</span>
                  </label>
                ))}
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm">
                この作業を開始する
              </button>"""

NEW = """              <button onClick={() => setAuthOpen(true)}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm">
                この作業を開始する
              </button>"""

p = rep(p, OLD, NEW, "print: 認証前オプションブロック削除")

count = p.count("段取シート発行オプション")
print(f"INFO: 削除後「段取シート発行オプション」残存: {count}箇所（1箇所が正常）")

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
subprocess.run(["git","commit","-m","fix(v96): 認証前オプション削除（リピート段取シート画面）"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v96")
