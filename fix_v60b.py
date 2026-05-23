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

# ── mc/[mc_id]/page.tsx — 写真・図セクション全体を正しく置換 ─────────
PAGE_TSX = f"{ROOT}/apps/web/app/mc/[mc_id]/page.tsx"

# fix_v60で半端に変換された壊れたブロックを正しいものに置換
OLD_BROKEN = '''        {/* ─── 写真・図 ─── */}
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
              {/* 📷 写真セクション */}
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
                          <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ?? f.original_name}</p>
                      <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}'''

NEW_FIXED = '''        {/* ─── 写真・図 ─── */}
        {mainTab === "files" && (
          <div className="max-w-3xl mx-auto space-y-6">
            {d.files.filter(f => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <div className="text-4xl mb-3">📁</div>
                <p className="text-slate-400 text-sm">ファイルがありません</p>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="mt-4 text-teal-600 text-sm hover:underline">編集画面でアップロード →</button>
              </div>
            ) : (
              <div>
                {/* 📷 写真セクション */}
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
                            <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ?? f.original_name}</p>
                            <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
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
                            <p className="text-[11px] text-purple-800 font-bold truncate">{f.stored_name ?? f.original_name}</p>
                            <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}'''

patch(PAGE_TSX, OLD_BROKEN, NEW_FIXED, "mc/[mc_id]/page.tsx 写真・図セクション修正")

# ── ビルド & デプロイ ────────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: MC詳細 写真/図セクション分離 JSX構文修正 v60b" && git push')
print("DONE")
