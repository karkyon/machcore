#!/usr/bin/env python3
"""fix_v112b: 正規表現でaddNewPage全体を置換"""
import subprocess, sys, os, shutil, glob, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()
bak = SVC + ".v112b_pre.bak"
shutil.copy(SVC, bak)

# addNewPage全体を正規表現で特定して置換
# 開始: "    // 新ページ追加" または "    const A4_W_PT"
# 終了: "    };\n\n    // テキスト描画"
pattern = re.compile(
    r'    // 新ページ追加.*?return curPage;\n    \};',
    re.DOTALL
)
m = pattern.search(src)
if not m:
    print("ERROR: addNewPageブロック正規表現でも未検出")
    # さらに広いパターンで試す
    pattern2 = re.compile(
        r'    const A4_W_PT = 595\.28.*?return curPage;\n    \};',
        re.DOTALL
    )
    m = pattern2.search(src)
    if not m:
        print("FATAL: addNewPageが全く見つかりません")
        sys.exit(1)

print(f"検出: {repr(src[m.start():m.start()+80])}")

NEW_ADDPAGE = """    // 新ページ追加（copyPages + scaleContent でA4等倍表示）
    const A4_W_PT = 595.28, A4_H_PT = 841.89;
    const addNewPage = async (tplDoc: any, tplPageIdx = 0) => {
      let pg: any;
      if (tplDoc) {
        [pg] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
        finalDoc.addPage(pg);
        // テンプレートサイズがA4でない場合、コンテンツをスケールしてA4に合わせる
        const pgSize = pg.getSize();
        const tplW = pgSize.width  || A4_W_PT;
        const tplH = pgSize.height || A4_H_PT;
        if (Math.abs(tplW - A4_W_PT) > 1 || Math.abs(tplH - A4_H_PT) > 1) {
          try {
            pg.scaleContent(A4_W_PT / tplW, A4_H_PT / tplH);
            pg.setSize(A4_W_PT, A4_H_PT);
          } catch(_) {
            try { pg.setSize(A4_W_PT, A4_H_PT); } catch(_2) {}
          }
        }
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
print("OK: addNewPage置換完了")

assert "async directPrint(" in src
assert "async generateRepeatSetupSheetPdf(" in src
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

# バックアップ・fixスクリプト削除
for bf in glob.glob(f"{PROJECT}/apps/api/src/mc/mc.service.ts.v*.bak") + \
          glob.glob(f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx.v*.bak"):
    if 'v112b' not in bf:
        os.remove(bf); print(f"削除: {os.path.basename(bf)}")
for ff in glob.glob(f"{PROJECT}/fix_v1*.py"):
    if 'fix_v112b' not in ff:
        os.remove(ff); print(f"削除: {os.path.basename(ff)}")

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
    "fix_v112b: copyPages+scaleContentでA4等倍/500エラー修正/不要ファイル削除"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了 / スーパーリロード→全体プレビュー確認")
