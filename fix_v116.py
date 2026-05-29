#!/usr/bin/env python3
"""fix_v116: ページ切替バーをスクロール固定位置に移動"""
import subprocess, sys, os, shutil

PROJECT = os.path.expanduser("~/projects/machcore")
PAGE = f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx"
page = open(PAGE, encoding="utf-8").read()
bak  = PAGE + ".v116_pre.bak"
shutil.copy(PAGE, bak)

# ══════════════════════════════════════════════════════════════
# 現在: ページ切替バーがPDFエリア内（overflow-autoの中）にある
# → スクロールすると隠れる
# 修正: 全体プレビューボタンの下にページ切替バーを移動（左パネル内・常時表示）
# ══════════════════════════════════════════════════════════════

# PDFエリア内のバーを削除
OLD_BAR_IN_PDF = """            {/* ページ切替バー（全体プレビュー時のみ有効） */}
            {pdfData && pdfTotalPages >= 1 && (
              <div className="shrink-0 flex items-center gap-2 bg-white rounded-lg shadow px-3 py-1.5">
                <button
                  onClick={() => setPreviewPage(p => Math.max(1, p - 1))}
                  disabled={previewPage <= 1}
                  className="px-2 py-0.5 text-xs bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-40 font-bold">
                  ◀ 前
                </button>
                <span className="text-xs font-bold text-slate-700 min-w-[60px] text-center">
                  {previewPage} / {pdfTotalPages}
                </span>
                <button
                  onClick={() => setPreviewPage(p => Math.min(pdfTotalPages, p + 1))}
                  disabled={previewPage >= pdfTotalPages}
                  className="px-2 py-0.5 text-xs bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-40 font-bold">
                  次 ▶
                </button>
              </div>
            )}
            <div className="flex items-start justify-center">"""

NEW_BAR_IN_PDF = """            <div className="flex items-start justify-center">"""

if OLD_BAR_IN_PDF in page:
    page = page.replace(OLD_BAR_IN_PDF, NEW_BAR_IN_PDF)
    print("OK: PDFエリア内バー削除")
else:
    # 別パターン試す
    import re
    pat = re.compile(r'\s*\{/\* ページ切替バー.*?\}\s*\n\s*<div className="flex items-start justify-center">', re.DOTALL)
    m = pat.search(page)
    if m:
        page = page[:m.start()] + '\n            <div className="flex items-start justify-center">' + page[m.end():]
        print("OK: PDFエリア内バー削除（正規表現）")
    else:
        print("WARN: PDFエリア内バーパターン未検出")

# 全体プレビューボタンの下にバーを追加（左パネル・スクロールしない位置）
OLD_PREVIEW_BUTTONS = """              <div className="flex gap-1.5">
                <button onClick={loadPreview} disabled={pdfLoading}
                  className="flex-1 px-2 py-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                  </svg>
                  {pdfLoading ? "生成中…" : "テンプレート表示"}
                </button>
                <button
                  onClick={sheetType === "repeat" ? loadFullPreview : loadNewFullPreview}
                  disabled={pdfLoading}
                  className="flex-1 px-2 py-1 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  {pdfLoading ? "生成中…" : "全体プレビュー"}
                </button>
              </div>
            </div>"""

NEW_PREVIEW_BUTTONS = """              <div className="flex gap-1.5">
                <button onClick={loadPreview} disabled={pdfLoading}
                  className="flex-1 px-2 py-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                  </svg>
                  {pdfLoading ? "生成中…" : "テンプレート表示"}
                </button>
                <button
                  onClick={sheetType === "repeat" ? loadFullPreview : loadNewFullPreview}
                  disabled={pdfLoading}
                  className="flex-1 px-2 py-1 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  {pdfLoading ? "生成中…" : "全体プレビュー"}
                </button>
              </div>
              {/* ページ切替バー: ボタン直下・常時表示 */}
              {pdfData && (
                <div className="flex items-center justify-center gap-2 pt-1">
                  <button onClick={() => setPreviewPage(p => Math.max(1, p - 1))}
                    disabled={previewPage <= 1}
                    className="px-3 py-1 text-xs bg-slate-200 hover:bg-slate-300 rounded font-bold disabled:opacity-30">
                    ◀ 前
                  </button>
                  <span className="text-xs font-bold text-slate-700 min-w-[50px] text-center">
                    {previewPage} / {pdfTotalPages}
                  </span>
                  <button onClick={() => setPreviewPage(p => Math.min(pdfTotalPages, p + 1))}
                    disabled={previewPage >= pdfTotalPages}
                    className="px-3 py-1 text-xs bg-slate-200 hover:bg-slate-300 rounded font-bold disabled:opacity-30">
                    次 ▶
                  </button>
                </div>
              )}
            </div>"""

if OLD_PREVIEW_BUTTONS in page:
    page = page.replace(OLD_PREVIEW_BUTTONS, NEW_PREVIEW_BUTTONS)
    print("OK: ページ切替バーをボタン直下に配置")
else:
    print("ERROR: プレビューボタンパターン未検出"); sys.exit(1)

open(PAGE, "w", encoding="utf-8").write(page)
print("OK: page.tsx 書き換え完了")

print("--- TSC (Web) ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/web/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"Webエラー {len(errs)}件"); [print(f"  {e}") for e in errs[:5]]
    shutil.copy(bak, PAGE); sys.exit(1)
print("Webエラー: 0件")

subprocess.run(["pm2","restart","machcore-web"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了(web)")

subprocess.run(["git","add","-A"], cwd=PROJECT)
r2 = subprocess.run(["git","commit","-m","fix_v116: ページ切替バーをボタン直下に固定配置"],
    capture_output=True, text=True, cwd=PROJECT)
print(r2.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了 / スーパーリロード後確認")
