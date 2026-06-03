#!/usr/bin/env python3
"""
fix_drawing_v3.py
RIDOC図面モーダル完全修正:
1. drawingAuthOpen用AuthModal描画を追加（既存authOpenとは別）
2. モーダル内表示をdrawingBlobUrl blob表示に修正
3. next build + pm2 restart + git push
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
NVM  = "export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && "

page = open(PAGE, encoding="utf-8").read()

# ── 1. drawingAuthOpen 用 AuthModal 追加
#    既存の「{/* 認証モーダル */}」の直後に挿入
print("=== [1] drawingAuthOpen AuthModal 追加 ===")

ANCHOR_AUTH = """{/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType={authType}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}"""

INSERT_AFTER = """{/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType={authType}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}

      {/* 📋 Ridoc図面 認証モーダル */}
      {drawingAuthOpen && (
        <AuthModal isOpen={true} mcProgramId={mcId} sessionType="edit"
          onSuccess={async () => {
            setDrawingAuthOpen(false);
            setDrawingModal(true);
            setDrawingLoading(true);
            try {
              const t = localStorage.getItem("work_token") ?? "";
              const res = await fetch(`/api/mc/${mcId}/drawing-image?imgType=ORG`, {
                headers: t ? { Authorization: `Bearer ${t}` } : {},
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const blob = await res.blob();
              setDrawingBlobUrl(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
            } catch { setDrawingBlobUrl(null); }
            finally { setDrawingLoading(false); }
          }}
          onCancel={() => setDrawingAuthOpen(false)} />
      )}"""

if "drawingAuthOpen" in page and "Ridoc図面 認証モーダル" not in page:
    if ANCHOR_AUTH not in page:
        print("  ⚠️  認証モーダルアンカーが見つからない")
        idx = page.find("authOpen &&")
        print(f"  DEBUG: {repr(page[max(0,idx-20):idx+120])}")
        sys.exit(1)
    page = page.replace(ANCHOR_AUTH, INSERT_AFTER)
    print("  OK: drawingAuthOpen AuthModal 追加")
elif "Ridoc図面 認証モーダル" in page:
    print("  SKIP: 既に存在")
else:
    print("  ⚠️  drawingAuthOpen state が見つからない")
    sys.exit(1)

# ── 2. 図面モーダル本体をblob表示に修正
print("\n=== [2] 図面モーダル本体 blob表示修正 ===")

OLD_MODAL_BODY = """            <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center">
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
            </div>"""

NEW_MODAL_BODY = """            <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center">
              {drawingLoading ? (
                <div className="flex flex-col items-center gap-3 text-slate-400">
                  <div className="w-8 h-8 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
                  <span className="text-sm">図面を取得中…</span>
                </div>
              ) : drawingBlobUrl ? (
                <img src={drawingBlobUrl} alt={`図面 ${d.part.drawingNo}`}
                  className="max-w-full max-h-full object-contain" />
              ) : (
                <p className="text-slate-400 text-sm text-center px-8">
                  図面を取得できませんでした<br />
                  <span className="text-xs text-slate-500">（Ridocサーバー未応答またはRIDOC_API_URL未設定）</span>
                </p>
              )}
            </div>"""

if OLD_MODAL_BODY in page:
    page = page.replace(OLD_MODAL_BODY, NEW_MODAL_BODY)
    print("  OK: モーダル本体をblob表示に更新")
elif "drawingBlobUrl ? (" in page:
    print("  SKIP: 既にblob表示済み")
else:
    print("  ⚠️  モーダル本体アンカー見つからない")
    idx = page.find("Ridoc図面モーダル")
    print(f"  DEBUG: {repr(page[idx:idx+400])}")
    sys.exit(1)

# ── 3. モーダルヘッダーの「新規タブで開く」を削除（blobダウンロードボタンに変更）
print("\n=== [3] モーダルヘッダー ダウンロードボタン修正 ===")

OLD_HEADER_BTN = """                <a href={`/api/mc/${mcId}/drawing-image?imgType=ORG`} target="_blank" rel="noopener noreferrer"
                  className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                  🔍 原寸を新規タブで開く
                </a>"""

NEW_HEADER_BTN = """                {drawingBlobUrl && (
                  <a href={drawingBlobUrl} download={`drawing-${d.part.drawingNo}.jpg`}
                    className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                    ⬇ ダウンロード
                  </a>
                )}"""

if OLD_HEADER_BTN in page:
    page = page.replace(OLD_HEADER_BTN, NEW_HEADER_BTN)
    print("  OK: ヘッダーボタンをダウンロードに変更")
elif "drawingBlobUrl && (" in page and "download={" in page:
    print("  SKIP: 既に修正済み")
else:
    # ボタン変更は任意なのでスキップ扱い
    print("  SKIP: アンカー見つからず（スキップ可）")

# ── 4. カードクリック時にも fetchを実行（認証済み時）──
#    既存のonClickは認証済みの場合にfetchしてblobUrlをセットするが
#    tokenではなくlocalStorageから直接取る（AuthContextのtokenがnullの場合の保険）
print("\n=== [4] カードクリック localStorage fallback 確認 ===")
if "localStorage.getItem" in page or "headers: token ?" in page:
    print("  OK: fetch実装済み")
else:
    print("  ⚠️  fetch未実装（要確認）")

# ── 書き込み ──
open(PAGE, "w", encoding="utf-8").write(page)
print("\n=== page.tsx 書き込み完了 ===")

# ── 5. next build ──
print("\n=== [5] next build ===")
r = subprocess.run(
    f"{NVM}cd {BASE}/apps/web && npx next build 2>&1 | tail -20",
    shell=True, capture_output=True, text=True
)
out = r.stdout[-2000:]
print(out)
if r.returncode != 0 or "Type error" in out or "Failed to compile" in out:
    print(r.stderr[-1000:])
    sys.exit(1)
print("OK: next build")

# ── 6. pm2 restart web ──
print("\n=== [6] pm2 restart web ===")
subprocess.run(
    f"{NVM}pm2 delete machcore-web; pm2 start {BASE}/ecosystem.config.js --only machcore-web",
    shell=True
)

# ── 7. git push ──
print("\n=== [7] git push ===")
subprocess.run(
    f"cd {BASE} && git add -A && "
    "git commit -m 'fix: drawing modal - drawingAuthOpen AuthModal + blob display' && "
    "git push",
    shell=True
)
print("\n=== DONE ===")
