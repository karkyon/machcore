#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分のみstr_replace修正"""
import os, subprocess

WEB  = "/home/karkyon/projects/machcore/apps/web"
REPO = "/home/karkyon/projects/machcore"
errs = []

def fix(path, fixes):
    fname = path.split("/")[-2]
    if not os.path.exists(path):
        print(f"⚠️  {fname}: ファイルなし"); return
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    orig = src
    print(f"\n[{fname}]")
    for old, new, label in fixes:
        if old in src:
            src = src.replace(old, new, 1)
            print(f"  ✅ {label}")
        else:
            print(f"  ⏭  {label}: パターン不一致（既修正 or 不要）")
    if src != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)

# ── timecards ──
fix(f"{WEB}/app/mc/timecards/page.tsx", [
    (
        'toastOk ? "bg-emerald-500" : "bg-red-500"',
        'toastOk ? "bg-green-600" : "bg-red-600"',
        "toast色 emerald→green"
    ),
    # main p4→p5 統一
    (
        '<main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">',
        '<main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">',
        "main padding p4→p5"
    ),
])

# ── settings ──
fix(f"{WEB}/app/admin/settings/page.tsx", [
    (
        'toast.ok ? "bg-emerald-500" : "bg-red-500"',
        'toast.ok ? "bg-green-600" : "bg-red-600"',
        "toast色 emerald→green"
    ),
    # transition-all 削除（usersに合わせる）
    (
        'text-sm font-bold transition-all ${toast.ok ? "bg-green-600" : "bg-red-600"',
        'text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"',
        "toast transition-all削除"
    ),
    # main: overflow-y-auto + スクロール可能なので p5 gap-3 に統一しつつスクロール維持
    (
        '<main className="flex-1 min-h-0 overflow-y-auto px-6 py-5">',
        '<main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">',
        "main className統一"
    ),
    # h1追加（まだない場合）
    (
        '          <div className="space-y-5 max-w-2xl">\n            {/* 会社情報 */}',
        '          <h1 className="text-xl font-bold text-slate-800 shrink-0">システム設定</h1>\n          <div className="space-y-5 max-w-2xl">\n            {/* 会社情報 */}',
        "h1 システム設定 追加"
    ),
])

# ── pdf-editor ──
fix(f"{WEB}/app/admin/pdf-editor/page.tsx", [
    (
        'toast.ok ? "bg-emerald-500" : "bg-red-500"',
        'toast.ok ? "bg-green-600" : "bg-red-600"',
        "toast色 emerald→green"
    ),
])

# ── system-logs ──
fix(f"{WEB}/app/admin/system-logs/page.tsx", [
    (
        '"bg-emerald-500"',
        '"bg-green-600"',
        "toast成功色"
    ),
    (
        # system-logsのtoastは { msg, ok } 形式で bg-red-500 が残っているか確認
        '"bg-red-500"',
        '"bg-red-600"',
        "toast失敗色"
    ),
])

# ── calendar ──
fix(f"{WEB}/app/admin/calendar/page.tsx", [
    (
        '"bg-emerald-500"',
        '"bg-green-600"',
        "toast成功色"
    ),
    (
        '"bg-red-500"',
        '"bg-red-600"',
        "toast失敗色"
    ),
])

# ── raw ──
fix(f"{WEB}/app/admin/raw/page.tsx", [
    (
        '"bg-emerald-500"',
        '"bg-green-600"',
        "toast成功色"
    ),
    (
        '"bg-red-500"',
        '"bg-red-600"',
        "toast失敗色"
    ),
])

# ── build ──
print("\n--- next build ---")
r = subprocess.run(["npx", "next", "build"], cwd=f"{WEB}", capture_output=True, text=True)
if r.returncode != 0:
    print("❌\n" + (r.stdout+r.stderr)[-2000:])
    import sys; sys.exit(1)
print("✅ next build OK")
subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True)
print("✅ pm2 restart")
subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "fix: admin UI - toast green/red, main p5, h1 settings, timecards p5"], cwd=REPO)
r3 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r3.stderr.strip() or r3.stdout.strip()))
print("✅ 完了")
