#!/usr/bin/env python3
"""
SCR-03 edit/page.tsx UI修正パッチ
修正内容:
  1. ヘッダー「← NC詳細」 → アイコン付き背景ボタン
  2. ナビタブ → セッション中は赤点滅ドット、非アクティブタブにロック表示
  3. ロック画面 → センター配置の大きなUI（データプレビュー50%透過付き）
"""
import re, sys, shutil
from pathlib import Path

TARGET = Path("/home/user/machcore/apps/web/app/nc/[nc_id]/edit/page.tsx")

if not TARGET.exists():
    # パスを探す
    for p in Path("/").rglob("page.tsx"):
        if "nc_id" in str(p) and "edit" in str(p) and ".bak" not in str(p):
            TARGET = p
            print(f"Found: {TARGET}")
            break

if not TARGET.exists():
    print("ERROR: edit/page.tsx が見つかりません")
    sys.exit(1)

shutil.copy(TARGET, str(TARGET) + ".bak_ui_patch")
print(f"Backup: {TARGET}.bak_ui_patch")

src = TARGET.read_text(encoding="utf-8")
original = src

# ============================================================
# 1. ヘッダーの「← NC詳細」ボタン強化
# ============================================================
OLD_BACK = '''          <button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="text-slate-400 hover:text-white text-xs transition-colors"
          >
            ← NC詳細
          </button>'''

NEW_BACK = '''          <button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            NC詳細に戻る
          </button>'''

if OLD_BACK in src:
    src = src.replace(OLD_BACK, NEW_BACK)
    print("OK: ← NC詳細 ボタン強化")
else:
    print("WARN: ← NC詳細 ボタンのパターンが見つかりません（手動確認要）")

# ============================================================
# 2. ナビタブ: セッション中は点滅ドット、非アクティブに説明追加
# ============================================================
# タブ配列の定義全体を置き換える
# 変更・登録タブが active: true のものを探す
OLD_TABS = '''        <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
          {([
            { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
            { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: true  },
            { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: false },
            { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: false },
          ] as { href: string; icon: string; label: string; active: boolean }[]).map(tab => (
            <button
              key={tab.href}
              onClick={() => router.push(tab.href)}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active
                  ? "border-sky-400 text-sky-300"
                  : "border-transparent text-slate-400 hover:text-white hover:border-slate-400"
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>'''

NEW_TABS = '''        <nav className="bg-slate-700 px-5 flex gap-0 shrink-0 border-t border-slate-600">
          {([
            { href: `/nc/${ncId}`,        label: "NC詳細",    active: false, lock: false },
            { href: `/nc/${ncId}/edit`,   label: "変更・登録", active: true,  lock: false },
            { href: `/nc/${ncId}/print`,  label: "段取シート", active: false, lock: true  },
            { href: `/nc/${ncId}/record`, label: "作業記録",  active: false, lock: true  },
          ] as { href: string; label: string; active: boolean; lock: boolean }[]).map(tab => (
            <button
              key={tab.href}
              onClick={() => router.push(tab.href)}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active
                  ? isAuthenticated
                    ? "border-red-400 text-red-300"
                    : "border-sky-400 text-sky-300"
                  : "border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-400"
              }`}
            >
              {tab.active && isAuthenticated && (
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              )}
              {!tab.active && tab.lock && (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-40">
                  <rect x="3" y="11" width="18" height="11" rx="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              )}
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>'''

if OLD_TABS in src:
    src = src.replace(OLD_TABS, NEW_TABS)
    print("OK: タブ点滅ドット・ロックアイコン追加")
else:
    print("WARN: タブのパターンが一致しません。部分置換を試みます...")
    # active: trueが変更・登録のケース
    pattern = r'(\{ href: `/nc/\$\{ncId\}/edit`,\s+icon: "[^"]+",\s+label: "[^"]+",\s+active: )(false|true)'
    if re.search(pattern, src):
        print("  → タブ配列は存在しますが構造が異なります（手動確認要）")
    else:
        print("  → タブナビゲーション自体が見つかりません")

# ============================================================
# 3. ロック画面を全面リデザイン
# ============================================================
OLD_LOCK = '''            {/* ロック状態バナー */}
            {!isAuthenticated && (
              <div className="mb-5 bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="text-amber-800 font-bold text-sm">🔒 編集にはWork Session認証が必要です</p>
                  <p className="text-amber-600 text-xs mt-0.5">担当者を選択してパスワードを入力してください</p>
                </div>
                <button
                  onClick={() => setAuthOpen(true)}
                  className="bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
                >
                  この作業を開始する
                </button>
              </div>
            )}'''

NEW_LOCK = '''            {/* ロック画面（認証前） */}
            {!isAuthenticated && (
              <div className="flex flex-col items-center justify-center py-10">
                <div className="bg-white rounded-2xl border-2 border-dashed border-slate-200 p-8 max-w-md w-full flex flex-col items-center gap-5 text-center">
                  {/* ロックアイコン */}
                  <div className="w-14 h-14 rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-800">変更・登録 — 作業開始前</h3>
                    <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                      変更・登録を行うには担当者の確認（パスワード）が必要です。
                    </p>
                  </div>
                  {/* 現在のデータプレビュー（50%透過） */}
                  <div className="w-full rounded-xl border border-slate-200 overflow-hidden opacity-50 pointer-events-none">
                    <div className="bg-slate-700 text-slate-300 text-[10px] font-bold px-3 py-1.5 tracking-wide uppercase">
                      現在のデータ
                    </div>
                    <div className="grid grid-cols-3 divide-x divide-slate-100">
                      <div className="p-2.5">
                        <div className="text-[10px] text-slate-400">機械</div>
                        <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">{d.machineName ?? "—"}</div>
                      </div>
                      <div className="p-2.5">
                        <div className="text-[10px] text-slate-400">ファイル名</div>
                        <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">{d.fileName ?? "—"}</div>
                      </div>
                      <div className="p-2.5">
                        <div className="text-[10px] text-slate-400">加工時間</div>
                        <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">{d.machiningTime != null ? `${d.machiningTime} 分` : "—"}</div>
                      </div>
                    </div>
                    {d.clampNote && (
                      <div className="p-2.5 border-t border-slate-100">
                        <div className="text-[10px] text-slate-400">備考</div>
                        <div className="text-xs text-slate-600 mt-0.5 line-clamp-2">{d.clampNote}</div>
                      </div>
                    )}
                  </div>
                  {/* 開始ボタン */}
                  <button
                    onClick={() => setAuthOpen(true)}
                    className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-700 text-white px-5 py-3 rounded-xl text-sm font-bold transition-colors"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <rect x="3" y="11" width="18" height="11" rx="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    この作業を開始する（担当者確認）
                  </button>
                  <p className="text-xs text-slate-400">担当者の選択とパスワード確認後に編集できます</p>
                </div>
              </div>
            )}'''

if OLD_LOCK in src:
    src = src.replace(OLD_LOCK, NEW_LOCK)
    print("OK: ロック画面をセンター配置に全面リデザイン")
else:
    print("WARN: ロック画面のパターンが一致しません（手動確認要）")

# ============================================================
# 認証後はフォームを表示、認証前はフォームを非表示にする
# フォームの冒頭の opacity-50 クラス維持（既存の仕組み）
# ============================================================

if src != original:
    TARGET.write_text(src, encoding="utf-8")
    print(f"\n✅ edit/page.tsx を更新しました: {TARGET}")
else:
    print("\n⚠ 変更がありません。パターンを確認してください。")
