#!/usr/bin/env python3
# coding: utf-8
import pathlib

edit = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/edit/page.tsx")
src = edit.read_text(encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# 現在の構造:
#   {isAuthenticated && (
#     <div flex flex-1 overflow-hidden>
#       サイドメニュー
#       <div flex-1 overflow-y-auto p-5>
#         {activeSection === "basic" && (...)}
#         {activeSection === "tooling" && (...)}
#         {activeSection === "offset" && (...)}
#         {activeSection === "index" && (...)}    ← ここの直後に files を挿入
#       </div>
#     </div>
#   )}
#   {/* 図・写真 */}   ← 現在ここにある（外側）→ 削除
#   {activeSection === "files" && (...)}
# ─────────────────────────────────────────────────────────────

# Step1: 外側に誤配置されている図・写真ブロックを削除
# インデックスPGセクション末尾の ")}}" の後ろにある図・写真ブロックを特定
# GitHubで確認: インデックスPG直後 → "</div></div>)}" → "      {/* 図・写真 */}" → "      {activeSection === "files" && ("

# 現在の外側ブロック全体を検索・削除
# まず外側ブロックの開始パターンを確認
lines = src.splitlines()
start_line = -1
end_line = -1
depth = 0
in_files = False

for i, l in enumerate(lines):
    if '      {/* 図・写真 */}' in l and not in_files:
        # この行以降が外側の図・写真ブロック
        # 次の activeSection === "files" から始まるJSXブロックを探す
        start_line = i
        in_files = True
    if in_files and start_line >= 0:
        # 認証モーダルコメントが来たら終了
        if '{/* 認証モーダル */}' in l:
            end_line = i
            break

print(f"外側図・写真ブロック: L{start_line+1} ～ L{end_line} (削除対象)")

# Step2: インデックスPGセクション末尾を特定（そこに figures セクションを挿入）
# パターン: "            )}\n\n          </div>\n        </div>\n      )}" (isAuthenticated ブロック終了)
# インデックスPG末尾 → "</div></div>)}" → "</div></div>" → ")}"

# 正確なパターン: インデックスPGセクション末尾
OLD_INDEX_END = '''            )}
          </div>
        </div>
      )}

      {/* 図・写真 */}'''

# files JSX（正しい位置に入れるもの）
FILES_JSX = '''            {/* 図・写真 */}
            {activeSection === "files" && (
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
                      if (f) handleFileUpload(f);
                    }}>
                    <p className="text-slate-400 text-sm mb-3">ファイルをここにドラッグ＆ドロップ</p>
                    <div className="flex items-center justify-center gap-3">
                      <label className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        写真を選択
                        <input ref={photoInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f); e.target.value = ""; } }} />
                      </label>
                      <label className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        図を選択
                        <input ref={scanInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f); e.target.value = ""; } }} />
                      </label>
                    </div>
                    {fileUploading && <p className="text-xs text-teal-600 mt-2 animate-pulse">アップロード中...</p>}
                    {fileUploadMsg && <p className="text-xs mt-2 font-bold text-slate-600">{fileUploadMsg}</p>}
                    <p className="text-[10px] text-slate-400 mt-2">すべてのファイル形式に対応（写真・図・PDF等）</p>
                  </div>
                </div>
                {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 ? (
                  <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">ファイルがありません</div>
                ) : (
                  <div className="grid grid-cols-3 gap-4">
                    {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").map((f: any) => (
                      <div key={f.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                        <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                          <img src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api"}/mc/${mcId}/files/${f.id}/thumb`}
                            alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                            onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                        </div>
                        <div className="px-2 py-1.5 flex items-center justify-between">
                          <p className="text-[11px] text-slate-600 truncate flex-1">{f.original_name}</p>
                          <button onClick={async () => {
                              if (!token || !window.confirm("削除しますか？")) return;
                              await mcFilesApi.delete(f.id, token);
                              const r = await mcApi.listFiles(mcId);
                              setFiles((r as any).data ?? []);
                            }}
                            className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0">✕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      )}

      {/* 図・写真 */}'''

if OLD_INDEX_END in src:
    src = src.replace(OLD_INDEX_END, FILES_JSX)
    print("OK: 図・写真セクションを正しい位置(isAuthenticated内)に挿入")
else:
    print("WARN: インデックスPG末尾パターン不一致")
    # デバッグ
    for i, l in enumerate(src.splitlines(), 1):
        if '図・写真' in l or ('</div>' in l and i > 550 and i < 600):
            print(f"L{i}: {repr(l)}")

# Step3: 外側の古い図・写真ブロック（Step2で置換後に残っている部分）を削除
# Step2の置換で OLD_INDEX_END の末尾 "{/* 図・写真 */" が含まれているので
# 残っているのは "{activeSection === "files" && (..." ブロック + authModal直前の ")}}"
# この残留ブロックを削除

# 残留ブロック: "{activeSection === "files" && (" から "{/* 認証モーダル */}" の直前まで
# 現在のファイルを再確認
lines2 = src.splitlines()
del_start = -1
del_end = -1
for i, l in enumerate(lines2):
    if del_start == -1 and '      {activeSection === "files" && (' in l:
        del_start = i
    if del_start >= 0 and del_end == -1 and '      {/* 認証モーダル */}' in l:
        del_end = i
        break

if del_start >= 0 and del_end >= 0:
    print(f"残留ブロック削除: L{del_start+1} ～ L{del_end}")
    lines2 = lines2[:del_start] + lines2[del_end:]
    src = "\n".join(lines2)
    print("OK: 残留ブロック削除")
else:
    print(f"INFO: 残留ブロック検索: start={del_start+1}, end={del_end}")

edit.write_text(src, encoding="utf-8")
print("完了")