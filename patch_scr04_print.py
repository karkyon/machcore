#!/usr/bin/env python3
"""
SCR-04 print/page.tsx UI修正パッチ
修正内容:
  1. ヘッダー「← NC詳細」 → アイコン付き背景ボタン
  2. ナビタブ → セッション中はアンバー点滅ドット、非アクティブタブにロック表示
  3. ロック画面 → センター配置の大きなUI（段取シートプレビュー50%透過付き）
"""
import sys, shutil
from pathlib import Path

TARGET = Path("/home/user/machcore/apps/web/app/nc/[nc_id]/print/page.tsx")

if not TARGET.exists():
    for p in Path("/").rglob("page.tsx"):
        if "nc_id" in str(p) and "print" in str(p) and ".bak" not in str(p):
            TARGET = p
            print(f"Found: {TARGET}")
            break

if not TARGET.exists():
    print("ERROR: print/page.tsx が見つかりません")
    sys.exit(1)

shutil.copy(TARGET, str(TARGET) + ".bak_ui_patch")
print(f"Backup: {TARGET}.bak_ui_patch")

src = TARGET.read_text(encoding="utf-8")
original = src

# ============================================================
# 1. ヘッダーの「← NC詳細」ボタン強化
# ============================================================
# print/page.tsx のヘッダーbackボタンを探す（複数パターン対応）
patterns_back = [
    # パターンA
    (
        '          <button\n            onClick={() => router.push(`/nc/${ncId}`)}\n            className="text-slate-400 hover:text-white text-xs transition-colors"\n          >\n            ← NC詳細\n          </button>',
        '          <button\n            onClick={() => router.push(`/nc/${ncId}`)}\n            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"\n          >\n            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">\n              <path d="M19 12H5M12 5l-7 7 7 7"/>\n            </svg>\n            NC詳細に戻る\n          </button>'
    ),
    # パターンB（インデント違い）
    (
        '        <button\n          onClick={() => router.push(`/nc/${ncId}`)}\n          className="text-slate-400 hover:text-white text-xs transition-colors"\n        >\n          ← NC詳細\n        </button>',
        '        <button\n          onClick={() => router.push(`/nc/${ncId}`)}\n          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"\n        >\n          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">\n            <path d="M19 12H5M12 5l-7 7 7 7"/>\n          </svg>\n          NC詳細に戻る\n        </button>'
    ),
]

back_replaced = False
for old, new in patterns_back:
    if old in src:
        src = src.replace(old, new)
        back_replaced = True
        print("OK: ← NC詳細 ボタン強化")
        break

if not back_replaced:
    # 正規表現で汎用パターンマッチ
    import re
    pattern = r'(<button[^>]*\n[^>]*onClick=\{[^}]*router\.push\(`/nc/\$\{ncId\}`\)[^}]*\}[^>]*\n[^>]*className="text-slate-400[^"]*"[^>]*>\s*← NC詳細\s*</button>)'
    m = re.search(pattern, src, re.DOTALL)
    if m:
        new_btn = '''<button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            NC詳細に戻る
          </button>'''
        src = src[:m.start()] + new_btn + src[m.end():]
        print("OK: ← NC詳細 ボタン強化（正規表現マッチ）")
    else:
        print("WARN: ← NC詳細 ボタンのパターンが見つかりません")

# ============================================================
# 2. ナビタブ: 段取シートタブ active=true, アンバー点滅ドット
# ============================================================
OLD_TABS = '''      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {([
          { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
          { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
          { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: true  },
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

NEW_TABS = '''      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0 border-t border-slate-600">
        {([
          { href: `/nc/${ncId}`,        label: "NC詳細",    active: false, lock: false },
          { href: `/nc/${ncId}/edit`,   label: "変更・登録", active: false, lock: true  },
          { href: `/nc/${ncId}/print`,  label: "段取シート", active: true,  lock: false },
          { href: `/nc/${ncId}/record`, label: "作業記録",  active: false, lock: true  },
        ] as { href: string; label: string; active: boolean; lock: boolean }[]).map(tab => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              tab.active
                ? isAuthenticated
                  ? "border-amber-400 text-amber-300"
                  : "border-sky-400 text-sky-300"
                : "border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-400"
            }`}
          >
            {tab.active && isAuthenticated && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
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
    print("WARN: タブのパターンが一致しません（手動確認要）")

# ============================================================
# 3. ロック画面を全面リデザイン
# ============================================================
OLD_LOCK = '''          {/* ── ロック状態 ── */}
          {!isAuthenticated && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-lg w-full">
                <div className="text-center mb-6">
                  <div className="text-5xl mb-3">🖨</div>
                  <h2 class'''

# 終端を見つけてブロック全体を置換する
if '          {/* ── ロック状態 ── */}\n          {!isAuthenticated && (' in src:
    # ブロック開始位置を見つける
    start_marker = '          {/* ── ロック状態 ── */}\n          {!isAuthenticated && ('
    end_marker_candidates = [
            '\n\n          {/* ── セッションバナー（認証後） ── */}',
            '\n\n          {/* ── エラー表示 ── */}',
            '\n\n          {/* エラー表示 */}',
    ]
    start_idx = src.find(start_marker)
    if start_idx >= 0:
        # 閉じ括弧の位置を見つける（バランスカウント）
        search_from = start_idx + len(start_marker)
        depth = 1
        i = search_from
        while i < len(src) and depth > 0:
            if src[i] == '(':
                depth += 1
            elif src[i] == ')':
                depth -= 1
            i += 1
        # i は閉じ括弧の次
        # )} の後の改行まで
        end_idx = src.find('\n', i) + 1
        
        NEW_LOCK_PRINT = '''          {/* ── ロック画面（認証前） ── */}
          {!isAuthenticated && (
            <div className="flex flex-col items-center justify-center py-10">
              <div className="bg-white rounded-2xl border-2 border-dashed border-slate-200 p-8 max-w-md w-full flex flex-col items-center gap-5 text-center">
                {/* ロックアイコン */}
                <div className="w-14 h-14 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#b45309" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 2v6l3 3-3 3v6h12v-6l-3-3 3-3V2z"/>
                    <path d="M6 8h12M6 16h12"/>
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800">段取シート — 作業開始前</h3>
                  <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                    段取シートの印刷・NCプログラムのUSB書き出しを行うには担当者の確認が必要です。
                  </p>
                </div>
                {/* 段取シートプレビュー（50%透過） */}
                {nc && (
                  <div className="w-full rounded-xl border border-slate-200 overflow-hidden opacity-45 pointer-events-none text-xs">
                    <div className="bg-slate-800 text-white px-3 py-2 font-bold text-left">
                      旋盤 段取シート — {nc.part.name}
                    </div>
                    <div className="p-3 space-y-1 text-left text-slate-700">
                      <div>機械: {nc.machineName ?? "—"} ｜ {nc.fileName ?? "—"} ｜ {nc.machiningTime != null ? `${nc.machiningTime}分` : "—"}</div>
                      {nc.clampNote && <div className="text-slate-500 line-clamp-2">{nc.clampNote}</div>}
                      <div className="border-t border-slate-100 pt-2 text-slate-400">
                        工具リスト {nc.tools?.length ?? 0}件...
                      </div>
                    </div>
                  </div>
                )}
                {/* 開始ボタン */}
                <button
                  onClick={() => setShowAuth(true)}
                  className="w-full flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-5 py-3 rounded-xl text-sm font-bold transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <rect x="3" y="11" width="18" height="11" rx="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                  この作業を開始する（担当者確認）
                </button>
                <p className="text-xs text-slate-400">担当者確認後に印刷・USB書き出しができます</p>
              </div>
            </div>
          )}
'''
        src = src[:start_idx] + NEW_LOCK_PRINT + src[end_idx:]
        print("OK: ロック画面をセンター配置に全面リデザイン")
    else:
        print("WARN: ロック画面の開始位置が見つかりません")
else:
    print("WARN: ロック画面のマーカーが見つかりません（別パターン）")

if src != original:
    TARGET.write_text(src, encoding="utf-8")
    print(f"\n✅ print/page.tsx を更新しました: {TARGET}")
else:
    print("\n⚠ 変更がありません。パターンを確認してください。")
