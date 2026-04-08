#!/bin/bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
cd /home/karkyon/projects/machcore/apps/web
exec node_modules/.bin/next start -p 3010 -H 0.0.0.0
