#!/bin/bash
# omega-dev2 で実行するパッチ適用スクリプト
# ファイルパスを自動探索 → パッチを順番に適用

set -e

# プロジェクトルートを特定
WEBROOT=$(find /home -type d -name "web" -path "*/apps/web" 2>/dev/null | head -1)
if [ -z "$WEBROOT" ]; then
  echo "ERROR: apps/web が見つかりません"
  exit 1
fi
echo "プロジェクト web root: $WEBROOT"

# ファイルパスを確認
EDIT_PAGE="$WEBROOT/app/nc/\[nc_id\]/edit/page.tsx"
PRINT_PAGE="$WEBROOT/app/nc/\[nc_id\]/print/page.tsx"
RECORD_PAGE="$WEBROOT/app/nc/\[nc_id\]/record/page.tsx"

echo ""
echo "=== 対象ファイル確認 ==="
ls -la "$EDIT_PAGE" "$PRINT_PAGE" "$RECORD_PAGE"

echo ""
echo "=== パッチ適用 ==="
python3 ~/patch_scr03_edit.py
echo ""
python3 ~/patch_scr04_print.py
echo ""
python3 ~/patch_scr05_record.py

echo ""
echo "=== ビルド・再起動 ==="
echo "※ frontend はビルド不要（Next.js dev mode は自動リロード）"
echo "  変更が反映されない場合は: pm2 restart machcore-web"
