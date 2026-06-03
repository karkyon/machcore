#!/usr/bin/env python3
"""
fix_tooling_screen_v1e.py
1. 参照画面 (page.tsx): 列順を旧システムに合わせる
   旧: N / 工具(記号) / T / H / D / D値 / SUB / コメント / 順番
   → N(工具記号) / T番号 / H補正 / D補正 / D値(径) / SUB / コメント / 順番
2. 編集画面 (edit/page.tsx):
   - setToolingRows 時に camelCase → snake_case に変換してセット
   - 表示が全部 N10/T01/... になっていた根本原因を修正
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────
# 1. 参照画面 列順を旧システムに合わせる
#    旧順: N(工具記号) | T番号 | H補正 | D補正 | 径(D値) | SUB | コメント | 順番
# ─────────────────────────────────────────────
print("=== [1] 参照画面 列順修正 ===")
with open(PAGE, "r") as f:
    src = f.read()

# ヘッダー: 現在の順番を旧システム順に変更
OLD_TH = '                    <tr>{["順番","N(工具記号)","T番号","コメント","H補正","D補正","径(mm)","SUB","種別","備考"].map(h =>'
NEW_TH = '                    <tr>{["N(工具記号)","T番号","H補正","D補正","径(mm)","SUB","コメント","順番"].map(h =>'
if OLD_TH in src:
    src = src.replace(OLD_TH, NEW_TH, 1)
    print("  OK: ヘッダー列順更新")
else:
    print("  WARN: ヘッダー不一致")
    idx = src.find("順番")
    print("  CONTEXT:", src[max(0,idx-100):idx+200])

# データ行: 旧システム順に対応するフィールドで並べ替え
MARKER = '<tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>'
idx = src.find(MARKER)
if idx == -1:
    print("  ERROR: <tr key={t.id}> not found")
    sys.exit(1)

block_end = src.find('</tr>', idx)
print("  現在のデータ行:", src[idx:min(idx+300, block_end)][:200])

NEW_BLOCK = (
    '<tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>\n'
    '                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{t.toolNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-700">{t.tNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.lengthOffsetNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diaOffsetNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diameter ? Number(t.diameter).toFixed(3) : "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-500">{t.subPgNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500 text-[11px]">{t.dValueContent ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono text-slate-400">{t.sortOrder}</td>\n'
    '                      </tr>'
)

src = src[:idx] + NEW_BLOCK + src[block_end + 5:]
with open(PAGE, "w") as f:
    f.write(src)
print("  OK: page.tsx データ行更新")

# ─────────────────────────────────────────────
# 2. 編集画面: setToolingRows の変換ロジック修正
#    d.tooling は camelCase で返るので snake_case に変換する
# ─────────────────────────────────────────────
print("\n=== [2] 編集画面 データ読み込みマッピング修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# setToolingRows(d.tooling ?? []) を変換付きに差し替え
OLD_SET = "      setToolingRows(d.tooling ?? []);"
NEW_SET = (
    "      setToolingRows((d.tooling ?? []).map((t: any) => ({\n"
    "        sort_order:       t.sortOrder       ?? t.sort_order       ?? 0,\n"
    "        tool_no:          t.toolNo          ?? t.tool_no          ?? \"\",\n"
    "        t_no:             t.tNo             ?? t.t_no             ?? \"\",\n"
    "        tool_name:        t.toolName        ?? t.tool_name        ?? \"\",\n"
    "        length_offset_no: t.lengthOffsetNo  ?? t.length_offset_no ?? \"\",\n"
    "        dia_offset_no:    t.diaOffsetNo     ?? t.dia_offset_no    ?? \"\",\n"
    "        diameter:         t.diameter        != null ? Number(t.diameter) : null,\n"
    "        d_value_content:  t.dValueContent   ?? t.d_value_content  ?? \"\",\n"
    "        sub_pg_no:        t.subPgNo         ?? t.sub_pg_no        ?? \"\",\n"
    "        tool_type:        t.toolType        ?? t.tool_type        ?? \"\",\n"
    "        note:             t.note            ?? \"\",\n"
    "        raw_program_line: t.rawProgramLine  ?? t.raw_program_line ?? \"\",\n"
    "      })));"
)
if OLD_SET in esrc:
    esrc = esrc.replace(OLD_SET, NEW_SET, 1)
    print("  OK: setToolingRows マッピング修正")
else:
    print("  WARN: setToolingRows 行が一致しない")
    idx2 = esrc.find("setToolingRows")
    print("  CONTEXT:", esrc[max(0,idx2-20):idx2+200])

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
    print("BUILD ERROR:", res.stderr[-500:])
    sys.exit(1)

print("=== [4] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK")

print("=== [5] git push ===")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1e - column order + edit camelCase mapping" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
