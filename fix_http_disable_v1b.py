#!/usr/bin/env python3
"""
fix_http_disable_v1b.py
TSCエラー修正 + next.config.ts SKIP対応
"""
import subprocess, sys, os, shutil

BASE     = "/home/karkyon/projects/machcore"
MAIN_TS  = f"{BASE}/apps/api/src/main.ts"
NEXT_CFG = f"{BASE}/apps/web/next.config.ts"

# ─── [1] main.ts: CORS callback 型修正 ─────────────────────────────
# TS2554: callback(null, true) → callback(null, true) は
# @types/cors の CorsOptionsDelegate の callback シグネチャに合わせる必要あり
# Fastify/NestJS の enableCors は関数形式で (origin, callback) を受け取るが
# 型定義上 callback(null, true) は callback(null, true) のまま OK の場合と
# callback(undefined, true) が必要な場合がある
# → シンプルに boolean 返す関数形式に変更
print("=== [1] main.ts CORS callback 型修正 ===")
with open(MAIN_TS, "r") as f:
    src = f.read()

OLD_CORS = """  app.enableCors({
    origin: (origin, callback) => {
      // 1. origin なし (curl / サーバサイド / Next.js rewrite 内部呼び出し)
      if (!origin) return callback(null, true);
      // 2. HTTPS 8443 (通常ブラウザアクセス)
      if (origin === 'https://192.168.1.11:8443') return callback(null, true);
      // 3. localhost 経由 (開発・PM2内部)
      if (/^https?:\\/\\/localhost(:\\d+)?$/.test(origin)) return callback(null, true);
      // 4. HTTP 3010 は Next.js→API の内部 rewrite のみ許可 (サーバサイド)
      //    ブラウザから直接 HTTP:3010 で API を叩くことを事実上防ぐ
      if (origin === 'http://192.168.1.11:3010') return callback(null, true);
      // 上記以外は拒否
      callback(new Error('CORS: origin not allowed'));
    },
    credentials: true,
  });"""

NEW_CORS = """  app.enableCors({
    // HTTPS:8443 (通常ブラウザ) + localhost (開発) + HTTP:3010 (Next.js内部rewrite) のみ許可
    origin: [
      'https://192.168.1.11:8443',
      'http://localhost:3010',
      'http://localhost:3011',
      'http://192.168.1.11:3010',  // Next.js→API内部rewrite用（サーバサイド）
    ],
    credentials: true,
  });"""

if OLD_CORS in src:
    src = src.replace(OLD_CORS, NEW_CORS)
    with open(MAIN_TS, "w") as f:
        f.write(src)
    print("  OK: CORS 配列形式に変更（TSC対応）")
else:
    print("  SKIP: アンカー不一致 — 手動確認要")
    sys.exit(1)

# ─── [2] next.config.ts: 実際の内容で更新 ─────────────────────────
print("=== [2] next.config.ts 更新 ===")
with open(NEXT_CFG, "r") as f:
    ncfg = f.read()

# allowedDevOrigins が既にあれば更新、なければ追加
if '"192.168.1.11"' in ncfg and 'allowedDevOrigins' in ncfg:
    ncfg = ncfg.replace(
        'allowedDevOrigins: ["192.168.1.11"]',
        'allowedDevOrigins: ["192.168.1.11", "https://192.168.1.11:8443"]'
    )
    with open(NEXT_CFG, "w") as f:
        f.write(ncfg)
    print("  OK: allowedDevOrigins に HTTPS 追加")
elif 'allowedDevOrigins' not in ncfg:
    # allowedDevOriginsが存在しない場合、serverExternalPackages行の後に追加
    ncfg = ncfg.replace(
        'const nextConfig: NextConfig = {',
        'const nextConfig: NextConfig = {\n  allowedDevOrigins: ["192.168.1.11", "https://192.168.1.11:8443"],'
    )
    with open(NEXT_CFG, "w") as f:
        f.write(ncfg)
    print("  OK: allowedDevOrigins 追加")
else:
    print("  INFO: 既に更新済み")

# ─── [3] tsc チェック ────────────────────────────────────────────
print("=== [3] API tsc チェック ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && npx tsc --noEmit 2>&1"],
    capture_output=True, text=True
)
if r.returncode != 0:
    print("  TSC エラー:"); print(r.stdout[-2000:]); sys.exit(1)
print("  OK: TypeCheck 通過")

# ─── [4] nest build ──────────────────────────────────────────────
print("=== [4] nest build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx nest build 2>&1"],
    capture_output=True, text=True
)
if r.returncode != 0:
    print(r.stdout[-1000:]); sys.exit(1)
print("  OK")

# ─── [5] Next.js build ───────────────────────────────────────────
print("=== [5] Next.js build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/web && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build 2>&1 | tail -15"],
    capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    sys.exit(1)
print("  OK")

# ─── [6] PM2 再起動 ──────────────────────────────────────────────
print("=== [6] PM2 再起動 ===")
subprocess.run(
    ["bash", "-c",
     "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && "
     "pm2 restart machcore-api --update-env && pm2 restart machcore-web"],
    capture_output=False
)

# ─── [7] クリーンアップ & git push ────────────────────────────────
print("=== [7] git push ===")
import glob
for s in glob.glob(f"{BASE}/fix_http_disable_v1.py"):
    try: os.remove(s)
    except: pass

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'fix: HTTP disable v1b - CORS array form, next.config HTTPS origin' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
