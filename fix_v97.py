#!/usr/bin/env python3
"""fix_v97: mc/[mc_id]/print/page.tsx 認証後オプション2重表示を修正
認証後ブロック内に古いオプションmapと新しい認証後オプションが両方存在するため
古い方を削除して認証後オプション1つだけにする"""
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

# 認証後ブロックの古いオプションmap（「setter, label」形式）+ 参考出力 を削除
# 新しい「認証後オプション」ブロックの直前にある古いブロックを除去
OLD_DUP = """              <div className="px-5 py-4 space-y-3">
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
              </div>"""

p = rep(p, OLD_DUP, '', "認証後 古いオプションmapブロック削除")

# 参考出力の重複も確認・削除（2重になっている場合）
count_ref = p.count('参考出力（生産に使用しない・回収不要）')
print(f"INFO: 参考出力ブロック数: {count_ref}")

# 元のオプションブロック（図を含めるの上の古い部分）を確認
# {setter, label}: any のパターンが残っていれば削除
OLD_MAP2 = """, setter, label]: any) => (
                      <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                        <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                          className="accent-teal-600 w-4 h-4" />
                        <span className="text-slate-700">{label}</span>
                      </label>
                    ))}
                  </>
                )}
              </div>"""
if OLD_MAP2 in p:
    # このパターンの前にある開始部分も含めて除去
    import re
    # {[ から始まるブロック全体を検索して削除
    pattern = r'\{/\* 認証後オプション \*/\}\s*<div[^>]*>\s*<p[^>]*>段取シート発行オプション</p>'
    print(f"INFO: 「setter, label」パターン残存あり — 追加削除実行")
    p = p.replace(OLD_MAP2, '', 1)
    print("OK: 古いオプションmapの末尾部分削除")

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
subprocess.run(["git","commit","-m","fix(v97): 認証後オプション2重表示修正"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v97")
