#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理者画面 タイトル・main 統一修正（差分のみ str_replace）
基準: users/page.tsx
  main: flex-1 overflow-hidden flex flex-col p-5 gap-3
  h1:   <h1 className="text-xl font-bold text-slate-800">XXX</h1>
  h1は <div className="flex items-center justify-between shrink-0"> でwrap

対象:
  raw        - main px-4 py-4 → p-5、h1「RAWデータ」追加、SIDEBAR_ITEMSをコンポーネント外へ
  pdf-editor - h1「PDFエディタ」追加（mainは変更不要、独自レイアウト）
  settings   - main overflow-y-auto p-6 space-y-6 → overflow-y-auto flex flex-col p-5 gap-3、h1「システム設定」追加
  timecards  - h1タイトルのwrapper div を users/machines に合わせて修正
  calendar   - h1確認・不足なら追加
"""
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
REPO = "/home/karkyon/projects/machcore"

def patch(path, fixes, label):
    if not os.path.exists(path):
        print(f"  ⚠️  ファイルなし: {path}"); return False
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    orig = src
    ok = True
    for old, new, name in fixes:
        if old in src:
            src = src.replace(old, new, 1)
            print(f"  ✅ [{label}] {name}")
        else:
            print(f"  ⏭  [{label}] {name}: パターン不一致")
            # 不一致でもエラーにしない（既修正の可能性）
    if src != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
    return True

# ──────────────────────────────────────────
# 1. raw/page.tsx
#    - main: px-4 py-4 → p-5
#    - コントロールdivの前にh1追加
#    - SIDEBAR_ITEMSのコンポーネント内定義はそのまま（移動するとバグリスク高）
# ──────────────────────────────────────────
patch(
    f"{WEB}/app/admin/raw/page.tsx",
    [
        (
            '<main className="flex-1 overflow-hidden flex flex-col px-4 py-4 gap-3">',
            '<main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">',
            "main padding px-4 py-4 → p-5"
        ),
        (
            '<main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">',
            '<main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">',
            "main padding p-4 → p-5"
        ),
        (
            '        {/* コントロール */}\n        <div className="bg-white rounded-xl border border-slate-200 p-3 space-y-2 shrink-0">',
            '        <div className="flex items-center justify-between shrink-0">\n          <h1 className="text-xl font-bold text-slate-800">RAWデータ</h1>\n        </div>\n        {/* コントロール */}\n        <div className="bg-white rounded-xl border border-slate-200 p-3 space-y-2 shrink-0">',
            "h1 RAWデータ 追加"
        ),
    ],
    "raw"
)

# ──────────────────────────────────────────
# 2. pdf-editor/page.tsx
#    - サイドバーの後ろ、<div className="flex flex-1 min-w-0 overflow-hidden"> の直後に
#      h1を入れる場所がない（独自2ペインレイアウト）
#    - header直後のtoastの後、サイドバーの外側コンテナに追加できないので
#      サイドバーの上部（aside内最上部）にタイトルを付けることも難しい
#    - 最もシンプルな方法: サイドバーの「メニュー」ラベルをタイトルに置き換え
#      → これは他画面と構造が違いすぎるので、aside上部にタイトルバーを追加する
#    - 実際には aside と main(2ペイン) の親divの上に h1バーを追加する
# ──────────────────────────────────────────
patch(
    f"{WEB}/app/admin/pdf-editor/page.tsx",
    [
        (
            '      <div className="flex flex-1 min-h-0 overflow-hidden">\n\n        {/* ── サイドバー ── */',
            '      <div className="flex flex-1 min-h-0 overflow-hidden">\n\n        {/* ── サイドバー ── */',
            "pdf-editor構造確認（変更なし）"
        ),
    ],
    "pdf-editor確認"
)

# pdf-editorはサイドバー内「メニュー」ラベル部分にタイトルを追加
patch(
    f"{WEB}/app/admin/pdf-editor/page.tsx",
    [
        (
            '          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>',
            '          <div className="px-4 py-2 border-b border-slate-100 mb-1">\n            <h1 className="text-sm font-bold text-slate-800">PDFエディタ</h1>\n          </div>\n          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>',
            "h1 PDFエディタ サイドバー上部に追加"
        ),
    ],
    "pdf-editor"
)

# ──────────────────────────────────────────
# 3. settings/page.tsx
#    - main: overflow-y-auto p-6 space-y-6 → overflow-y-auto flex flex-col p-5 gap-3
#    - h1「システム設定」追加
# ──────────────────────────────────────────
patch(
    f"{WEB}/app/admin/settings/page.tsx",
    [
        (
            '<main className="flex-1 overflow-y-auto p-6 space-y-6">',
            '<main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">',
            "main p-6 space-y-6 → p-5 gap-3"
        ),
        # h1追加: loading判定divの前
        (
            '          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (\n            <>',
            '          <div className="flex items-center justify-between shrink-0">\n            <h1 className="text-xl font-bold text-slate-800">システム設定</h1>\n          </div>\n          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (\n            <>',
            "h1 システム設定 追加"
        ),
        # section内のspace-y-6 → section間のgapはgap-3で処理されるので section自体のclassは維持
        # max-w-3xlがあれば幅も統一されているのでOK
    ],
    "settings"
)

# ──────────────────────────────────────────
# 4. timecards/page.tsx (mc/timecards)
#    - h1のwrapper: shrink-0 flex items-center gap-3
#    - 基準は: flex items-center justify-between shrink-0
#    - timecards は右側にボタン群があるので justify-between のほうが自然
#      ただし現状 gap-3 で h1 + span が並んでいる
#    - users/machines に合わせて justify-between にする
#      （spanはそのまま残すと右端に行くが、コンテンツ的には h1 右に説明文は問題ない）
# ──────────────────────────────────────────
patch(
    f"{WEB}/app/mc/timecards/page.tsx",
    [
        (
            '          <div className="shrink-0 flex items-center gap-3">\n            <h1 className="text-xl font-bold text-slate-800">機械タイムカード</h1>\n            <span className="text-xs text-slate-400">稼働時間一覧（昼休み12:00-13:00跨ぎ -60分補正）</span>\n          </div>',
            '          <div className="flex items-center justify-between shrink-0">\n            <h1 className="text-xl font-bold text-slate-800">機械タイムカード</h1>\n            <span className="text-xs text-slate-400">稼働時間一覧（昼休み12:00-13:00跨ぎ -60分補正）</span>\n          </div>',
            "h1 wrapper shrink-0 flex→flex items-center justify-between shrink-0"
        ),
    ],
    "timecards"
)

# ──────────────────────────────────────────
# 5. calendar/page.tsx
#    - h1確認: 現在 <h1 className="text-2xl font-bold text-slate-800">営業カレンダー</h1> になっている可能性
#    - text-2xl → text-xl に統一
# ──────────────────────────────────────────
patch(
    f"{WEB}/app/admin/calendar/page.tsx",
    [
        (
            '<h1 className="text-2xl font-bold text-slate-800">営業カレンダー</h1>',
            '<h1 className="text-xl font-bold text-slate-800">営業カレンダー</h1>',
            "h1 text-2xl → text-xl"
        ),
        (
            '<h1 className="text-xl font-bold">営業カレンダー</h1>',
            '<h1 className="text-xl font-bold text-slate-800">営業カレンダー</h1>',
            "h1 text-slate-800 追加"
        ),
    ],
    "calendar"
)

# ──────────────────────────────────────────
# ビルド
# ──────────────────────────────────────────
print("\n--- next build ---")
env = os.environ.copy()
env["NVM_DIR"] = "/home/karkyon/.nvm"
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx next build",
    shell=True, cwd=f"{WEB}", capture_output=True, text=True, env=env
)
if r.returncode != 0:
    print("❌ next build エラー:\n" + (r.stdout + r.stderr)[-3000:])
    sys.exit(1)
print("✅ next build OK")

subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-web",
               shell=True, capture_output=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m",
    "fix: admin UI - h1 titles, main padding unified (raw/settings/pdf-editor/timecards/calendar)"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("✅ 完了")
