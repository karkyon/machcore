#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deploy_manual_links.py
--------------------------------------------------------------------
MC/NC/CMS それぞれのダッシュボードに「📖 マニュアル」リンクを恒久的に追加し、
マニュアルHTMLをNext.jsのpublicフォルダに配置してどこからでも参照できるようにする。

前提:
  - このスクリプトは machcore リポジトリのルート（package.json がある場所）で実行する
  - 事前に以下2ファイルを、このスクリプトと同じ場所に置いておくこと
      business-manual.html   (MC/NC共通・スクショ埋め込み済み)
      cms-manual.html        (CMS用・スクショ埋め込み済み)

実行:
  cd ~/projects/machcore
  python3 deploy_manual_links.py

このスクリプトは:
  1. 上記2ファイルを apps/web/public/manuals/ にコピー
     (business-manual.html / cms-manual.html にリネーム)
  2. apps/web/app/mc/page.tsx にマニュアルリンクを追加
  3. apps/web/app/nc/page.tsx にマニュアルリンクを追加（#nc付きURLでNCタブを自動選択）
  4. apps/web/components/admin/AdminLayout.tsx にマニュアルリンクを追加
  5. ja.json / vi.json に表示文言を追加
  6. next build を実行し、エラーが無ければ pm2 delete + pm2 start で反映
  7. すべて成功した場合のみ git add / commit / push

途中で1つでも失敗したら、その時点で停止し、変更したファイルの一覧を表示する
（zero errorsでない限りビルド・pushは実行しない）。
--------------------------------------------------------------------
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
WEB = ROOT / "apps" / "web"
MC_PAGE = WEB / "app" / "mc" / "page.tsx"
NC_PAGE = WEB / "app" / "nc" / "page.tsx"
ADMIN_LAYOUT = WEB / "components" / "admin" / "AdminLayout.tsx"
JA_DICT = WEB / "lib" / "i18n" / "dictionaries" / "ja.json"
VI_DICT = WEB / "lib" / "i18n" / "dictionaries" / "vi.json"
PUBLIC_MANUALS = WEB / "public" / "manuals"

SRC_MC_NC_MANUAL = ROOT / "business-manual.html"
SRC_CMS_MANUAL = ROOT / "cms-manual.html"

changed_files = []


def die(msg):
    print(f"\n❌ {msg}")
    if changed_files:
        print("\n途中まで変更したファイル（ロールバックする場合は git checkout -- <path>）:")
        for p in changed_files:
            print("  -", p)
    sys.exit(1)


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            print(f"  ↷ {label}: 既に適用済みのためスキップ")
            return
        die(f"{label}: 差し替え対象の文字列が見つかりません。ファイル構成が想定と異なる可能性があります。\n   対象ファイル: {path}")
    if text.count(old) != 1:
        die(f"{label}: 差し替え対象の文字列が複数箇所にヒットしました（一意になっていません）。\n   対象ファイル: {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    changed_files.append(str(path.relative_to(ROOT)))
    print(f"  ✅ {label}")


# ----------------------------------------------------------------
# 0. 事前チェック
# ----------------------------------------------------------------
print("=== 0. 事前チェック ===")
for p in (MC_PAGE, NC_PAGE, ADMIN_LAYOUT, JA_DICT, VI_DICT):
    if not p.exists():
        die(f"想定パスにファイルが見つかりません: {p}\n（machcoreリポジトリのルートで実行しているか確認してください）")
if not SRC_MC_NC_MANUAL.exists() or not SRC_CMS_MANUAL.exists():
    die("マニュアルHTML（MachCore_業務オペレーションマニュアル_v2.html / MachCore_CMS管理マニュアル.html）が"
        "スクリプトと同じディレクトリに見つかりません。先に配置してください。")
print("OK")

# ----------------------------------------------------------------
# 1. public/manuals/ へ配置
# ----------------------------------------------------------------
print("\n=== 1. マニュアルHTMLをpublic/manuals/へ配置 ===")
PUBLIC_MANUALS.mkdir(parents=True, exist_ok=True)
shutil.copy(SRC_MC_NC_MANUAL, PUBLIC_MANUALS / "business-manual.html")
shutil.copy(SRC_CMS_MANUAL, PUBLIC_MANUALS / "cms-manual.html")
changed_files.append(str((PUBLIC_MANUALS / "business-manual.html").relative_to(ROOT)))
changed_files.append(str((PUBLIC_MANUALS / "cms-manual.html").relative_to(ROOT)))
print("  ✅ apps/web/public/manuals/business-manual.html")
print("  ✅ apps/web/public/manuals/cms-manual.html")

# ----------------------------------------------------------------
# 2. MC dashboard にマニュアルリンク追加
# ----------------------------------------------------------------
print("\n=== 2. MCダッシュボード (apps/web/app/mc/page.tsx) ===")
mc_old = '''              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t("dashboard.adminSection", "管理")}</div>
              <button onClick={() => { sessionStorage.setItem("admin_origin", "mc"); router.push("/admin/login"); }}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
                {t("dashboard.adminPanel", "管理パネル")}
              </button>
            </div>'''
mc_new = '''              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t("dashboard.adminSection", "管理")}</div>
              <button onClick={() => { sessionStorage.setItem("admin_origin", "mc"); router.push("/admin/login"); }}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
                {t("dashboard.adminPanel", "管理パネル")}
              </button>
              <a href="/manuals/business-manual.html" target="_blank" rel="noopener noreferrer"
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/></svg>
                {t("dashboard.manualLink", "📖 業務マニュアル")}
              </a>
            </div>'''
replace_once(MC_PAGE, mc_old, mc_new, "マニュアルリンク追加")

# ----------------------------------------------------------------
# 3. NC dashboard にマニュアルリンク追加（#nc付きでNCタブを自動選択）
# ----------------------------------------------------------------
print("\n=== 3. NCダッシュボード (apps/web/app/nc/page.tsx) ===")
nc_old = '''              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t("dashboard.adminSection", "管理")}</div>
              <button onClick={() => { sessionStorage.setItem("admin_origin", "nc"); router.push("/admin/login"); }}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
                {t("dashboard.adminPanel", "管理パネル")}
              </button>'''
nc_new = '''              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t("dashboard.adminSection", "管理")}</div>
              <button onClick={() => { sessionStorage.setItem("admin_origin", "nc"); router.push("/admin/login"); }}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
                {t("dashboard.adminPanel", "管理パネル")}
              </button>
              <a href="/manuals/business-manual.html#nc" target="_blank" rel="noopener noreferrer"
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/></svg>
                {t("dashboard.manualLink", "📖 業務マニュアル")}
              </a>'''
replace_once(NC_PAGE, nc_old, nc_new, "マニュアルリンク追加（#nc付き）")

# ----------------------------------------------------------------
# 4. AdminLayout（CMS全画面共通）にマニュアルリンク追加
# ----------------------------------------------------------------
print("\n=== 4. AdminLayout (apps/web/components/admin/AdminLayout.tsx) ===")
admin_old = '''          <div className="mx-3 my-1 border-t border-slate-200" />
          {BOTTOM_ITEMS.map(href => {'''
admin_new = '''          <div className="mx-3 my-1 border-t border-slate-200" />
          <a href="/manuals/cms-manual.html" target="_blank" rel="noopener noreferrer"
            className="mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-50 hover:text-slate-900">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/></svg>
            {t("adminLayout.menuManual", "📖 マニュアル")}
          </a>
          <div className="mx-3 my-1 border-t border-slate-200" />
          {BOTTOM_ITEMS.map(href => {'''
replace_once(ADMIN_LAYOUT, admin_old, admin_new, "マニュアルリンク追加")

# ----------------------------------------------------------------
# 5. i18n辞書に文言追加
# ----------------------------------------------------------------
print("\n=== 5. i18n辞書 (ja.json / vi.json) ===")

def add_dict_keys(path: Path, adds: dict, label: str):
    data = json.loads(path.read_text(encoding="utf-8"))
    touched = False
    for section, kv in adds.items():
        if section not in data:
            die(f"{label}: セクション '{section}' が見つかりません。辞書構造が想定と異なります。")
        for k, v in kv.items():
            if k not in data[section]:
                data[section][k] = v
                touched = True
    if touched:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed_files.append(str(path.relative_to(ROOT)))
        print(f"  ✅ {label}: 文言を追加")
    else:
        print(f"  ↷ {label}: 既に追加済みのためスキップ")

add_dict_keys(JA_DICT, {
    "dashboard": {"manualLink": "📖 業務マニュアル"},
    "adminLayout": {"menuManual": "📖 マニュアル"},
}, "ja.json")

add_dict_keys(VI_DICT, {
    "dashboard": {"manualLink": "📖 Sổ tay nghiệp vụ"},
    "adminLayout": {"menuManual": "📖 Sổ tay hướng dẫn"},
}, "vi.json")

# ----------------------------------------------------------------
# 6. ビルド
# ----------------------------------------------------------------
print("\n=== 6. next build (apps/web) ===")
build = subprocess.run(["npm", "run", "build"], cwd=WEB)
if build.returncode != 0:
    die("next build が失敗しました。上記のビルドログを確認し、修正してから再実行してください。\n"
        "（このスクリプトはビルド失敗時に pm2 反映・git push を行いません）")
print("  ✅ ビルド成功")

# ----------------------------------------------------------------
# 7. PM2再起動
# ----------------------------------------------------------------
print("\n=== 7. PM2再起動 (machcore-web) ===")
subprocess.run(["pm2", "delete", "machcore-web"], cwd=ROOT)
restart = subprocess.run(["pm2", "start", "ecosystem.config.js", "--only", "machcore-web"], cwd=ROOT)
if restart.returncode != 0:
    die("pm2 start に失敗しました。手動で `pm2 start ecosystem.config.js --only machcore-web` を実行してください。")
print("  ✅ machcore-web を再起動しました")

# ----------------------------------------------------------------
# 8. git commit & push（ビルド成功時のみ）
# ----------------------------------------------------------------
print("\n=== 8. git commit & push ===")
subprocess.run(["git", "add"] + changed_files, cwd=ROOT)
commit = subprocess.run(
    ["git", "commit", "-m", "feat: MC/NC/CMSダッシュボードに業務マニュアルへの恒久リンクを追加"],
    cwd=ROOT,
)
if commit.returncode == 0:
    push = subprocess.run(["git", "push"], cwd=ROOT)
    if push.returncode == 0:
        print("  ✅ git push 完了")
    else:
        print("  ⚠ git push に失敗しました。手動で `git push` を実行してください。")
else:
    print("  ↷ コミット対象の変更がありませんでした（既に反映済みの可能性）")

print("\n=== 完了 ===")
print("MC:  https://192.168.1.11:8443/mc  → 左サイドバー「📖 業務マニュアル」")
print("NC:  https://192.168.1.11:8443/nc  → 左サイドバー「📖 業務マニュアル」（NCタブが自動選択されます）")
print("CMS: https://192.168.1.11:8443/admin/... 任意の管理画面 → 左サイドバー「📖 マニュアル」")
