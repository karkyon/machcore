#!/usr/bin/env python3
"""
fix_tooling_screen_v1i.py
- table-fixed + colgroup で各列幅を明示的に固定（重なり解消）
- 工具・コメント列を十分な幅に拡大
- 削除ボタンを洗練されたUIに変更
- 参照画面・編集画面の外枠を max-w-6xl に拡大
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────
# 1. 参照画面: max-w-4xl → max-w-6xl、colgroup追加
# ─────────────────────────────────────────────
print("=== [1] 参照画面 修正 ===")
with open(PAGE, "r") as f:
    src = f.read()

# ツーリングセクションの外枠幅拡張
OLD_OUTER = '        {mainTab === "tooling" && (\n          <div className="max-w-4xl mx-auto">'
NEW_OUTER = '        {mainTab === "tooling" && (\n          <div className="max-w-6xl mx-auto">'
if OLD_OUTER in src:
    src = src.replace(OLD_OUTER, NEW_OUTER, 1)
    print("  OK: 外枠 max-w-6xl に拡張")
else:
    print("  SKIP: 外枠幅（既に変更済みか不一致）")

# ヘッダーテーブルに colgroup 追加（sticky header table）
OLD_TH_TABLE = (
    '                  <table className="w-full text-xs table-fixed">\n'
    '                    <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">\n'
    '                      <tr>{["N","\u5de5\u5177","T","H","D","D\u5024","SUB","\u30b3\u30e1\u30f3\u30c8","\u9806\u756a"].map(h =>\n'
    '                        <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100">{h}</th>)}</tr>\n'
    '                    </thead>\n'
    '                  </table>'
)
NEW_TH_TABLE = (
    '                  <table className="w-full text-xs table-fixed">\n'
    '                    <colgroup>\n'
    '                      <col style={{width:"90px"}}/><col style={{width:"180px"}}/><col style={{width:"55px"}}/>\n'
    '                      <col style={{width:"55px"}}/><col style={{width:"55px"}}/><col style={{width:"70px"}}/>\n'
    '                      <col style={{width:"65px"}}/><col style={{width:"200px"}}/><col style={{width:"55px"}}/>\n'
    '                    </colgroup>\n'
    '                    <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">\n'
    '                      <tr>\n'
    '                        {[["N","90px"],["工具","180px"],["T","55px"],["H","55px"],["D","55px"],["D値","70px"],["SUB","65px"],["コメント","200px"],["順番","55px"]].map(([h]) =>\n'
    '                          <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">{h}</th>)}\n'
    '                      </tr>\n'
    '                    </thead>\n'
    '                  </table>'
)
if OLD_TH_TABLE in src:
    src = src.replace(OLD_TH_TABLE, NEW_TH_TABLE, 1)
    print("  OK: 参照ヘッダーテーブル colgroup追加")
else:
    print("  SKIP: 参照ヘッダーテーブル不一致")

# データ行テーブルにも同じ colgroup 追加
OLD_DATA_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                      <tbody>'
)
NEW_DATA_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                      <colgroup>\n'
    '                        <col style={{width:"90px"}}/><col style={{width:"180px"}}/><col style={{width:"55px"}}/>\n'
    '                        <col style={{width:"55px"}}/><col style={{width:"55px"}}/><col style={{width:"70px"}}/>\n'
    '                        <col style={{width:"65px"}}/><col style={{width:"200px"}}/><col style={{width:"55px"}}/>\n'
    '                      </colgroup>\n'
    '                      <tbody>'
)
if OLD_DATA_TABLE in src:
    src = src.replace(OLD_DATA_TABLE, NEW_DATA_TABLE, 1)
    print("  OK: 参照データテーブル colgroup追加")
else:
    print("  SKIP: 参照データテーブル不一致")

with open(PAGE, "w") as f:
    f.write(src)

# ─────────────────────────────────────────────
# 2. 編集画面: 全体幅拡張・colgroup追加・入力幅修正・削除ボタンUI改善
# ─────────────────────────────────────────────
print("\n=== [2] 編集画面 修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# ツーリングセクション外枠拡張（max-w-4xl があれば）
OLD_EWIDTH = '            {activeSection === "tooling" && (\n              <div className="max-w-4xl">'
NEW_EWIDTH = '            {activeSection === "tooling" && (\n              <div className="max-w-full">'
if OLD_EWIDTH in esrc:
    esrc = esrc.replace(OLD_EWIDTH, NEW_EWIDTH, 1)
    print("  OK: 編集外枠 max-w-full に拡張")
else:
    print("  SKIP: 編集外枠（既に変更済みか不一致）")

# ヘッダーテーブルに colgroup 追加
OLD_ETH_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                      <thead className="bg-teal-50 sticky top-0 z-10">\n'
    '                        <tr>{["","N","工具","T","H","D","D値","SUB","コメント","順番",""].map(h =>\n'
    '                          <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>\n'
    '                      </thead>\n'
    '                    </table>'
)
NEW_ETH_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                      <colgroup>\n'
    '                        <col style={{width:"80px"}}/><col style={{width:"90px"}}/><col style={{width:"160px"}}/>\n'
    '                        <col style={{width:"60px"}}/><col style={{width:"60px"}}/><col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"70px"}}/><col style={{width:"70px"}}/><col style={{width:"200px"}}/>\n'
    '                        <col style={{width:"70px"}}/><col style={{width:"60px"}}/>\n'
    '                      </colgroup>\n'
    '                      <thead className="bg-teal-50 sticky top-0 z-10">\n'
    '                        <tr>{["","N","工具","T","H","D","D値","SUB","コメント","順番",""].map(h =>\n'
    '                          <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100 whitespace-nowrap">{h}</th>)}</tr>\n'
    '                      </thead>\n'
    '                    </table>'
)
if OLD_ETH_TABLE in esrc:
    esrc = esrc.replace(OLD_ETH_TABLE, NEW_ETH_TABLE, 1)
    print("  OK: 編集ヘッダーテーブル colgroup追加")
else:
    print("  SKIP: 編集ヘッダーテーブル不一致")

# データ行テーブルにも colgroup 追加
OLD_EDATA_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                    <tbody>'
)
NEW_EDATA_TABLE = (
    '                    <table className="w-full text-xs table-fixed">\n'
    '                      <colgroup>\n'
    '                        <col style={{width:"80px"}}/><col style={{width:"90px"}}/><col style={{width:"160px"}}/>\n'
    '                        <col style={{width:"60px"}}/><col style={{width:"60px"}}/><col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"70px"}}/><col style={{width:"70px"}}/><col style={{width:"200px"}}/>\n'
    '                        <col style={{width:"70px"}}/><col style={{width:"60px"}}/>\n'
    '                      </colgroup>\n'
    '                    <tbody>'
)
if OLD_EDATA_TABLE in esrc:
    esrc = esrc.replace(OLD_EDATA_TABLE, NEW_EDATA_TABLE, 1)
    print("  OK: 編集データテーブル colgroup追加")
else:
    print("  SKIP: 編集データテーブル不一致")

# 入力フィールド幅を colgroup に合わせて修正（w-full で統一）
OLD_INPUTS = (
    '                          <td className="px-2 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}\n'
    '                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.t_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_no: e.target.value} : x))}\n'
    '                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}\n'
    '                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}\n'
    '                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.diameter != null ? String(t.diameter) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, diameter: e.target.value === "" ? null : Number(e.target.value)} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" step="0.001" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.sub_pg_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sub_pg_no: e.target.value} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.note ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}\n'
    '                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.sort_order != null ? String(t.sort_order) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sort_order: e.target.value === "" ? 0 : Number(e.target.value)} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" /></td>\n'
    '                          <td className="px-2 py-1"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}\n'
    '                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>'
)
NEW_INPUTS = (
    '                          <td className="px-1 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.t_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_no: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.diameter != null ? String(t.diameter) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, diameter: e.target.value === "" ? null : Number(e.target.value)} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" step="0.001" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.sub_pg_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sub_pg_no: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.note ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-1 py-1"><input value={t.sort_order != null ? String(t.sort_order) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sort_order: e.target.value === "" ? 0 : Number(e.target.value)} : x))}\n'
    '                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" /></td>\n'
    '                          <td className="px-1 py-1 text-center"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}\n'
    '                            className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">\u5220\u9664</button></td>'
)
if OLD_INPUTS in esrc:
    esrc = esrc.replace(OLD_INPUTS, NEW_INPUTS, 1)
    print("  OK: 入力フィールド幅修正・削除ボタンUI改善")
else:
    print("  WARN: 入力フィールドが一致しない")
    idx = esrc.find('tool_no ?? ""')
    print("  CONTEXT:", repr(esrc[max(0,idx-50):idx+200]))

with open(EDIT, "w") as f:
    f.write(esrc)
print("  SAVED:", EDIT)

# ─────────────────────────────────────────────
# 3. ビルド & 再起動 & git push
# ─────────────────────────────────────────────
print("\n=== [3] Next.js ビルド (apps/web) ===")
res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -10"],
    capture_output=True, text=True
)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:", res.stderr[-800:])
    sys.exit(1)

print("=== [4] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK")

print("=== [5] git push ===")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1i - colgroup fixed widths, w-full inputs, delete button UI" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
