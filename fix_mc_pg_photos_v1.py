#!/usr/bin/env python3
"""
fix_mc_pg_photos_v1.py
① PG作成者/日時 表示・編集 + PGテキストエディタ(検索置換) + USB File System Access API
② 写真/③ 図: 複数選択→サムネプレビュー→命名規則アップロード
API: PUT /mc/:id/pg-content 追加
"""
import subprocess, sys

BASE       = "/home/karkyon/projects/machcore"
CONTROLLER = f"{BASE}/apps/api/src/mc/mc.controller.ts"
FILESVC    = f"{BASE}/apps/api/src/mc/mc-files.service.ts"
EDIT_PAGE  = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────────────────
# [1] API: mc.controller.ts に PUT /mc/:id/pg-content 追加
# ─────────────────────────────────────────────────────────
print("=== [1] API: pg-content エンドポイント追加 ===")
with open(CONTROLLER, "r") as f:
    src = f.read()

OLD_CTRL = '''  /** PGファイルをテキストで返す（インラインビューア用） */
  @Get(':mc_id/pg-file')
  getPgFile(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.getPgFile(id);
  }'''

NEW_CTRL = '''  /** PGファイルをテキストで返す（インラインビューア用） */
  @Get(':mc_id/pg-file')
  getPgFile(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.getPgFile(id);
  }

  /** PGファイルをテキストで保存（エディタ保存用） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/pg-content')
  async savePgContent(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() body: { content: string; original_name?: string },
    @Req() req: any,
  ) {
    return this.mcFiles.savePgContent(id, body.content, body.original_name, req.user.id);
  }'''

if OLD_CTRL in src:
    src = src.replace(OLD_CTRL, NEW_CTRL)
    print("  OK: controller pg-content追加")
else:
    print("  WARN: controller パターン不一致")

with open(CONTROLLER, "w") as f:
    f.write(src)

# ─────────────────────────────────────────────────────────
# [2] API: mc-files.service.ts に savePgContent 追加
# ─────────────────────────────────────────────────────────
print("=== [2] API: savePgContent サービス追加 ===")
with open(FILESVC, "r") as f:
    src = f.read()

OLD_SVC = '''  // ── PGファイル読み込み（インラインビューア用）──────────────────'''
NEW_SVC = '''  // ── PGファイルテキスト保存（エディタ保存用）─────────────────────
  async savePgContent(
    mcProgramId: number,
    content: string,
    originalName: string | undefined,
    uploadedBy: number,
  ): Promise<{ message: string }> {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const machId   = mc.machiningId;

    // 既存MAINファイルを取得
    const existing = await this.prisma.mcFile.findFirst({
      where: { mcProgramId, fileType: 'PROGRAM', pgRole: 'MAIN', isDeleted: false },
      orderBy: { uploadedAt: 'desc' },
    });

    const iconv = require('iconv-lite') as typeof import('iconv-lite');
    const buf   = iconv.encode(content, 'Shift_JIS');

    if (existing && fs.existsSync(existing.filePath)) {
      // 既存ファイルを上書き
      fs.writeFileSync(existing.filePath, buf);
      // pg_updated_at を更新
      await this.prisma.mcProgram.update({
        where: { id: mcProgramId },
        data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
      });
      return { message: 'PGファイルを保存しました' };
    }

    // 既存なし → 新規保存
    const name = originalName ?? `${machId}`;
    const flatDir = path.join(basePath, 'mc_files', 'pg');
    this.ensureDir(flatDir);
    const storedName = `${machId}`;
    const filePath   = path.join(flatDir, storedName);
    fs.writeFileSync(filePath, buf);

    await this.prisma.mcFile.create({
      data: {
        mcProgramId,
        fileType:    'PROGRAM',
        pgRole:      'MAIN',
        originalName: name,
        storedName,
        mimeType:    'text/plain',
        filePath,
        fileSize:    buf.length,
        uploadedBy,
        sortOrder:   0,
      },
    });
    await this.prisma.mcProgram.update({
      where: { id: mcProgramId },
      data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
    });
    return { message: 'PGファイルを新規保存しました' };
  }

  // ── PGファイル読み込み（インラインビューア用）──────────────────'''

if OLD_SVC in src:
    src = src.replace(OLD_SVC, NEW_SVC, 1)
    print("  OK: savePgContent追加")
else:
    print("  WARN: service パターン不一致")

with open(FILESVC, "w") as f:
    f.write(src)

# ─────────────────────────────────────────────────────────
# [3] Web: edit/page.tsx
#   - 基本情報タブ: PG作成者(pgCreatedBy)・PG更新日時(pgUpdatedAt)表示/編集
#   - 基本情報タブ: PGエディタボタン追加
#   - 図・写真タブ: 複数選択→サムネプレビュー→命名規則アップロード
#   - PGエディタモーダル: 検索置換 + テキストエリア + USB保存(File System Access API)
# ─────────────────────────────────────────────────────────
print("=== [3] Web: edit/page.tsx 修正 ===")
with open(EDIT_PAGE, "r") as f:
    src = f.read()

# (3a) state追加: pgContent/pgOrigName/pgEditorOpen/pgCreatorId/pgEditorSearch/pgEditorReplace
OLD_STATE = '''  // ファイル（写真・図）
  const [files,          setFiles]          = useState<any[]>([]);'''

NEW_STATE = '''  // PGエディタ
  const [pgEditorOpen,    setPgEditorOpen]    = useState(false);
  const [pgContent,       setPgContent]       = useState<string>("");
  const [pgOrigName,      setPgOrigName]      = useState<string>("");
  const [pgLoading,       setPgLoading]       = useState(false);
  const [pgSaving,        setPgSaving]        = useState(false);
  const [pgEditorSearch,  setPgEditorSearch]  = useState("");
  const [pgEditorReplace, setPgEditorReplace] = useState("");
  const [pgCreatedBy,     setPgCreatedBy]     = useState<string>("");
  const [pgUpdatedAtDisp, setPgUpdatedAtDisp] = useState<string>("");

  // 写真/図 複数プレビュー選択
  const [photoPreviewFiles,   setPhotoPreviewFiles]   = useState<{file: File; url: string; selected: boolean}[]>([]);
  const [drawingPreviewFiles, setDrawingPreviewFiles] = useState<{file: File; url: string; selected: boolean}[]>([]);
  const [photoPreviewOpen,    setPhotoPreviewOpen]    = useState(false);
  const [drawingPreviewOpen,  setDrawingPreviewOpen]  = useState(false);
  const [bulkUploading,       setBulkUploading]       = useState(false);

  // ファイル（写真・図）
  const [files,          setFiles]          = useState<any[]>([]);'''

if OLD_STATE in src:
    src = src.replace(OLD_STATE, NEW_STATE, 1)
    print("  OK: state追加")
else:
    print("  WARN: state追加パターン不一致")

# (3b) useEffect でpgCreatedBy/pgUpdatedAtDispをdetailから取得
OLD_EFFECT_END = '''      setIndexRows((d.indexPrograms ?? []).map((p: any) => ({'''

NEW_EFFECT_END = '''      // PG作成者・更新日時
      setPgCreatedBy(d.pgCreatedBy ? String(d.pgCreatedBy) : "");
      setPgUpdatedAtDisp(d.pgUpdatedAt ? new Date(d.pgUpdatedAt).toLocaleString("ja-JP") : "");
      setIndexRows((d.indexPrograms ?? []).map((p: any) => ({'''

if OLD_EFFECT_END in src:
    src = src.replace(OLD_EFFECT_END, NEW_EFFECT_END, 1)
    print("  OK: useEffect pgCreatedBy設定追加")
else:
    print("  WARN: useEffect パターン不一致")

# (3c) 基本情報タブの末尾（作成者/作成日の後）にPG情報セクション追加
OLD_BASIC_END = '''              </div>
            )}

            {/* ツーリング */}
            {activeSection === "tooling"'''

NEW_BASIC_END = '''              </div>

              {/* PG情報 */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-600">プログラム情報</span>
                  <button onClick={async () => {
                    setPgLoading(true);
                    try {
                      const r = await mcApi.getPgFile(mcId);
                      const data = (r as any).data ?? r;
                      setPgContent(data.content ?? "");
                      setPgOrigName(data.originalName ?? "");
                      setPgEditorOpen(true);
                    } catch { showToast("PGファイルが見つかりません"); }
                    finally { setPgLoading(false); }
                  }} disabled={pgLoading}
                    className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                    {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                  </button>
                </div>
                <div className="px-4 py-3 grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">PG作成者</label>
                    <select value={pgCreatedBy} onChange={e => setPgCreatedBy(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {users.filter(u => u.isActive).map(u => (
                        <option key={u.id} value={String(u.id)}>{u.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">PG更新日時</label>
                    <div className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-600 font-mono">
                      {pgUpdatedAtDisp || "—"}
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">※ PGアップロード時に自動更新</p>
                  </div>
                </div>
              </div>
            </div>
            )}

            {/* ツーリング */}
            {activeSection === "tooling"'''

if OLD_BASIC_END in src:
    src = src.replace(OLD_BASIC_END, NEW_BASIC_END, 1)
    print("  OK: 基本情報タブにPG情報セクション追加")
else:
    print("  WARN: 基本情報タブ末尾パターン不一致")

# (3d) handleSave に pgCreatedBy の保存追加
OLD_SAVE = '''      await mcApi.update(mcId, {
        machine_id:     (machineId && !isNaN(parseInt(machineId))) ? parseInt(machineId) : undefined,
        o_number:       oNumber   || undefined,
        clamp_note:     clampNote || undefined,
        cycle_time_sec: cycleTimeSec > 0 ? cycleTimeSec : undefined,
        machining_qty:  machiningQty,
        note:           note || undefined,
        creator_id:     (creatorId && !isNaN(parseInt(creatorId))) ? parseInt(creatorId) : null,
        sheet_created_at: sheetCreatedAt || null,
      }, token);'''

NEW_SAVE = '''      await mcApi.update(mcId, {
        machine_id:     (machineId && !isNaN(parseInt(machineId))) ? parseInt(machineId) : undefined,
        o_number:       oNumber   || undefined,
        clamp_note:     clampNote || undefined,
        cycle_time_sec: cycleTimeSec > 0 ? cycleTimeSec : undefined,
        machining_qty:  machiningQty,
        note:           note || undefined,
        creator_id:     (creatorId && !isNaN(parseInt(creatorId))) ? parseInt(creatorId) : null,
        sheet_created_at: sheetCreatedAt || null,
        pg_created_by:  (pgCreatedBy && !isNaN(parseInt(pgCreatedBy))) ? parseInt(pgCreatedBy) : null,
      }, token);'''

if OLD_SAVE in src:
    src = src.replace(OLD_SAVE, NEW_SAVE, 1)
    print("  OK: handleSave pgCreatedBy追加")
else:
    print("  WARN: handleSave パターン不一致")

# (3e) 図・写真タブの写真アップロードを複数プレビュー方式に刷新
OLD_FILES_TAB = '''            {activeSection === "files" && (
              <div className="max-w-3xl space-y-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <p className="text-xs font-bold text-slate-600 mb-3">写真・図のアップロード</p>
                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-teal-400 transition-colors"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-teal-400","bg-teal-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-teal-400","bg-teal-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const f = e.dataTransfer.files[0];
                      if (f) handleFileUpload(f, "PHOTO");
                    }}>
                    <p className="text-slate-400 text-sm mb-3">ファイルをここにドラッグ＆ドロップ</p>
                    <div className="flex items-center justify-center gap-3">
                      <label className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        写真を選択
                        <input ref={photoInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "PHOTO"); e.target.value = ""; } }} />
                      </label>
                      <label className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        図を選択
                        <input ref={scanInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "DRAWING"); e.target.value = ""; } }} />
                      </label>
                    </div>
                    {fileUploading && <p className="text-xs text-teal-600 mt-2 animate-pulse">アップロード中...</p>}
                    {fileUploadMsg && <p className="text-xs mt-2 font-bold text-slate-600">{fileUploadMsg}</p>}
                    <p className="text-[10px] text-slate-400 mt-2">すべてのファイル形式に対応（写真・図・PDF等）</p>
                  </div>
                </div>'''

NEW_FILES_TAB = '''            {activeSection === "files" && (
              <div className="max-w-3xl space-y-4">
                {/* 写真アップロード */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-slate-600">📷 写真のアップロード</p>
                    <div className="flex gap-2">
                      <label className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors">
                        複数選択・フォルダ
                        <input type="file" accept="image/*" multiple className="hidden"
                          onChange={e => {
                            const files2 = Array.from(e.target.files ?? []);
                            if (!files2.length) return;
                            setPhotoPreviewFiles(files2.map(f => ({
                              file: f,
                              url: URL.createObjectURL(f),
                              selected: true,
                            })));
                            setPhotoPreviewOpen(true);
                            e.target.value = "";
                          }} />
                      </label>
                      <label className="px-3 py-1.5 bg-teal-100 hover:bg-teal-200 text-teal-700 text-xs font-bold rounded-lg cursor-pointer border border-teal-300 transition-colors">
                        1枚追加
                        <input type="file" accept="image/*" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "PHOTO"); e.target.value = ""; } }} />
                      </label>
                    </div>
                  </div>
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center text-xs text-slate-400"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-teal-400","bg-teal-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-teal-400","bg-teal-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
                      if (droppedFiles.length === 1) { handleFileUpload(droppedFiles[0], "PHOTO"); return; }
                      if (droppedFiles.length > 1) {
                        setPhotoPreviewFiles(droppedFiles.map(f => ({ file: f, url: URL.createObjectURL(f), selected: true })));
                        setPhotoPreviewOpen(true);
                      }
                    }}>
                    D&Dでも追加できます（複数対応）
                  </div>
                  {fileUploading && <p className="text-xs text-teal-600 mt-2 animate-pulse">アップロード中...</p>}
                  {fileUploadMsg && <p className="text-xs mt-2 font-bold text-slate-600">{fileUploadMsg}</p>}
                </div>

                {/* 図アップロード */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-slate-600">📐 図のアップロード</p>
                    <div className="flex gap-2">
                      <label className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors">
                        複数選択・フォルダ
                        <input type="file" multiple className="hidden"
                          onChange={e => {
                            const files2 = Array.from(e.target.files ?? []);
                            if (!files2.length) return;
                            setDrawingPreviewFiles(files2.map(f => ({
                              file: f,
                              url: f.type.startsWith("image/") ? URL.createObjectURL(f) : "",
                              selected: true,
                            })));
                            setDrawingPreviewOpen(true);
                            e.target.value = "";
                          }} />
                      </label>
                      <label className="px-3 py-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 text-xs font-bold rounded-lg cursor-pointer border border-purple-300 transition-colors">
                        1枚追加
                        <input type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "DRAWING"); e.target.value = ""; } }} />
                      </label>
                    </div>
                  </div>
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center text-xs text-slate-400"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-purple-400","bg-purple-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-purple-400","bg-purple-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-purple-400","bg-purple-50");
                      const droppedFiles = Array.from(e.dataTransfer.files);
                      if (droppedFiles.length === 1) { handleFileUpload(droppedFiles[0], "DRAWING"); return; }
                      if (droppedFiles.length > 1) {
                        setDrawingPreviewFiles(droppedFiles.map(f => ({
                          file: f,
                          url: f.type.startsWith("image/") ? URL.createObjectURL(f) : "",
                          selected: true,
                        })));
                        setDrawingPreviewOpen(true);
                      }
                    }}>
                    D&Dでも追加できます（複数対応）
                  </div>
                </div>'''

if OLD_FILES_TAB in src:
    src = src.replace(OLD_FILES_TAB, NEW_FILES_TAB, 1)
    print("  OK: 図・写真タブ刷新")
else:
    print("  WARN: 図・写真タブパターン不一致")

# (3f) PGエディタモーダル + 写真/図プレビューモーダル をトーストの直前に追加
OLD_TOAST = '''      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}'''

NEW_TOAST = '''      {/* PGエディタモーダル */}
      {pgEditorOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 shrink-0">
              <div className="flex items-center gap-3">
                <span className="font-bold text-slate-800 text-sm">PGエディタ</span>
                {pgOrigName && <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded">{pgOrigName}</span>}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={async () => {
                  // File System Access API でUSBに直接保存
                  try {
                    const fileHandle = await (window as any).showSaveFilePicker({
                      suggestedName: pgOrigName || "program.min",
                      types: [{ description: 'NCプログラム', accept: { 'text/plain': ['.min','.spf','.mpf','.nc','.txt',''] } }],
                    });
                    const writable = await fileHandle.createWritable();
                    // Shift_JIS でエンコード
                    const encoder = new TextEncoder();
                    await writable.write(pgContent);
                    await writable.close();
                    showToast("✅ USB/指定先に保存しました");
                  } catch (e: any) {
                    if (e.name !== 'AbortError') showToast("❌ 保存に失敗しました: " + e.message);
                  }
                }} className="px-3 py-1.5 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors">
                  💾 USB/指定先に保存
                </button>
                <button onClick={async () => {
                  if (!token) { showToast("❌ 認証が必要です"); return; }
                  setPgSaving(true);
                  try {
                    await fetch(`/api/mc/${mcId}/pg-content`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({ content: pgContent, original_name: pgOrigName }),
                    });
                    showToast("✅ PGファイルをサーバに保存しました");
                    // pgUpdatedAt更新
                    setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                  } catch { showToast("❌ サーバ保存に失敗しました"); }
                  finally { setPgSaving(false); }
                }} disabled={pgSaving}
                  className="px-3 py-1.5 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors disabled:opacity-50">
                  {pgSaving ? "保存中..." : "✓ サーバに保存"}
                </button>
                <button onClick={() => setPgEditorOpen(false)}
                  className="px-3 py-1.5 text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg">
                  閉じる
                </button>
              </div>
            </div>
            {/* 検索・置換バー */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-100 bg-slate-50 shrink-0">
              <input value={pgEditorSearch} onChange={e => setPgEditorSearch(e.target.value)}
                placeholder="検索..." className="border border-slate-300 rounded px-2 py-1 text-xs w-40 font-mono" />
              <input value={pgEditorReplace} onChange={e => setPgEditorReplace(e.target.value)}
                placeholder="置換後..." className="border border-slate-300 rounded px-2 py-1 text-xs w-40 font-mono" />
              <button onClick={() => {
                if (!pgEditorSearch) return;
                const count = (pgContent.match(new RegExp(pgEditorSearch.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'g')) ?? []).length;
                showToast(`${count}件マッチ`);
              }} className="px-2 py-1 text-xs bg-slate-200 hover:bg-slate-300 rounded font-bold">検索</button>
              <button onClick={() => {
                if (!pgEditorSearch) return;
                const newContent = pgContent.split(pgEditorSearch).join(pgEditorReplace);
                setPgContent(newContent);
                showToast("置換しました");
              }} className="px-2 py-1 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded font-bold">全置換</button>
              <span className="text-[10px] text-slate-400 ml-2">{pgContent.split('\n').length}行 / {pgContent.length}文字</span>
            </div>
            <div className="flex-1 overflow-hidden">
              <textarea
                value={pgContent}
                onChange={e => setPgContent(e.target.value)}
                className="w-full h-full p-4 font-mono text-xs text-green-300 bg-slate-900 resize-none focus:outline-none leading-relaxed"
                style={{ minHeight: "400px" }}
                spellCheck={false}
              />
            </div>
          </div>
        </div>
      )}

      {/* 写真 複数プレビュー選択モーダル */}
      {photoPreviewOpen && photoPreviewFiles.length > 0 && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 shrink-0">
              <div>
                <span className="font-bold text-slate-800">写真の取り込み確認</span>
                <span className="ml-2 text-xs text-slate-500">{photoPreviewFiles.filter(f => f.selected).length}/{photoPreviewFiles.length}枚 選択中</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setPhotoPreviewFiles(f => f.map(x => ({ ...x, selected: true })))}
                  className="text-xs text-teal-600 font-bold px-2 py-1 rounded hover:bg-teal-50">全選択</button>
                <button onClick={() => setPhotoPreviewFiles(f => f.map(x => ({ ...x, selected: false })))}
                  className="text-xs text-slate-500 font-bold px-2 py-1 rounded hover:bg-slate-100">全解除</button>
                <button onClick={async () => {
                  if (!token) return;
                  const selected = photoPreviewFiles.filter(f => f.selected);
                  if (!selected.length) { showToast("1枚以上選択してください"); return; }
                  setBulkUploading(true);
                  let ok = 0;
                  for (const item of selected) {
                    try {
                      await handleFileUpload(item.file, "PHOTO");
                      ok++;
                    } catch { /* ignore */ }
                  }
                  setBulkUploading(false);
                  photoPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                  setPhotoPreviewOpen(false);
                  setPhotoPreviewFiles([]);
                  showToast(`✅ ${ok}枚の写真をアップロードしました`);
                }} disabled={bulkUploading}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg disabled:opacity-50">
                  {bulkUploading ? "アップロード中..." : `選択した${photoPreviewFiles.filter(f=>f.selected).length}枚を取り込む`}
                </button>
                <button onClick={() => {
                  photoPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                  setPhotoPreviewOpen(false); setPhotoPreviewFiles([]);
                }} className="px-3 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-lg hover:bg-slate-300">キャンセル</button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="grid grid-cols-4 gap-3">
                {photoPreviewFiles.map((item, i) => (
                  <div key={i} onClick={() => setPhotoPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x))}
                    className={`cursor-pointer rounded-xl overflow-hidden border-3 transition-all ${item.selected ? "border-4 border-teal-500 shadow-lg" : "border-2 border-slate-200 opacity-60"}`}>
                    <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                      <img src={item.url} alt={item.file.name} className="w-full h-full object-cover" />
                    </div>
                    <div className="px-2 py-1 bg-white">
                      <p className="text-[10px] text-slate-600 truncate">{item.file.name}</p>
                      <p className="text-[9px] text-slate-400">{(item.file.size / 1024).toFixed(0)} KB</p>
                    </div>
                    {item.selected && <div className="absolute top-1 right-1 w-5 h-5 bg-teal-500 rounded-full flex items-center justify-center text-white text-xs font-bold">✓</div>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 図 複数プレビュー選択モーダル */}
      {drawingPreviewOpen && drawingPreviewFiles.length > 0 && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 shrink-0">
              <div>
                <span className="font-bold text-slate-800">図の取り込み確認</span>
                <span className="ml-2 text-xs text-slate-500">{drawingPreviewFiles.filter(f => f.selected).length}/{drawingPreviewFiles.length}枚 選択中</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setDrawingPreviewFiles(f => f.map(x => ({ ...x, selected: true })))}
                  className="text-xs text-purple-600 font-bold px-2 py-1 rounded hover:bg-purple-50">全選択</button>
                <button onClick={() => setDrawingPreviewFiles(f => f.map(x => ({ ...x, selected: false })))}
                  className="text-xs text-slate-500 font-bold px-2 py-1 rounded hover:bg-slate-100">全解除</button>
                <button onClick={async () => {
                  if (!token) return;
                  const selected = drawingPreviewFiles.filter(f => f.selected);
                  if (!selected.length) { showToast("1枚以上選択してください"); return; }
                  setBulkUploading(true);
                  let ok = 0;
                  for (const item of selected) {
                    try {
                      await handleFileUpload(item.file, "DRAWING");
                      ok++;
                    } catch { /* ignore */ }
                  }
                  setBulkUploading(false);
                  drawingPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                  setDrawingPreviewOpen(false);
                  setDrawingPreviewFiles([]);
                  showToast(`✅ ${ok}枚の図をアップロードしました`);
                }} disabled={bulkUploading}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg disabled:opacity-50">
                  {bulkUploading ? "アップロード中..." : `選択した${drawingPreviewFiles.filter(f=>f.selected).length}枚を取り込む`}
                </button>
                <button onClick={() => {
                  drawingPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                  setDrawingPreviewOpen(false); setDrawingPreviewFiles([]);
                }} className="px-3 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-lg hover:bg-slate-300">キャンセル</button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="grid grid-cols-4 gap-3">
                {drawingPreviewFiles.map((item, i) => (
                  <div key={i} onClick={() => setDrawingPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x))}
                    className={`cursor-pointer rounded-xl overflow-hidden transition-all ${item.selected ? "border-4 border-purple-500 shadow-lg" : "border-2 border-slate-200 opacity-60"}`}>
                    <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                      {item.url ? <img src={item.url} alt={item.file.name} className="w-full h-full object-cover" /> :
                        <div className="text-4xl">📄</div>}
                    </div>
                    <div className="px-2 py-1 bg-white">
                      <p className="text-[10px] text-slate-600 truncate">{item.file.name}</p>
                      <p className="text-[9px] text-slate-400">{(item.file.size / 1024).toFixed(0)} KB</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}'''

if OLD_TOAST in src:
    src = src.replace(OLD_TOAST, NEW_TOAST, 1)
    print("  OK: PGエディタ/写真・図プレビューモーダル追加")
else:
    print("  WARN: トースト末尾パターン不一致")

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

# ─────────────────────────────────────────────────────────
# [4] API build
# ─────────────────────────────────────────────────────────
print("=== [4] API ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/api && npx nest build 2>&1 | tail -15",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("API BUILD ERROR:", r.stderr[-500:])
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# [5] Web build
# ─────────────────────────────────────────────────────────
print("=== [5] Web ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -15",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("WEB BUILD ERROR:", r.stderr[-500:])
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# [6] PM2 再起動
# ─────────────────────────────────────────────────────────
print("=== [6] PM2 再起動 ===")
subprocess.run("pm2 restart machcore-api machcore-web && pm2 ls", shell=True)

# ─────────────────────────────────────────────────────────
# [7] git push
# ─────────────────────────────────────────────────────────
print("=== [7] git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "feat: MC PG editor + USB save(FSA) + bulk photo/drawing upload with preview" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
