#!/usr/bin/env python3
"""
fix_tooling_screen_v1n.py
コメント列: col（幅なし） → 300px（元200px × 1.5倍）
ヘッダーと明細両方のcolgroupを同時修正。
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

print("=== [1] コメント列幅修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# colgroup内のコメント列（幅なし <col/>）を300pxに修正
# ツーリングテーブルのcolgroupは2箇所ある（ヘッダー用・データ用）→ 両方修正
OLD_COL = (
    '                        <col style={{width:"72px"}}/>\n'
    '                        <col style={{width:"90px"}}/>\n'
    '                        <col style={{width:"210px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
)
NEW_COL = (
    '                        <col style={{width:"72px"}}/>\n'
    '                        <col style={{width:"90px"}}/>\n'
    '                        <col style={{width:"210px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"300px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
)

count = esrc.count(OLD_COL)
if count == 0:
    print("  ERROR: colgroup が見つかりません")
    sys.exit(1)

esrc = esrc.replace(OLD_COL, NEW_COL)  # 全箇所（ヘッダー＋データ両方）修正
print(f"  OK: {count}箇所 コメント列 col → 300px に修正")

with open(EDIT, "w") as f:
    f.write(esrc)
print("  SAVED:", EDIT)

# ─────────────────────────────────────────────
print("\n=== [2] Next.js ビルド ===")
res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -8"],
    capture_output=True, text=True
)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:\n", res.stderr[-500:])
    sys.exit(1)

print("=== [3] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK")

print("=== [4] git push ===")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1n - comment col 300px (200px x1.5)" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
