#!/usr/bin/env python3
"""
fix_v105f.py
============
【修正内容】
1. __header_end_y__ はデザイナーでドラッグして位置を決める
   → note列ではなく y列(pdf-lib座標=下から)をそのまま curY に使用
   → デザイナーで動かすだけで反映される

2. __note_cfg__ / __clamp_cfg__ の x/w もデザイナーの x/y/font_size を使用
   → note列のx=30,w=535は廃止
   → x列 = ブロック左端X座標
   → y列 = (使わない、curYから相対で決まる)  
   → font_size列 = フォントサイズ
   → note列 = 'w=幅,label_w=ラベル幅,min_h=最小高' のみ残す

3. 備考・クランプのラベル列幅を現在の2倍(28→56)に変更
   → DBのnote列を更新

【設計】
  curY = DBの __header_end_y__ の y列(pdf-lib Y座標) をそのまま使用
  ブロックX = DBの __note_cfg__ の x列
  ブロック幅 = DBの __note_cfg__ の note列 w= パラメータ
  ラベル幅  = DBの __note_cfg__ の note列 label_w= パラメータ
"""
import subprocess, sys, os

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

DB_URL_RAW = "postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"
env_path = f"{PROJECT}/.env"
db_url = DB_URL_RAW
if os.path.exists(env_path):
    for line in open(env_path):
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=",1)[1].strip().strip('"').strip("'")
            break
psql_url = db_url.split('?')[0] if '?' in db_url else db_url

# DBのnote列を w/label_w/min_h のみに変更（x/wはx列・note列から取得する新方式）
# label_wを56(現在の2倍)に変更
RESET_SQL = """
UPDATE pdf_field_definitions
  SET note = 'w=535,label_w=56,min_h=22'
WHERE field_key IN ('__note_cfg__', '__clamp_cfg__');
"""

print("=== fix_v105f: __header_end_y__をy列使用に変更 + ブロック幅2倍 ===")
print("--- DB更新 ---")
r = subprocess.run(["psql", psql_url, "-c", RESET_SQL], capture_output=True, text=True, timeout=30)
print("  完了" if r.returncode==0 else f"  警告: {r.stderr[:100]}")

r2 = subprocess.run(["psql", psql_url, "-c",
    "SELECT field_key, x, y, font_size, note FROM pdf_field_definitions "
    "WHERE field_key IN ('__header_end_y__','__note_cfg__','__clamp_cfg__') ORDER BY field_key;"],
    capture_output=True, text=True, timeout=30)
print(r2.stdout)

src = open(SVC, encoding="utf-8").read()

# ── 修正①: curY を y列(pdf-lib座標)から直接取得 ──
OLD_CURY = '''      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      const headerEndPK  = headerEndCfg ? parseFloat(headerEndCfg.note || '152.8') : 152.8;
      // pdfkit Y → pdf-lib Y = pageH - pdfkitY
      curY = curPageH - headerEndPK;
      console.log('[PDF-DEBUG] headerEndPK=', headerEndPK, 'curY=', curY, 'curPageH=', curPageH);'''

NEW_CURY = '''      // __header_end_y__ の y列(pdf-lib座標=下から)をそのまま curY に使用
      // デザイナーでドラッグするだけで反映される
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      curY = headerEndCfg ? Number(headerEndCfg.y) : (curPageH - 310);
      console.log('[PDF-DEBUG] curY from y-col=', curY, 'curPageH=', curPageH);'''

# ── 修正②: NOTE_X/NOTE_W を x列・note列から取得する方式に変更 ──
OLD_NOTECFG = '''    const noteCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_cfg__');
    const noteCfgStr = noteCfgF?.note || 'x=30,w=535,fs=7,label_w=28,min_h=20';
    const noteCfg    = parseCfgStr(noteCfgStr);

    const NOTE_X       = noteCfg.x       ?? 30;
    const NOTE_W       = noteCfg.w       ?? 535;
    const NOTE_FS      = noteCfg.fs      ?? 7;
    const NOTE_LBL_W   = noteCfg.label_w ?? 28;
    const NOTE_MIN_H   = noteCfg.min_h   ?? 20;
    const NOTE_LH      = NOTE_FS * 1.55;  // 行高
    const NOTE_PAD_V   = 4;               // 上下内側余白
    const NOTE_PAD_H   = 3;               // 左右内側余白'''

NEW_NOTECFG = '''    // __note_cfg__: x列=ブロック左端X, font_size列=フォントサイズ
    //               note列='w=幅,label_w=ラベル幅,min_h=最小高'
    const noteCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_cfg__');
    const noteCfgOpt = parseCfgStr(noteCfgF?.note || 'w=535,label_w=56,min_h=22');

    const NOTE_X       = noteCfgF ? Number(noteCfgF.x)         : 30;
    const NOTE_W       = noteCfgOpt.w        ?? 535;
    const NOTE_FS      = noteCfgF ? Number(noteCfgF.font_size)  : 7;
    const NOTE_LBL_W   = noteCfgOpt.label_w  ?? 56;
    const NOTE_MIN_H   = noteCfgOpt.min_h    ?? 22;
    const NOTE_LH      = NOTE_FS * 1.55;  // 行高
    const NOTE_PAD_V   = 4;               // 上下内側余白
    const NOTE_PAD_H   = 3;               // 左右内側余白
    console.log('[PDF-DEBUG] NOTE_X=',NOTE_X,'NOTE_W=',NOTE_W,'NOTE_FS=',NOTE_FS,'NOTE_LBL_W=',NOTE_LBL_W);'''

# ── 修正③: clampCfg も同様に x列から取得 ──
OLD_CLAMPCFG = '''    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgStr = clampCfgF?.note || 'x=30,w=535,fs=7,label_w=28,min_h=20';
    const clampCfg    = parseCfgStr(clampCfgStr);

    await drawNoteBlock(
      'クランプ', clampText,
      clampCfg.x ?? 30, clampCfg.w ?? 535, clampCfg.fs ?? 7,
      clampCfg.label_w ?? 28, clampCfg.min_h ?? 20, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );'''

NEW_CLAMPCFG = '''    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgOpt = parseCfgStr(clampCfgF?.note || 'w=535,label_w=56,min_h=22');
    const CLAMP_X     = clampCfgF ? Number(clampCfgF.x)        : NOTE_X;
    const CLAMP_W     = clampCfgOpt.w       ?? NOTE_W;
    const CLAMP_FS    = clampCfgF ? Number(clampCfgF.font_size) : NOTE_FS;
    const CLAMP_LBL_W = clampCfgOpt.label_w ?? NOTE_LBL_W;
    const CLAMP_MIN_H = clampCfgOpt.min_h   ?? NOTE_MIN_H;

    await drawNoteBlock(
      'クランプ', clampText,
      CLAMP_X, CLAMP_W, CLAMP_FS,
      CLAMP_LBL_W, CLAMP_MIN_H, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );'''

new_src = src
changes = 0
for old, new, label in [
    (OLD_CURY,     NEW_CURY,     'curY from y-col'),
    (OLD_NOTECFG,  NEW_NOTECFG,  'NOTE_X/W from x-col'),
    (OLD_CLAMPCFG, NEW_CLAMPCFG, 'CLAMP from x-col'),
]:
    if old in new_src:
        new_src = new_src.replace(old, new, 1)
        changes += 1
        print(f"OK: {label}")
    else:
        print(f"WARNING: パターン未検出: {label}")

if changes == 0:
    print("ERROR: 変更なし"); sys.exit(1)

open(SVC, "w", encoding="utf-8").write(new_src)
print("OK: mc.service.ts 書き換え完了")

print("--- ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errors = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TSエラー: {len(errors)}件"); [print(f"  {e}") for e in errors[:10]]
    open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
print("TypeScriptエラー: 0件")

nest_candidates = [f"{PROJECT}/node_modules/.bin/nest", f"{PROJECT}/apps/api/node_modules/.bin/nest"]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    found = subprocess.run(["find",PROJECT,"-path","*/node_modules/.bin/nest",
        "-not","-path","*/node_modules/*/node_modules/*"],
        capture_output=True,text=True).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)
if nest_bin:
    r2 = subprocess.run([nest_bin,"build","api"],capture_output=True,text=True,cwd=f"{PROJECT}/apps/api")
    if r2.returncode != 0:
        print(f"nest build 失敗: {(r2.stdout+r2.stderr)[:300]}")
        open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
    print("nest build 成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")

subprocess.run(["git","add","-A"], cwd=PROJECT)
subprocess.run(["git","commit","-m",
    "fix_v105f: header_end_yをy列使用/note_cfgをx列使用/ラベル幅2倍"], cwd=PROJECT)
r3 = subprocess.run(["git","push"],capture_output=True,text=True,cwd=PROJECT)
print("fix_v105f 完了" if r3.returncode==0 else f"push警告: {r3.stderr[:100]}")
print("""
【変更後の操作方法】
  ヘッダ固定部下端Y: PDFエディタで __header_end_y__ フィールドをドラッグ → 保存
  備考ブロック左端X: PDFエディタで __note_cfg__ フィールドをドラッグ → 保存
  クランプブロック左端X: PDFエディタで __clamp_cfg__ フィールドをドラッグ → 保存
  幅/ラベル幅/最小高: note列を 'w=535,label_w=56,min_h=22' 形式で直接編集
""")
