#!/usr/bin/env python3
"""
fix_v53.py
1. mcFilesApi.delete: /files/:id → /mc/:mcId/files/:id に修正
2. edit/page.tsx 削除ボタン: mcFilesApi.deleteにmcIdを渡す
3. @fastify/multipartのfields取得方法確認・修正
4. 写真/図を視覚的に区別するUIバッジ追加（緑=写真、紫=図）
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

API_TS = os.path.join(ROOT, "apps/web/lib/api.ts")
EDIT   = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/edit/page.tsx")

# ============================================================
# 1. api.ts: mcFilesApi.delete を MC専用エンドポイントに修正
# ============================================================
patch(API_TS,
    """  delete: (fileId: number, token: string) =>
    api.delete(`/files/${fileId}`, { headers: { Authorization: `Bearer ${token}` } }),""",
    """  delete: (mcId: number, fileId: number, token: string) =>
    api.delete(`/mc/${mcId}/files/${fileId}`, { headers: { Authorization: `Bearer ${token}` } }),""",
    "api.ts mcFilesApi.delete → /mc/:mcId/files/:fileId"
)

# ============================================================
# 2. edit/page.tsx 削除ボタン: mcFilesApi.deleteにmcIdを渡す
# ============================================================
patch(EDIT,
    """                              if (!token || !window.confirm("削除しますか？")) return;
                              await mcFilesApi.delete(f.id, token);""",
    """                              if (!token || !window.confirm("削除しますか？")) return;
                              await mcFilesApi.delete(mcId, f.id, token);""",
    "edit/page.tsx 削除ボタン mcIdを渡す"
)

# ============================================================
# 3. サムネイルURLをrelativeパスに修正（localhost直叩き問題解消）
# ============================================================
patch(EDIT,
    '          <img src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api"}/mc/${mcId}/files/${f.id}/thumb`}',
    '          <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}',
    "edit/page.tsx サムネイルURLをrelativeに修正"
)

# ============================================================
# 4. 写真/図を視覚的に区別するUI（バッジ + ボーダー色）
# ============================================================
patch(EDIT,
    """                    {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 ? (
                  <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">ファイルがありません</div>
                ) : (
                  <div className="grid grid-cols-3 gap-4">
                    {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").map((f: any) => (
                      <div key={f.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                        <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
                          <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                            alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                            onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                        </div>
                        <div className="px-2 py-1.5 flex items-center justify-between">
                          <p className="text-[11px] text-slate-600 truncate flex-1">{f.stored_name ?? f.original_name}</p>
                          <button onClick={async () => {
                              if (!token || !window.confirm("削除しますか？")) return;
                              await mcFilesApi.delete(mcId, f.id, token);
                              const r = await mcApi.listFiles(mcId);
                              setFiles((r as any).data ?? []);
                            }}
                            className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0">✕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}""",
    """                    {/* 写真セクション */}
                  {files.filter((f: any) => f.file_type === "PHOTO").length > 0 && (
                    <div className="mb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold text-teal-700 bg-teal-100 px-2 py-0.5 rounded">📷 写真</span>
                        <span className="text-xs text-slate-400">{files.filter((f: any) => f.file_type === "PHOTO").length}枚</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {files.filter((f: any) => f.file_type === "PHOTO").map((f: any) => (
                          <div key={f.id} className="bg-white rounded-xl border-2 border-teal-200 overflow-hidden">
                            <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden relative">
                              <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                                alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                                onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                            </div>
                            <div className="px-2 py-1.5 flex items-center justify-between bg-teal-50">
                              <p className="text-[11px] text-teal-700 font-bold truncate flex-1">{f.stored_name ?? f.original_name}</p>
                              <button onClick={async () => {
                                  if (!token || !window.confirm("削除しますか？")) return;
                                  await mcFilesApi.delete(mcId, f.id, token);
                                  const r = await mcApi.listFiles(mcId);
                                  setFiles((r as any).data ?? []);
                                }}
                                className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0">✕</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* 図セクション */}
                  {files.filter((f: any) => f.file_type === "DRAWING").length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded">📐 図</span>
                        <span className="text-xs text-slate-400">{files.filter((f: any) => f.file_type === "DRAWING").length}枚</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {files.filter((f: any) => f.file_type === "DRAWING").map((f: any) => (
                          <div key={f.id} className="bg-white rounded-xl border-2 border-purple-200 overflow-hidden">
                            <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden relative">
                              <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                                alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                                onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                            </div>
                            <div className="px-2 py-1.5 flex items-center justify-between bg-purple-50">
                              <p className="text-[11px] text-purple-700 font-bold truncate flex-1">{f.stored_name ?? f.original_name}</p>
                              <button onClick={async () => {
                                  if (!token || !window.confirm("削除しますか？")) return;
                                  await mcFilesApi.delete(mcId, f.id, token);
                                  const r = await mcApi.listFiles(mcId);
                                  setFiles((r as any).data ?? []);
                                }}
                                className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0">✕</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 && (
                    <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">ファイルがありません</div>
                  )}""",
    "edit/page.tsx 写真/図セクション分離 + バッジUI"
)

# ============================================================
# BUILD & PUSH
# ============================================================
print("\n--- npm run build ---")
r = subprocess.run("cd ~/projects/machcore/apps/web && npm run build", shell=True, capture_output=True, text=True)
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
stderr_clean = "\n".join(l for l in r.stderr.split("\n") if "react-pdf" not in l)
if stderr_clean.strip():
    print("STDERR:", stderr_clean[-500:])

if r.returncode != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

print("\n--- pm2 restart web ---")
subprocess.run("pm2 restart machcore-web --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "fix: MC削除エンドポイント修正・写真/図セクション分離バッジUI・サムネイルrelativeURL v53" && git push',
    shell=True
)
print("DONE")
