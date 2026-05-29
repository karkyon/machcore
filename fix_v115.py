#!/usr/bin/env python3
"""
fix_v115:
1. LINE_X_END: col_noteのx+w(236)=659.9 がA4超過 → 右端をA4幅-右マージン(565)に制限
2. ページ切替バー: renderingRef解放後にpdfTotalPagesが更新されない問題修正
"""
import subprocess, sys, os, shutil, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC  = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
PAGE = f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx"

src  = open(SVC,  encoding="utf-8").read()
page = open(PAGE, encoding="utf-8").read()
bak_svc  = SVC  + ".v115_pre.bak"
bak_page = PAGE + ".v115_pre.bak"
shutil.copy(SVC,  bak_svc)
shutil.copy(PAGE, bak_page)
print("バックアップ完了")

# ══════════════════════════════════════════════════════════════
# [mc.service.ts] 修正1: LINE_X_END をA4内に制限
# col_note幅236はデータ幅であり罫線長ではない
# 実際のテンプレート罫線右端はX=565付近（A4幅595-余白30）
# ══════════════════════════════════════════════════════════════
OLD_LINE_END = """      const lastCol = T_COLS[T_COLS.length - 1];
      const LINE_X_END = lastCol.x + lastCol.w;"""

NEW_LINE_END = """      const lastCol = T_COLS[T_COLS.length - 1];
      // 罫線右端: A4幅(595.28)-右マージン(30)=565 を上限とする
      const LINE_X_END = Math.min(lastCol.x + lastCol.w, 565);"""

if OLD_LINE_END in src:
    src = src.replace(OLD_LINE_END, NEW_LINE_END)
    print("OK: LINE_X_END上限565に制限")
else:
    print("ERROR: LINE_X_ENDパターン未検出"); sys.exit(1)

assert "async directPrint(" in src
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

# ══════════════════════════════════════════════════════════════
# [page.tsx] 修正2: ページ切替バーを常時表示 + renderingRef解放後に確実更新
# pdfTotalPagesをfinallyブロックで設定してrenderingRefと競合しないように
# ══════════════════════════════════════════════════════════════

# 2a: renderingRefをfinallyで解放する前にpdfTotalPagesを設定
OLD_RENDER = """        const pdf = await lib.getDocument({ data: dataCopy }).promise;
        setPdfTotalPages(pdf.numPages);
        const pageNum = Math.min(previewPage, pdf.numPages);"""

NEW_RENDER = """        const pdf = await lib.getDocument({ data: dataCopy }).promise;
        const numPages = pdf.numPages;
        setPdfTotalPages(numPages);
        const pageNum = Math.min(previewPage, numPages);"""

if OLD_RENDER in page:
    page = page.replace(OLD_RENDER, NEW_RENDER)
    print("OK: numPages変数化")
else:
    print("WARN: renderパターン未検出")

# 2b: ページ切替バー条件を pdfTotalPages >= 1（PDFがあれば常時表示）
OLD_COND = "            {pdfData && ("
NEW_COND = "            {pdfData && pdfTotalPages >= 1 && ("
if OLD_COND in page:
    page = page.replace(OLD_COND, NEW_COND, 1)
    print("OK: ページ切替バー常時表示")
elif "pdfData && pdfTotalPages > 1" in page:
    page = page.replace("pdfData && pdfTotalPages > 1", "pdfData && pdfTotalPages >= 1")
    print("OK: ページ切替バー条件>=1に変更")
else:
    print("WARN: ページ切替バー条件パターン未検出")

open(PAGE, "w", encoding="utf-8").write(page)
print("OK: page.tsx 書き換え完了")

# ══════════════════════════════════════════════════════════════
# TSC + build
# ══════════════════════════════════════════════════════════════
print("--- TSC (API) ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"TSエラー {len(errs)}件"); [print(f"  {e}") for e in errs[:5]]
    shutil.copy(bak_svc,SVC); shutil.copy(bak_page,PAGE); sys.exit(1)
print("TSエラー: 0件")

print("--- TSC (Web) ---")
r2 = subprocess.run(["npx","tsc","--noEmit","-p","apps/web/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs2 = [l for l in (r2.stdout+r2.stderr).splitlines() if "error TS" in l]
if errs2:
    print(f"Webエラー {len(errs2)}件"); [print(f"  {e}") for e in errs2[:5]]
    shutil.copy(bak_svc,SVC); shutil.copy(bak_page,PAGE); sys.exit(1)
print("Webエラー: 0件")

print("--- nest build ---")
nest_bin = f"{PROJECT}/apps/api/node_modules/.bin/nest"
r3 = subprocess.run([nest_bin,"build","api"], capture_output=True, text=True,
    cwd=f"{PROJECT}/apps/api")
if r3.returncode != 0:
    print(f"nest build失敗:\n{(r3.stdout+r3.stderr)[:400]}")
    shutil.copy(bak_svc,SVC); shutil.copy(bak_page,PAGE); sys.exit(1)
print("nest build成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
subprocess.run(["pm2","restart","machcore-web"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")

subprocess.run(["git","add","-A"], cwd=PROJECT)
r4 = subprocess.run(["git","commit","-m",
    "fix_v115: LINE_X_END上限565/ページ切替バー修正"],
    capture_output=True, text=True, cwd=PROJECT)
print(r4.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了")
