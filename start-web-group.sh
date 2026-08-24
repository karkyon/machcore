#!/bin/bash
# グループ会社インスタンス用 Web起動スクリプト（自社の start-web.sh と対になる）
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
cd /home/karkyon/projects/machcore-group/apps/web
exec node_modules/.bin/next start -p 3020 -H 0.0.0.0
