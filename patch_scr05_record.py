#!/usr/bin/env python3
"""
SCR-05 record/page.tsx UI修正パッチ
修正内容:
  1. ヘッダー「← NC詳細」 → アイコン付き背景ボタン
  2. ナビタブ → セッション中は緑点滅ドット、非アクティブタブにロック表示
  3. ロック画面 → センター配置の大きなUI（過去記録プレビュー50%透過付き）
"""
import sys, shutil
from pathlib import Path

TARGET = Path("/home/user/machcore/apps/web/app/nc/[nc_id]/record/page.tsx")

if not TARGET.exists():
    for p in Path("/").rglob("page.tsx"):
        if "nc_id" in str(p) and "record" in str(p) and ".bak" not in str(p):
            TARGET = p
            print(f"Found: {TARGET}")
            break

if not TARGET.exists():
    print("ERROR: record/page.tsx が見つかりません")
    sys.exit(1)

shutil.copy(TARGET, str(TARGET) + ".bak_ui_patch")
print(f"Backup: {TARGET}.bak_ui_patch")

src = TARGET.read_text(encoding="utf-8")
original = src

# ============================================================
# 1. ヘッダーの「← NC詳細」ボタン強化
# ============================================================
import re

# 汎用正規表現でbackボタンを探す
pattern_back = r'(<button\s[^>]*onClick=\{[^}]*router\.push\(`/nc/\$\{ncId\}`\)[^}]*\}\s*\n\s*className="text-slate-400[^"]*"[^>]*>\s*←\s*NC詳細\s*</button>)'
m = re.search(pattern_back, src, re.DOTALL)

if m:
    indent = "          "  # デフォルトインデント
    new_btn = f'''{indent}<button
{indent}  onClick={{() => router.push(`/nc/${{ncId}}`)}}
{indent}  className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"
{indent}>
{indent}  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
{indent}    <path d="M19 12H5M12 5l-7 7 7 7"/>
{indent}  </svg>
{indent}  NC詳細に戻る
{indent}</button>'''
    src = src[:m.start()] + new_btn + src[m.end():]
    print("OK: ← NC詳細 ボタン強化")
else:
    # 直接文字列マッチ
    old_back_variants = [
        ('          <button\n            onClick={() => router.push(`/nc/${ncId}`)}\n            className="text-slate-400 hover:text-white text-xs transition-colors"\n          >\n            ← NC詳細\n          </button>',
         '          <button\n            onClick={() => router.push(`/nc/${ncId}`)}\n            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"\n          >\n            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">\n              <path d="M19 12H5M12 5l-7 7 7 7"/>\n            </svg>\n            NC詳細に戻る\n          </button>'),
        ('        <button\n          onClick={() => router.push(`/nc/${ncId}`)}\n          className="text-slate-400 hover:text-white text-xs transition-colors"\n        >\n          ← NC詳細\n        </button>',
         '        <button\n          onClick={() => router.push(`/nc/${ncId}`)}\n          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-sky-400 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition-colors"\n        >\n          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">\n            <path d="M19 12H5M12 5l-7 7 7 7"/>\n          </svg>\n          NC詳細に戻る\n        </button>'),
    ]
    replaced = False
    for old, new in old_back_variants:
        if old in src:
            src = src.replace(old, new)
            replaced = True
            print("OK: ← NC詳細 ボタン強化")
            break
    if not replaced:
        print("WARN: ← NC詳細 ボタンのパターンが見つかりません（手動確認要）")

# ============================================================
# 2. ナビタブ: 作業記録タブ active=true, 緑点滅ドット
# ============================================================
OLD_TABS_PATTERNS = [
    # パターンA: インデント8スペース
    '''        <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
          {([
            { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
            { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
            { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: false },
            { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: true  },
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
        </nav>''',
    # パターンB: インデント6スペース
    '''      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {([
          { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
          { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
          { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: false },
          { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: true  },
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
      </nav>''',
]

NEW_TABS = '''        <nav className="bg-slate-700 px-5 flex gap-0 shrink-0 border-t border-slate-600">
          {([
            { href: `/nc/${ncId}`,        label: "NC詳細",    active: false, lock: false },
            { href: `/nc/${ncId}/edit`,   label: "変更・登録", active: false, lock: true  },
            { href: `/nc/${ncId}/print`,  label: "段取シート", active: false, lock: true  },
            { href: `/nc/${ncId}/record`, label: "作業記録",  active: true,  lock: false },
          ] as { href: string; label: string; active: boolean; lock: boolean }[]).map(tab => (
            <button
              key={tab.href}
              onClick={() => router.push(tab.href)}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active
                  ? isAuthenticated
                    ? "border-green-400 text-green-300"
                    : "border-sky-400 text-sky-300"
                  : "border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-400"
              }`}
            >
              {tab.active && isAuthenticated && (
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
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

tab_replaced = False
for old_tabs in OLD_TABS_PATTERNS:
    if old_tabs in src:
        src = src.replace(old_tabs, NEW_TABS)
        tab_replaced = True
        print("OK: タブ点滅ドット・ロックアイコン追加")
        break

if not tab_replaced:
    print("WARN: タブのパターンが一致しません（手動確認要）")

# ============================================================
# 3. ロック画面の強化（record/page.tsx のロック画面）
# ============================================================
# record/page.tsx のロック状態を探す
# 認証前はshowAuthModal でフラグを持ちisAuthenticated==false の状態
# 現在の実装でロック画面がどう書かれているか確認して置換

# ロック画面の一般的なパターンを探す
lock_markers = [
    '!isAuthenticated && (',
    '!isAuthenticated &&(',
]

# まず record の isAuthenticated 変数名を確認（isAuthenticated or workToken等）
auth_var = 'isAuthenticated'
if 'workToken' in src and 'isAuthenticated' not in src:
    auth_var = '!workToken'

# 認証前ロック画面（過去の記録一覧も表示する設計）
LOCK_SECTION_COMMENT = '{/* 認証前ロック画面 */}'

if LOCK_SECTION_COMMENT not in src:
    # 既存のロック画面パターンを探して置換
    # record/page.tsx では認証前に「作業開始」ボタンを見せるUIがある
    # パターン: isAuthenticated が false の時の表示ブロック
    
    # showAuthModal を開くボタンを含むロック画面を探す
    lock_pattern = re.search(
        r'\{(/\*[^*]*\*/\s*)?\s*!isAuthenticated\s*&&\s*\(\s*\n(.*?)(?=\n\s*\{(?:/\*|isAuthenticated|\s*<))',
        src, re.DOTALL
    )
    
    if lock_pattern:
        print(f"INFO: ロック画面ブロック検出 (位置: {lock_pattern.start()}-{lock_pattern.end()})")
        # このブロックを新しいUIに置き換える（複雑なため手動対応を促す）
        print("INFO: ロック画面の自動置換は複雑なため、手動で確認・修正してください")
        print("      以下のコードを参考に修正:")
        print("""
      {/* 認証前ロック画面 */}
      {!isAuthenticated && (
        <div className="flex flex-col items-center justify-center py-10">
          <div className="bg-white rounded-2xl border-2 border-dashed border-slate-200 p-8 max-w-md w-full flex flex-col items-center gap-5 text-center">
            <div className="w-14 h-14 rounded-full bg-green-50 border border-green-200 flex items-center justify-center">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#15803d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l4 2"/>
              </svg>
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800">作業記録 — 作業開始前</h3>
              <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                段取・加工時間、ワーク数を記録するには担当者の確認が必要です。
              </p>
            </div>
            {/* 過去の記録プレビュー（50%透過） */}
            {records && records.length > 0 && (
              <div className="w-full rounded-xl border border-slate-200 overflow-hidden opacity-45 pointer-events-none">
                <div className="bg-slate-700 text-slate-300 text-[10px] font-bold px-3 py-1.5 tracking-wide uppercase text-left">
                  過去の作業記録（{records.length}件）
                </div>
                <div className="divide-y divide-slate-100">
                  {records.slice(0, 3).map(r => (
                    <div key={r.id} className="px-3 py-2 flex justify-between text-xs text-slate-600">
                      <span className="font-mono">{r.workDate}</span>
                      <span>{r.setupTimeMin != null ? `${Math.floor(r.setupTimeMin/60)}h${r.setupTimeMin%60}m` : "—"}</span>
                      <span>{r.quantity != null ? `${r.quantity}個` : "—"}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button
              onClick={() => setShowAuthModal(true)}
              className="w-full flex items-center justify-center gap-2 bg-green-700 hover:bg-green-800 text-white px-5 py-3 rounded-xl text-sm font-bold transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <rect x="3" y="11" width="18" height="11" rx="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              この作業を開始する（担当者確認）
            </button>
            <p className="text-xs text-slate-400">担当者確認後に記録の入力・編集ができます</p>
          </div>
        </div>
      )}
""")
    else:
        print("WARN: ロック画面のパターンが見つかりません。ファイル内容を直接確認してください。")

if src != original:
    TARGET.write_text(src, encoding="utf-8")
    print(f"\n✅ record/page.tsx を更新しました: {TARGET}")
else:
    print("\n⚠ 変更がありません。パターンを確認してください。")
