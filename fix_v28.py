#!/usr/bin/env python3
# coding: utf-8
import pathlib

BASE = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app")

# ─────────────────────────────────────────────────────────────
# 1. page.tsx: モーダルの「回収済みにする」ボタン削除
# ─────────────────────────────────────────────────────────────
root = BASE / "page.tsx"
src = root.read_text(encoding="utf-8")

OLD_COLLECT_BTN = '''                    <button
                      onClick={() => setSbAuthOpen(true)}
                      disabled={sbCollecting}
                      className="w-full py-2 border-2 border-teal-600 text-teal-700 hover:bg-teal-50 text-sm font-bold rounded-xl transition-colors disabled:opacity-40">
                      {sbCollecting ? "回収処理中..." : "✓ このシートを回収済みにする"}
                    </button>'''

if OLD_COLLECT_BTN in src:
    src = src.replace(OLD_COLLECT_BTN, "")
    print("OK: page.tsx 回収済みボタン削除")
else:
    print("WARN: page.tsx 回収ボタンパターン不一致")

root.write_text(src, encoding="utf-8")
print("OK: page.tsx 書き込み完了")

# ─────────────────────────────────────────────────────────────
# 2. edit/page.tsx
#    - sbMode state 追加（useEffect でmount時に sessionStorage 確認）
#    - ヘッダー: sbMode時はバナー表示、ナビボタン非表示
#    - タブナビ: sbMode時は変更・登録以外を disabled/opacity
#    - セッションバナーのキャンセル: sbMode時は sessionStorage削除→/へ
# ─────────────────────────────────────────────────────────────
edit = BASE / "mc" / "[mc_id]" / "edit" / "page.tsx"
esrc = edit.read_text(encoding="utf-8")

# (a) sbMode state + useEffect 追加
# useParams の後に追加
OLD_PARAMS = "  const { mc_id } = useParams<{ mc_id: string }>();\n  const mcId  = parseInt(mc_id);\n  const router = useRouter();"
NEW_PARAMS = """  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();
  const [sbMode, setSbMode] = React.useState(false);
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === parseInt(mc_id)) setSbMode(true);
    }
  }, [mc_id]);"""

if OLD_PARAMS in esrc:
    esrc = esrc.replace(OLD_PARAMS, NEW_PARAMS)
    print("OK: edit sbMode state追加")
else:
    print("WARN: edit params パターン不一致")

# React import確認・追加
if '"react"' in esrc or "'react'" in esrc:
    if 'import React' not in esrc:
        esrc = esrc.replace('import {', 'import React, {', 1)
        print("OK: edit React import追加")
    else:
        print("INFO: edit React import既存")

# (b) ヘッダーのナビボタン: sbMode時非表示 → STEPバナー置換
OLD_HEADER_BTNS = '''        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium text-white">MC 詳細</span>
        <span className="ml-auto flex items-center gap-3">
          <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            ダッシュボードへ
          </button>
          <button onClick={() => router.push("/mc/search")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 rounded-lg text-xs font-bold text-white transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            部品検索へ戻る
          </button>'''
NEW_HEADER_BTNS = '''        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium text-white">MC 詳細</span>
        {sbMode && (
          <span className="ml-2 flex items-center gap-2 bg-blue-700 border border-blue-500 rounded-lg px-3 py-1">
            <span className="bg-blue-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">1</span>
            <span className="text-xs font-bold text-blue-100">段取シートバック — STEP1: マシニング情報登録</span>
            <span className="text-blue-400 text-xs">→ 完了後 STEP2 作業記録へ自動遷移</span>
          </span>
        )}
        <span className="ml-auto flex items-center gap-3">
          {!sbMode && (
            <>
              <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
                ダッシュボードへ
              </button>
              <button onClick={() => router.push("/mc/search")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 rounded-lg text-xs font-bold text-white transition-colors">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
                部品検索へ戻る
              </button>
            </>
          )}'''

if OLD_HEADER_BTNS in esrc:
    esrc = esrc.replace(OLD_HEADER_BTNS, NEW_HEADER_BTNS)
    print("OK: edit ヘッダーバナー追加")
else:
    print("WARN: edit ヘッダーパターン不一致")

# (c) タブナビ: sbMode時は変更・登録以外 disabled
OLD_TAB_MC = '''        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-1.5 text-[12'''
NEW_TAB_MC = '''        <button onClick={() => !sbMode && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 rounded-t-md transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/record`)}
          className={"px-4 py-1.5 text-[12'''

if OLD_TAB_MC in esrc:
    esrc = esrc.replace(OLD_TAB_MC, NEW_TAB_MC)
    print("OK: edit タブ無効化")
else:
    print("WARN: edit タブパターン不一致")

# 作業記録タブ末尾も無効化（className部分）
OLD_RECORD_TAB_CLS = '''          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録'''
NEW_RECORD_TAB_CLS = '''          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録'''

if OLD_RECORD_TAB_CLS in esrc:
    esrc = esrc.replace(OLD_RECORD_TAB_CLS, NEW_RECORD_TAB_CLS)
    print("OK: edit 作業記録タブ無効化")
else:
    print("WARN: edit 作業記録タブパターン不一致")

# (d) セッションバナーのキャンセル: sbMode時はsessionStorage削除→/へ
OLD_CANCEL = '''            <button onClick={() => { logout(); router.push(`/mc/${mcId}`); }}
              className="text-red-200 hover:text-white">キャンセル</button>'''
NEW_CANCEL = '''            <button onClick={() => {
                logout();
                if (sbMode && typeof window !== "undefined") {
                  sessionStorage.removeItem("sb_next_record");
                  router.push("/");
                } else {
                  router.push(`/mc/${mcId}`);
                }
              }}
              className="text-red-200 hover:text-white">キャンセル</button>'''

if OLD_CANCEL in esrc:
    esrc = esrc.replace(OLD_CANCEL, NEW_CANCEL)
    print("OK: edit キャンセル処理修正")
else:
    print("WARN: edit キャンセルパターン不一致")

edit.write_text(esrc, encoding="utf-8")
print("OK: edit/page.tsx 書き込み完了")

# ─────────────────────────────────────────────────────────────
# 3. record/page.tsx
#    - sbMode state 追加
#    - ヘッダー: sbMode時バナー表示・MC詳細/ダッシュボードボタン非表示
#    - タブナビ: MC詳細・MC詳細へ戻るなど無効化
#    - 登録完了後: sbMode時 sessionStorage削除→/へ
# ─────────────────────────────────────────────────────────────
rec = BASE / "mc" / "[mc_id]" / "record" / "page.tsx"
rsrc = rec.read_text(encoding="utf-8")

# React import確認
if 'import React' not in rsrc:
    rsrc = rsrc.replace('import {', 'import React, {', 1)
    print("OK: record React import追加")

# sbMode state追加: useParams後
OLD_REC_PARAMS = "  const { mc_id } = useParams<{ mc_id: string }>();\n  const mcId  = parseInt(mc_id);\n  const router = useRouter();"
NEW_REC_PARAMS = """  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();
  const [sbMode, setSbMode] = React.useState(false);
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === parseInt(mc_id)) setSbMode(true);
    }
  }, [mc_id]);"""

if OLD_REC_PARAMS in rsrc:
    rsrc = rsrc.replace(OLD_REC_PARAMS, NEW_REC_PARAMS)
    print("OK: record sbMode state追加")
else:
    print("WARN: record params パターン不一致")

# ヘッダー: MC詳細ボタン・ダッシュボードボタン → sbMode時非表示
OLD_REC_HEADER = '''        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          ダッシュボードへ
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">作業記録</span>'''
NEW_REC_HEADER = '''        {!sbMode && (
          <>
            <button onClick={() => router.push(`/mc/${mcId}`)}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
              <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
              </span>
              MC詳細
            </button>
            <span className="text-slate-600">|</span>
            <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
              ダッシュボードへ
            </button>
          </>
        )}
        {sbMode && (
          <span className="flex items-center gap-2 bg-teal-700 border border-teal-500 rounded-lg px-3 py-1">
            <span className="bg-teal-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span className="text-xs font-bold text-teal-100">段取シートバック — STEP2: 作業記録入力</span>
            <span className="text-teal-400 text-xs">（登録で完了）</span>
          </span>
        )}
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">作業記録</span>'''

if OLD_REC_HEADER in rsrc:
    rsrc = rsrc.replace(OLD_REC_HEADER, NEW_REC_HEADER)
    print("OK: record ヘッダーバナー追加")
else:
    print("WARN: record ヘッダーパターン不一致")

# タブナビ: MC詳細ボタン無効化
OLD_REC_TAB = '''        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}'''
NEW_REC_TAB = '''        <button onClick={() => !sbMode && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/edit`)}'''

if OLD_REC_TAB in rsrc:
    rsrc = rsrc.replace(OLD_REC_TAB, NEW_REC_TAB)
    print("OK: record タブMC詳細無効化")
else:
    print("WARN: record タブパターン不一致")

# 変更・登録タブ無効化
OLD_REC_EDIT_TAB = '''          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録'''
NEW_REC_EDIT_TAB = '''          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録'''

if OLD_REC_EDIT_TAB in rsrc:
    rsrc = rsrc.replace(OLD_REC_EDIT_TAB, NEW_REC_EDIT_TAB)
    print("OK: record 変更登録タブ無効化")
else:
    print("WARN: record 変更登録タブパターン不一致")

# 段取シートタブも無効化
OLD_REC_PRINT_TAB = '''          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート'''
NEW_REC_PRINT_TAB = '''          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート'''

if OLD_REC_PRINT_TAB in rsrc:
    rsrc = rsrc.replace(OLD_REC_PRINT_TAB, NEW_REC_PRINT_TAB)
    print("OK: record 段取シートタブ無効化")
else:
    print("WARN: record 段取シートタブパターン不一致")

# 登録完了後: sbMode時 sessionStorage削除→/へ
OLD_REC_TOAST = '''      showToast("✅ 作業記録を登録しました");'''
NEW_REC_TOAST = '''      showToast("✅ 作業記録を登録しました");
      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          sessionStorage.removeItem("sb_next_record");
          setTimeout(() => router.push("/"), 1200);
        }
      }'''

if OLD_REC_TOAST in rsrc:
    rsrc = rsrc.replace(OLD_REC_TOAST, NEW_REC_TOAST)
    print("OK: record 登録完了後ダッシュボード遷移")
else:
    print("WARN: record toast パターン不一致")

# キャンセルボタンもsbMode時はsessionStorage削除せずに/へ（STEP1完了状態保持のため削除しない）
OLD_REC_CANCEL = '''                <button onClick={() => { logout(); router.push(`/mc/${mcId}`); }}
                  className="px-6 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
                  ✕ キャンセル
                </button>'''
NEW_REC_CANCEL = '''                <button onClick={() => {
                    logout();
                    if (sbMode) {
                      router.push("/");
                    } else {
                      router.push(`/mc/${mcId}`);
                    }
                  }}
                  className="px-6 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
                  {sbMode ? "中断（ダッシュボードへ）" : "✕ キャンセル"}
                </button>'''

if OLD_REC_CANCEL in rsrc:
    rsrc = rsrc.replace(OLD_REC_CANCEL, NEW_REC_CANCEL)
    print("OK: record キャンセル処理修正")
else:
    print("WARN: record キャンセルパターン不一致")

rec.write_text(rsrc, encoding="utf-8")
print("OK: record/page.tsx 書き込み完了")

print("\n全処理完了")