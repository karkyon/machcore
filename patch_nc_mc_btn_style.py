#!/usr/bin/env python3
"""
NC/MC切替ボタン スタイル統一パッチ
- ボタンラベル: 「⇄ MC」 / 「⇄ NC」 で統一
- スタイル: border付きで視認性UP
- 配置: 全ページ統一
"""

import os, re

BASE = os.path.expanduser("~/projects/machcore/apps/web/app")

# 共通ボタンスタイル（両方同じデザイン）
MC_BTN = (
    '<button onClick={() => router.push("/mc/search")} '
    'className="text-xs border border-teal-600 hover:border-teal-400 '
    'text-teal-400 hover:text-white hover:bg-teal-700 '
    'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>'
)

NC_BTN = (
    '<button onClick={() => router.push("/nc/search")} '
    'className="text-xs border border-sky-600 hover:border-sky-400 '
    'text-sky-400 hover:text-white hover:bg-sky-700 '
    'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>'
)

results = []

def replace_in_file(rel_path, old, new, label=""):
    path = os.path.join(BASE, rel_path)
    if not os.path.exists(path):
        results.append(f"SKIP (not found): {rel_path}")
        return False
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        results.append(f"FAIL (not found): {rel_path} [{label}]")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new, 1))
    results.append(f"OK: {rel_path} [{label}]")
    return True

# ══════════════════════════════════════════════════════
# NC → MC ボタン: 旧スタイル → 新スタイルに置換
# ══════════════════════════════════════════════════════
OLD_MC_BTN = (
    'className="text-[10px] bg-teal-800 hover:bg-teal-600 text-teal-300 '
    'hover:text-white px-2 py-0.5 rounded font-bold transition-colors">MC →</button>'
)
NEW_MC_BTN = (
    'className="text-xs border border-teal-600 hover:border-teal-400 '
    'text-teal-400 hover:text-white hover:bg-teal-700 '
    'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>'
)

NC_PAGES = [
    "nc/search/page.tsx",
    "nc/[nc_id]/page.tsx",
    "nc/[nc_id]/edit/page.tsx",
    "nc/[nc_id]/print/page.tsx",
    "nc/[nc_id]/record/page.tsx",
]

for p in NC_PAGES:
    replace_in_file(p, OLD_MC_BTN, NEW_MC_BTN, "MC→スタイル統一")

# ══════════════════════════════════════════════════════
# MC → NC ボタン: 旧スタイル → 新スタイルに置換
# ══════════════════════════════════════════════════════
OLD_NC_BTN = (
    'className="text-[10px] bg-sky-800 hover:bg-sky-600 text-sky-300 '
    'hover:text-white px-2 py-0.5 rounded font-bold transition-colors">← NC</button>'
)
NEW_NC_BTN = (
    'className="text-xs border border-sky-600 hover:border-sky-400 '
    'text-sky-400 hover:text-white hover:bg-sky-700 '
    'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>'
)

MC_PAGES = [
    "mc/[mc_id]/page.tsx",
    "mc/[mc_id]/edit/page.tsx",
    "mc/[mc_id]/print/page.tsx",
    "mc/[mc_id]/record/page.tsx",
]

for p in MC_PAGES:
    replace_in_file(p, OLD_NC_BTN, NEW_NC_BTN, "NC→スタイル統一")

# ══════════════════════════════════════════════════════
# MC search: 既存の「NC 旋盤」クリック部分のスタイルを統一
# ── 現在: `text-xs text-slate-400 hover:text-slate-200 transition-colors`
# ── 変更: border付きボタンに変更
# ══════════════════════════════════════════════════════
mc_search_path = os.path.join(BASE, "mc/search/page.tsx")
if os.path.exists(mc_search_path):
    with open(mc_search_path, encoding="utf-8") as f:
        src = f.read()

    # MC search ヘッダーの「NC 旋盤」リンク部分を置換
    # パターン: button onClick router.push /nc/search ... NC 旋盤
    old_mc_search = (
        '<button onClick={() => router.push("/nc/search")} '
        'className="text-xs text-slate-400 hover:text-slate-200 transition-colors">NC 旋盤</button>'
    )
    new_mc_search = (
        '<button onClick={() => router.push("/nc/search")} '
        'className="text-xs border border-sky-600 hover:border-sky-400 '
        'text-sky-400 hover:text-white hover:bg-sky-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>'
    )

    if old_mc_search in src:
        # ヘッダーの構造も調整: 「NC 旋盤 → MC マシニング」の → テキストとMCテキストを整理
        new_src = src.replace(old_mc_search, new_mc_search, 1)
        # 「→」スパンと「MC マシニング」テキストを削除してシンプルにする
        new_src = new_src.replace(
            '\n        <span className="text-slate-600 text-xs">→</span>\n'
            '        <span className="text-sm font-medium text-teal-300">MC マシニング</span>',
            '\n        <span className="text-sm font-medium text-teal-300">MC マシニング管理</span>'
        )
        with open(mc_search_path, "w", encoding="utf-8") as f:
            f.write(new_src)
        results.append("OK: mc/search/page.tsx [NC→スタイル統一]")
    else:
        # フォールバック: ⇄ NC ボタンがすでにある場合はスタイルのみ更新
        old2 = 'className="text-xs border border-sky-600 hover:border-sky-400 text-sky-300 hover:text-white px-2 py-0.5 rounded font-bold transition-colors">← NC</button>'
        if old2 in src:
            new2 = (
                'className="text-xs border border-sky-600 hover:border-sky-400 '
                'text-sky-400 hover:text-white hover:bg-sky-700 '
                'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>'
            )
            with open(mc_search_path, "w", encoding="utf-8") as f:
                f.write(src.replace(old2, new2, 1))
            results.append("OK: mc/search/page.tsx [NC→スタイル統一 fallback]")
        else:
            results.append("SKIP: mc/search/page.tsx [パターン不一致 - 手動確認]")
            # ファイルの実際のボタン周辺を表示
            idx = src.find('router.push("/nc/search")')
            if idx >= 0:
                print(f"\n[mc/search 実際のコード]:\n{src[max(0,idx-50):idx+200]}\n")

print("=== NC/MC切替ボタン スタイル統一結果 ===")
for r in results:
    print(r)
print("\n完了")
