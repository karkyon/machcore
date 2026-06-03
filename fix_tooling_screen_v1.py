#!/usr/bin/env python3
"""
fix_tooling_screen_v1.py
ツーリング画面修正:
  - 参照画面 /mc/[mc_id]/page.tsx: 不足列(順番・N工具記号・T番号・コメント・SUB)追加
  - 編集画面 /mc/[mc_id]/edit/page.tsx: 不足列(T番号・径・SUB)追加
"""
import subprocess, sys, os

BASE = os.path.expanduser("~/projects/machcore")
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────
# 1. 参照画面 page.tsx
# ─────────────────────────────────────────────
print("=== [1] 参照画面 ツーリングテーブル修正 ===")
with open(PAGE, "r") as f:
    src = f.read()

# ヘッダー列
OLD_TH = '                    <tr>{["T番号","工具名","径(mm)","H補正","D補正","種別","備考"].map(h =>'
NEW_TH = '                    <tr>{["順番","N(工具記号)","T番号","コメント","H補正","D補正","径(mm)","SUB","種別","備考"].map(h =>'
if OLD_TH in src:
    src = src.replace(OLD_TH, NEW_TH, 1)
    print("  OK: ヘッダー列更新")
else:
    print("  SKIP: ヘッダー列 既に更新済みか不一致")

# データ行（旧7列 → 新10列）
OLD_ROWS = (
    '                        <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>\n'
    '                        <td className="px-3 py-2 font-mono font-bold text-teal-600">{t.toolNo}</td>\n'
    '                        <td className="px-3 py-2">{t.toolName ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center">{t.diameter ? Number(t.diameter).toFixed(1) : "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.lengthOffsetNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diaOffsetNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2">{t.toolType ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500">{t.note ?? "—"}</td>'
)
NEW_ROWS = (
    '                        <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>\n'
    '                        <td className="px-3 py-2 text-center font-mono text-slate-400 w-10">{t.sortOrder}</td>\n'
    '                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{t.toolNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-700">{t.tNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500 text-[11px] max-w-[120px] truncate" title={t.dValueContent ?? ""}>{t.dValueContent ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.lengthOffsetNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diaOffsetNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diameter ? Number(t.diameter).toFixed(3) : "—"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-500">{t.subPgNo ?? "—"}</td>\n'
    '                        <td className="px-3 py-2">{t.toolType ?? "—"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500">{t.note ?? "—"}</td>'
)
if OLD_ROWS in src:
    src = src.replace(OLD_ROWS, NEW_ROWS, 1)
    print("  OK: データ行更新")
else:
    print("  WARN: データ行 既に更新済みか不一致 — 手動確認要")
    # コンテキスト表示
    idx = src.find('<tr key={t.id}')
    if idx != -1:
        print("  CONTEXT (先頭の<tr key={t.id}>周辺):\n", src[idx:idx+600])

with open(PAGE, "w") as f:
    f.write(src)
print("  SAVED:", PAGE)

# ─────────────────────────────────────────────
# 2. 編集画面 edit/page.tsx
# ─────────────────────────────────────────────
print("\n=== [2] 編集画面 ツーリングテーブル修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# ツーリングのtheadを特定 (現行: N(工具記号)|工具名|H補正番号|D補正番号|種別|削除)
OLD_ETH = '                      <tr>{["N(工具記号)","工具名","H補正番号","D補正番号","種別",""].map(h =>'
NEW_ETH = '                      <tr>{["N(工具記号)","T番号","工具名","H補正番号","D補正番号","径(mm)","SUB","種別",""].map(h =>'
if OLD_ETH in esrc:
    esrc = esrc.replace(OLD_ETH, NEW_ETH, 1)
    print("  OK: 編集ヘッダー列更新")
else:
    print("  SKIP: 編集ヘッダー 既に更新済みか不一致")
    # フォールバック検索
    idx = esrc.find('N(工具記号)')
    if idx != -1:
        print("  CONTEXT:", repr(esrc[max(0,idx-50):idx+300]))

# 編集行: tool_no の次に t_no を追加、tool_name の次に diameter・sub_pg_no を追加
OLD_EROW = (
    '                          <td className="px-2 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}\n'
    '                            className="w-40 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.tool_type ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_type: e.target.value} : x))}\n'
    '                            className="w-20 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>'
)
NEW_EROW = (
    '                          <td className="px-2 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}\n'
    '                            className="w-20 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" placeholder="N10" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.t_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_no: e.target.value} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" placeholder="T01" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}\n'
    '                            className="w-36 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" placeholder="H1" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}\n'
    '                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" placeholder="D1" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.diameter != null ? String(t.diameter) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, diameter: e.target.value === "" ? null : Number(e.target.value)} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" placeholder="0.000" type="number" step="0.001" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.sub_pg_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sub_pg_no: e.target.value} : x))}\n'
    '                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" placeholder="1001" /></td>\n'
    '                          <td className="px-2 py-1"><input value={t.tool_type ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_type: e.target.value} : x))}\n'
    '                            className="w-20 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>'
)
if OLD_EROW in esrc:
    esrc = esrc.replace(OLD_EROW, NEW_EROW, 1)
    print("  OK: 編集データ行更新（T番号・径・SUB列追加）")
else:
    print("  WARN: 編集データ行 不一致 — 手動確認要")
    idx = esrc.find("tool_no")
    if idx != -1:
        print("  CONTEXT:", repr(esrc[max(0,idx-20):idx+500]))

with open(EDIT, "w") as f:
    f.write(esrc)
print("  SAVED:", EDIT)

# ─────────────────────────────────────────────
# 3. ビルド & 再起動
# ─────────────────────────────────────────────
print("\n=== [3] Next.js ビルド ===")
res = subprocess.run(
    ["sh", "-c", "cd ~/projects/machcore && npx next build 2>&1 | tail -8"],
    capture_output=True, text=True
)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:", res.stderr)
    sys.exit(1)

print("\n=== [4] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK: machcore-web restarted")

# ─────────────────────────────────────────────
# 4. git push
# ─────────────────────────────────────────────
print("\n=== [5] git push ===")
subprocess.run(["sh", "-c",
    'cd ~/projects/machcore && git add -A && '
    'git commit -m "fix: tooling screen - add missing columns (N/T/diameter/SUB/sortOrder)" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
