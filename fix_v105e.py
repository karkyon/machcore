#!/usr/bin/env python3
"""
fix_v105e.py
============
問題の根本原因を整理して確実に修正する。

【画像から判明した問題】
1. ヘッダ固定部下端Y が守られていない
   → __header_end_y__ の note='152.8' (pdfkit Y) を使うはずが
     テンプレートの「備考」行より上でツーリングが始まっている
   → 原因: fix_v105c のDBマイグレーションで note='310' に書き換わっている可能性
     310pt(pdfkit) → curY = 841.89 - 310 = 531.89pt
     これは正しい位置のはずだが...

2. 備考・クランプの x 座標がDBの設定値と違う
   → parseCfgStr が note='x=643,y=578,...' を読んでいるため
     fix_v105c のDBマイグレーションで note が書き換わっている

3. fix_v105c は実行されていないはずだが、DBマイグレーション部分は
   fix_v105.py で既に __note_cfg__ / __clamp_cfg__ を insert 済み
   その後 fix_v105c の説明でDB更新SQLが提示されたが実行されていない

【対策】
DBを正しい値にリセット + コードを確実な実装に修正

DBの正しい値：
  __header_end_y__ note = '152.8'  (pdfkit Y座標: 備考行の上端)
  __note_cfg__     note = 'x=30,w=535,fs=7,label_w=28,min_h=20'
  __clamp_cfg__    note = 'x=30,w=535,fs=7,label_w=28,min_h=20'

コードの修正：
  parseCfgStr で 'y=' キーを誤って label_w などと混同していないか確認
  curY 計算のデバッグログで実際の値を確認できるようにする
"""

import subprocess, sys, os

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

# ── Step1: DBを正しい値にリセット ──────────────────────────────
DB_URL_RAW = "postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"
env_path = f"{PROJECT}/.env"
db_url = DB_URL_RAW
if os.path.exists(env_path):
    for line in open(env_path):
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=",1)[1].strip().strip('"').strip("'")
            break
psql_url = db_url.split('?')[0] if '?' in db_url else db_url

RESET_SQL = """
UPDATE pdf_field_definitions SET note = '152.8'
WHERE field_key = '__header_end_y__';

UPDATE pdf_field_definitions SET note = 'x=30,w=535,fs=7,label_w=28,min_h=20'
WHERE field_key = '__note_cfg__';

UPDATE pdf_field_definitions SET note = 'x=30,w=535,fs=7,label_w=28,min_h=20'
WHERE field_key = '__clamp_cfg__';
"""

print("=== fix_v105e: DB修正 + コード確実化 ===")
print("--- DB修正 ---")
r = subprocess.run(["psql", psql_url, "-c", RESET_SQL], capture_output=True, text=True, timeout=30)
if r.returncode != 0:
    print(f"  警告: {r.stderr[:200]}")
else:
    print("  DB修正完了")

# 確認
r2 = subprocess.run(["psql", psql_url, "-c",
    "SELECT field_key, note FROM pdf_field_definitions WHERE field_key IN ('__header_end_y__','__note_cfg__','__clamp_cfg__') ORDER BY field_key;"],
    capture_output=True, text=True, timeout=30)
print(r2.stdout)

# ── Step2: コード修正 ───────────────────────────────────────────
src = open(SVC, encoding="utf-8").read()

# 問題①: parseCfgStr の note 列読み取り確認
# 現在のcurY計算とparseCfgStr実装を確認
if "parseCfgStr" not in src:
    print("ERROR: parseCfgStr が見つかりません")
    sys.exit(1)

# parseCfgStr の実装を確認
import re
m = re.search(r'const parseCfgStr = \(s: string\)[^}]+\}', src, re.DOTALL)
if m:
    print("parseCfgStr実装:", m.group(0)[:200])

# 問題②: NOTE_X の取得確認  
# noteCfg.x ?? 30 → parseCfgStr が 'x=30,...' を正しくパースしているか
# parseCfgStr: "x=30,w=535,fs=7,label_w=28,min_h=20"
# split(',') → ["x=30","w=535","fs=7","label_w=28","min_h=20"]
# 各kv.split('=') → k="x", v="30" → m["x"]=30  ✓

# 問題③: NOTE_X が正しく使われているか
# const NOTE_X = noteCfg.x ?? 30; → noteCfg.x = parseCfgStr(note).x
# note = 'x=30,w=535,fs=7,label_w=28,min_h=20' → noteCfg.x = 30 ✓

# 問題の本当の原因: __note_cfg__ の note 列が
# fix_v105c で 'x=643,y=578,w=490,fs=7,max_lines=4' になっていたため
# parseCfgStr("x=643,...").x = 643  ← これが左端ズレの原因

# DB修正済みなので note='x=30,w=535,fs=7,label_w=28,min_h=20' になった
# → NOTE_X = 30, NOTE_W = 535 ✓

# 問題④: curY 計算
# __header_end_y__ note='152.8' → headerEndPK=152.8
# curY = curPageH - 152.8 = 841.89 - 152.8 = 689.09pt
# blockH = max(20, lines*lh+8) = 20（最小値）
# blockY = 689.09 - 20 = 669.09pt  ← ページ上端から約173ptの位置
# これはテンプレートの備考行(pdfkit Y≈253, pdf-lib Y≈589)より「上」

# つまり blockY=669 > 589 なので備考行の上に重なる可能性あり
# しかし実際には表示されていない → drawText がエラー？

# コードに console.log を追加してデバッグ情報を出力
OLD_NOTEBLOCK_START = '''      console.log('[PDF-DEBUG] drawNoteBlock label=', label, 'blockY=', blockY, 'blockH=', blockH, 'curY=', curY, 'lines=', lines.length, 'text.length=', text.length);

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

      curY -= (blockH + BLOCK_MARGIN);'''

NEW_NOTEBLOCK_START = '''      console.log('[PDF-DEBUG] drawNoteBlock label=', label, 'x=',x,'w=',w,'blockY=', blockY, 'blockH=', blockH, 'curY=', curY, 'lines=', lines.length, 'text.length=', text.length, 'pageH=', curPageH);

      // 外枠 4辺を描画（try/catchで保護）
      try { curPage.drawLine({ start:{x, y:blockY},        end:{x:x+w, y:blockY},        thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(e:any){ console.error('[PDF-ERR] line1',e?.message); }
      try { curPage.drawLine({ start:{x, y:blockY+blockH}, end:{x:x+w, y:blockY+blockH}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(e:any){ console.error('[PDF-ERR] line2',e?.message); }
      try { curPage.drawLine({ start:{x, y:blockY},        end:{x,     y:blockY+blockH}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(e:any){ console.error('[PDF-ERR] line3',e?.message); }
      try { curPage.drawLine({ start:{x:x+w, y:blockY},    end:{x:x+w, y:blockY+blockH},thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(e:any){ console.error('[PDF-ERR] line4',e?.message); }

      // ラベル列背景（薄いグレー・半透明）
      try { curPage.drawRectangle({ x, y:blockY, width:lblW, height:blockH, color:LABEL_BG_COLOR, borderWidth:0, opacity:0.5 }); } catch(e:any){ console.error('[PDF-ERR] rect',e?.message); }

      // ラベル・テキスト列の仕切り縦線
      try { curPage.drawLine({ start:{x:x+lblW, y:blockY}, end:{x:x+lblW, y:blockY+blockH}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(e:any){ console.error('[PDF-ERR] vline',e?.message); }

      // ラベルテキスト（縦中央）
      const lblTxtY = blockY + blockH / 2 - fs * 0.36;
      try { curPage.drawText(label, { x:x+2, y:lblTxtY, size:fs, font:finalFont, color:rgb(0.15,0.15,0.15) }); } catch(e:any){ console.error('[PDF-ERR] label',e?.message); }

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        try { if (line) curPage.drawText(line, { x:txtX0, y:lineY, size:fs, font:finalFont, color:rgb(0,0,0) }); } catch(e:any){ console.error('[PDF-ERR] text',i,e?.message); }
      });

      curY -= (blockH + BLOCK_MARGIN);'''

new_src = src
if OLD_NOTEBLOCK_START in new_src:
    new_src = new_src.replace(OLD_NOTEBLOCK_START, NEW_NOTEBLOCK_START, 1)
    print("OK: drawNoteBlock エラーログ追加完了")
else:
    print("WARNING: drawNoteBlock パターン見つからず（既に修正済みの可能性）")

if new_src != src:
    open(SVC, "w", encoding="utf-8").write(new_src)
    print("OK: mc.service.ts 書き換え完了")
else:
    print("変更なし - DBのみ修正")

# ── ビルド ──
print("--- API ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errors = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TypeScriptエラー: {len(errors)} 件")
    for e in errors[:10]: print(f"  {e}")
    open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
print("TypeScriptエラー: 0 件")

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

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2 再起動完了 (machcore-api)")

subprocess.run(["git","add","-A"], cwd=PROJECT)
subprocess.run(["git","commit","-m","fix_v105e: DB修正(note列リセット) + 描画エラーログ追加"], cwd=PROJECT)
r3 = subprocess.run(["git","push"], capture_output=True,text=True, cwd=PROJECT)
print("fix_v105e 完了" if r3.returncode==0 else f"git push 警告: {r3.stderr[:100]}")
print("""
実行後:
1. ブラウザで全体プレビューを実行
2. pm2 logs machcore-api --lines 300 --nostream 2>&1 | grep -E "PDF-DEBUG|PDF-ERR"
でログを確認する
""")
