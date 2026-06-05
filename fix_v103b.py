#!/usr/bin/env python3
# fix_v103b.py — AuthModal props修正
# common-parts/page.tsx の AuthModal 呼び出しを正しいprops形式に修正

import os, subprocess, sys
BASE = os.path.expanduser("~/projects/machcore")

def r(p):
    with open(p, encoding="utf-8") as f: return f.read()

def w(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
    print(f"  WRITE {p.replace(BASE+'/','')}")

def patch(p, old, new, tag=""):
    c = r(p)
    if old not in c:
        print(f"  SKIP [{tag}] not found")
        return False
    w(p, c.replace(old, new, 1))
    print(f"  PATCH [{tag}]")
    return True

def run(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd or BASE,
                         capture_output=True, text=True)
    if res.stdout: print(res.stdout[-4000:])
    if res.stderr: print(res.stderr[-2000:])
    return res.returncode

# ── 1. common-parts/page.tsx: AuthModal props修正 ──────────────
CP = f"{BASE}/apps/web/app/mc/common-parts/page.tsx"

# AuthModal を正しいprops形式に修正
# onClose → onCancel + onSuccess、sessionType追加
patch(CP,
  "      <AuthModal isOpen={authOpen} onClose={() => setAuthOpen(false)} />",
  "      {authOpen && (\n        <AuthModal isOpen={true} sessionType=\"edit\"\n          onSuccess={() => setAuthOpen(false)}\n          onCancel={() => setAuthOpen(false)} />\n      )}",
  "common-parts AuthModal props fix")

# ── 2. Web ビルド ──────────────────────────────────────────────
print("\n=== BUILD: Web ===")
rc = run("cd apps/web && npx next build 2>&1")
if rc != 0:
    print("WEB BUILD FAILED — abort")
    sys.exit(1)

# ── 3. PM2再起動 ──────────────────────────────────────────────
print("\n=== PM2 restart ===")
run("pm2 restart machcore-api machcore-web")

# ── 4. git push ───────────────────────────────────────────────
print("\n=== Git push ===")
run("git add -A")
run('git commit -m "fix: 共通部品ページ AuthModal props修正 (fix_v103b)"')
run("git push origin main")

# ── 5. クリーンアップ ─────────────────────────────────────────
try: os.remove("/tmp/fix_v103b.py"); print("  cleaned /tmp/fix_v103b.py")
except: pass

print("\n✅ fix_v103b 完了")
