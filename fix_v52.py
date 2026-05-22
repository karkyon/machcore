#!/usr/bin/env python3
"""
fix_v52.py
写真と図を完全独立管理
- 「写真を選択」→ file_type=PHOTO 強制指定
- 「図を選択」→ file_type=DRAWING 強制指定
- APIにfile_typeフォームフィールドを追加
- mc-files.service.tsでfile_typeフィールドを優先（MIMEタイプ自動判定を上書き）
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

# ============================================================
# 1. api.ts: mcFilesApi.upload に fileType パラメータ追加
# ============================================================
API_TS = os.path.join(ROOT, "apps/web/lib/api.ts")
patch(API_TS,
    """export const mcFilesApi = {
  upload: (mcId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<{ id: number; message: string }>(`/mc/${mcId}/files/upload`, fd, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },""",
    """export const mcFilesApi = {
  upload: (mcId: number, file: File, token: string, fileType?: 'PHOTO' | 'DRAWING') => {
    const fd = new FormData();
    fd.append('file', file);
    if (fileType) fd.append('file_type', fileType);
    return api.post<{ id: number; message: string }>(`/mc/${mcId}/files/upload`, fd, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },""",
    "api.ts mcFilesApi.upload fileTypeパラメータ追加"
)

# ============================================================
# 2. edit/page.tsx: 写真ボタン→PHOTO, 図ボタン→DRAWING を明示指定
# ============================================================
EDIT = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/edit/page.tsx")

# 写真アップロード
patch(EDIT,
    """                      <label className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        写真を選択
                        <input ref={photoInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f); e.target.value = ""; } }} />
                      </label>
                      <label className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        図を選択
                        <input ref={scanInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f); e.target.value = ""; } }} />
                      </label>""",
    """                      <label className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        写真を選択
                        <input ref={photoInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "PHOTO"); e.target.value = ""; } }} />
                      </label>
                      <label className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        図を選択
                        <input ref={scanInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "DRAWING"); e.target.value = ""; } }} />
                      </label>""",
    "edit/page.tsx 写真/図ボタンにfileType指定"
)

# D&Dは写真として扱う（D&DはデフォルトPHOTO）
patch(EDIT,
    """                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const f = e.dataTransfer.files[0];
                      if (f) handleFileUpload(f);
                    }}>""",
    """                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const f = e.dataTransfer.files[0];
                      if (f) handleFileUpload(f, "PHOTO");
                    }}>""",
    "edit/page.tsx D&DはPHOTOとして扱う"
)

# handleFileUpload関数にfileType引数追加
patch(EDIT,
    "  const handleFileUpload = async (file: File) => {\n    if (!token) return;",
    "  const handleFileUpload = async (file: File, fileType?: 'PHOTO' | 'DRAWING') => {\n    if (!token) return;",
    "edit/page.tsx handleFileUpload fileType引数追加"
)

patch(EDIT,
    "      await mcFilesApi.upload(mcId, file, token);",
    "      await mcFilesApi.upload(mcId, file, token, fileType);",
    "edit/page.tsx handleFileUpload mcFilesApi.uploadにfileType渡す"
)

# ============================================================
# 3. mc-files.service.ts: file_typeフォームフィールドを優先的に使用
# ============================================================
CONTROLLER = os.path.join(ROOT, "apps/api/src/mc/mc.controller.ts")
patch(CONTROLLER,
    "    const pgRole = (data.fields?.pg_role?.value ?? undefined) as 'MAIN' | 'SUB' | undefined;\n    const result = await this.mcFiles.upload(id, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf }, pgRole, isFolderUpload);",
    """    const pgRole = (data.fields?.pg_role?.value ?? undefined) as 'MAIN' | 'SUB' | undefined;
    const fileTypeOverride = (data.fields?.file_type?.value ?? undefined) as 'PHOTO' | 'DRAWING' | undefined;
    const result = await this.mcFiles.upload(id, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf }, pgRole, isFolderUpload, fileTypeOverride);""",
    "mc.controller.ts file_type フォームフィールド受け取り"
)

SERVICE = os.path.join(ROOT, "apps/api/src/mc/mc-files.service.ts")
# uploadメソッドのシグネチャにfileTypeOverride追加
patch(SERVICE,
    """  async upload(
    mcProgramId:    number,
    uploadedBy:     number,
    file:           { filename: string; mimetype: string; data: Buffer },
    pgRoleOverride?: PgRole,
    isFolderUpload?: boolean,  // true=ケース2（フォルダ構成）、false/undefined=ケース1（単一）
  ) {""",
    """  async upload(
    mcProgramId:    number,
    uploadedBy:     number,
    file:           { filename: string; mimetype: string; data: Buffer },
    pgRoleOverride?: PgRole,
    isFolderUpload?: boolean,  // true=ケース2（フォルダ構成）、false/undefined=ケース1（単一）
    fileTypeOverride?: 'PHOTO' | 'DRAWING',  // フロントから明示指定されたファイル種別
  ) {""",
    "mc-files.service.ts uploadシグネチャ fileTypeOverride追加"
)

# fileTypeEnumの決定でfileTypeOverrideを最優先
patch(SERVICE,
    """    let fileTypeEnum: string;
    if (isProgram)             fileTypeEnum = 'PROGRAM';
    else if (isImage || isPdf) fileTypeEnum = ['image/jpeg','image/jpg','image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';
    else                       fileTypeEnum = 'OTHER';""",
    """    let fileTypeEnum: string;
    if (isProgram)                      fileTypeEnum = 'PROGRAM';
    else if (fileTypeOverride)          fileTypeEnum = fileTypeOverride;  // フロント指定を最優先
    else if (isImage || isPdf)          fileTypeEnum = ['image/jpeg','image/jpg','image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';
    else                                fileTypeEnum = 'OTHER';""",
    "mc-files.service.ts fileTypeOverrideを最優先に"
)

# ============================================================
# BUILD & PUSH
# ============================================================
print("\n--- API npx tsc --noEmit ---")
r2 = subprocess.run("cd ~/projects/machcore/apps/api && npx tsc --noEmit", shell=True, capture_output=True, text=True)
if r2.returncode != 0:
    print(r2.stdout); print("STDERR:", r2.stderr)
    print("API TSC FAILED — abort"); sys.exit(1)
else:
    print("(no output)")

print("\n--- API nest build ---")
r3 = subprocess.run("cd ~/projects/machcore/apps/api && npx nest build", shell=True, capture_output=True, text=True)
if r3.returncode != 0:
    print(r3.stdout); print("STDERR:", r3.stderr[-500:])
    print("API BUILD FAILED — abort"); sys.exit(1)
else:
    print("(no output)")

print("\n--- npm run build ---")
r = subprocess.run("cd ~/projects/machcore/apps/web && npm run build", shell=True, capture_output=True, text=True)
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
stderr_clean = "\n".join(l for l in r.stderr.split("\n") if "react-pdf" not in l)
if stderr_clean.strip():
    print("STDERR:", stderr_clean[-500:])

if r.returncode != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run("pm2 restart machcore-api machcore-web --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "feat: 写真/図を完全独立管理 ボタン別fileType指定 v52" && git push',
    shell=True
)
print("DONE")
