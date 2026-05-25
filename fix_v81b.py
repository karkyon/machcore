#!/usr/bin/env python3
"""fix_v81b.py - partApproved stateを正確なパターンで挿入してビルド"""
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

new_page = f"{WEB}/app/mc/new/page.tsx"

# 実際のパターンを確認
c = read(new_page)
print("=== saving/saveError付近 ===")
idx = c.find("saving,    setSaving]")
if idx >= 0:
    print(c[idx-20:idx+200])
print("===")

# 正確なパターンで partApproved state を追加
patch(new_page,
    "  const [saving,    setSaving]    = useState(false);\n  const [saveError, setSaveError] = useState<string | null>(null);",
    "  const [saving,    setSaving]    = useState(false);\n  const [saveError, setSaveError] = useState<string | null>(null);\n  const [partApproved, setPartApproved] = useState<boolean | null>(null);",
    "mc/new/page.tsx partApproved state追加（正確なパターン）"
)

# saveError表示の前に警告メッセージを追加
# 現在のsaveError部分の正確なパターンを確認して挿入
c2 = read(new_page)
idx2 = c2.find("saveError && (")
if idx2 >= 0:
    print("=== saveError付近 ===")
    print(c2[idx2-100:idx2+200])
    print("===")

# 仮登録ボタン付近を確認
idx3 = c2.find("仮登録後の流れ")
if idx3 >= 0:
    print("=== 仮登録後の流れ付近 ===")
    print(c2[idx3-500:idx3+300])
    print("===")

# saveError の直前に警告メッセージを挿入
# 実際のパターン（saveError の前）
old_save_err = """          {saveError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">{saveError}</div>
          )}

          {/* ボタン */}"""

new_save_err = """          {/* 未承認警告 */}
          {partApproved === false && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-sm text-amber-800">
              <p className="font-bold mb-0.5">⚠️ この部品は承認済みレコードがありません</p>
              <p className="text-xs text-amber-600">承認済みの段取シートが存在する部品のみ、新たな加工IDを仮登録できます。</p>
            </div>
          )}
          {partApproved === null && selectedPart && (
            <div className="text-xs text-slate-400 animate-pulse">承認ステータスを確認中…</div>
          )}

          {saveError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">{saveError}</div>
          )}

          {/* ボタン */}"""

if old_save_err in read(new_page):
    patch(new_page, old_save_err, new_save_err, "mc/new/page.tsx 未承認警告メッセージ追加")
else:
    # フォールバック: saveError のみ探す
    c3 = read(new_page)
    # より広いパターンで検索
    if '{saveError && (' in c3:
        # saveError の直前の行を探す
        idx4 = c3.find('{saveError && (')
        # 10行前のコンテキストを表示
        print("=== saveError直前 ===")
        before = c3[max(0,idx4-300):idx4+300]
        print(before)
        print("===")
        # saveError ブロック全体を置換
        old_block = c3[max(0,idx4-2):idx4+200]
        print("置換対象候補:", repr(old_block[:100]))
    else:
        print("WARN: saveError パターンが見つかりません。手動確認が必要です")

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v81b): partApproved state追加+ビルド修正' && git push", cwd=ROOT)
print("DONE v81b")
