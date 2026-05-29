#!/usr/bin/env python3
"""
fix_v105h.py
- ラベルセンタリング: 日本語全角文字を考慮した幅計算に修正
- ラベルフォントサイズ: fs-1 → fs-2 に変更
- 本文テキストフォントサイズ: fs → fs-1 に変更（全体的に一回り小さく）
"""
import subprocess, sys, os

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
src     = open(SVC, encoding="utf-8").read()

# ① ラベルセンタリング修正（全角文字幅 = fs*1.0、半角 = fs*0.6 で計算）
# ② ラベルfs: fs-1 → fs-2
# ③ 本文テキストfs: fs → fs-1
OLD_LABEL = '''      // ラベルテキスト（縦中央・水平センタリング・フォントサイズ-1）
      const lblFs    = Math.max(5, fs - 1);
      const lblTxtY  = blockY + blockH / 2 - lblFs * 0.36;
      // 水平センタリング: 文字幅を推定してX位置を調整
      const lblCharW = lblFs * 0.6;
      const lblTextW = label.length * lblCharW;
      const lblTxtX  = x + (lblW - lblTextW) / 2;
      try { curPage.drawText(label, { x:lblTxtX, y:lblTxtY, size:lblFs, font:finalFont, color:rgb(0.15,0.15,0.15) }); } catch(e:any){ console.error('[PDF-ERR] label',e?.message); }'''

NEW_LABEL = '''      // ラベルテキスト（縦中央・水平センタリング・フォントサイズ-2）
      const lblFs   = Math.max(4, fs - 2);
      const lblTxtY = blockY + blockH / 2 - lblFs * 0.36;
      // 全角文字幅=fs*1.0、半角=fs*0.55 で推定してセンタリング
      const lblTextW = [...label].reduce((acc, c) => acc + (c.charCodeAt(0) > 0xFF ? lblFs * 1.0 : lblFs * 0.55), 0);
      const lblTxtX  = x + Math.max(2, (lblW - lblTextW) / 2);
      try { curPage.drawText(label, { x:lblTxtX, y:lblTxtY, size:lblFs, font:finalFont, color:rgb(0.15,0.15,0.15) }); } catch(e:any){ console.error('[PDF-ERR] label',e?.message); }'''

# ③ 本文テキストのフォントサイズを fs-1 に変更
OLD_BODY = '''      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        try { if (line) curPage.drawText(line, { x:txtX0, y:lineY, size:fs, font:finalFont, color:rgb(0,0,0) }); } catch(e:any){ console.error('[PDF-ERR] text',i,e?.message); }
      });'''

NEW_BODY = '''      // 本文テキスト（フォントサイズ fs-1）
      const bodyFs = Math.max(5, fs - 1);
      const txtX0  = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        try { if (line) curPage.drawText(line, { x:txtX0, y:lineY, size:bodyFs, font:finalFont, color:rgb(0,0,0) }); } catch(e:any){ console.error('[PDF-ERR] text',i,e?.message); }
      });'''

new_src = src
changes = 0
for old, new, label in [(OLD_LABEL, NEW_LABEL, 'ラベルセンタリング+fs-2'), (OLD_BODY, NEW_BODY, '本文fs-1')]:
    if old in new_src:
        new_src = new_src.replace(old, new, 1); changes += 1; print(f"OK: {label}")
    else:
        print(f"WARNING: {label} パターン未検出")

if new_src != src:
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
subprocess.run(["git","commit","-m","fix_v105h: ラベル全角幅対応センタリング/fs-2/本文fs-1"], cwd=PROJECT)
r3 = subprocess.run(["git","push"],capture_output=True,text=True,cwd=PROJECT)
print("fix_v105h 完了" if r3.returncode==0 else f"push警告: {r3.stderr[:100]}")
