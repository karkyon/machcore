#!/usr/bin/env python3
"""
NC/MC切替ボタン: 白背景・左寄り配置・タイトル変更パッチ
- ボタン: bg-white, border付き → 暗いヘッダーで目立つ
- 配置: MachCore | の直後（左寄り）
- NC タイトル: "NC 旋盤管理システム"
- MC タイトル: "MC マシニング管理システム"
"""

import os, re

BASE = os.path.expanduser("~/projects/machcore/apps/web/app")

WHITE_MC_BTN = (
    '<button onClick={() => router.push("/mc/search")} '
    'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
    'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ MC</button>'
)

WHITE_NC_BTN = (
    '<button onClick={() => router.push("/nc/search")} '
    'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
    'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>'
)

PIPE = '<span className="text-slate-400 text-xs">|</span>'

results = []

def patch(path, old, new, label):
    if not os.path.exists(path):
        results.append(f"SKIP (not found): {path}")
        return
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        results.append(f"FAIL: {os.path.relpath(path, BASE)} [{label}]")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new, 1))
    results.append(f"OK: {os.path.relpath(path, BASE)} [{label}]")

# ══════════════════════════════════════════════════
# 1. NC検索 (nc/search/page.tsx)
#    - ボタンを右(ml-auto内)から左(|の直後)へ移動
#    - タイトル変更
#    - ボタンを白背景に
# ══════════════════════════════════════════════════
NC_SEARCH = os.path.join(BASE, "nc/search/page.tsx")
if os.path.exists(NC_SEARCH):
    with open(NC_SEARCH, encoding="utf-8") as f:
        src = f.read()

    # Step1: ml-auto内のボタンを削除
    old1 = (
        '<div className="ml-auto flex items-center gap-2">\n'
        '          <button onClick={() => router.push("/mc/search")} '
        'className="text-xs border border-teal-600 hover:border-teal-400 '
        'text-teal-400 hover:text-white hover:bg-teal-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>\n'
        '          <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>'
    )
    new1 = (
        '<div className="ml-auto flex items-center gap-2">\n'
        '          <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>'
    )

    # Step2: |の直後にボタンを挿入 + タイトル変更
    old2 = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '        <span className="text-sm font-medium">'
        '{adminInfo?.companyName ?? "NC 旋盤プログラム管理システム"}</span>'
    )
    new2 = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '        ' + WHITE_MC_BTN + '\n'
        '        <span className="text-sm font-medium">'
        '{adminInfo?.companyName ?? "NC 旋盤管理システム"}</span>'
    )

    ok = True
    if old1 in src:
        src = src.replace(old1, new1, 1)
    else:
        results.append("WARN: nc/search ml-auto内ボタン削除パターン不一致")
        ok = False

    if old2 in src:
        src = src.replace(old2, new2, 1)
        with open(NC_SEARCH, "w", encoding="utf-8") as f:
            f.write(src)
        results.append("OK: nc/search/page.tsx [左配置+白背景+タイトル変更]")
    else:
        results.append("FAIL: nc/search/page.tsx [タイトルパターン不一致]")
        with open(NC_SEARCH, "w", encoding="utf-8") as f:
            f.write(src)

# ══════════════════════════════════════════════════
# 2. NC詳細 (nc/[nc_id]/page.tsx)
#    - 現在: タイトル後に MC ボタンあり (ml-auto)
#    - 変更: |の直後に移動 + 白背景
# ══════════════════════════════════════════════════
NC_DETAIL = os.path.join(BASE, "nc/[nc_id]/page.tsx")
if os.path.exists(NC_DETAIL):
    with open(NC_DETAIL, encoding="utf-8") as f:
        src = f.read()

    # 現在の配置: `NC 詳細</span>` の後に MC ボタン (ml-auto)
    # → |の後に移動
    old_pipe_detail = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '          <span className="text-sm font-medium">NC 詳細</span>'
    )
    new_pipe_detail = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '          ' + WHITE_MC_BTN + '\n'
        '          <span className="text-sm font-medium">NC 詳細</span>'
    )

    # 旧ボタン削除(ml-auto前のbutton)
    old_old_btn = (
        '          <button onClick={() => router.push("/mc/search")} '
        'className="ml-auto text-[10px] bg-teal-800 hover:bg-teal-600 '
        'text-teal-300 hover:text-white px-2 py-0.5 rounded font-bold transition-colors">MC →</button>\n\n        </header>'
    )
    new_old_btn = '\n\n        </header>'

    old_new_btn = (
        '          <button onClick={() => router.push("/mc/search")} '
        'className="ml-auto text-xs border border-teal-600 hover:border-teal-400 '
        'text-teal-400 hover:text-white hover:bg-teal-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>\n\n        </header>'
    )

    # 古いボタン削除
    for old_b in [old_old_btn, old_new_btn]:
        if old_b in src:
            src = src.replace(old_b, new_old_btn, 1)
            break

    if old_pipe_detail in src:
        src = src.replace(old_pipe_detail, new_pipe_detail, 1)
        with open(NC_DETAIL, "w", encoding="utf-8") as f:
            f.write(src)
        results.append("OK: nc/[nc_id]/page.tsx [左配置+白背景]")
    else:
        with open(NC_DETAIL, "w", encoding="utf-8") as f:
            f.write(src)
        results.append("WARN: nc/[nc_id]/page.tsx [パターン不一致 - 既に適用済みかも]")

# ══════════════════════════════════════════════════
# 3. NC変更登録 (nc/[nc_id]/edit/page.tsx)
#    現在: `変更・登録` span の前に MC ボタン(mid)
#    変更: |の後に移動 + 白背景
# ══════════════════════════════════════════════════
NC_EDIT = os.path.join(BASE, "nc/[nc_id]/edit/page.tsx")
if os.path.exists(NC_EDIT):
    with open(NC_EDIT, encoding="utf-8") as f:
        src = f.read()

    # |の後に白ボタン挿入
    old_pipe = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '          <span className="text-sm font-medium flex items-center gap-1.5">'
    )
    new_pipe = (
        '<span className="text-slate-400 text-xs">|</span>\n'
        '          ' + WHITE_MC_BTN + '\n'
        '          <span className="text-sm font-medium flex items-center gap-1.5">'
    )

    # 旧ボタン削除
    old_btn = (
        '<button onClick={() => router.push("/mc/search")} '
        'className="text-xs border border-teal-600 hover:border-teal-400 '
        'text-teal-400 hover:text-white hover:bg-teal-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>\n'
        '          <span className="ml-auto">'
    )
    new_btn = '<span className="ml-auto">'

    if old_btn in src:
        src = src.replace(old_btn, new_btn, 1)

    if old_pipe in src:
        src = src.replace(old_pipe, new_pipe, 1)
        with open(NC_EDIT, "w", encoding="utf-8") as f:
            f.write(src)
        results.append("OK: nc/[nc_id]/edit/page.tsx [左配置+白背景]")
    else:
        with open(NC_EDIT, "w", encoding="utf-8") as f:
            f.write(src)
        results.append("WARN: nc/[nc_id]/edit/page.tsx [|パターン不一致]")

# ══════════════════════════════════════════════════
# 4. NC段取シート / NC作業記録
#    同様のパターン
# ══════════════════════════════════════════════════
for rel in ["nc/[nc_id]/print/page.tsx", "nc/[nc_id]/record/page.tsx"]:
    fpath = os.path.join(BASE, rel)
    if not os.path.exists(fpath):
        results.append(f"SKIP: {rel}")
        continue
    with open(fpath, encoding="utf-8") as f:
        src = f.read()

    old_btn2 = (
        '<button onClick={() => router.push("/mc/search")} '
        'className="text-xs border border-teal-600 hover:border-teal-400 '
        'text-teal-400 hover:text-white hover:bg-teal-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>\n'
        '          <span className="ml-auto">'
    )
    new_btn2 = '<span className="ml-auto">'

    if old_btn2 in src:
        src = src.replace(old_btn2, new_btn2, 1)

    # ヘッダー内の | 後を探してボタン挿入
    # パターン: | → 戻るボタン後のタイトル系
    # print/record は MachCore | ← 戻る | タイトル 構造
    old_pipe2 = (
        'className="text-slate-400 hover:text-white text-sm transition-colors"\n'
        '        >\n'
        '          ← 戻る\n'
        '        </button>\n'
        '        <span className="text-slate-400">|</span>'
    )
    new_pipe2 = (
        'className="text-slate-400 hover:text-white text-sm transition-colors"\n'
        '        >\n'
        '          ← 戻る\n'
        '        </button>\n'
        '        <span className="text-slate-400">|</span>\n'
        '        ' + WHITE_MC_BTN
    )

    if old_pipe2 in src:
        src = src.replace(old_pipe2, new_pipe2, 1)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(src)
        results.append(f"OK: {rel} [左配置+白背景]")
    else:
        # フォールバック: MachCore span の後
        old_mc_span = (
            '<span className="font-bold text-sky-400 tracking-wide">MachCore</span>\n'
            '        <span className="ml-auto text-xs text-slate-400">'
        )
        new_mc_span = (
            '<span className="font-bold text-sky-400 tracking-wide">MachCore</span>\n'
            '        ' + WHITE_MC_BTN + '\n'
            '        <span className="ml-auto text-xs text-slate-400">'
        )
        if old_mc_span in src:
            src = src.replace(old_mc_span, new_mc_span, 1)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(src)
            results.append(f"OK: {rel} [左配置+白背景 fallback]")
        else:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(src)
            results.append(f"WARN: {rel} [パターン不一致]")

# ══════════════════════════════════════════════════
# 5. MC検索 (mc/search/page.tsx)
#    - ボタン白背景に変更
#    - タイトル "MC マシニング管理システム" に変更
# ══════════════════════════════════════════════════
MC_SEARCH = os.path.join(BASE, "mc/search/page.tsx")
if os.path.exists(MC_SEARCH):
    with open(MC_SEARCH, encoding="utf-8") as f:
        src = f.read()

    # ボタンスタイル変更
    old_nc_btn = (
        'className="text-xs border border-sky-600 hover:border-sky-400 '
        'text-sky-400 hover:text-white hover:bg-sky-700 '
        'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>'
    )
    new_nc_btn = (
        'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
        'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>'
    )
    if old_nc_btn in src:
        src = src.replace(old_nc_btn, new_nc_btn, 1)

    # タイトル変更
    src = src.replace(
        '<span className="text-sm font-medium text-teal-300">MC マシニング管理</span>',
        '<span className="text-sm font-medium text-teal-300">MC マシニング管理システム</span>'
    )

    with open(MC_SEARCH, "w", encoding="utf-8") as f:
        f.write(src)
    results.append("OK: mc/search/page.tsx [白背景+タイトル変更]")

# ══════════════════════════════════════════════════
# 6. MC詳細/編集/印刷/作業記録
#    - ⇄ NC ボタンを左寄りに移動 + 白背景
#    - 現在: ml-auto前 or isAuthenticated前
#    - 変更: MachCore MC ボタン の直後に挿入
# ══════════════════════════════════════════════════
MC_PAGES = [
    "mc/[mc_id]/page.tsx",
    "mc/[mc_id]/edit/page.tsx",
    "mc/[mc_id]/print/page.tsx",
    "mc/[mc_id]/record/page.tsx",
]

OLD_NC_BTN_TEAL = (
    '<button onClick={() => router.push("/nc/search")} '
    'className="text-xs border border-sky-600 hover:border-sky-400 '
    'text-sky-400 hover:text-white hover:bg-sky-700 '
    'px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>\n'
)

for rel in MC_PAGES:
    fpath = os.path.join(BASE, rel)
    if not os.path.exists(fpath):
        results.append(f"SKIP: {rel}")
        continue
    with open(fpath, encoding="utf-8") as f:
        src = f.read()

    # 旧ボタン削除(現在位置から)
    src_clean = src.replace(OLD_NC_BTN_TEAL, '', 1)

    # MachCore MC ボタン直後に白ボタン挿入
    # パターン: `router.push("/mc/search")` ... `MachCore MC</button>` の後
    old_mc_btn_pos = (
        'className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>\n'
        '        <span className="text-slate-600">›</span>'
    )
    new_mc_btn_pos = (
        'className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>\n'
        '        ' + WHITE_NC_BTN + '\n'
        '        <span className="text-slate-600">›</span>'
    )

    # record ページのパターン確認
    old_mc_btn_pos2 = (
        'className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>\n'
        '        <span className="text-slate-600">›</span>\n'
        '        <span className="text-xs text-slate-300">'
    )

    if old_mc_btn_pos in src_clean:
        src_clean = src_clean.replace(old_mc_btn_pos, new_mc_btn_pos, 1)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(src_clean)
        results.append(f"OK: {rel} [左配置+白背景]")
    else:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(src_clean)
        results.append(f"WARN: {rel} [MachCoreボタン後パターン不一致]")

print("=== ボタン白背景・左配置・タイトル変更 結果 ===")
for r in results:
    print(r)
print("\n完了")
