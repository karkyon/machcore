#!/usr/bin/env python3
"""
fix_v131_frontend.py
正規化後のAPI構造に合わせてフロントエンドを修正する。

戦略: mc.service.ts の findOne() return で machining フィールドを平坦化して
      フロントが今まで通り d.version / d.machine / d.oNumber 等を参照できるようにする。
      同時に api.ts の McDetail / McProcessItem / McCommonGroupItem 型も整合させる。

修正箇所:
  1. mc.service.ts findOne() return: machining 配下フィールドを展開して返す
  2. apps/web/lib/api.ts: McDetail に machining 型追加、McProcessItem/McCommonGroupItem 修正
"""
import subprocess, sys, shutil, os

BASE     = '/home/karkyon/projects/machcore'
SVC      = f'{BASE}/apps/api/src/mc/mc.service.ts'
API_TS   = f'{BASE}/apps/web/lib/api.ts'
API_DIR  = f'{BASE}/apps/api'
WEB_DIR  = f'{BASE}/apps/web'

def read(p): return open(p,'r',encoding='utf-8').read()
def write(p,c): open(p,'w',encoding='utf-8').write(c)

# ═══════════════════════════════════════════════════
# 1. mc.service.ts findOne(): return で machining を平坦化
#    フロントは引き続き d.version / d.machine / d.oNumber 等を直参照できる
# ═══════════════════════════════════════════════════
svc = read(SVC)

old_fo_return = """    return {
      ...r,
      files: r.files.map(f => ({
        ...f,
        file_type:      f.fileType,
        original_name:  f.originalName,
        stored_name:    f.storedName,
        mime_type:      f.mimeType,
        file_path:      f.filePath,
        thumbnail_path: f.thumbnailPath,
        file_size:      f.fileSize,
        uploaded_by:    f.uploadedBy,
        uploaded_at:    f.uploadedAt,
      })),
      processes,
      commonGroup,
    };"""
new_fo_return = """    const mach = (r as any).machining ?? {};
    return {
      ...r,
      // machining フィールドを平坦化（フロント後方互換）
      version:        mach.version        ?? '1.0001',
      machine:        mach.machine        ?? null,
      oNumber:        mach.oNumber        ?? null,
      clampNote:      mach.clampNote      ?? null,
      cycleTimeSec:   mach.cycleTimeSec   ?? null,
      mcProcessNo:    mach.mcProcessNo    ?? null,
      fileName:       mach.fileName       ?? null,
      folder1:        mach.folder1        ?? null,
      folder2:        mach.folder2        ?? null,
      hasIndexProgram: mach.hasIndexProgram ?? false,
      hasWorkOffset:  mach.hasWorkOffset  ?? false,
      rc:             mach.rc             ?? 0,
      pgIsFolder:     mach.pgIsFolder     ?? false,
      pgFolderName:   mach.pgFolderName   ?? null,
      pgCreatedBy:    mach.pgCreatedBy    ?? null,
      pgUpdatedAt:    mach.pgUpdatedAt    ?? null,
      creatorId:      mach.creatorId      ?? null,
      sheetCreatedAt: mach.sheetCreatedAt ?? null,
      commonPartCode: mach.commonPartCode ?? null,
      pgCreator:      mach.pgCreator      ?? null,
      creator:        mach.creator        ?? null,
      tooling:        (r as any).machining?.tooling       ?? [],
      workOffsets:    (r as any).machining?.workOffsets   ?? [],
      indexPrograms:  (r as any).machining?.indexPrograms ?? [],
      files: r.files.map(f => ({
        ...f,
        file_type:      f.fileType,
        original_name:  f.originalName,
        stored_name:    f.storedName,
        mime_type:      f.mimeType,
        file_path:      f.filePath,
        thumbnail_path: f.thumbnailPath,
        file_size:      f.fileSize,
        uploaded_by:    f.uploadedBy,
        uploaded_at:    f.uploadedAt,
      })),
      processes: processes.map((p: any) => ({
        ...p,
        version:     p.machining?.version     ?? '1.0001',
        mcProcessNo: p.machining?.mcProcessNo ?? null,
        machine:     p.machining?.machine     ?? null,
      })),
      commonGroup: commonGroup.map((cg: any) => ({
        ...cg,
        version: cg.machining?.version ?? '1.0001',
      })),
    };"""

if old_fo_return in svc:
    svc = svc.replace(old_fo_return, new_fo_return)
    print('[fix] OK: findOne() return 平坦化')
else:
    print('[fix] SKIP: findOne() return pattern not found')

# findOne の include に tooling/workOffsets/indexPrograms/pgCreator/creator を追加
# （平坦化して返すため machining 経由で取得する必要がある）
old_fo_inc = """      include: {
        part:      true,
        machining: { include: { machine: true } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        files:     { orderBy: { uploadedAt: 'desc' } },
      },"""
new_fo_inc = """      include: {
        part:      true,
        machining: { include: {
          machine:      true,
          pgCreator:    { select: { id: true, name: true } },
          creator:      { select: { id: true, name: true } },
          tooling:      { orderBy: { sortOrder: 'asc' } },
          workOffsets:  { orderBy: { gCode: 'asc' } },
          indexPrograms: { orderBy: { sortOrder: 'asc' } },
        } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        files:     { orderBy: { uploadedAt: 'desc' } },
      },"""
if old_fo_inc in svc:
    svc = svc.replace(old_fo_inc, new_fo_inc)
    print('[fix] OK: findOne() include 拡張')
else:
    print('[fix] SKIP: findOne() include pattern not found')

write(SVC, svc)
print('[fix] mc.service.ts 書き込み完了')

# ═══════════════════════════════════════════════════
# 2. apps/web/lib/api.ts の型定義を正規化後に合わせる
#    - McDetail: machining フィールド追加（任意）、既存フィールドはそのまま維持
#    - McProcessItem: machining 経由フィールド追加
#    - McCommonGroupItem: machining 経由 version 追加
# ═══════════════════════════════════════════════════
api = read(API_TS)

# McCommonGroupItem: version は machining 経由で返ってくる（平坦化済み）→型そのまま維持
# McDetail: machining ネストオブジェクトを追加（オプショナル）
old_mcdetail = """export type McDetail = {
  id:             number;
  machiningId:    number;
  status:         McStatus;
  version:        string;
  oNumber:        string | null;
  clampNote:      string | null;
  cycleTimeSec:   number | null;
  machiningQty:   number | null;
  commonPartCode: string | null;
  note:           string | null;
  legacyMcid:     number | null;
  mcProcessNo:    number | null;
  registeredAt:   string;
  approvedAt:     string | null;
  rc:             number;
  hasIndexProgram: boolean;
  hasWorkOffset:   boolean;
  pgIsFolder:     boolean;
  pgFolderName:   string | null;
  pgCreatedBy:    number | null;
  pgUpdatedAt:    string | null;
  part:    { drawingNo: string; name: string; clientName: string | null; partId: string | null; mainModel: string | null };
  machine: { machineCode: string; machineName: string } | null;
  registrar: { name: string };
  approver:  { name: string } | null;
  pgCreator: { name: string } | null;
  creatorId:      number | null;
  sheetCreatedAt: string | null;
  creator:        { name: string } | null;
  tooling:      McTooling[];
  workOffsets:  McWorkOffset[];
  indexPrograms: McIndexProgram[];
  files:        McFile[];
  processes:    McProcessItem[];
  commonGroup:  McCommonGroupItem[];
};"""
new_mcdetail = """export type McDetail = {
  id:             number;
  machiningId:    number;
  status:         McStatus;
  version:        string;
  oNumber:        string | null;
  clampNote:      string | null;
  cycleTimeSec:   number | null;
  machiningQty:   number | null;
  commonPartCode: string | null;
  note:           string | null;
  legacyMcid:     number | null;
  mcProcessNo:    number | null;
  registeredAt:   string;
  approvedAt:     string | null;
  rc:             number;
  hasIndexProgram: boolean;
  hasWorkOffset:   boolean;
  pgIsFolder:     boolean;
  pgFolderName:   string | null;
  pgCreatedBy:    number | null;
  pgUpdatedAt:    string | null;
  fileName:       string | null;
  folder1:        string | null;
  folder2:        string | null;
  part:    { drawingNo: string; name: string; clientName: string | null; partId: string | null; mainModel: string | null };
  machine: { machineCode: string; machineName: string } | null;
  registrar: { name: string };
  approver:  { name: string } | null;
  pgCreator: { name: string } | null;
  creatorId:      number | null;
  sheetCreatedAt: string | null;
  creator:        { name: string } | null;
  tooling:      McTooling[];
  workOffsets:  McWorkOffset[];
  indexPrograms: McIndexProgram[];
  files:        McFile[];
  processes:    McProcessItem[];
  commonGroup:  McCommonGroupItem[];
  /** 正規化後の machining ネスト（平坦化フィールドのソース）*/
  machining?: {
    version: string;
    machine: { machineCode: string; machineName: string } | null;
    oNumber: string | null;
    clampNote: string | null;
    cycleTimeSec: number | null;
    mcProcessNo: number | null;
    fileName: string | null;
    folder1: string | null;
    folder2: string | null;
    hasIndexProgram: boolean;
    hasWorkOffset: boolean;
    rc: number;
    pgIsFolder: boolean;
    pgFolderName: string | null;
    pgCreatedBy: number | null;
    pgUpdatedAt: string | null;
    creatorId: number | null;
    sheetCreatedAt: string | null;
    commonPartCode: string | null;
    pgCreator: { id: number; name: string } | null;
    creator:   { id: number; name: string } | null;
  } | null;
};"""

if old_mcdetail in api:
    api = api.replace(old_mcdetail, new_mcdetail)
    print('[fix] OK: McDetail 型更新')
else:
    print('[fix] SKIP: McDetail 型 pattern not found')

# McProcessItem: machining 経由フィールドをオプションで追加
old_mpi = """export type McProcessItem = {
  id:           number;
  legacyMcid:   number | null;
  machiningId:  number;
  mcProcessNo:  number | null;
  version:      string;
  status:       McStatus;
  machine:      { machineC"""
# 型全体の末尾まで取得するため、閉じ括弧を探す
# McProcessItem の全体を置換
import re
mpi_match = re.search(
    r'export type McProcessItem = \{[^}]+\};',
    api, re.DOTALL
)
if mpi_match:
    old_mpi_full = mpi_match.group(0)
    new_mpi_full = """export type McProcessItem = {
  id:           number;
  legacyMcid:   number | null;
  machiningId:  number;
  mcProcessNo:  number | null;
  version:      string;
  status:       McStatus;
  machine:      { machineCode: string } | null;
  /** 正規化後のネスト（平坦化済みフィールドのソース） */
  machining?:   { version: string; mcProcessNo: number | null; machine: { machineCode: string } | null } | null;
};"""
    api = api.replace(old_mpi_full, new_mpi_full)
    print('[fix] OK: McProcessItem 型更新')
else:
    print('[fix] SKIP: McProcessItem 型 pattern not found')

write(API_TS, api)
print('[fix] api.ts 書き込み完了')

# ═══════════════════════════════════════════════════
# TSC (API) 確認
# ═══════════════════════════════════════════════════
print('[fix] API TSC 確認中...')
r = subprocess.run(['npx','tsc','--noEmit'], cwd=API_DIR, capture_output=True, text=True)
out = (r.stdout + r.stderr).strip()
if out:
    print(out[:4000])
if r.returncode != 0:
    print(f'[fix] API TSCエラー残存 (rc={r.returncode})')
    sys.exit(1)
print('[fix] API TSC OK ✅')

# ═══════════════════════════════════════════════════
# next build
# ═══════════════════════════════════════════════════
print('[fix] next build...')
b = subprocess.run(['npx','next','build'], cwd=WEB_DIR, capture_output=True, text=True)
out = (b.stdout + b.stderr)
# TypeScript エラーのみ抽出
ts_errors = [l for l in out.split('\n') if 'error TS' in l or 'Type error' in l or 'error:' in l.lower()]
if ts_errors:
    print('\n'.join(ts_errors[:50]))
if b.returncode != 0:
    print(f'[fix] next build FAILED (rc={b.returncode})')
    sys.exit(1)
print('[fix] next build OK ✅')

# ═══════════════════════════════════════════════════
# nest build → PM2 → git push
# ═══════════════════════════════════════════════════
print('[fix] nest build...')
nb = subprocess.run(['npx','nest','build'], cwd=API_DIR, capture_output=True, text=True)
if nb.returncode != 0:
    print(nb.stderr[-2000:])
    sys.exit(1)
print('[fix] nest build OK ✅')

subprocess.run(['pm2','restart','machcore-api'], cwd=BASE)
subprocess.run(['pm2','restart','machcore-web'], cwd=BASE)
subprocess.run(['git','add','-A'], cwd=BASE)
subprocess.run(['git','commit','-m','fix(frontend): normalize McDetail type + findOne flatten machining fields [fix_v131]'], cwd=BASE)
subprocess.run(['git','push','origin','main'], cwd=BASE)
print('[fix] 完了 ✅')

# ゴミ片付け
for g in ['fix_v131_frontend.py']:
    p = f'{BASE}/{g}'
    if os.path.exists(p):
        shutil.move(p, '/tmp/')
        print(f'[fix] ゴミ移動: {p}')
