#!/usr/bin/env python3
# coding: utf-8
"""
fix_v30.py — 段取シートバックSTEP1/2 UI修正
  1. edit/page.tsx: 赤いセッションバナー削除, 青バナーにキャンセルボタン追加
  2. record/page.tsx: sbMode時タブ全無効化, 作業開始前パネル非表示, STEP2バナー追加,
                      作業記録登録完了後に collectSetupSheet 自動コール
  3. page.tsx (dashboard): STEP1認証成功時に sb_sheet_log_id も sessionStorage に保存
  4. lib/api.ts: mcApi.collectSetupSheet 追加
"""
import pathlib, subprocess, sys, re

ROOT = "/home/karkyon/projects/machcore"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    src = p.read_text(encoding="utf-8")
    if old in src:
        src = src.replace(old, new, 1)
        p.write_text(src, encoding="utf-8")
        print(f"OK: {label}")
    else:
        print(f"WARN: {label} — パターン不一致")

# ─────────────────────────────────────────────────────────────
# 1. lib/api.ts: mcApi に collectSetupSheet 追加
# ─────────────────────────────────────────────────────────────
apply(
    ROOT + "/apps/web/lib/api.ts",
    "  createTimecard:  (body: any, token: string) =>\n    api.post('/mc/timecards', body, { headers: { Authorization: `Bearer ${token}` } }),\n};",
    """  createTimecard:  (body: any, token: string) =>
    api.post('/mc/timecards', body, { headers: { Authorization: `Bearer ${token}` } }),
  collectSetupSheet: (mcId: number, logId: number, token: string) =>
    api.put(`/mc/${mcId}/setup-sheet-logs/${logId}/collect`, {}, { headers: { Authorization: `Bearer ${token}` } }),
};""",
    "api.ts: mcApi.collectSetupSheet 追加"
)

# ─────────────────────────────────────────────────────────────
# 2. page.tsx (dashboard): STEP1認証成功時に sb_sheet_log_id 保存
# ─────────────────────────────────────────────────────────────
apply(
    ROOT + "/apps/web/app/page.tsx",
    """          onSuccess={() => {
            setSbStep1AuthOpen(false);
            if (typeof window !== "undefined") {
              sessionStorage.setItem("sb_next_record", String(sbStep1McId));
            }
            router.push(`/mc/${sbStep1McId}/edit`);
          }}""",
    """          onSuccess={() => {
            setSbStep1AuthOpen(false);
            if (typeof window !== "undefined") {
              sessionStorage.setItem("sb_next_record", String(sbStep1McId));
              // sbSelectedSheet.id (log_id) を保存 — STEP2完了時のcollect用
              const sheetId = sbSelectedSheet?.id ?? 0;
              sessionStorage.setItem("sb_sheet_log_id", String(sheetId));
            }
            router.push(`/mc/${sbStep1McId}/edit`);
          }}""",
    "page.tsx: sb_sheet_log_id を sessionStorage に保存"
)

# ─────────────────────────────────────────────────────────────
# 3. edit/page.tsx: 赤いセッションバナー削除 + 青バナーにキャンセルボタン追加
# ─────────────────────────────────────────────────────────────

# 3a. 青バナーにキャンセルボタン追加（STEP1完了ボタンの後に追加）
apply(
    ROOT + "/apps/web/app/mc/[mc_id]/edit/page.tsx",
    """          <button onClick={handleSave} disabled={saving}
            className="bg-white text-blue-700 px-4 py-1 rounded font-bold hover:bg-blue-50 disabled:opacity-50 text-sm">
            {saving ? "保存中..." : "STEP1完了 → STEP2(作業記録)へ"}
          </button>
        </div>
      )}
      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => {
                logout();
                if (sbMode && typeof window !== "undefined") {
                  sessionStorage.removeItem("sb_next_record");
                  router.push("/");
                } else {
                  router.push(`/mc/${mcId}`);
                }
              }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : sbMode ?""",
    """          <div className="flex items-center gap-2">
            <button onClick={() => {
                logout();
                if (typeof window !== "undefined") {
                  sessionStorage.removeItem("sb_next_record");
                  sessionStorage.removeItem("sb_sheet_log_id");
                }
                router.push("/");
              }}
              className="text-blue-200 hover:text-white text-xs px-3 py-1 rounded border border-blue-400 hover:border-white transition-colors">
              キャンセル（中断）
            </button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-blue-700 px-4 py-1 rounded font-bold hover:bg-blue-50 disabled:opacity-50 text-sm">
              {saving ? "保存中..." : "STEP1完了 → STEP2(作業記録)へ"}
            </button>
          </div>
        </div>
      )}
      {isAuthenticated && operator && !sbMode && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => {
                logout();
                router.push(`/mc/${mcId}`);
              }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : sbMode ?""",
    "edit/page.tsx: 赤バナーsbMode時非表示 + 青バナーキャンセルボタン追加"
)

# ─────────────────────────────────────────────────────────────
# 4. record/page.tsx の修正
# ─────────────────────────────────────────────────────────────
rec_path = ROOT + "/apps/web/app/mc/[mc_id]/record/page.tsx"
src = pathlib.Path(rec_path).read_text(encoding="utf-8")

# 4a. sbMode state に sb_sheet_log_id 読み込みを追加
OLD_SB_STATE = """  const [sbMode, setSbMode] = React.useState(false);
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v) setSbMode(parseInt(v) === mcId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);"""

NEW_SB_STATE = """  const [sbMode, setSbMode] = React.useState(false);
  const [sbSheetLogId, setSbSheetLogId] = React.useState<number>(0);
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === mcId) {
        setSbMode(true);
        const lid = sessionStorage.getItem("sb_sheet_log_id");
        if (lid) setSbSheetLogId(parseInt(lid));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);"""

if OLD_SB_STATE in src:
    src = src.replace(OLD_SB_STATE, NEW_SB_STATE, 1)
    print("OK: record/page.tsx: sbSheetLogId state追加")
else:
    print("WARN: record sbMode state パターン不一致")

# 4b. タブ: 段取シートタブのsbMode無効化（既にMC詳細・変更登録はsbMode無効、段取シートは未対応）
OLD_PRINT_TAB = """        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ?"""

NEW_PRINT_TAB = """        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ?"""

if OLD_PRINT_TAB in src:
    src = src.replace(OLD_PRINT_TAB, NEW_PRINT_TAB, 1)
    print("OK: record/page.tsx: 段取シートタブ sbMode無効化")
else:
    print("WARN: record 段取シートタブ パターン不一致")

# 4c. ヘッダーの「ダッシュボードへ」ボタン: sbMode時も非表示（!sbMode条件が未対応）
OLD_DASH_BTN = """            <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
              ダッシュボードへ
            </button>"""

NEW_DASH_BTN = """            {!sbMode && (
              <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
                ダッシュボードへ
              </button>
            )}"""

if OLD_DASH_BTN in src:
    src = src.replace(OLD_DASH_BTN, NEW_DASH_BTN, 1)
    print("OK: record/page.tsx: ダッシュボードボタン sbMode時非表示")
else:
    print("WARN: record ダッシュボードボタン パターン不一致")

# 4d. sbMode時にSTEP2バナーをタブナビ直下に追加（既存tealバナーはヘッダー内）
# ヘッダーのsbModeバナー後に追加
OLD_TEAL_BANNER = """        {sbMode && (
          <span className="flex items-center gap-2 bg-teal-700 border border-teal-500 rounded-lg px-3 py-1">
            <span className="bg-teal-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span className="text-xs font-bold text-teal-100">段取シートバック — STEP2: 作業記録入力</span>
            <span className="text-teal-400 text-xs">（登録で完了）</span>
          </span>
        )}"""

NEW_TEAL_BANNER = """        {sbMode && (
          <span className="flex items-center gap-2 bg-teal-700 border border-teal-500 rounded-lg px-3 py-1">
            <span className="bg-teal-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span className="text-xs font-bold text-teal-100">段取シートバック — STEP2: 作業記録入力</span>
            <span className="text-teal-400 text-xs">（登録で完了・回収済みになります）</span>
          </span>
        )}"""

if OLD_TEAL_BANNER in src:
    src = src.replace(OLD_TEAL_BANNER, NEW_TEAL_BANNER, 1)
    print("OK: record/page.tsx: STEP2バナー更新")
else:
    print("WARN: record STEP2バナー パターン不一致")

# 4e. sbMode時は「作業開始前」パネルを非表示 → 直接フォーム表示
OLD_AUTH_PANEL = """          {!isAuthenticated && (
            <div className="mb-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-teal-600 mt-0.5">
                  {selectedSheet ? `段取シート（${new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP")}）を選択中` : "左リストから段取シートを選択してください"}
                </div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                この作業を開始する
              </button>
            </div>
          )}"""

NEW_AUTH_PANEL = """          {!isAuthenticated && !sbMode && (
            <div className="mb-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-teal-600 mt-0.5">
                  {selectedSheet ? `段取シート（${new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP")}）を選択中` : "左リストから段取シートを選択してください"}
                </div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                この作業を開始する
              </button>
            </div>
          )}"""

if OLD_AUTH_PANEL in src:
    src = src.replace(OLD_AUTH_PANEL, NEW_AUTH_PANEL, 1)
    print("OK: record/page.tsx: 作業開始前パネル sbMode時非表示")
else:
    print("WARN: record 作業開始前パネル パターン不一致")

# 4f. フォーム disabled条件: sbMode時は isAuthenticated=false でも入力可能
OLD_FORM_DIS = """          <div className={!isAuthenticated ? "opacity-40 pointer-events-none select-none" : ""}>"""
NEW_FORM_DIS = """          <div className={!isAuthenticated && !sbMode ? "opacity-40 pointer-events-none select-none" : ""}>"""

if OLD_FORM_DIS in src:
    src = src.replace(OLD_FORM_DIS, NEW_FORM_DIS, 1)
    print("OK: record/page.tsx: フォームdisabled sbMode時スキップ")
else:
    print("WARN: record フォームdisabled パターン不一致")

# 4g. 作業記録登録完了後 → collectSetupSheet 自動コール + sessionStorage削除 + ダッシュボードへ
OLD_COMPLETE = """      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          sessionStorage.removeItem("sb_next_record");
          setTimeout(() => router.push("/"), 1200);
        }
      }"""

NEW_COMPLETE = """      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          // STEP2完了 → setup_sheet_log を回収済み(work_collected=true)に更新
          const logId = sbSheetLogId || parseInt(sessionStorage.getItem("sb_sheet_log_id") ?? "0");
          if (logId && token) {
            try {
              await mcApi.collectSetupSheet(mcId, logId, token);
              showToast("✅ 段取シートバック完了 — 回収済みに更新しました");
            } catch { showToast("⚠️ 作業記録登録済み（回収済み更新に失敗しました）"); }
          }
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          setTimeout(() => router.push("/"), 1500);
        }
      }"""

if OLD_COMPLETE in src:
    src = src.replace(OLD_COMPLETE, NEW_COMPLETE, 1)
    print("OK: record/page.tsx: STEP2完了後 collectSetupSheet自動コール")
else:
    print("WARN: record STEP2完了処理 パターン不一致")

pathlib.Path(rec_path).write_text(src, encoding="utf-8")
print("OK: record/page.tsx 書き込み完了")

# ─────────────────────────────────────────────────────────────
# Build & start
# ─────────────────────────────────────────────────────────────
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart ---")
r2 = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && source \"$NVM_DIR/nvm.sh\" && "
    "cd /home/karkyon/projects/machcore && "
    "pm2 delete machcore-web && "
    "pm2 start ecosystem.config.js --only machcore-web",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout)
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-1000:])
    sys.exit(1)

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'feat: sbMode STEP1青バナーのみ(赤削除+キャンセルボタン)/STEP2タブ全無効+作業開始前パネル非表示+collectSheet自動完了 v30' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])

print("\nDONE")