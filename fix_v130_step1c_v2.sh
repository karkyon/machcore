#!/bin/bash
# Step1c: Prisma generate + マイグレーション状態マーク + TSC確認
set -e
cd /home/karkyon/projects/machcore/apps/api

echo "=== Step1c: Prisma generate ==="
# .env を明示的に指定して generate
DATABASE_URL="postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public" \
  npx prisma generate

echo ""
echo "=== マイグレーション履歴に登録（DBは直接適用済み） ==="
# 生成されたマイグレーションディレクトリ名を取得
MIG_NAME=$(ls prisma/migrations/ | grep normalize_mc_machining_details | tail -1)
if [ -n "$MIG_NAME" ]; then
  echo "マイグレーション名: $MIG_NAME"
  DATABASE_URL="postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public" \
    npx prisma migrate resolve --applied "$MIG_NAME" || echo "resolve失敗（既に登録済みの可能性あり、無視）"
else
  echo "マイグレーションディレクトリなし（スキップ）"
fi

echo ""
echo "=== TSCコンパイルエラー確認 ==="
npx tsc --noEmit 2>&1 | head -60 || true

echo ""
echo "=== Step1c 完了 ==="
