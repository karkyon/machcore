#!/usr/bin/env python3
"""
fix_tooling_screen_v1b.py
- 参照画面 page.tsx: データ行を実際の文字列で置換（v1でWARNになった箇所を修正）
- 編集画面 edit/page.tsx: ヘッダーをv1でSKIPした箇所を修正
- ビルド & pm2 restart & git push
"""
import subprocess, sys, os

BASE = "/home/karkyon/projects/machcore"
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────
# 1. 参照画面 データ行置換（先頭の<tr key={t.id}>を検索して</tr>まで丸ごと置換）
# ─────────────────────────────────────────────
print("=== [1] 参照画面 データ行置換 ===")
with open(PAGE, "r") as f:
    src = f.read()

MARKER = '<tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>'
idx = src.find(MARKER)
if idx == -1:
    print("  ERROR: <tr key={t.id}> が見つかりません")
    sys.exit(1)

block_end = src.find('</tr>', idx)
old_block = src[idx:block_end + 5]
print("  置換前ブロック:\n", old_block[:400])

NEW_BLOCK = (
    '<tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>\n'
    '                        <td className="px-3 py-2 text-center font-mono text-slate-400 w-10">{t.sortOrder}</td>\n'
    '                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{t.toolNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-700">{t.tNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500 text-[11px] max-w-[120px] truncate" title={t.dValueContent ?? ""}>{t.dValueContent ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.lengthOffsetNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diaOffsetNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-center font-mono">{t.diameter ? Number(t.diameter).toFixed(3) : "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 font-mono text-slate-500">{t.subPgNo ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2">{t.toolType ?? "\u2014"}</td>\n'
    '                        <td className="px-3 py-2 text-slate-500">{t.note ?? "\u2014"}</td>\n'
    '                      </tr>'
)

src = src[:idx] + NEW_BLOCK + src[block_end + 5:]
with open(PAGE, "w") as f:
    f.write(src)
print("  OK: page.tsx データ行置換完了")

# ─────────────────────────────────────────────
# 2. 編集画面 ヘッダー修正（v1でSKIPした箇所 — 実際の文字列を探して置換）
# ─────────────────────────────────────────────
print("\n=== [2] 編集画面 ヘッダー修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# 実際のヘッダー文字列を検索
EHEAD_MARKER = '"N(工具記号)"'
idx2 = esrc.find(EHEAD_MARKER)
if idx2 == -1:
    print("  WARN: 編集画面ヘッダーが見つかりません — スキップ")
else:
    line_start = esrc.rfind('\n', 0, idx2) + 1
    line_end   = esrc.find('\n', idx2)
    old_line   = esrc[line_start:line_end]
    print("  現在のヘッダー行:", old_line.strip())

    # 既にT番号が含まれていれば何もしない
    if '"T番号"' in old_line and '"径(mm)"' in old_line and '"SUB"' in old_line:
        print("  SKIP: 既に更新済み")
    else:
        # 行全体を新しいヘッダー行に置換
        NEW_ELINE = (
            '                      <tr>{["N(工具記号)","T番号","工具名","H補正番号","D補正番号","径(mm)","SUB","種別",""].map(h =>'
        )
        # map(h => から始まる閉じ括弧行まで含めて置換
        map_end = esrc.find('</tr>', line_start)
        old_head_block = esrc[line_start:map_end + 5]
        # 閉じ <th> パターンを維持して行だけ差し替え
        esrc = esrc[:line_start] + NEW_ELINE + esrc[line_end:]
        print("  OK: 編集ヘッダー行更新")

    with open(EDIT, "w") as f:
        f.write(esrc)
    print("  SAVED:", EDIT)

# ─────────────────────────────────────────────
# 3. ビルド & 再起動 & git push
# ─────────────────────────────────────────────
print("\n=== [3] Next.js ビルド ===")
res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore && npx next build 2>&1 | tail -10"],
    capture_output=True, text=True
)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:\n", res.stderr[-800:])
    sys.exit(1)

print("=== [4] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK")

print("=== [5] git push ===")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling screen v1b - reference/edit columns (N/T/diameter/SUB/sortOrder)" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
