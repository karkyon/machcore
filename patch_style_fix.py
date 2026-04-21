#!/usr/bin/env python3
"""
1. nc/[nc_id]/record ボタン修正（FAIL対応）
2. タイトル文字色: MC系 text-white に統一
3. タイトル文字サイズ: text-sm → text-base
4. MachCore文字サイズ: text-sm → text-base
"""
import os, re

BASE = os.path.expanduser("~/projects/machcore/apps/web/app")

WHITE_MC = (
    '<button onClick={() => router.push("/mc/search")} '
    'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
    'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ MC</button>'
)

def patch(rel, old, new, label=""):
    path = os.path.join(BASE, rel)
    with open(path, encoding="utf-8") as f: src = f.read()
    if old not in src:
        print(f"FAIL [{label}]: {rel}")
        return False
    with open(path, "w", encoding="utf-8") as f: f.write(src.replace(old, new, 1))
    print(f"OK [{label}]: {rel}")
    return True

def replace_all(rel, replacements):
    path = os.path.join(BASE, rel)
    with open(path, encoding="utf-8") as f: src = f.read()
    changed = 0
    for old, new in replacements:
        if old in src:
            src = src.replace(old, new)
            changed += 1
    with open(path, "w", encoding="utf-8") as f: f.write(src)
    print(f"OK [style {changed}件]: {rel}")

# ════════════════════════════════════════════════
# 1. nc/[nc_id]/record — 実際のヘッダーパターンを総当り
# ════════════════════════════════════════════════
rec = os.path.join(BASE, "nc/[nc_id]/record/page.tsx")
with open(rec, encoding="utf-8") as f: rec_src = f.read()

# ⇄ MC が既に入っているか確認
if "⇄ MC" in rec_src:
    print("SKIP [already patched]: nc/[nc_id]/record/page.tsx")
else:
    # ヘッダー内の `ml-auto` 直前（どんなspanでも）にMCボタンを挿入
    # パターンA: `<span className="ml-auto flex items-center`
    patA_old = '          <span className="ml-auto flex items-center'
    patA_new = f'          {WHITE_MC}\n          <span className="ml-auto flex items-center'
    # パターンB: `<span className="ml-auto`
    patB_old = '          <span className="ml-auto'
    patB_new = f'          {WHITE_MC}\n          <span className="ml-auto'
    # パターンC: MachCore span → |  → タイトルspan (edit/printと同構造)
    patC_old = (
        '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
        '          <span className="text-slate-400 text-xs">|</span>\n'
        '          <span className="text-sm font-medium'
    )
    patC_new = (
        '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
        '          <span className="text-slate-400 text-xs">|</span>\n'
        f'          {WHITE_MC}\n'
        '          <span className="text-sm font-medium'
    )
    # パターンD: 古いstyle (font-bold text-sky-400 tracking-wide)
    patD_old = (
        '<span className="font-bold text-sky-400 tracking-wide">MachCore</span>\n'
        '        <span className="ml-auto'
    )
    patD_new = (
        '<span className="font-bold text-sky-400 tracking-wide">MachCore</span>\n'
        f'        {WHITE_MC}\n'
        '        <span className="ml-auto'
    )

    inserted = False
    for old, new in [(patC_old, patC_new), (patA_old, patA_new), (patD_old, patD_new), (patB_old, patB_new)]:
        if old in rec_src:
            rec_src = rec_src.replace(old, new, 1)
            with open(rec, "w", encoding="utf-8") as f: f.write(rec_src)
            print(f"OK [MCボタン挿入]: nc/[nc_id]/record/page.tsx")
            inserted = True
            break
    if not inserted:
        print("FAIL [全パターン不一致]: nc/[nc_id]/record/page.tsx")
        # ヘッダー内のコードを表示して確認
        h = re.search(r'<header[^>]*>(.*?)</header>', rec_src, re.DOTALL)
        if h: print("  [header内容]:", h.group(1)[:400])

# ════════════════════════════════════════════════
# 2. タイトル文字色・サイズ + MachCore文字サイズ
#    対象: 全10画面
# ════════════════════════════════════════════════

# ── NC系: MachCore text-sm → text-base ──
NC_MACHCORE_PAGES = [
    "nc/search/page.tsx",
    "nc/[nc_id]/page.tsx",
    "nc/[nc_id]/edit/page.tsx",
    "nc/[nc_id]/print/page.tsx",
    "nc/[nc_id]/record/page.tsx",
]
for p in NC_MACHCORE_PAGES:
    replace_all(p, [
        # MachCore 文字サイズ
        ('className="font-mono text-sky-400 font-bold text-sm">MachCore</span>',
         'className="font-mono text-sky-400 font-bold text-base">MachCore</span>'),
        ('className="font-bold text-sky-400 tracking-wide">MachCore</span>',
         'className="font-bold text-sky-400 text-base tracking-wide">MachCore</span>'),
        # タイトル文字サイズ
        ('"NC 旋盤管理システム"}</span>',
         '"NC 旋盤管理システム"}</span>'.replace(
             'className="text-sm font-medium"',
             'className="text-base font-medium"'
         )),
    ])

# NC search タイトルサイズ個別対応（adminInfo条件付きspan）
patch("nc/search/page.tsx",
    '<span className="text-sm font-medium">{adminInfo?.companyName ?? "NC 旋盤管理システム"}</span>',
    '<span className="text-base font-medium">{adminInfo?.companyName ?? "NC 旋盤管理システム"}</span>',
    "NCタイトルサイズ"
)

# ── MC系 ──
MC_MACHCORE_PAGES = [
    "mc/search/page.tsx",
    "mc/[mc_id]/page.tsx",
    "mc/[mc_id]/edit/page.tsx",
    "mc/[mc_id]/print/page.tsx",
    "mc/[mc_id]/record/page.tsx",
]

# mc/search: MachCore + タイトル
patch("mc/search/page.tsx",
    'className="font-mono text-teal-400 font-bold text-sm">MachCore</span>',
    'className="font-mono text-teal-400 font-bold text-base">MachCore</span>',
    "MCMachCoreサイズ"
)
patch("mc/search/page.tsx",
    'className="text-sm font-medium text-teal-300">MC マシニング管理システム</span>',
    'className="text-base font-medium text-white">MC マシニング管理システム</span>',
    "MCタイトル色+サイズ"
)

# mc/[mc_id]系: "MachCore MC" ボタンのサイズ
for p in ["mc/[mc_id]/page.tsx", "mc/[mc_id]/edit/page.tsx",
          "mc/[mc_id]/print/page.tsx", "mc/[mc_id]/record/page.tsx"]:
    # MachCore MCボタンのテキストサイズ変更
    replace_all(p, [
        ('className="text-teal-400 font-bold text-sm font-mono hover:text-teal-300">MachCore MC</button>',
         'className="text-teal-400 font-bold text-base font-mono hover:text-teal-300">MachCore MC</button>'),
        ('className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>',
         'className="text-teal-400 font-bold text-base font-mono">MachCore MC</button>'),
    ])

print("\n全処理完了")
