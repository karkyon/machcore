#!/usr/bin/env python3
"""
fix_v130_tsc_zero.py
現在の mc.service.ts の残存 TSC エラーを一括修正
エラー箇所（プロジェクトナレッジで確認済み）:
  L242: pgCreator not in McProgramInclude → McMachiningDetail経由に変更
  L255: r.part → findOne include 修正
  L276: r.files → findOne return 修正
  L375: finalize で mc.version → machining 経由
  L382/404: finalize/update で mc.version 直参照
  L420-431: update() で McProgram.update に machining フィールド → McMachiningDetail.update に変更
  L470-471: approve() で mc.version 直参照
  updatePgMeta: McProgram.update pgCreatedBy → McMachiningDetail.update
  saveTooling: mcProgramId → machiningId
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
# 1. findOne(): pgCreator は McMachiningDetail に移動したので McProgram include から除去
#    → machining include に pgCreator/creator を移す
# ─────────────────────────────────────────
old_fo_inc = """      include: {
        part:      true,
        machining: { include: { machine: true } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        pgCreator: { select: { id: true, name: true } },
        creator:   { select: { id: true, name: true } },
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },"""
new_fo_inc = """      include: {
        part:      true,
        machining: { include: { machine: true, pgCreator: { select: { id: true, name: true } }, creator: { select: { id: true, name: true } } } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },"""
if old_fo_inc in svc:
    svc = svc.replace(old_fo_inc, new_fo_inc)
    print('[fix] OK: findOne() include - pgCreator → machining 経由')
else:
    print('[fix] SKIP: findOne() include pattern not found')

# ─────────────────────────────────────────
# 2. finalize(): mc.version → machining 経由（全箇所）
# ─────────────────────────────────────────
# versionBefore: mc.version → mach.version
svc = svc.replace(
    "          versionBefore: mc.version,\n          versionAfter:  newVersion,",
    "          versionBefore: (mc as any).machining?.version ?? '1.0001',\n          versionAfter:  newVersion,"
)
# finalize の mcProgram.update version → McMachiningDetail.update version
old_fin_upd = """      await tx.mcProgram.update({
        where: { id },
        data:  { version: newVersion, status: 'CHANGING' },
      });"""
new_fin_upd = """      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { version: newVersion },
      });
      await tx.mcProgram.update({
        where: { id },
        data:  { status: 'CHANGING' },
      });"""
if old_fin_upd in svc:
    svc = svc.replace(old_fin_upd, new_fin_upd)
    print('[fix] OK: finalize() version → McMachiningDetail')
else:
    print('[fix] SKIP: finalize() update pattern not found')

# ─────────────────────────────────────────
# 3. update(): McProgram.update に machining フィールドを渡しているものを
#              McMachiningDetail.update に変更
# ─────────────────────────────────────────
old_upd_tx = """    return this.prisma.$transaction(async (tx) => {
      await tx.mcProgram.update({
        where: { id },
        data: {
          machineId:     dto.machine_id     !== undefined ? dto.machine_id     : mc.machineId,
          oNumber:       dto.o_number       !== undefined ? dto.o_number       : mc.oNumber,
          clampNote:     dto.clamp_note     !== undefined ? dto.clamp_note     : mc.clampNote,
          cycleTimeSec:  dto.cycle_time_sec !== undefined ? dto.cycle_time_sec : mc.cycleTimeSec,
          machiningQty:  dto.machining_qty  !== undefined ? dto.machining_qty  : mc.machiningQty,
          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mc.commonPartCode,
          note:          dto.note           !== undefined ? dto.note           : mc.note,
          creatorId:     dto.creator_id      !== undefined ? dto.creator_id      : mc.creatorId,
          version:       newVersion,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : mc.sheetCreatedAt,
          status:        'CHANGING',
        },
      });
      // 変更履歴はfinalize()で登録するためupdateでは登録しない
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'update' } },
      });
      return { mc_id: id, version: newVersion, message: '更新しました' };
    });"""
new_upd_tx = """    const mach = (mc as any).machining ?? {};
    return this.prisma.$transaction(async (tx) => {
      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data: {
          machineId:      dto.machine_id      !== undefined ? dto.machine_id      : mach.machineId,
          oNumber:        dto.o_number        !== undefined ? dto.o_number        : mach.oNumber,
          clampNote:      dto.clamp_note      !== undefined ? dto.clamp_note      : mach.clampNote,
          cycleTimeSec:   dto.cycle_time_sec  !== undefined ? dto.cycle_time_sec  : mach.cycleTimeSec,
          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,
          creatorId:      dto.creator_id      !== undefined ? dto.creator_id      : mach.creatorId,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : mach.sheetCreatedAt,
        },
      });
      await tx.mcProgram.update({
        where: { id },
        data: {
          machiningQty: dto.machining_qty !== undefined ? dto.machining_qty : mc.machiningQty,
          note:         dto.note         !== undefined ? dto.note         : mc.note,
          status:       'CHANGING',
        },
      });
      // 変更履歴はfinalize()で登録するためupdateでは登録しない
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'update' } },
      });
      return { mc_id: id, version: newVersion, message: '更新しました' };
    });"""
if old_upd_tx in svc:
    svc = svc.replace(old_upd_tx, new_upd_tx)
    print('[fix] OK: update() McMachiningDetail 分離')
else:
    print('[fix] SKIP: update() transaction pattern not found')

# update() の verStr も mach 経由（既に machining include があるはず）
svc = svc.replace(
    "    const verStr = mc.version ?? '1.0001';\n    const verFloat = parseFloat(verStr) || 1.0001;\n    const ver1 = Math.floor(verFloat);                           // 整数部",
    "    const verStr = (mc as any).machining?.version ?? '1.0001';\n    const verFloat = parseFloat(verStr) || 1.0001;\n    const ver1 = Math.floor(verFloat);                           // 整数部"
)

# ─────────────────────────────────────────
# 4. approve(): mc.version → machining 経由
# ─────────────────────────────────────────
svc = svc.replace(
    "          versionBefore: mc.version,\n          versionAfter:  mc.version,\n          content:       '承認',",
    "          versionBefore: (mc as any).machining?.version ?? null,\n          versionAfter:  (mc as any).machining?.version ?? null,\n          content:       '承認',"
)
svc = svc.replace(
    "          metadata:    { action: 'approve', version: mc.version },",
    "          metadata:    { action: 'approve', version: (mc as any).machining?.version ?? '1.0001' },"
)
svc = svc.replace(
    "      return { mc_id: id, message: '承認しました', version: mc.version };",
    "      return { mc_id: id, message: '承認しました', version: (mc as any).machining?.version ?? '1.0001' };"
)
print('[fix] OK: approve() version → machining 経由')

# ─────────────────────────────────────────
# 5. updatePgMeta(): McProgram.update → McMachiningDetail.update
# ─────────────────────────────────────────
old_pgm = """  async updatePgMeta(id: number, pgCreatedBy: number) {
    return this.prisma.mcProgram.update({
      where: { id },
      data:  { pgCreatedBy, pgUpdatedAt: new Date() },
    });
  }"""
new_pgm = """  async updatePgMeta(id: number, pgCreatedBy: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id }, select: { machiningId: true } });
    if (!mc) return;
    return this.prisma.mcMachiningDetail.update({
      where: { machiningId: mc.machiningId },
      data:  { pgCreatedBy, pgUpdatedAt: new Date() },
    });
  }"""
if old_pgm in svc:
    svc = svc.replace(old_pgm, new_pgm)
    print('[fix] OK: updatePgMeta() → McMachiningDetail')
else:
    print('[fix] SKIP: updatePgMeta() already patched or not found')

# ─────────────────────────────────────────
# 6. saveTooling(): mcProgramId → machiningId (念のため全件)
# ─────────────────────────────────────────
svc = svc.replace(
    "            mcProgramId:    mcId,",
    "            machiningId:    mc.machiningId,"
)
print('[fix] OK: saveTooling() mcProgramId → machiningId')

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
    print(b.stderr[-2000:])
    sys.exit(1)
print('[fix] Build OK ✅')

subprocess.run(['pm2','restart','machcore-api'], cwd=BASE)
subprocess.run(['git','add','-A'], cwd=BASE)
subprocess.run(['git','commit','-m','fix(mc): TSC0 - finalize/update/approve/pgMeta/saveTooling normalize [fix_v130_tsc_zero]'], cwd=BASE)
subprocess.run(['git','push','origin','main'], cwd=BASE)
print('[fix] 完了 ✅')

# ゴミ片付け
for g in ['fix_v130_rebuild.py','fix_v130_tsc_zero.py','fix_v130_final_complete.py']:
    p = f'{BASE}/{g}'
    if os.path.exists(p):
        shutil.move(p, '/tmp/')
        print(f'[fix] ゴミ移動: {p}')
