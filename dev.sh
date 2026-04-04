#!/bin/bash
# MachCore 開発用: TypeCheck + pm2 restart + 疎通確認
set -e

PM2=/home/karkyon/.nvm/versions/node/v20.20.0/bin/pm2
PNPX=/home/karkyon/.nvm/versions/node/v20.20.0/bin/npx
ROOT=~/projects/machcore

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " MachCore dev.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "[1/4] API TypeCheck & Build..."
cd "$ROOT/apps/api" && $PNPX tsc --noEmit
echo "✅ API OK"

echo "[2/4] Web TypeCheck..."
cd "$ROOT/apps/web" && $PNPX tsc --noEmit
echo "✅ Web OK"

echo "[3/4] pm2 restart machcore-api..."
$PM2 restart machcore-api
sleep 5

echo "[4/4] 疎通確認..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3011/api/nc/search?key=folder&q=&limit=1)
if [ "$HTTP" = "200" ]; then
  echo "✅ API 応答: HTTP $HTTP"
else
  echo "⚠️  API 応答: HTTP $HTTP"
fi

echo ""
$PM2 list
echo ""
echo "✅ 完了"
