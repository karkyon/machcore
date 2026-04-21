#!/usr/bin/env python3
"""WARN 3ファイルの NC/MC切替ボタン修正"""
import os

BASE = os.path.expanduser("~/projects/machcore/apps/web/app")

WHITE_MC = (
    '<button onClick={() => router.push("/mc/search")} '
    'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
    'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ MC</button>'
)
WHITE_NC = (
    '<button onClick={() => router.push("/nc/search")} '
    'className="text-xs bg-white text-slate-800 hover:bg-slate-100 '
    'border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>'
)

def patch(rel, old, new):
    path = os.path.join(BASE, rel)
    with open(path, encoding="utf-8") as f: src = f.read()
    if old not in src:
        print(f"FAIL: {rel}")
        return
    with open(path, "w", encoding="utf-8") as f: f.write(src.replace(old, new, 1))
    print(f"OK: {rel}")

# ── nc/[nc_id]/print: MachCore | の後にMCボタン挿入 ──
patch("nc/[nc_id]/print/page.tsx",
    '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
    '          <span className="text-slate-400 text-xs">|</span>\n'
    '          <span className="text-sm font-medium flex items-center gap-1.5">',
    '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
    '          <span className="text-slate-400 text-xs">|</span>\n'
    f'          {WHITE_MC}\n'
    '          <span className="text-sm font-medium flex items-center gap-1.5">'
)

# ── nc/[nc_id]/record: 同パターン ──
patch("nc/[nc_id]/record/page.tsx",
    '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
    '          <span className="text-slate-400 text-xs">|</span>\n'
    '          <span className="text-sm font-medium flex items-center gap-1.5">',
    '<span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>\n'
    '          <span className="text-slate-400 text-xs">|</span>\n'
    f'          {WHITE_MC}\n'
    '          <span className="text-sm font-medium flex items-center gap-1.5">'
)

# ── mc/[mc_id]/page: MachCore MC の直後にNCボタン挿入 ──
patch("mc/[mc_id]/page.tsx",
    'className="text-teal-400 font-bold text-sm font-mono hover:text-teal-300">MachCore MC</button>\n'
    '        <span className="text-slate-600">›</span>',
    'className="text-teal-400 font-bold text-sm font-mono hover:text-teal-300">MachCore MC</button>\n'
    f'        {WHITE_NC}\n'
    '        <span className="text-slate-600">›</span>'
)

print("完了")
