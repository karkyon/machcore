#!/usr/bin/env python3
"""
fix_v130_mach_rc.py — 残り3エラーを直接修正
L399/412: const mach 二重宣言 → L412 の重複を削除
L539: McProgram.update に rc が存在しない → McMachiningDetail.update の rc に変更
"""
import subprocess, sys, shutil, os

BASE    = '/home/karkyon/projects/machcore'
SVC     = f'{BASE}/apps/api/src/mc/mc.service.ts'
API_DIR = f'{BASE}/apps/api'

def read(p): return open(p,'r',encoding='utf-8').read()
def write(p,c): open(p,'w',encoding='utf-8').write(c)

svc = read(SVC)
orig = svc

# ─────────────────────────────────────────
# 1. const mach 二重宣言: L412の重複行を削除
# ─────────────────────────────────────────
# L399: const mach = (mc as any).machining ?? {};  ← 正しい（先に宣言）
# L412: const mach = (mc as any).machining ?? {};  ← 重複 → 削除
# この重複は "    const mach = ...\n    return this.prisma.$transaction" のパターン
old_dup = "    const mach = (mc as any).machining ?? {};\n    return this.prisma.$transaction(async (tx) => {\n      await tx.mcMachiningDetail.update("
new_dup = "    return this.prisma.$transaction(async (tx) => {\n      await tx.mcMachiningDetail.update("
if old_dup in svc:
    svc = svc.replace(old_dup, new_dup)
    print('[fix] OK: const mach 重複行削除')
else:
    print('[fix] SKIP: const mach dup pattern not found')

# ─────────────────────────────────────────
# 2. saveTooling(): McProgram.update の rc → McMachiningDetail.update の rc に変更
# ─────────────────────────────────────────
old_rc = """      // RC自動更新（ツーリング件数をmc_programsに反映）
      await tx.mcProgram.update({
        where: { id: mcId },
        data:  { rc: dto.items.length },
      });"""
new_rc = """      // RC自動更新（ツーリング件数をmc_machining_detailsに反映）
      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { rc: dto.items.length },
      });"""
if old_rc in svc:
    svc = svc.replace(old_rc, new_rc)
    print('[fix] OK: saveTooling() rc → McMachiningDetail.update')
else:
    print('[fix] SKIP: saveTooling() rc pattern not found')

# ─────────────────────────────────────────
# 書き込み
# ─────────────────────────────────────────
if svc != orig:
    write(SVC, svc)
    print('[fix] mc.service.ts 書き込み完了')
else:
    print('[fix] 変更なし')

# ─────────────────────────────────────────
# TSC確認
# ─────────────────────────────────────────
print('[fix] TSC 確認中...')
r = subprocess.run(['npx','tsc','--noEmit'], cwd=API_DIR, capture_output=True, text=True)
out = (r.stdout + r.stderr).strip()
if out:
    print(out[:5000])
else:
    print('[fix] TSCエラーなし ✅')

if r.returncode != 0:
    print(f'[fix] TSCエラー残存 (rc={r.returncode})')
    sys.exit(1)

# ─────────────────────────────────────────
# Build → PM2 → git push
# ─────────────────────────────────────────
print('[fix] nest build...')
b = subprocess.run(['npx','nest','build'], cwd=API_DIR, capture_output=True, text=True)
if b.returncode != 0:
    print('[fix] BUILD FAILED:')
    print(b.stderr[-3000:])
    sys.exit(1)
print('[fix] Build OK ✅')

subprocess.run(['pm2','restart','machcore-api'], cwd=BASE)
subprocess.run(['git','add','-A'], cwd=BASE)
subprocess.run(['git','commit','-m','fix(mc): TSC0 - mach dup/rc normalize complete [fix_v130_done]'], cwd=BASE)
subprocess.run(['git','push','origin','main'], cwd=BASE)
print('[fix] 完了 ✅')

# ゴミ片付け
for g in ['fix_v130_mach_rc.py','fix_v130_final.py','fix_v130_tsc_zero.py','fix_v130_rebuild.py']:
    p = f'{BASE}/{g}'
    if os.path.exists(p):
        shutil.move(p,'/tmp/')
        print(f'[fix] ゴミ移動: {p}')
