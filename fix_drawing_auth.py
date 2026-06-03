#!/usr/bin/env python3
import subprocess, sys, os

BASE = "/home/karkyon/projects/machcore"
ENV  = f"{BASE}/.env"
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"

# ── 1. .env に RIDOC_API_URL 追加 ──
env_text = open(ENV, encoding="utf-8").read()
if "RIDOC_API_URL" in env_text:
    print("SKIP .env: RIDOC_API_URL already set")
else:
    env_text = env_text.rstrip() + "\n\n# Ridoc図面サーバー (im-prodと共通)\nRIDOC_API_URL=http://192.168.1.207:5087\n"
    open(ENV, "w", encoding="utf-8").write(env_text)
    print("OK .env: RIDOC_API_URL added")

# ── 2. page.tsx: drawingModal/state/モーダル修正 ──
page = open(PAGE, encoding="utf-8").read()

# 2a. drawingBlobUrl state追加
if "drawingBlobUrl" not in page:
    OLD = "  const [drawingModal, setDrawingModal] = useState(false);"
    NEW = """  const [drawingModal,   setDrawingModal]   = useState(false);
  const [drawingBlobUrl, setDrawingBlobUrl] = useState<string | null>(null);
  const [drawingLoading, setDrawingLoading] = useState(false);
  const [drawingAuthOpen, setDrawingAuthOpen] = useState(false);"""
    if OLD not in page:
        idx = page.find("drawingModal")
        print("DEBUG drawingModal:", repr(page[idx:idx+80])); sys.exit(1)
    page = page.replace(OLD, NEW)
    print("OK page: blob state added")
else:
    print("SKIP page: blob state")

# 2b. 図面カードのonClickを認証チェック付きに変更
OLD_CLICK = '                    onClick={() => setDrawingModal(true)}>'
NEW_CLICK = """                    onClick={async () => {
                      if (!isAuthenticated) { setDrawingAuthOpen(true); return; }
                      setDrawingModal(true);
                      setDrawingLoading(true);
                      try {
                        const res = await fetch(`/api/mc/${mcId}/drawing-image?imgType=ORG`, {
                          headers: token ? { Authorization: `Bearer ${token}` } : {},
                        });
                        if (!res.ok) throw new Error(`HTTP ${res.status}`);
                        const blob = await res.blob();
                        setDrawingBlobUrl(prev => { if(prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
                      } catch { setDrawingBlobUrl(null); }
                      finally { setDrawingLoading(false); }
                    }}>"""
if OLD_CLICK not in page:
    idx = page.find("setDrawingModal(true)")
    print("DEBUG click:", repr(page[max(0,idx-60):idx+60])); sys.exit(1)
page = page.replace(OLD_CLICK, NEW_CLICK)
print("OK page: card onClick updated")

# 2c. Ridocモーダル本体を blob表示 + loading + 認証AuthModal付きに置換
OLD_MODAL = """      {/* 📋 Ridoc図面モーダル */}
      {drawingModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-0"
          onClick={() => setDrawingModal(false)}>
          <div className="bg-white flex flex-col w-screen h-screen" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 shrink-0 gap-2">
              <p className="text-sm font-bold text-slate-700">📋 図面 — {d.part.drawingNo}</p>
              <div className="flex items-center gap-2">
                <a href={`/api/mc/${mcId}/drawing-image?imgType=ORG`} target="_blank" rel="noopener noreferrer"
                  className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                  🔍 原寸を新規タブで開く
                </a>
                <button onClick={() => setDrawingModal(false)}
                  className="ml-1 text-slate-400 hover:text-slate-700 text-lg px-1.5">✕</button>
              </div>
            </div>
            <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center">
              <img src={`/api/mc/${mcId}/drawing-image?imgType=ORG`} alt={`図面 ${d.part.drawingNo}`}
                className="max-w-full max-h-full object-contain"
                onError={e => {
                  const el=e.target as HTMLImageElement; el.style.display="none";
                  const p=el.parentElement;
                  if(p && !p.querySelector(".no-draw-msg")){
                    const m=document.createElement("p"); m.className="no-draw-msg text-slate-400 text-sm text-center";
                    m.textContent="図面を取得できませんでした（RidocサーバーまたはRIDOC_API_URL未設定）"; p.appendChild(m);
                  }
                }} />
            </div>
          </div>
        </div>
      )}"""

NEW_MODAL = """      {/* 📋 Ridoc図面モーダル */}
      {drawingAuthOpen && (
        <AuthModal isOpen={true} mcProgramId={mcId} sessionType="edit"
          onSuccess={async () => {
            setDrawingAuthOpen(false);
            setDrawingModal(true);
            setDrawingLoading(true);
            try {
              const res = await fetch(`/api/mc/${mcId}/drawing-image?imgType=ORG`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const blob = await res.blob();
              setDrawingBlobUrl(prev => { if(prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
            } catch { setDrawingBlobUrl(null); }
            finally { setDrawingLoading(false); }
          }}
          onCancel={() => setDrawingAuthOpen(false)} />
      )}
      {drawingModal && (
        <div className="fixed inset-0 z-[60] bg-black/85 flex items-center justify-center p-0"
          onClick={() => { setDrawingModal(false); }}>
          <div className="bg-white flex flex-col w-screen h-screen" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 shrink-0 gap-2">
              <p className="text-sm font-bold text-slate-700">
                📋 図面 — {d.part.drawingNo}
                {operator && <span className="ml-2 text-xs font-normal text-slate-400">閲覧者: {operator.name}</span>}
              </p>
              <div className="flex items-center gap-2">
                {drawingBlobUrl && (
                  <a href={drawingBlobUrl} download={`${d.part.drawingNo}.jpg`}
                    className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                    ⬇ ダウンロード
                  </a>
                )}
                <button onClick={() => { setDrawingModal(false); }}
                  className="ml-1 text-slate-400 hover:text-slate-700 text-lg px-1.5">✕</button>
              </div>
            </div>
            <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center">
              {drawingLoading ? (
                <div className="text-slate-400 text-sm flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
                  図面を取得中…
                </div>
              ) : drawingBlobUrl ? (
                <img src={drawingBlobUrl} alt={`図面 ${d.part.drawingNo}`}
                  className="max-w-full max-h-full object-contain" />
              ) : (
                <p className="text-slate-400 text-sm text-center px-8">
                  図面を取得できませんでした<br />
                  <span className="text-xs text-slate-500">（RidocサーバーまたはRIDOC_API_URL未設定）</span>
                </p>
              )}
            </div>
          </div>
        </div>
      )}"""

if "drawingAuthOpen" not in page:
    if OLD_MODAL not in page:
        idx = page.find("Ridoc図面モーダル")
        print("DEBUG modal:", repr(page[idx:idx+200])); sys.exit(1)
    page = page.replace(OLD_MODAL, NEW_MODAL)
    print("OK page: modal replaced")
else:
    print("SKIP page: modal")

open(PAGE, "w", encoding="utf-8").write(page)
print("OK page written")

# ── 3. next build ──
print("\n--- next build ---")
r = subprocess.run(
    "export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -20",
    shell=True, capture_output=True, text=True)
print(r.stdout[-2000:])
if r.returncode != 0: print(r.stderr[-2000:]); sys.exit(1)
print("OK next build")

# ── 4. PM2 ──
print("\n--- pm2 restart api (RIDOC_API_URL反映) ---")
subprocess.run("export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && pm2 restart machcore-api", shell=True)
print("\n--- pm2 delete + start web ---")
subprocess.run(
    "export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && pm2 delete machcore-web; pm2 start /home/karkyon/projects/machcore/ecosystem.config.js --only machcore-web",
    shell=True)

# ── 5. git ──
print("\n--- git push ---")
subprocess.run(
    "cd /home/karkyon/projects/machcore && git add -A && "
    'git commit -m "feat: MC drawing viewer - auth check + blob display + RIDOC_API_URL" && git push',
    shell=True)
print("\nDONE")
