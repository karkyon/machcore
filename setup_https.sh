#!/bin/bash
# setup_https.sh
# omega-dev2 (Ubuntu 24.04) を HTTPS 化する
# nginx をリバースプロキシとして立て、mkcert でローカルCA証明書を発行
# アクセス: https://192.168.1.11 → machcore-web (3010)
#           https://192.168.1.11/api → machcore-api (3011)

set -e
echo "=== [1] nginx インストール ==="
sudo apt-get update -qq
sudo apt-get install -y nginx

echo "=== [2] mkcert インストール ==="
# mkcert バイナリをダウンロード
if ! command -v mkcert &>/dev/null; then
  curl -Lo /tmp/mkcert https://dl.filippo.io/mkcert/latest?for=linux/amd64
  chmod +x /tmp/mkcert
  sudo mv /tmp/mkcert /usr/local/bin/mkcert
fi
mkcert --version

echo "=== [3] ローカルCA インストール ==="
mkcert -install

echo "=== [4] 証明書発行 ==="
sudo mkdir -p /etc/nginx/ssl
cd /tmp
mkcert 192.168.1.11 localhost 127.0.0.1
# 生成されたファイルを /etc/nginx/ssl/ にコピー
sudo cp /tmp/192.168.1.11+2.pem     /etc/nginx/ssl/machcore.crt
sudo cp /tmp/192.168.1.11+2-key.pem /etc/nginx/ssl/machcore.key
sudo chmod 600 /etc/nginx/ssl/machcore.key
echo "  OK: 証明書を /etc/nginx/ssl/ に配置"

echo "=== [5] nginx 設定 ==="
sudo tee /etc/nginx/sites-available/machcore > /dev/null << 'NGINX_EOF'
# MachCore - HTTP → HTTPS リダイレクト
server {
    listen 80;
    server_name 192.168.1.11;
    return 301 https://$host$request_uri;
}

# MachCore - HTTPS
server {
    listen 443 ssl;
    server_name 192.168.1.11;

    ssl_certificate     /etc/nginx/ssl/machcore.crt;
    ssl_certificate_key /etc/nginx/ssl/machcore.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # タイムアウト（大きめのファイルアップロード対応）
    client_max_body_size 100m;
    proxy_read_timeout   300s;
    proxy_connect_timeout 60s;

    # Web フロントエンド (Next.js port 3010)
    location / {
        proxy_pass         http://127.0.0.1:3010;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # API (NestJS port 3011) - /api パスはそのままAPIへ
    # ※ Next.js の rewrite と重複しないよう直接 3011 には向けない
    # Next.js 側が /api を localhost:3011 にリライトするため不要
}
NGINX_EOF

# sites-enabled にシンボリックリンク
sudo ln -sf /etc/nginx/sites-available/machcore /etc/nginx/sites-enabled/machcore
# デフォルト設定を無効化（ポート競合回避）
sudo rm -f /etc/nginx/sites-enabled/default

echo "=== [6] nginx 設定テスト ==="
sudo nginx -t

echo "=== [7] nginx 起動 / 再起動 ==="
sudo systemctl enable nginx
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager | head -10

echo "=== [8] CORS 更新: API が https://192.168.1.11 を許可 ==="
# main.ts の CORS に https://192.168.1.11 を追加
MAIN_TS="/home/karkyon/projects/machcore/apps/api/src/main.ts"
if grep -q "https://192.168.1.11" "$MAIN_TS"; then
  echo "  SKIP: 既に設定済み"
else
  sed -i "s|'http://192.168.1.11:3010',|'http://192.168.1.11:3010',\n      'https://192.168.1.11',|" "$MAIN_TS"
  echo "  OK: CORS に https://192.168.1.11 追加"
fi

echo "=== [9] API リビルド ==="
cd /home/karkyon/projects/machcore/apps/api
npx nest build 2>&1 | tail -5
pm2 restart machcore-api

echo ""
echo "=== 完了 ==="
echo ""
echo "【次のステップ】"
echo "1. 各PCで mkcert のルートCA証明書をインストールしてください"
echo "   (rootCA.pem の場所: \$(mkcert -CAROOT)/rootCA.pem)"
echo ""
echo "2. アクセスURL:"
echo "   https://192.168.1.11  ← 新しいHTTPS URL"
echo "   http://192.168.1.11:3010  ← 旧HTTP（引き続き動作、httpsリダイレクト）"
echo ""
echo "3. File System Access API (showSaveFilePicker) は HTTPS 接続時のみ有効です"
