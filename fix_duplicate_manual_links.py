#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_duplicate_manual_links.py
--------------------------------------------------------------------
deploy_manual_links.py のバグにより、NCダッシュボードと管理パネル(AdminLayout)に
「📖 マニュアル」リンクが重複して追加されてしまった状態を修正する。
（原因：重複チェックが不完全で、2回目の実行で再度追記されていた）

このスクリプトは重複しているリンクブロックを検出し、1つだけ残して
余分なコピーと余分な区切り線を削除する。何回実行しても安全（冪等）。

実行:
  cd ~/projects/machcore
  python3 fix_duplicate_manual_links.py
--------------------------------------------------------------------
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
NC_PAGE = ROOT / "apps" / "web" / "app" / "nc" / "page.tsx"
MC_PAGE = ROOT / "apps" / "web" / "app" / "mc" / "page.tsx"
ADMIN_LAYOUT = ROOT / "apps" / "web" / "components" / "admin" / "AdminLayout.tsx"

changed_files = []


def die(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def dedupe_block(path: Path, block_pattern: str, label: str):
    """block_patternに一致するブロックが複数あれば最初の1つだけ残す"""
    if not path.exists():
        die(f"ファイルが見つかりません: {path}")
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(block_pattern, text, re.S))
    if len(matches) <= 1:
        print(f"  ↷ {label}: 重複なし（{len(matches)}件）。変更不要")
        return
    print(f"  ⚠ {label}: {len(matches)}件の重複を検出。最初の1件だけ残します")
    keep = matches[0].group(0)
    # 2件目以降のブロックをまるごと削除
    new_text = text[: matches[0].end()]
    tail_start = matches[0].end()
    for m in matches[1:]:
        new_text += text[tail_start:m.start()]
        tail_start = m.end()
    new_text += text[tail_start:]

    # 削除の結果、区切り線(divider)が連続して残るケースを1本に正規化
    new_text = re.sub(
        r'(<div className="mx-3 my-1 border-t border-slate-200" />\s*){2,}',
        '<div className="mx-3 my-1 border-t border-slate-200" />\n          ',
        new_text,
    )

    path.write_text(new_text, encoding="utf-8")
    changed_files.append(str(path.relative_to(ROOT)))
    print(f"  ✅ {label}: 修正しました")


print("=== 1. NCダッシュボードの重複チェック ===")
dedupe_block(
    NC_PAGE,
    r'<a href="/manuals/business-manual\.html#nc".*?</a>',
    "nc/page.tsx",
)

print("\n=== 2. MCダッシュボードの重複チェック（念のため） ===")
dedupe_block(
    MC_PAGE,
    r'<a href="/manuals/business-manual\.html" target="_blank".*?</a>',
    "mc/page.tsx",
)

print("\n=== 3. 管理パネル(AdminLayout)の重複チェック ===")
dedupe_block(
    ADMIN_LAYOUT,
    r'<a href="/manuals/cms-manual\.html".*?</a>',
    "AdminLayout.tsx",
)

if not changed_files:
    print("\n重複は見つかりませんでした。変更はありません。")
    sys.exit(0)

print(f"\n変更したファイル: {changed_files}")

# ----------------------------------------------------------------
# ビルド → PM2再起動 → git push
# ----------------------------------------------------------------
print("\n=== 4. next build (apps/web) ===")
build = subprocess.run(["npm", "run", "build"], cwd=ROOT / "apps" / "web")
if build.returncode != 0:
    die("next build が失敗しました。ビルドログを確認してください。pm2反映・pushは行いません。")
print("  ✅ ビルド成功")

print("\n=== 5. PM2再起動 (machcore-web) ===")
subprocess.run(["pm2", "delete", "machcore-web"], cwd=ROOT)
restart = subprocess.run(["pm2", "start", "ecosystem.config.js", "--only", "machcore-web"], cwd=ROOT)
if restart.returncode != 0:
    die("pm2 start に失敗しました。手動で `pm2 start ecosystem.config.js --only machcore-web` を実行してください。")
print("  ✅ machcore-web を再起動しました")

print("\n=== 6. git commit & push ===")
subprocess.run(["git", "add"] + changed_files, cwd=ROOT)
commit = subprocess.run(["git", "commit", "-m", "fix: マニュアルリンクの重複表示を修正"], cwd=ROOT)
if commit.returncode == 0:
    push = subprocess.run(["git", "push"], cwd=ROOT)
    if push.returncode == 0:
        print("  ✅ git push 完了")
    else:
        print("  ⚠ git push に失敗しました。手動で `git push` を実行してください。")
else:
    print("  ↷ コミット対象の変更がありませんでした")

print("\n=== 完了 ===")
print("NC / CMS のサイドバーで「📖」リンクが1つだけになっているか確認してください。")
