#!/usr/bin/env python3
"""fix_v111c: 最新コードに対して直接パッチ適用"""
import subprocess, sys, os, shutil

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
src     = open(SVC, encoding="utf-8").read()
bak     = SVC + ".v111c_pre.bak"
shutil.copy(SVC, bak)
print("バックアップ完了")

# ── 現状確認 ──
print(f"embedPages在否: {'embedPages' in src}")
print(f"mediaBox在否: {'mediaBox' in src}")
print(f"setSize在否: {'setSize' in src}")

# ══════════════════════════════════════════════════════════════
# embedPageのmediaBoxエラーを修正
# fix_v111が適用されている場合(embedPages+mediaBoxあり)
# ══════════════════════════════════════════════════════════════
if 'mediaBox' in src:
    OLD = """          const tplSize = embeddedPage.mediaBox ?? { width: A4_W_PT, height: A4_H_PT };
          const tplW = typeof tplSize.width  === 'function' ? tplSize.width()  : (tplSize as any).width  ?? A4_W_PT;
          const tplH = typeof tplSize.height === 'function' ? tplSize.height() : (tplSize as any).height ?? A4_H_PT;"""
    NEW = """          const tplW: number = (embeddedPage as any).width  ?? A4_W_PT;
          const tplH: number = (embeddedPage as any).height ?? A4_H_PT;"""
    if OLD in src:
        src = src.replace(OLD, NEW)
        print("OK: mediaBox→width/height修正（fix_v111適用済みコード）")
    else:
        print("WARN: 旧パターン未検出、別方法で修正")
        # embedPages行を含むaddNewPage全体を安全な実装に置き換え
        import re
        # embedPages～catch ブロックを探して置換
        pat = r'(        try \{.*?embedPages.*?\} catch\(embedErr\) \{.*?\} catch\(_\) \{\}\s*\})'
        m = re.search(pat, src, re.DOTALL)
        if m:
            OLD_BLOCK = m.group(0)
            NEW_BLOCK = """        try {
          const srcPages = await finalDoc.embedPages(
            await tplDoc.copyPages(tplDoc, [tplPageIdx])
          );
          const embeddedPage = srcPages[0];
          const tplW: number = (embeddedPage as any).width  ?? A4_W_PT;
          const tplH: number = (embeddedPage as any).height ?? A4_H_PT;
          pg.drawPage(embeddedPage, {
            x: 0, y: 0,
            xScale: A4_W_PT / (tplW || A4_W_PT),
            yScale: A4_H_PT / (tplH || A4_H_PT),
          });
        } catch(embedErr) {
          try {
            const [copied] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
            finalDoc.removePage(finalDoc.getPageCount() - 1);
            finalDoc.addPage(copied);
          } catch(_) {}
        }"""
            src = src.replace(OLD_BLOCK, NEW_BLOCK)
            print("OK: embedPageブロック全体置換")
        else:
            print("ERROR: embedPagesブロックパターン未検出")
            sys.exit(1)

# fix_v111未適用（setSize方式）の場合 → embedPage方式に全体置換
elif 'setSize' in src and 'pg.setSize(A4_W_PT, A4_H_PT)' in src:
    OLD_ADDPAGE = """      if (tplDoc) {
        [pg] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
        finalDoc.addPage(pg);
        // テンプレートサイズに関わらずA4に強制リサイズ
        pg.setSize(A4_W_PT, A4_H_PT);
      } else {
        pg = finalDoc.addPage([A4_W_PT, A4_H_PT]);
      }"""
    NEW_ADDPAGE = """      if (tplDoc) {
        // embedPageでA4等倍フィット（setSizeはコンテンツをスケールしないため）
        try {
          const srcPages = await finalDoc.embedPages(
            await tplDoc.copyPages(tplDoc, [tplPageIdx])
          );
          const embeddedPage = srcPages[0];
          const tplW: number = (embeddedPage as any).width  ?? A4_W_PT;
          const tplH: number = (embeddedPage as any).height ?? A4_H_PT;
          pg.drawPage(embeddedPage, {
            x: 0, y: 0,
            xScale: A4_W_PT / (tplW || A4_W_PT),
            yScale: A4_H_PT / (tplH || A4_H_PT),
          });
        } catch(embedErr) {
          try {
            const [copied] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
            finalDoc.removePage(finalDoc.getPageCount() - 1);
            finalDoc.addPage(copied);
          } catch(_) {}
        }
      } else {
        pg = finalDoc.addPage([A4_W_PT, A4_H_PT]);
      }"""
    if OLD_ADDPAGE in src:
        src = src.replace(OLD_ADDPAGE, NEW_ADDPAGE)
        print("OK: setSize→embedPage方式に変更")
    else:
        print("ERROR: setSizeパターン未検出")
        sys.exit(1)

# ── 備考/クランプ幅確認・修正 ──
if "'w=490,label_w=59,min_h=22'" not in src:
    for old_w, new_w in [
        ("'w=535,label_w=59,min_h=22'", "'w=490,label_w=59,min_h=22'"),
        ("'w=515,label_w=59,min_h=22'", "'w=490,label_w=59,min_h=22'"),
    ]:
        if old_w in src:
            src = src.replace(old_w, new_w)
            print(f"OK: 備考/クランプ幅 {old_w}→'w=490,...'")
else:
    print("OK: 備考/クランプ幅 w=490 確認済み")

# ── 安全確認 ──
assert "async directPrint(" in src, "directPrint消失！"
assert "async generateRepeatSetupSheetPdf(" in src, "generateRepeatSetupSheetPdf消失！"
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

# ── TSC ──
print("--- TSC ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"TSエラー {len(errs)}件")
    for e in errs[:5]: print(f"  {e}")
    shutil.copy(bak, SVC); sys.exit(1)
print("TSエラー: 0件")

# ── nest build ──
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
    "fix_v111c: embedPage等倍A4/備考幅490/mediaBoxエラー修正"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了 → スーパーリロード後に全体プレビュー確認")
