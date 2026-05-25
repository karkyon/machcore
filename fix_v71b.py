#!/usr/bin/env python3
"""
fix_v71b.py
===========
fix_v71.pyのビルド失敗を修正:
  1. app.module.ts の ScheduleModule import パターン修正
  2. @nestjs/schedule を pnpm で api ワークスペースにインストール
  3. ビルドコマンドを pnpm 対応に修正（npm run build --workspace=web → pnpm --filter web build）
"""
import subprocess, sys, os, re

ROOT = os.path.expanduser("~/projects/machcore")
API  = f"{ROOT}/apps/api/src"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ─────────────────────────────────────────────────────────────
# 1. app.module.ts ScheduleModule import 修正
#    patterが不一致だったので実際のimport行を確認して修正
# ─────────────────────────────────────────────────────────────
app_module = f"{API}/app.module.ts"
content = read(app_module)
print("=== app.module.ts 現在のimport部分 ===")
for i, line in enumerate(content.split('\n')[:20]):
    print(f"  {i+1}: {line}")
print("===")

# ScheduleModule が既に imports[] に追加されているか確認
if "ScheduleModule.forRoot()" in content:
    print("OK: ScheduleModule.forRoot() 既に追加済み")
else:
    print("WARN: ScheduleModule.forRoot() が見つからない")

# ScheduleModule の import文がない場合は追加
if "from '@nestjs/schedule'" not in content:
    # 最初のimport行を探して後に追加
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import '):
            insert_idx = i + 1
    lines.insert(insert_idx, "import { ScheduleModule } from '@nestjs/schedule';")
    write(app_module, '\n'.join(lines))
    print("OK: app.module.ts ScheduleModule import追加")
else:
    print("OK: ScheduleModule import 既に追加済み")

# ─────────────────────────────────────────────────────────────
# 2. @nestjs/schedule を pnpm で api ワークスペースにインストール
# ─────────────────────────────────────────────────────────────
# api/package.json に既にあるか確認
api_pkg = f"{ROOT}/apps/api/package.json"
api_pkg_content = read(api_pkg)
if "@nestjs/schedule" not in api_pkg_content:
    print("--- pnpm: @nestjs/schedule インストール ---")
    rc = run("pnpm --filter api add @nestjs/schedule", cwd=ROOT)
    if rc != 0:
        # fallback: 直接 package.json に追記
        print("WARN: pnpm install失敗。package.jsonに直接追加します")
        import json
        with open(api_pkg, 'r') as f:
            pkg = json.load(f)
        pkg['dependencies']['@nestjs/schedule'] = '^4.1.2'
        with open(api_pkg, 'w') as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)
        run("pnpm install --frozen-lockfile=false", cwd=ROOT)
else:
    print("OK: @nestjs/schedule 既にインストール済み")

# ─────────────────────────────────────────────────────────────
# 3. ビルド（pnpm対応）
# ─────────────────────────────────────────────────────────────
print("--- prisma generate ---")
run("pnpm --filter api exec prisma generate", cwd=ROOT)

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0:
    # フォールバック: apps/web で直接ビルド
    print("WARN: pnpm --filter失敗。apps/webで直接ビルド")
    rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")

if rc != 0:
    print("BUILD FAILED (web) — abort")
    sys.exit(1)

print("--- build api ---")
rc2 = run("pnpm --filter api build", cwd=ROOT)
if rc2 != 0:
    print("WARN: api build失敗。apps/apiで直接ビルド")
    rc2 = run("pnpm run build", cwd=f"{ROOT}/apps/api")

if rc2 != 0:
    print("BUILD FAILED (api) — abort")
    sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-api machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v71): タイムカードadminエンドポイント+RAW修正+UI改善+システム設定MC/NC分離+cron' && git push", cwd=ROOT)
print("DONE v71b")
