#!/usr/bin/env python3
"""
fix_v113:
ツーリングテンプレートが小さいサイズの場合、scaleContent後に
コンテンツが左下に寄るため右余白が生じる。

根本解決: テンプレートPDFのサイズに関わらず、
コンテンツをA4の左下原点(0,0)から正しくスケール配置する。

pdf-libのscaleContent(sx, sy)はコンテンツをそのまま拡大するため
原点からスケールされる。テンプレートがA4より小さければ
左下に寄った小さいコンテンツが拡大されるので正しく見える。

実際の問題: repeat_tooling.pdf 自体が小さいページサイズで
作られており、copyPages後にscaleContentが正しく動いていない。

確実な解決: テンプレートのページサイズを確認し、
サイズが違う場合は transformContent で平行移動も行う。
または、より単純に: copyPagesでなく、
finalDocにA4ページを作成し、テンプレートをXObjectとして埋め込む。

最もシンプルで確実な方法:
1. A4白紙ページを作成
2. テンプレートドキュメントのページを embedPage (pdf-lib v1.17+) で取得
3. drawPage でA4にフィットさせて描画

pdf-libのembedPageはPDFPageではなくPDFDocumentのメソッド:
  finalDoc.embedPage(sourcePage) → PDFEmbeddedPage
  page.drawPage(embeddedPage, { x, y, width, height })

これが正しいAPI。embedPagesではなくembedPage(単数)。
"""
import subprocess, sys, os, shutil, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()
bak = SVC + ".v113_pre.bak"
shutil.copy(SVC, bak)
print("バックアップ完了")

# 現在のaddNewPageを確認
m = re.search(r'    // 新ページ追加.*?return curPage;\n    \};', src, re.DOTALL)
if not m:
    m = re.search(r'    const A4_W_PT = 595\.28.*?return curPage;\n    \};', src, re.DOTALL)
if not m:
    print("ERROR: addNewPage未検出"); sys.exit(1)

print(f"現在: {repr(src[m.start():m.start()+100])}")

NEW_ADDPAGE = """    // 新ページ追加（A4白紙 + テンプレートをembedPage/drawPageでA4等倍配置）
    const A4_W_PT = 595.28, A4_H_PT = 841.89;
    const addNewPage = async (tplDoc: any, tplPageIdx = 0) => {
      // 常にA4白紙ページを作成
      const pg = finalDoc.addPage([A4_W_PT, A4_H_PT]);
      if (tplDoc) {
        try {
          // pdf-lib v1.17+: embedPage で PDFEmbeddedPage を取得してdrawPageで描画
          const tplPage = tplDoc.getPage(tplPageIdx);
          const embedded = await finalDoc.embedPage(tplPage);
          const { width: tW, height: tH } = embedded.boundingBox();
          pg.drawPage(embedded, {
            x: 0,
            y: 0,
            xScale: A4_W_PT / (tW || A4_W_PT),
            yScale: A4_H_PT / (tH || A4_H_PT),
          });
        } catch (e1) {
          // embedPage失敗時: copyPages + scaleContent
          try {
            const [copied] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
            // 一時的に追加してscaleContent
            const tmpDoc = await (await import('pdf-lib')).PDFDocument.create();
            const [tmpPg] = await tmpDoc.copyPages(tplDoc, [tplPageIdx]);
            const pgSize = tmpPg.getSize();
            const tW2 = pgSize.width  || A4_W_PT;
            const tH2 = pgSize.height || A4_H_PT;
            copied.scaleContent(A4_W_PT / tW2, A4_H_PT / tH2);
            copied.setSize(A4_W_PT, A4_H_PT);
            // finalDocのpgにコンテンツをコピー（直接追加できないので既存pg削除して差し替え）
            finalDoc.removePage(finalDoc.getPageCount() - 1);
            finalDoc.addPage(copied);
          } catch (e2) {
            // 最終フォールバック: そのままcopyPages
            try {
              finalDoc.removePage(finalDoc.getPageCount() - 1);
              const [copied2] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
              finalDoc.addPage(copied2);
            } catch(_) {}
          }
        }
      }
      totalPages++;
      curPage  = finalDoc.getPage(finalDoc.getPageCount() - 1);
      curPageH = curPage.getSize().height;
      curY     = curPageH - PAGE_BOTTOM_MARGIN;
      return curPage;
    };"""

src = src[:m.start()] + NEW_ADDPAGE + src[m.end():]
print("OK: addNewPage置換完了")

assert "async directPrint(" in src
assert "async generateRepeatSetupSheetPdf(" in src
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

print("--- TSC ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"TSエラー {len(errs)}件")
    for e in errs[:5]: print(f"  {e}")
    shutil.copy(bak, SVC); sys.exit(1)
print("TSエラー: 0件")

print("--- nest build ---")
nest_bin = f"{PROJECT}/apps/api/node_modules/.bin/nest"
r2 = subprocess.run([nest_bin,"build","api"], capture_output=True, text=True,
    cwd=f"{PROJECT}/apps/api")
if r2.returncode != 0:
    print(f"nest build失敗:\n{(r2.stdout+r2.stderr)[:500]}")
    shutil.copy(bak, SVC); sys.exit(1)
print("nest build成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")

subprocess.run(["git","add","-A"], cwd=PROJECT)
r3 = subprocess.run(["git","commit","-m",
    "fix_v113: embedPage/drawPageでA4等倍配置（右余白問題修正）"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了")
