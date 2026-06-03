#!/bin/bash
# setup_https_v2.sh
# nginx を 8443(HTTPS) / 8080(HTTP) で起動
# 80/443 は docker-proxy が占有しているため回避
set -e

echo "=== [1] nginx 設定 (8443/8080) ==="
sudo tee /etc/nginx/sites-available/machcore > /dev/null << 'NGINX_EOF'
# HTTP 8080 → HTTPS 8443 リダイレクト
server {
    listen 8080;
    server_name 192.168.1.11;
    return 301 https://$host:8443$request_uri;
}

# HTTPS 8443
server {
    listen 8443 ssl;
    server_name 192.168.1.11;

    ssl_certificate     /etc/nginx/ssl/machcore.crt;
    ssl_certificate_key /etc/nginx/ssl/machcore.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 100m;
    proxy_read_timeout   300s;
    proxy_connect_timeout 60s;

    location / {
        proxy_pass         http://127.0.0.1:3010;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_cache_bypass $http_upgrade;
    }
}
NGINX_EOF

sudo ln -sf /etc/nginx/sites-available/machcore /etc/nginx/sites-enabled/machcore
sudo rm -f /etc/nginx/sites-enabled/default

echo "=== [2] 設定テスト ==="
sudo nginx -t

echo "=== [3] nginx 起動 ==="
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager | head -5

echo "=== [4] CORS 更新 ==="
MAIN_TS="/home/karkyon/projects/machcore/apps/api/src/main.ts"
if grep -q "https://192.168.1.11:8443" "$MAIN_TS"; then
  echo "  SKIP: 既に設定済み"
else
  sed -i "s|'http://192.168.1.11:3010',|'http://192.168.1.11:3010',\n      'https://192.168.1.11:8443',|" "$MAIN_TS"
  echo "  OK: CORS に https://192.168.1.11:8443 追加"
fi

echo "=== [5] API リビルド ==="
cd /home/karkyon/projects/machcore/apps/api
npx nest build 2>&1 | tail -5
pm2 restart machcore-api

echo "=== [6] git push ==="
cd /home/karkyon/projects/machcore
git add -A && git commit -m "feat: HTTPS via nginx:8443 (mkcert)" && git push origin main

echo ""
echo "=== 完了 ==="
echo "アクセスURL: https://192.168.1.11:8443"
echo ""
echo "【各PCでの証明書インポート手順】"
echo "1. omega-dev2 から rootCA.pem をコピー:"
echo "   $(mkcert -CAROOT)/rootCA.pem"
echo "2. Windowsの場合: .crt にリネームしてダブルクリック → 「信頼されたルート証明機関」にインポート"
