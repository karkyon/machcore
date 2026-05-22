#!/usr/bin/env python3
# coding: utf-8
"""
fix_v32b.py — prisma generate → API tsc → pm2 restart → git push
  (fix_v32.pyでschema.prismaは修正済み。prisma generateが未実行だったためPrismaクライアントに型が存在しない)
"""
import subprocess, sys

ROOT = "/home/karkyon/projects/machcore"

print("--- prisma generate ---")
r = subprocess.run(
    f"cd {ROOT}/apps/api && npx prisma generate",
    shell=True, capture_output=True, text=True
)
print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-1000:])
    print("PRISMA GENERATE FAILED — abort")
    sys.exit(1)

print("\n--- API npx tsc ---")
r2 = subprocess.run(
    f"cd {ROOT}/apps/api && npx tsc --noEmit",
    shell=True, capture_output=True, text=True
)
print(r2.stdout or "(no output)")
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-2000:])
    print("API TSC FAILED — abort")
    sys.exit(1)

print("\n--- Web npm run build ---")
r3 = subprocess.run(
    f"cd {ROOT}/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
out = r3.stdout
print(out[-4000:] if len(out) > 4000 else out)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-2000:])
    print("WEB BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart ---")
r4 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    f'cd {ROOT} && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web && '
    'pm2 restart machcore-api',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r4.stdout)

print("\n--- git commit & push ---")
r5 = subprocess.run(
    f"cd {ROOT} && "
    "git add -A && "
    "git commit -m 'feat: prisma generate prg_man/prg_time_min/prg_plas Prismaクライアント更新 v32b' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r5.stdout)
if r5.returncode != 0:
    print("STDERR:", r5.stderr[-500:])

print("\nDONE")
