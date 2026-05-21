#!/usr/bin/env python3
import os, sys

ROOT = os.path.expanduser("~/projects/machcore")
page = os.path.join(ROOT, "apps/web/app/page.tsx")

with open(page) as f:
    content = f.read()

# users fetch useEffect を削除
OLD_EFFECT = """
  useEffect(() => {
    const _API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
    fetch(`${_API}/users`).then(r => r.json()).then(d => setUsers(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);"""
if OLD_EFFECT in content:
    content = content.replace(OLD_EFFECT, "", 1)
    print("OK: users fetch useEffect 削除")
else:
    print("WARN: users fetch useEffect が見つかりません")
    for i, line in enumerate(content.split('\n')):
        if 'setUsers' in line:
            print(f"  L{i+1}: {line.rstrip()}")

# authApi, mcApi, ncApi, usersApi の不要 import も整理
# ただし authApi は AuthModal 内部で使うので不要、import 行から削除
OLD_IMPORT = 'import { authApi, mcApi, ncApi, usersApi } from "@/lib/api";'
if OLD_IMPORT in content:
    content = content.replace(OLD_IMPORT, "", 1)
    print("OK: 不要 api import 削除")

with open(page, 'w') as f:
    f.write(content)

print("\n✅ 完了")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
