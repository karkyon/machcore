#!/usr/bin/env python3
"""
fix_v73.py
===========
修正内容:
  1. [UI] mc/[mc_id]/print/page.tsx:
     - status=NEW の場合、印刷オプション（ツーリング/クランプ/図/ワークオフセット/インデックス）を非表示
     - status=NEW の場合、「参考出力」チェックボックスを非表示
     - PDFプレビューボタン: is_preview=true を送信（DBに記録しない・ファイル保存しない）
     - プリンタに直接印刷: is_preview=false（従来通りDBに記録・ファイル保存）

  2. [API] mc.service.ts generateSetupSheetPdf:
     - is_preview=true の場合:
       a. DBに McSetupSheetLog を作成しない
       b. 各ページに「プレビュー」透かしを描画（対角斜め、薄いグレー）
     - directPrint: is_preview を false で固定（常にDB記録あり）

  3. [API] PrintMcDto: is_preview フィールド追加

ビルド→pm2 restart→git push まで自動実行
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"
API  = f"{ROOT}/apps/api/src"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ─────────────────────────────────────────────────────────────
# 1. PrintMcDto: is_preview フィールド追加
# ─────────────────────────────────────────────────────────────
dto_path = f"{API}/mc/dto/print-mc.dto.ts"
patch(dto_path,
    "  @IsOptional() @IsBoolean() is_reference?: boolean;\n}",
    "  @IsOptional() @IsBoolean() is_reference?: boolean;\n  @IsOptional() @IsBoolean() is_preview?: boolean;\n}",
    "PrintMcDto: is_preview追加"
)

# ─────────────────────────────────────────────────────────────
# 2. mc.service.ts: generateSetupSheetPdf に is_preview 対応（透かし + DB記録スキップ）
# ─────────────────────────────────────────────────────────────
mc_service = f"{API}/mc/mc.service.ts"

# P1+P2結合後の最終doc保存直前に透かし処理を挿入
old_save = """    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

    await this.prisma.mcSetupSheetLog.create({
      data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
              ...(typeof (options as any).is_reference !== 'undefined' ? { isReference: (options as any).is_reference } : {}) },
    }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));

    return pdfBuffer;"""

new_save = """    // ── プレビュー透かし処理 ──
    const isPreview = (options as any).is_preview === true;
    if (isPreview) {
      // 全ページに「プレビュー」透かしを描画
      const allPages = finalDoc.getPages();
      const fontkit2 = await import('@pdf-lib/fontkit');
      finalDoc.registerFontkit(fontkit2.default ?? fontkit2);
      const FONT_PATH2 = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
      const fontBytes2 = fs.readFileSync(FONT_PATH2);
      const wFont = await finalDoc.embedFont(fontBytes2);
      const { degrees } = await import('pdf-lib');
      for (const page of allPages) {
        const { width, height } = page.getSize();
        // 対角方向に「プレビュー」を薄いグレーで複数回描画
        const wText = 'プレビュー';
        const wSize = 60;
        const wColor = rgb(0.75, 0.75, 0.75);
        const positions = [
          { x: width * 0.15, y: height * 0.25 },
          { x: width * 0.35, y: height * 0.55 },
          { x: width * 0.55, y: height * 0.75 },
        ];
        for (const pos of positions) {
          page.drawText(wText, {
            x: pos.x, y: pos.y,
            size: wSize,
            font: wFont,
            color: wColor,
            rotate: degrees(35),
            opacity: 0.35,
          });
        }
      }
    }

    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

    // プレビューの場合はDB記録・ファイル保存をスキップ
    if (!isPreview) {
      await this.prisma.mcSetupSheetLog.create({
        data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
                ...(typeof (options as any).is_reference !== 'undefined' ? { isReference: (options as any).is_reference } : {}) },
      }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));
    }

    return pdfBuffer;"""

patch(mc_service, old_save, new_save, "mc.service.ts is_preview透かし+DB記録スキップ")

# ─────────────────────────────────────────────────────────────
# 3. mc/[mc_id]/print/page.tsx: 新規時オプション非表示 + プレビューボタンに is_preview=true
# ─────────────────────────────────────────────────────────────
print_page = f"{WEB}/app/mc/[mc_id]/print/page.tsx"
content = read(print_page)

# status=NEW 判定: nc.status === 'NEW'
# 新規の時: オプション/参考出力を非表示、プレビューに is_preview=true 付与

# handlePrint に is_preview=true 追加
old_handle_print = """  const handlePrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setPrinting(true); setPrintError(null);
    try {
      const res = await fetch(`/api/mc/${mcId}/print`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({...printBody, is_reference: isReference}),
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
      logout();
      showToast("✅ 段取シートを発行しました");
      setTimeout(() => router.push(`/mc/${mcId}`), 1500);
    } catch (e: any) {
      setPrintError(e.message ?? "PDF生成に失敗しました");
    } finally {
      setPrinting(false);
    }
  };"""

new_handle_print = """  const isNew = nc?.status === "NEW";

  const handlePrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setPrinting(true); setPrintError(null);
    try {
      const res = await fetch(`/api/mc/${mcId}/print`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        // プレビューボタン: is_preview=true → DBに記録しない・透かし入り
        body: JSON.stringify({...printBody, is_reference: isReference, is_preview: true}),
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      const blob = await res.blob();
      // プレビューはセッション継続（logout しない・画面遷移しない）
      window.open(URL.createObjectURL(blob), "_blank");
      showToast("📄 プレビューを開きました（DBに記録されません）");
    } catch (e: any) {
      setPrintError(e.message ?? "PDF生成に失敗しました");
    } finally {
      setPrinting(false);
    }
  };"""

if old_handle_print in content:
    content = content.replace(old_handle_print, new_handle_print, 1)
    print("OK: print/page.tsx handlePrint is_preview=true 追加")
else:
    print("WARN: handlePrint パターン不一致")

# 印刷オプションブロックを isNew 条件で囲む
# 認証後の <div className="p-5 space-y-3"> の中に options がある部分
old_options_block = """              <div className="p-5 space-y-3">
                {[
                  [includeTooling,       setIncludeTooling,       "ツーリングリストを含める"],
                  [includeClamp,         setIncludeClamp,         "クランプ情報を含める"],
                  [includeDrawings,      setIncludeDrawings,      "図を含める"],
                  [includeWorkOffsets,   setIncludeWorkOffsets,   "ワークオフセットを含める"],
                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],
                ].map(([val, setter, label]: any) => (
                  <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                    <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">{label}</span>
                  </label>
                ))}
              </div>
              <div className="px-5 py-3 border-t border-slate-100">
                <label className="flex items-center gap-3 text-sm cursor-pointer">
                  <input type="checkbox" checked={isReference} onChange={e => setIsReference(e.target.checked)}
                    className="accent-amber-500 w-4 h-4" />
                  <span className="text-amber-700 font-bold">参考出力（生産に使用しない・回収不要）</span>
                </label>
                {isReference && <p className="text-[11px] text-amber-600 mt-1 ml-7">参考出力はダッシュボードの未回収一覧に表示されません</p>}
              </div>"""

new_options_block = """              {/* 新規(NEW)以外のみ印刷オプション表示 */}
              {!isNew && (
                <>
                  <div className="p-5 space-y-3">
                    {[
                      [includeTooling,       setIncludeTooling,       "ツーリングリストを含める"],
                      [includeClamp,         setIncludeClamp,         "クランプ情報を含める"],
                      [includeDrawings,      setIncludeDrawings,      "図を含める"],
                      [includeWorkOffsets,   setIncludeWorkOffsets,   "ワークオフセットを含める"],
                      [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],
                    ].map(([val, setter, label]: any) => (
                      <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                        <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                          className="accent-teal-600 w-4 h-4" />
                        <span className="text-slate-700">{label}</span>
                      </label>
                    ))}
                  </div>
                  <div className="px-5 py-3 border-t border-slate-100">
                    <label className="flex items-center gap-3 text-sm cursor-pointer">
                      <input type="checkbox" checked={isReference} onChange={e => setIsReference(e.target.checked)}
                        className="accent-amber-500 w-4 h-4" />
                      <span className="text-amber-700 font-bold">参考出力（生産に使用しない・回収不要）</span>
                    </label>
                    {isReference && <p className="text-[11px] text-amber-600 mt-1 ml-7">参考出力はダッシュボードの未回収一覧に表示されません</p>}
                  </div>
                </>
              )}"""

if old_options_block in content:
    content = content.replace(old_options_block, new_options_block, 1)
    print("OK: print/page.tsx 新規時オプション非表示")
else:
    print("WARN: optionsブロック パターン不一致")

# プレビューボタンのラベルを変更（新規時は「プレビュー（透かし入り・記録なし）」と分かるように）
old_preview_btn = """                <button onClick={handlePrint} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>"""

new_preview_btn = """                <button onClick={handlePrint} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : isNew ? "📄 プレビュー（透かし入り・記録なし）" : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>"""

if old_preview_btn in content:
    content = content.replace(old_preview_btn, new_preview_btn, 1)
    print("OK: print/page.tsx プレビューボタンラベル変更")
else:
    print("WARN: プレビューボタン パターン不一致")

write(print_page, content)

# ─────────────────────────────────────────────────────────────
# 4. ビルド + pm2 + push
# ─────────────────────────────────────────────────────────────
print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0:
    rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED (web) — abort")
    sys.exit(1)

print("--- build api ---")
rc2 = run("pnpm --filter api build", cwd=ROOT)
if rc2 != 0:
    rc2 = run("pnpm run build", cwd=f"{ROOT}/apps/api")
if rc2 != 0:
    print("BUILD FAILED (api) — abort")
    sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-api machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v73): 新規段取シート プレビュー透かし+オプション非表示+直接印刷のみDB記録' && git push", cwd=ROOT)
print("DONE v73")
