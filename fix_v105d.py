#!/usr/bin/env python3
"""
fix_v105d.py - 備考・クランプを確実に表示するための最小修正
問題の核心: curY=683ptから blockH=20pt を引いた blockY=663pt に描画しているが、
ページ座標的には正しいはずなのに表示されない。
→ try/catch が全部握りつぶしているため原因不明のまま。

対策:
1. drawNoteBlock を完全に書き直し、try/catch を除去してエラーを表面化
2. ブロックの高さ計算を見直し（テキストあり/なし両方で最低30ptを確保）
3. blockY がページ範囲外にならないよう確認ログを追加
4. DB の __header_end_y__ を確実な値（152.8）のまま使う
   curY計算を単純化: curY = pageH - 152.8（BLOCK_MARGINを引かない）
"""
import subprocess, sys, os

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
src     = open(SVC, encoding="utf-8").read()

# ── curY計算を単純化（BLOCk_MARGIN引かない）──
OLD_CURLY = '''      // ヘッダ固定部の下端Y（pdfkit座標 → pdf-lib座標に変換）
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      const headerEndPK  = headerEndCfg ? parseFloat(headerEndCfg.note || '152.8') : 152.8;
      // pdfkit Y → pdf-lib Y = pageH - pdfkitY
      curY = curPageH - headerEndPK - BLOCK_MARGIN;
    } else {
      curY = curPageH - 155;
    }'''

NEW_CURLY = '''      // ヘッダ固定部の下端Y（pdfkit座標 → pdf-lib座標に変換）
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      const headerEndPK  = headerEndCfg ? parseFloat(headerEndCfg.note || '152.8') : 152.8;
      // pdfkit Y → pdf-lib Y = pageH - pdfkitY
      curY = curPageH - headerEndPK;
      console.log('[PDF-DEBUG] headerEndPK=', headerEndPK, 'curY=', curY, 'curPageH=', curPageH);
    } else {
      curY = curPageH - 155;
    }'''

# ── drawNoteBlock を try/catch なしで書き直し ──
OLD_DRAW = '''    // 備考ブロック描画関数
    const drawNoteBlock = async (
      label: string, text: string,
      x: number, w: number, fs: number,
      lblW: number, minH: number, lh: number,
      padV: number, padH: number,
    ) => {
      const textAreaW = w - lblW - padH * 2;
      const lines     = wrapLines(text, textAreaW, fs);
      const blockH    = Math.max(minH, lines.length * lh + padV * 2);

      await ensureSpace(blockH + 2);

      const blockY = curY - blockH; // pdf-lib: 左下Y

      // 外枠（全体）
      drawRect(x, blockY, w, blockH);

      // ラベル列背景（薄いグレー・半透明）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0, opacity: 0.5,
        });
      } catch(_) {}

      // ラベル・テキスト列の仕切り縦線
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}

      // ラベルテキスト（縦中央）
      const lblTxtY = blockY + blockH / 2 - fs * 0.36;
      drawTxt(label, x + 2, lblTxtY, fs, rgb(0.15,0.15,0.15));

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        drawTxt(line, txtX0, lineY, fs);
      });

      curY -= (blockH + BLOCK_MARGIN);
    };'''

NEW_DRAW = '''    // 備考ブロック描画関数（try/catchなし・エラーを表面化）
    const drawNoteBlock = async (
      label: string, text: string,
      x: number, w: number, fs: number,
      lblW: number, minH: number, lh: number,
      padV: number, padH: number,
    ) => {
      const textAreaW = w - lblW - padH * 2;
      const lines     = wrapLines(text, textAreaW, fs);
      // テキストなしでも最低30ptを確保
      const blockH    = Math.max(minH, lines.length > 0 ? lines.length * lh + padV * 2 : minH);

      await ensureSpace(blockH + 2);

      const blockY = curY - blockH; // pdf-lib: 左下Y
      console.log('[PDF-DEBUG] drawNoteBlock label=', label, 'blockY=', blockY, 'blockH=', blockH, 'curY=', curY, 'lines=', lines.length, 'text.length=', text.length);

      // 外枠 4辺を描画
      curPage.drawLine({ start:{x, y:blockY},         end:{x:x+w, y:blockY},         thickness:BOX_LINE_W, color:BOX_LINE_COLOR });
      curPage.drawLine({ start:{x, y:blockY+blockH},  end:{x:x+w, y:blockY+blockH},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR });
      curPage.drawLine({ start:{x, y:blockY},         end:{x,     y:blockY+blockH},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR });
      curPage.drawLine({ start:{x:x+w, y:blockY},     end:{x:x+w, y:blockY+blockH}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR });

      // ラベル列背景（薄いグレー・半透明）
      curPage.drawRectangle({ x, y:blockY, width:lblW, height:blockH, color:LABEL_BG_COLOR, borderWidth:0, opacity:0.5 });

      // ラベル・テキスト列の仕切り縦線
      curPage.drawLine({ start:{x:x+lblW, y:blockY}, end:{x:x+lblW, y:blockY+blockH}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR });

      // ラベルテキスト（縦中央）
      const lblTxtY = blockY + blockH / 2 - fs * 0.36;
      curPage.drawText(label, { x:x+2, y:lblTxtY, size:fs, font:finalFont, color:rgb(0.15,0.15,0.15) });

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        if (line) curPage.drawText(line, { x:txtX0, y:lineY, size:fs, font:finalFont, color:rgb(0,0,0) });
      });

      curY -= (blockH + BLOCK_MARGIN);
    };'''

new_src = src
changes = 0
for old, new in [(OLD_CURLY, NEW_CURLY), (OLD_DRAW, NEW_DRAW)]:
    if old not in new_src:
        print(f"WARNING: パターンが見つかりません（先頭: {old[:60]}）")
    else:
        new_src = new_src.replace(old, new, 1)
        changes += 1
        print(f"OK: 置換 {changes}")

if changes == 0:
    print("ERROR: 変更なし")
    sys.exit(1)

open(SVC + ".v105b.bak2", "w", encoding="utf-8").write(src)
open(SVC, "w", encoding="utf-8").write(new_src)
print("OK: mc.service.ts 書き換え完了")

# ── ビルド ──
print("--- API ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errors = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TypeScriptエラー: {len(errors)} 件")
    for e in errors[:20]: print(f"  {e}")
    open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
print("TypeScriptエラー: 0 件")

# nest build
nest_candidates = [f"{PROJECT}/node_modules/.bin/nest", f"{PROJECT}/apps/api/node_modules/.bin/nest"]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    found = subprocess.run(["find",PROJECT,"-path","*/node_modules/.bin/nest","-not","-path","*/node_modules/*/node_modules/*"],
        capture_output=True,text=True).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)
if nest_bin:
    r2 = subprocess.run([nest_bin,"build","api"], capture_output=True,text=True, cwd=f"{PROJECT}/apps/api")
    if r2.returncode != 0:
        print(f"nest build 失敗: {(r2.stdout+r2.stderr)[:300]}")
        open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
    print("nest build 成功!")

subprocess.run(["pm2","restart","api"], capture_output=True, cwd=PROJECT)
print("PM2 再起動完了")
subprocess.run(["git","add","-A"], cwd=PROJECT)
subprocess.run(["git","commit","-m","fix_v105d: drawNoteBlockのtry/catch除去・デバッグログ追加"], cwd=PROJECT)
r3 = subprocess.run(["git","push"], capture_output=True,text=True, cwd=PROJECT)
print("fix_v105d 完了" if r3.returncode==0 else f"git push 警告: {r3.stderr[:100]}")
print("""
実行後: pm2 logs api --lines 50 | grep PDF-DEBUG
で座標値を確認し、備考・クランプの描画座標を把握する。
""")
