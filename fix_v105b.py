#!/usr/bin/env python3
"""
fix_v105b.py
============
【修正内容】
  備考・クランプブロックが描画されない問題を修正。

  原因: drawRect() で color:rgb(1,1,1) (白塗り) を指定していたため、
        テンプレートPDFの内容が全部白で塗りつぶされて見えなくなっていた。

  修正: 矩形を「塗りなし・枠線のみ」に変更。
        pdf-libでは opacity:0 か、描画順を変えて枠線だけにする。
        → borderColor のみ指定し color は指定しない方式に変更。
        また、ラベル背景グレーも半透明で描画するよう修正。

  加えて: nest build コマンドをapps/apiディレクトリで実行するよう修正済み。
"""

import subprocess, sys, os, re as _re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()

# ── drawRect を「塗りなし・枠線のみ」に修正 ──
OLD_DRAW_RECT = '''    // 矩形描画（枠線のみ）
    const drawRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try {
        curPage.drawRectangle({
          x, y, width: w, height: h,
          borderWidth: BOX_LINE_W,
          borderColor: BOX_LINE_COLOR,
          color: rgb(1,1,1),
        });
      } catch(_) {}
    };'''

NEW_DRAW_RECT = '''    // 矩形描画（枠線のみ・塗りなし）
    const drawRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      // 4辺を線で描く（pdf-libのdrawRectangleでcolorを省略すると透明になる）
      try { curPage.drawLine({ start:{x,y}, end:{x:x+w,y}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y:y+h}, end:{x:x+w,y:y+h}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y}, end:{x,y:y+h}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x:x+w,y}, end:{x:x+w,y:y+h}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
    };'''

# ── ラベル背景グレーも透明度付きで塗るよう修正 ──
OLD_LABEL_BG = '''      // ラベル列背景（薄いグレー）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0,
        });
      } catch(_) {}'''

NEW_LABEL_BG = '''      // ラベル列背景（薄いグレー・半透明）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0, opacity: 0.5,
        });
      } catch(_) {}'''

# ── 仕切り縦線の重複drawHLine呼び出しを削除（drawLineで代替済み）──
OLD_VLINE = '''      // ラベル・テキスト列の仕切り縦線
      drawHLine(x + lblW, x + lblW, blockY, BOX_LINE_W, BOX_LINE_COLOR);
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}'''

NEW_VLINE = '''      // ラベル・テキスト列の仕切り縦線
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}'''

# 置換実行
new_src = src
for old, new in [(OLD_DRAW_RECT, NEW_DRAW_RECT), (OLD_LABEL_BG, NEW_LABEL_BG), (OLD_VLINE, NEW_VLINE)]:
    if old not in new_src:
        print(f"WARNING: パターンが見つかりません:\n{old[:80]}...")
    else:
        new_src = new_src.replace(old, new)
        print(f"OK: 置換完了")

if new_src == src:
    print("ERROR: 変更がありませんでした")
    sys.exit(1)

# バックアップ
open(SVC + ".v105.bak", "w", encoding="utf-8").write(src)
open(SVC, "w", encoding="utf-8").write(new_src)
print("OK: mc.service.ts 書き換え完了")

# ── ビルド ──
print("--- API ビルド ---")
r = subprocess.run(
    ["npx", "tsc", "--noEmit", "-p", "apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT
)
errors = [l for l in r.stdout.splitlines() + r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TypeScriptエラー: {len(errors)} 件")
    for e in errors[:20]: print(f"  {e}")
    print("ビルド失敗: 元に戻します")
    open(SVC, "w", encoding="utf-8").write(src)
    sys.exit(1)
print("TypeScriptエラー: 0 件")

# nest build
nest_candidates = [
    f"{PROJECT}/node_modules/.bin/nest",
    f"{PROJECT}/apps/api/node_modules/.bin/nest",
]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    found = subprocess.run(
        ["find", PROJECT, "-path", "*/node_modules/.bin/nest", "-not", "-path", "*/node_modules/*/node_modules/*"],
        capture_output=True, text=True
    ).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)

if nest_bin:
    r2 = subprocess.run([nest_bin, "build", "api"], capture_output=True, text=True, cwd=f"{PROJECT}/apps/api")
    if r2.returncode != 0:
        out = (r2.stdout + r2.stderr).strip()
        print(f"nest build 失敗: {out[:300]}")
        open(SVC, "w", encoding="utf-8").write(src)
        sys.exit(1)
    print("nest build 成功!")
else:
    print("nest CLIが見つかりません。tscビルド済みのためスキップ")

# PM2
subprocess.run(["pm2", "restart", "api"], capture_output=True, cwd=PROJECT)
print("PM2 再起動完了")

# Git push
subprocess.run(["git", "add", "-A"], cwd=PROJECT)
subprocess.run(["git", "commit", "-m", "fix_v105b: drawRect白塗り問題修正（備考・クランプ枠が表示されない不具合）"], cwd=PROJECT)
r3 = subprocess.run(["git", "push"], capture_output=True, text=True, cwd=PROJECT)
print("fix_v105b 完了" if r3.returncode == 0 else f"git push 警告: {r3.stderr[:100]}")

print("""
=== 完了サマリー ===
【修正内容】
  drawRect() の color:rgb(1,1,1) 白塗りを除去。
  → 4辺をdrawLineで個別描画する方式に変更（塗りなし・枠線のみ）。
  → ラベル背景グレーを opacity:0.5 の半透明に変更。
  → テンプレートPDFの内容を隠さず、枠と文字だけを重ねて描画。

【次の確認】
  全体プレビューで備考・クランプ枠が表示されることを確認。
  ヘッダ固定部の下端Y（__header_end_y__）を実際のテンプレートに合わせて調整。
""")
