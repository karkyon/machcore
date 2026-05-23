import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    content = read(path)
    if old not in content:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, content.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ── 1. DB: mc_filesのfile_typeをファイルパスで補正 ──────────────────
print("--- DB: mc_files file_type補正 ---")
sql = """
-- drawings/パスにあるファイルをDRAWINGに修正
UPDATE mc_files
SET file_type = 'DRAWING'
WHERE (file_path LIKE '%/drawings/%' OR file_path LIKE '%\\drawings\\%')
  AND file_type != 'DRAWING';

-- photos/パスにあるファイルをPHOTOに修正
UPDATE mc_files
SET file_type = 'PHOTO'
WHERE (file_path LIKE '%/photos/%' OR file_path LIKE '%\\photos\\%')
  AND file_type != 'PHOTO';

SELECT file_type, COUNT(*) FROM mc_files GROUP BY file_type ORDER BY file_type;
"""
r = subprocess.run(
    ["docker", "exec", "machcore-postgres", "psql",
     "-U", "machcore", "-d", "machcore_dev", "-c", sql],
    capture_output=True, text=True, cwd=ROOT
)
print(r.stdout or "(no output)")
if r.stderr: print("STDERR:", r.stderr)

# ── 2. mc/[mc_id]/page.tsx — 写真・図セクション分離表示 ─────────────
PAGE_TSX = f"{ROOT}/apps/web/app/mc/[mc_id]/page.tsx"

OLD_FILES_SECTION = '''        {/* ─── 写真・図 ─── */}
        {mainTab === "files" && (
          <div className="max-w-3xl mx-auto">
            {d.files.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <div className="text-4xl mb-3">📁</div>
                <p className="text-slate-400 text-sm">ファイルがありません</p>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="mt-4 text-teal-600 text-sm hover:underline">編集画面でアップロード →</button>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                {d.files.filter(f => f.file_type === "PHOTO" || f.file_type === "DRAWING").map(f => (
                  <div key={f.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => setPreviewFile(f)}>
                    <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                      <img
                        src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                        alt={f.original_name}
                        className="w-full h-full object-contain"
                        loading="lazy"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    </div>
                    <div className="px-2 py-1.5">
                      <p className="text-[11px] text-slate-600 truncate">{f.stored_name ??'''

# 次の部分まで含めて取得
content = read(PAGE_TSX)
old_start = old_start_idx = content.find(OLD_FILES_SECTION)
if old_start_idx == -1:
    print("WARN: mc/[mc_id]/page.tsx 写真・図セクション — パターン不一致")
else:
    # セクション全体の終わりを探す（次の大きなブロックの前まで）
    # "previewFileモーダル" or "mainTab === " の次の出現位置
    search_after = old_start_idx + len(OLD_FILES_SECTION)
    # ")}\n\n        {/* " パターンで終わりを探す
    end_marker = "\n        {/* プレビュー"
    end_idx = content.find(end_marker, search_after)
    if end_idx == -1:
        end_marker2 = "\n      )}\n    </div>"
        end_idx = content.find(end_marker2, search_after)
    
    if end_idx == -1:
        print("WARN: mc/[mc_id]/page.tsx 写真・図セクション終端 — 見つからない")
    else:
        # 終端の探索："})}' + 次のコメントブロック
        # ファイルセクション全体を特定するために少し後ろを見る
        chunk = content[old_start_idx:end_idx+50]
        # 終端は最後の ")}\n        )}\n\n" のパターン
        # もっとシンプルに: ファイルセクションの具体的な終わりを探す
        close_pattern = "            )}\n          </div>\n        )}\n\n        {/* プレビュー"
        close_idx = content.find(close_pattern, search_after - 200)
        if close_idx == -1:
            close_pattern2 = "            )}\n          </div>\n        )}\n"
            close_idx = content.find(close_pattern2, search_after - 200)
        
        print(f"INFO: セクション開始={old_start_idx}, 候補終端={close_idx}")

# パターンが複雑なので直接置換で対応
OLD_FILES = '''              <div className="grid grid-cols-3 gap-4">
                {d.files.filter(f => f.file_type === "PHOTO" || f.file_type === "DRAWING").map(f => (
                  <div key={f.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => setPreviewFile(f)}>
                    <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                      <img
                        src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                        alt={f.original_name}
                        className="w-full h-full object-contain"
                        loading="lazy"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    </div>
                    <div className="px-2 py-1.5">
                      <p className="text-[11px] text-slate-600 truncate">{f.stored_name ??'''

NEW_FILES = '''              {/* 📷 写真セクション */}
              {d.files.filter(f => f.file_type === "PHOTO").length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-bold text-white bg-teal-600 px-2.5 py-0.5 rounded-full">📷 写真</span>
                    <span className="text-xs text-slate-400">{d.files.filter(f => f.file_type === "PHOTO").length}枚</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    {d.files.filter(f => f.file_type === "PHOTO").map(f => (
                      <div key={f.id} className="bg-white rounded-xl border-2 border-teal-300 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                        onClick={() => setPreviewFile(f)}>
                        <div className="aspect-square bg-teal-50 flex items-center justify-center overflow-hidden">
                          <img src={`/api/mc/${mcId}/files/${f.id}/thumb`} alt={f.original_name}
                            className="w-full h-full object-contain" loading="lazy"
                            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                        </div>
                        <div className="px-2 py-1.5 bg-teal-50 border-t border-teal-200">
                          <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ??'''

patch(PAGE_TSX, OLD_FILES, NEW_FILES, "mc/[mc_id]/page.tsx 写真グリッド置換開始")

# 写真グリッドの続き（ファイル名の後）～図グリッドの追加
OLD_FILES_CONT = '''                      <p className="text-[11px] text-slate-600 truncate">{f.stored_name ??'''

content2 = read(PAGE_TSX)
# 直前の変更で teal-800 になっているはずなので、残りのパターンを修正
OLD_FILE_REST = '''                          <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ??'''

idx = content2.find(OLD_FILE_REST)
if idx == -1:
    print("WARN: 写真グリッド続き — パターン不一致")
else:
    # この後のoriginal_nameまで含めて置換
    # 元の: {f.original_name}</p>\n                    </div>\n                  </div>\n                ))}\n              </div>
    # + 図グリッドを追加
    OLD_CLOSE = '''                          <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ??
                        f.original_name}</p>
                        </div>
                      </div>
                    ))}
                  </div>
            )}
          </div>
        )}'''
    
    NEW_CLOSE = '''                          <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ??
                        f.original_name}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 📐 図セクション */}
              {d.files.filter(f => f.file_type === "DRAWING").length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-bold text-white bg-purple-600 px-2.5 py-0.5 rounded-full">📐 図</span>
                    <span className="text-xs text-slate-400">{d.files.filter(f => f.file_type === "DRAWING").length}枚</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    {d.files.filter(f => f.file_type === "DRAWING").map(f => (
                      <div key={f.id} className="bg-white rounded-xl border-2 border-purple-300 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                        onClick={() => setPreviewFile(f)}>
                        <div className="aspect-square bg-purple-50 flex items-center justify-center overflow-hidden">
                          <img src={`/api/mc/${mcId}/files/${f.id}/thumb`} alt={f.original_name}
                            className="w-full h-full object-contain" loading="lazy"
                            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                        </div>
                        <div className="px-2 py-1.5 bg-purple-50 border-t border-purple-200">
                          <p className="text-[11px] text-purple-800 font-bold truncate">{f.stored_name ??
                        f.original_name}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            )}
          </div>
        )}'''

    patch(PAGE_TSX, OLD_CLOSE, NEW_CLOSE, "mc/[mc_id]/page.tsx 図グリッド追加")

# ── 3. ビルド & デプロイ ────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: MC詳細 写真/図セクション分離表示 + DBのfile_type補正 v60" && git push')
print("DONE")
