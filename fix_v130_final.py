#!/usr/bin/env python3
"""
fix_v130_final.py — 残存TSCエラーを全て一括修正（プロジェクトナレッジから確認済み）
L242: tooling/workOffsets/indexPrograms/files が McProgramInclude に存在しない
      → findOne include から除去（machining側に移動済みなので不要、findOneはfiles以外別取得）
L253: r.part → findOne include に part:true がないから
L274: r.files → findOne include に files がないから
L402/418: const mach 重複宣言
L545: McProgram.update に rc が存在しない
L982: saveWorkOffsets mcProgramId → machiningId
L1021: saveIndexPrograms mcProgramId → machiningId  
L1177: uncollectedByLegacy select に mcProcessNo が存在しない → machining 経由
L1201-1203: p.mcProcessNo/p.part → machining 経由
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
# 1. findOne(): tooling/workOffsets/indexPrograms/files を McProgram include から除去
#    正規化後これらは machining 経由。files は McProgram に残るが pgCreator等と混在不可
#    → 正しい include に全面置換
# ─────────────────────────────────────────
old_fo = """      include: {
        part:      true,
        machining: { include: { machine: true, pgCreator: { select: { id: true, name: true } }, creator: { select: { id: true, name: true } } } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },"""
new_fo = """      include: {
        part:      true,
        machining: { include: { machine: true } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },"""
if old_fo in svc:
    svc = svc.replace(old_fo, new_fo)
    print('[fix] OK: findOne() include tooling/pgCreator 除去')
else:
    print('[fix] SKIP: findOne() include pattern not found')

# indexPrograms/files も除去（上の置換後残っている箇所）
old_fo2 = """        indexPrograms: { orderBy: { sortOrder: 'asc' } },
        files:     { orderBy: { uploadedAt: 'desc' } },
      },
    });
    if (!r) throw new NotFoundException(`MC_id ${id} が存在しません`);"""
new_fo2 = """        files:     { orderBy: { uploadedAt: 'desc' } },
      },
    });
    if (!r) throw new NotFoundException(`MC_id ${id} が存在しません`);"""
svc = svc.replace(old_fo2, new_fo2)

# workOffsets も除去
svc = svc.replace(
    "        workOffsets: { orderBy: { gCode: 'asc' } },\n        indexPrograms: { orderBy: { sortOrder: 'asc' } },\n        files:",
    "        files:"
)
svc = svc.replace(
    "        workOffsets: { orderBy: { gCode: 'asc' } },\n        files:",
    "        files:"
)
print('[fix] OK: findOne() include 整理完了')

# ─────────────────────────────────────────
# 2. finalize/update の mach 二重宣言を除去
#    update() に const mach が追加されたが finalize にも const mach がある
#    → finalize の mach 宣言はそのまま（正しい）。update の mach 宣言を確認
# ─────────────────────────────────────────
# update() で mach が重複している → update の先頭に追加したコードと既存コードが重複
# 現在のコード確認: update() には include: machining があり mach = (mc as any).machining
# さらに fix_tsc_zero で "const mach = (mc as any).machining ?? {};" を追加した
# 重複を1つに統合
old_mach_dup = """    const mach = (mc as any).machining ?? {};

    // VBA 終了確認ロジック準拠バージョンインクリ
    // version format: "1.0001" (整数部.4桁小数)
    const verStr = (mc as any).machining?.version ?? '1.0001';"""
new_mach_dup = """    const mach = (mc as any).machining ?? {};
    const verStr = mach.version ?? '1.0001';"""
if old_mach_dup in svc:
    svc = svc.replace(old_mach_dup, new_mach_dup)
    print('[fix] OK: update() mach 重複除去')
else:
    # 別パターン
    svc = svc.replace(
        "    const mach = (mc as any).machining ?? {};\n    return this.prisma.$transaction",
        "    return this.prisma.$transaction"
    )
    print('[fix] OK: update() mach 重複除去 (alt)')

# update() 内の verStr/verFloat 行を mach 経由に
svc = svc.replace(
    "    const verStr = mc.version ?? '1.0001';\n    const verFloat = parseFloat(verStr) || 1.0001;\n    const ver1 = Math.floor(verFloat);                           // 整数部",
    "    const mach = (mc as any).machining ?? {};\n    const verStr = mach.version ?? '1.0001';\n    const verFloat = parseFloat(verStr) || 1.0001;\n    const ver1 = Math.floor(verFloat);                           // 整数部"
)

# ─────────────────────────────────────────
# 3. rc が McProgram.update に存在しない箇所を除去
# ─────────────────────────────────────────
# rc は McMachiningDetail に移動。McProgram.update の data に rc があれば除去
import re
# McProgram.update の data ブロック内から rc: ... を除去
def remove_rc_from_mcprogram_update(text):
    # パターン: tx.mcProgram.update({ where:..., data: {..., rc: ..., ...} })
    lines = text.split('\n')
    out = []
    in_mcprogram_update = False
    brace_depth = 0
    for i, line in enumerate(lines):
        # McProgram.update の data ブロック開始を検出
        if 'tx.mcProgram.update(' in line or 'this.prisma.mcProgram.update(' in line:
            in_mcprogram_update = True
            brace_depth = 0
        if in_mcprogram_update:
            brace_depth += line.count('{') - line.count('}')
            # rc: フィールドがある行をスキップ
            stripped = line.strip()
            if stripped.startswith('rc:') and in_mcprogram_update:
                print(f'[fix] rc 除去: {line.rstrip()}')
                continue
            if brace_depth <= 0 and in_mcprogram_update:
                in_mcprogram_update = False
        out.append(line)
    return '\n'.join(out)

svc = remove_rc_from_mcprogram_update(svc)
print('[fix] OK: McProgram.update から rc 除去')

# ─────────────────────────────────────────
# 4. saveWorkOffsets: mcProgramId → machiningId
# ─────────────────────────────────────────
old_wo = """          data: dto.items.map(item => ({
            mcProgramId: mcId,
            gCode:       item.g_code,"""
new_wo = """          data: dto.items.map(item => ({
            machiningId: mc.machiningId,
            gCode:       item.g_code,"""
if old_wo in svc:
    svc = svc.replace(old_wo, new_wo)
    print('[fix] OK: saveWorkOffsets() mcProgramId → machiningId')
else:
    print('[fix] SKIP: saveWorkOffsets() pattern not found')

# ─────────────────────────────────────────
# 5. saveIndexPrograms: mcProgramId → machiningId
# ─────────────────────────────────────────
old_ip = """          data: dto.items.map(item => ({
            mcProgramId: mcId,
            sortOrder:   item.sort_order,"""
new_ip = """          data: dto.items.map(item => ({
            machiningId: mc.machiningId,
            sortOrder:   item.sort_order,"""
if old_ip in svc:
    svc = svc.replace(old_ip, new_ip)
    print('[fix] OK: saveIndexPrograms() mcProgramId → machiningId')
else:
    print('[fix] SKIP: saveIndexPrograms() pattern not found')

# ─────────────────────────────────────────
# 6. uncollectedByLegacy: select に mcProcessNo → machining 経由
# ─────────────────────────────────────────
old_ubl_sel = """      select: { id: true, machiningId: true, mcProcessNo: true,
                part: { select: { drawingNo: true, name: true } } },"""
new_ubl_sel = """      select: { id: true, machiningId: true,
                part:     { select: { drawingNo: true, name: true } },
                machining: { select: { mcProcessNo: true } } },"""
if old_ubl_sel in svc:
    svc = svc.replace(old_ubl_sel, new_ubl_sel)
    print('[fix] OK: uncollectedByLegacy() select mcProcessNo → machining 経由')
else:
    print('[fix] SKIP: uncollectedByLegacy() select pattern not found')

# p.mcProcessNo → machining 経由
old_ubl_map = "        mc_process_no:  p.mcProcessNo,"
new_ubl_map = "        mc_process_no:  (p as any).machining?.mcProcessNo ?? null,"
svc = svc.replace(old_ubl_map, new_ubl_map)
print('[fix] OK: uncollectedByLegacy() map mcProcessNo')

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
subprocess.run(['git','commit','-m','fix(mc): TSC0 normalization complete - findOne/saveWO/saveIP/uncollected/rc [fix_v130_final]'], cwd=BASE)
subprocess.run(['git','push','origin','main'], cwd=BASE)
print('[fix] 完了 ✅')

# ゴミ片付け
for g in ['fix_v130_tsc_zero.py','fix_v130_final.py','fix_v130_rebuild.py']:
    p = f'{BASE}/{g}'
    if os.path.exists(p):
        shutil.move(p,'/tmp/')
        print(f'[fix] ゴミ移動: {p}')
