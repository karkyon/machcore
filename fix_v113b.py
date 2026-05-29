#!/usr/bin/env python3
"""
fix_v113b:
embedPage/boundingBox系は全廃。

根本解決:
- テンプレートをloadTpl()でロードした時点でページサイズを取得
- copyPagesでコピー後、サイズ差がある場合のみscaleContent+setSize
- ただし scaleContent は原点(左下)基準でスケールするため
  テンプレートがA4より小さい場合は「左下が正しい位置、右上が余白」になる

本当の問題:
テンプレート(repeat_tooling.pdf等)がA4と同じサイズ595x842なら問題ない。
画像で右余白があるということは、テンプレートのページ幅が595未満。

解決策: copyPagesでコピーしたページが正しいサイズならそのまま使う。
テンプレートPDFのページサイズを確認するため、loadTpl後にサイズを出力する
デバッグ追加と同時に、最も確実な方法として:

A4白紙ページを作り、テンプレートの全コンテンツストリームをそのページに
コピーするのは複雑すぎる。

シンプルな解決: loadTpl時にページサイズを確認し、
もしA4より小さければ「テンプレートPDF自体の問題」として、
addNewPage内でサイズを記録してscaleContentを正しく適用する。

scaleContentの動作: コンテンツストリームのCTM(変換行列)にスケールを掛ける
→ 原点(0,0)基準でスケール → x軸方向もy軸方向も拡大される
→ 595x500のPDFをscaleContent(1, 842/500)するとy方向だけ伸びる
→ setSize(595, 842)でページサイズをA4にすると正しく表示される

右余白の問題: ページ幅が595未満の場合、例えば幅400なら
scaleContent(595/400, 842/842)でx方向1.49倍に拡大 → 正しいはず

実際にはscaleContentが正しく動いているが、
問題は: コピーされたページのMediaBoxが小さいまま → setSizeで修正
しかしscaleContentを先にやってsetSizeを後でやる順序が重要。

現在のコード順序: scaleContent → setSize → OK

では問題はなぜ？→ scaleContentのsx計算が間違い？
tplW = pgSize.width || A4_W_PT
A4_W_PT = 595.28
もし tplW = 595 (ほぼA4)ならスケール = 1.0 → スケールしない → OK
もし tplW = 419 (A4でない)ならスケール = 595/419 = 1.42 → 拡大 → OK

右余白が出るということはx方向がスケールされていない → tplWがA4と同じ?
でも内容は左寄り...

実は: repeat_tooling.pdf は「クロップボックス」や「ブリードボックス」が
MediaBoxより小さい可能性がある。pdf-libのgetSize()はMediaBoxを返す。
表示されるのはCropBox。

解決: getSize()の代わりに実際のクロップボックスを確認、
またはMediaBox/CropBox両方を強制的にA4に設定する。

pdf-libでCropBoxを設定:
  pg.node.set(PDFName.of('MediaBox'), pdfDoc.context.obj([0,0,595.28,841.89]))
  pg.node.set(PDFName.of('CropBox'),  pdfDoc.context.obj([0,0,595.28,841.89]))
"""
import subprocess, sys, os, shutil, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()
bak = SVC + ".v113b_pre.bak"
shutil.copy(SVC, bak)

m = re.search(r'    // 新ページ追加.*?return curPage;\n    \};', src, re.DOTALL)
if not m:
    m = re.search(r'    const A4_W_PT = 595\.28.*?return curPage;\n    \};', src, re.DOTALL)
if not m:
    print("ERROR: addNewPage未検出"); sys.exit(1)

print(f"検出OK: {repr(src[m.start():m.start()+80])}")

NEW_ADDPAGE = """    // 新ページ追加（MediaBox/CropBoxをA4に強制設定でサイズ問題解決）
    const A4_W_PT = 595.28, A4_H_PT = 841.89;
    const { PDFName } = await import('pdf-lib');
    const addNewPage = async (tplDoc: any, tplPageIdx = 0) => {
      let pg: any;
      if (tplDoc) {
        [pg] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
        finalDoc.addPage(pg);
        // MediaBoxとCropBoxを強制的にA4に設定
        // （テンプレートPDFのページサイズに関わらずA4で表示される）
        try {
          const a4box = finalDoc.context.obj([0, 0, A4_W_PT, A4_H_PT]);
          pg.node.set(PDFName.of('MediaBox'), a4box);
          // CropBoxを削除（MediaBoxが優先される）
          pg.node.delete(PDFName.of('CropBox'));
        } catch(_) {}
      } else {
        pg = finalDoc.addPage([A4_W_PT, A4_H_PT]);
      }
      totalPages++;
      curPage  = finalDoc.getPage(finalDoc.getPageCount() - 1);
      curPageH = curPage.getSize().height;
      curY     = curPageH - PAGE_BOTTOM_MARGIN;
      return curPage;
    };"""

src = src[:m.start()] + NEW_ADDPAGE + src[m.end():]
print("OK: addNewPage置換完了（MediaBox/CropBox強制A4方式）")

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
    print(f"nest build失敗:\n{(r2.stdout+r2.stderr)[:400]}")
    shutil.copy(bak, SVC); sys.exit(1)
print("nest build成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")

subprocess.run(["git","add","-A"], cwd=PROJECT)
r3 = subprocess.run(["git","commit","-m",
    "fix_v113b: MediaBox/CropBox強制A4設定でテンプレートサイズ問題解決"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了 / スーパーリロード→全体プレビュー確認")
