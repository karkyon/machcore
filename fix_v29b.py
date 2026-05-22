#!/usr/bin/env python3
# coding: utf-8
import pathlib, subprocess, sys

root = "/home/karkyon/projects/machcore"

# ─────────────────────────────────────────────────────────────
# 1. page.tsx: STEP1ボタン押下時に認証→成功後にedit遷移
# ─────────────────────────────────────────────────────────────
root_page = pathlib.Path(root + "/apps/web/app/page.tsx")
src = root_page.read_text(encoding="utf-8")

# (a) sbStep1AuthOpen state追加
OLD_SB_STATE = "  const [sbAuthOpen,      setSbAuthOpen]      = useState(false);\n  const [sbCollecting,    setSbCollecting]    = useState(false);"
NEW_SB_STATE = """  const [sbAuthOpen,      setSbAuthOpen]      = useState(false);
  const [sbCollecting,    setSbCollecting]    = useState(false);
  const [sbStep1AuthOpen, setSbStep1AuthOpen] = useState(false);
  const [sbStep1McId,     setSbStep1McId]     = useState<number>(0);"""

if OLD_SB_STATE in src:
    src = src.replace(OLD_SB_STATE, NEW_SB_STATE)
    print("OK: sbStep1AuthOpen state追加")
else:
    print("WARN: sbAuthOpen state パターン不一致")

# (b) STEP1ボタン: sessionStorage設定→editへの直接遷移を削除し、認証モーダルを開くように変更
OLD_STEP1_BTN = '''                        <button
                          onClick={() => {
                            if (typeof window !== "undefined") {
                              sessionStorage.setItem("sb_next_record", String(sbSelectedSheet.mc_id));
                            }
                            setSbModalOpen(false);
                            router.push(`/mc/${sbSelectedSheet.mc_id}/edit`);
                          }}
                          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors">
                          STEP 1: マシニング情報を登録（新規）
                        </button>'''

NEW_STEP1_BTN = '''                        <button
                          onClick={() => {
                            setSbStep1McId(sbSelectedSheet.mc_id);
                            setSbModalOpen(false);
                            setSbStep1AuthOpen(true);
                          }}
                          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors">
                          STEP 1: マシニング情報を登録（新規）— 担当者認証へ
                        </button>'''

if OLD_STEP1_BTN in src:
    src = src.replace(OLD_STEP1_BTN, NEW_STEP1_BTN)
    print("OK: STEP1ボタン→認証モーダルへ変更")
else:
    print("WARN: STEP1ボタンパターン不一致")

# (c) sbStep1AuthOpen用のAuthModalとonSuccess処理を追加
# 認証モーダルの直後に追加
OLD_AUTH_MODAL_CLOSE = '''      {/* 認証モーダル */}
      {sbAuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="WORK_RECORD"
          mcProgramId={sbSelectedSheet?.mc_id ?? sbResult?.programs?.[0]?.mc_id ??'''

NEW_AUTH_MODAL_CLOSE = '''      {/* STEP1認証モーダル */}
      {sbStep1AuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="edit"
          mcProgramId={sbStep1McId}
          onSuccess={() => {
            setSbStep1AuthOpen(false);
            if (typeof window !== "undefined") {
              sessionStorage.setItem("sb_next_record", String(sbStep1McId));
            }
            router.push(`/mc/${sbStep1McId}/edit`);
          }}
          onCancel={() => setSbStep1AuthOpen(false)}
        />
      )}

      {/* 認証モーダル */}
      {sbAuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="WORK_RECORD"
          mcProgramId={sbSelectedSheet?.mc_id ?? sbResult?.programs?.[0]?.mc_id ??'''

if OLD_AUTH_MODAL_CLOSE in src:
    src = src.replace(OLD_AUTH_MODAL_CLOSE, NEW_AUTH_MODAL_CLOSE)
    print("OK: STEP1認証モーダル追加")
else:
    print("WARN: 認証モーダルパターン不一致")

root_page.write_text(src, encoding="utf-8")
print("OK: page.tsx 書き込み完了")

# ─────────────────────────────────────────────────────────────
# 2. lib/api.ts: mcFilesApi.upload エンドポイント修正
# ─────────────────────────────────────────────────────────────
api_ts = pathlib.Path(root + "/apps/web/lib/api.ts")
asrc = api_ts.read_text(encoding="utf-8")

OLD_UPLOAD = '''export const mcFilesApi = {
  upload: (mcId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('mc_program_id', String(mcId));
    return api.post<{ id: number; message: string }>('/files/upload', fd, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },'''

NEW_UPLOAD = '''export const mcFilesApi = {
  upload: (mcId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post<{ id: number; message: string }>(`/mc/${mcId}/files/upload`, fd, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },'''

if OLD_UPLOAD in asrc:
    asrc = asrc.replace(OLD_UPLOAD, NEW_UPLOAD)
    print("OK: mcFilesApi.upload エンドポイント修正")
else:
    print("WARN: mcFilesApi パターン不一致（既に修正済みの可能性）")

api_ts.write_text(asrc, encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# 3. edit/page.tsx: ツーリングファイル Shift-JIS→UTF-8に変更
# ─────────────────────────────────────────────────────────────
edit = pathlib.Path(root + "/apps/web/app/mc/[mc_id]/edit/page.tsx")
esrc = edit.read_text(encoding="utf-8")

esrc = esrc.replace('reader.readAsText(f, "shift-jis")', 'reader.readAsText(f)')
esrc = esrc.replace('reader.readAsText(f2, "shift-jis")', 'reader.readAsText(f2)')
print("OK: ツーリングファイル UTF-8読み込みに変更")

edit.write_text(esrc, encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# ビルド + PM2 + push
# ─────────────────────────────────────────────────────────────
web = root + "/apps/web"
print("\n--- npm run build ---")
r = subprocess.run(["npm", "run", "build"], cwd=web, capture_output=True, text=True)
out = r.stdout + r.stderr
print(out[-3000:] if len(out) > 3000 else out)
if r.returncode != 0:
    print("BUILD ERROR - Pushしない")
    sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["bash", "-c",
    "export NVM_DIR=$HOME/.nvm && source $NVM_DIR/nvm.sh && "
    "pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web && pm2 save"
], cwd=root, executable="/bin/bash")

print("\n--- git push ---")
subprocess.run(["git", "add", "-A"], cwd=root)
subprocess.run(["git", "commit", "-m",
    "fix: STEP1ボタン→認証先行→edit遷移 + ファイルUPエンドポイント修正 v29"
], cwd=root)
r2 = subprocess.run(["git", "push", "origin", "main"], cwd=root, capture_output=True, text=True)
print(r2.stdout, r2.stderr)
print("完了")