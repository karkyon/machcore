#!/usr/bin/env python3
"""fix_v117: ページ切替バーを無条件表示、pdfTotalPages更新を確実化"""
import subprocess, sys, os, shutil

PROJECT = os.path.expanduser("~/projects/machcore")
PAGE = f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx"
page = open(PAGE, encoding="utf-8").read()
bak  = PAGE + ".v117_pre.bak"
shutil.copy(PAGE, bak)

# ══════════════════════════════════════════════════════════════
# 問題1: renderingRef=trueのまま setPdfTotalPages が呼ばれない
# useEffectの依存配列に pdfData があるが、renderingRef.current=trueで
# 早期returnしてしまい、2回目のレンダリング（previewPage変更時）で
# numPagesが取得できない
# 
# 修正: renderingRef をやめて、pdfTotalPages 更新を別のuseEffectに分離
# pdfDataが変わった時だけページ数を取得する専用のeffectを追加
# ══════════════════════════════════════════════════════════════

# pdfData変更時にpdfTotalPagesを更新する専用effect追加
OLD_LOAD_FIELDS = """  const loadFields = async () => {"""

NEW_LOAD_FIELDS = """  // pdfDataが変わったらページ数を取得（renderingRefと独立）
  useEffect(() => {
    if (!pdfData || !pdfjsReady) return;
    (async () => {
      try {
        const lib = (window as any).pdfjsLib;
        const dataCopy = pdfData.slice(0);
        const pdf = await lib.getDocument({ data: dataCopy }).promise;
        setPdfTotalPages(pdf.numPages);
      } catch(_) {}
    })();
  }, [pdfData, pdfjsReady]);

  const loadFields = async () => {"""

if OLD_LOAD_FIELDS in page:
    page = page.replace(OLD_LOAD_FIELDS, NEW_LOAD_FIELDS, 1)
    print("OK: pdfTotalPages専用effect追加")
else:
    print("WARN: loadFields前パターン未検出")

# ══════════════════════════════════════════════════════════════
# 問題2: ページ切替バーが {pdfData && (...)} で条件付き
# pdfDataはあるがpdfTotalPagesが1のままなので見えにくい
# → 常時表示（pdfData条件も外す）してpage/totalを常に見せる
# ══════════════════════════════════════════════════════════════
OLD_PAGE_BAR = """              {/* ページ切替バー: ボタン直下・常時表示 */}
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
              )}"""

NEW_PAGE_BAR = """              {/* ページ切替バー: 常時表示 */}
              <div className="flex items-center justify-center gap-2 pt-1 border-t border-slate-100 mt-1">
                <button onClick={() => setPreviewPage(p => Math.max(1, p - 1))}
                  disabled={previewPage <= 1}
                  className="px-3 py-1 text-xs bg-slate-200 hover:bg-slate-300 rounded font-bold disabled:opacity-30">
                  ◀ 前
                </button>
                <span className="text-xs font-bold text-slate-700 min-w-[60px] text-center bg-white border border-slate-200 rounded px-2 py-0.5">
                  {previewPage} / {pdfTotalPages}
                </span>
                <button onClick={() => setPreviewPage(p => Math.min(pdfTotalPages, p + 1))}
                  disabled={previewPage >= pdfTotalPages}
                  className="px-3 py-1 text-xs bg-slate-200 hover:bg-slate-300 rounded font-bold disabled:opacity-30">
                  次 ▶
                </button>
              </div>"""

if OLD_PAGE_BAR in page:
    page = page.replace(OLD_PAGE_BAR, NEW_PAGE_BAR)
    print("OK: ページ切替バー常時表示化（条件なし）")
else:
    print("ERROR: ページ切替バーパターン未検出"); sys.exit(1)

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
r2 = subprocess.run(["git","commit","-m",
    "fix_v117: ページ切替バー常時表示/pdfTotalPages専用effect追加"],
    capture_output=True, text=True, cwd=PROJECT)
print(r2.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了")
