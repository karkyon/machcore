#!/bin/bash
set -e
cd ~/projects/machcore

echo "=== パッチ適用開始 ==="

# パッチ1: SCR-01 管理者エリア
bash ~/projects/machcore/patch_01_search.sh
echo "1/3 SCR-01 完了"

# パッチ2: SCR-02 PG→USB AUTH連携
bash ~/projects/machcore/patch_02_ncdetail.sh
echo "2/3 SCR-02 完了"

# パッチ3: SCR-04 図を含めるPDF埋め込み
bash ~/projects/machcore/patch_03_ncservice.sh
echo "3/3 SCR-04 完了"

echo ""
echo "=== API ビルド ==="
cd ~/projects/machcore/apps/api
pnpm run build 2>&1 | tail -5

echo ""
echo "=== PM2 API 再起動 ==="
cd ~/projects/machcore
pm2 restart machcore-api
sleep 5
pm2 list | grep machcore-api

echo ""
echo "=== Git コミット ==="
cd ~/projects/machcore
git add -A
git commit -m "feat: SCR-01 admin area, SCR-02 USB AUTH, SCR-04 include_drawings PDF embed"
git push origin main

echo ""
echo "=== 完了 ==="
pm2 list | grep -E "machcore|online|error"
