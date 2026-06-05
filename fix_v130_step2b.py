# fix_v130_step2b.py - 残存エラー一括修正

import subprocess, sys
from pathlib import Path

BASE = Path("/home/karkyon/projects/machcore")
API  = BASE / "apps/api/src"
MC_SVC   = API / "mc/mc.service.ts"
DASH_SVC = API / "dashboard/dashboard.service.ts"

def log(msg): print(f"[step2b] {msg}")
def patch(fp, old, new, desc):
    p = Path(fp); src = p.read_text(encoding="utf-8")
    if old not in src: log(f"SKIP: {desc}"); return False
    p.write_text(src.replace(old, new, 1), encoding="utf-8"); log(f"OK: {desc}"); return True

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dashboard.service.ts: uncollectedMc 完全書き換え
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
patch(DASH_SVC,
"""  async uncollectedMc() {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where: { workCollected: false },
      orderBy: [
        { mcProgram: { machine: { sortOrder: 'asc' } } },
        { printedAt: 'asc' },
      ],
      include: {
        operator:  { select: { name: true } },
        mcProgram: {
          include: {
            part:    { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },
            machine: { select: { machineCode: true, machineName: true, sortOrder: true } },
          },
        },
      },
    });""",
"""  async uncollectedMc() {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where: { workCollected: false },
      orderBy: [
        { printedAt: 'asc' },
      ],
      include: {
        operator:  { select: { name: true } },
        mcProgram: {
          include: {
            part:     { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },
            machining: { select: { machine: { select: { machineCode: true, machineName: true, sortOrder: true } } } },
          },
        },
      },
    });""",
"dashboard: uncollectedMc orderBy/include 修正")

# mcProgram.machine → mcProgram.machining.machine
patch(DASH_SVC,
"""      machine_code:  s.mcProgram.machine?.machineCode ?? null,
      machine_name:  s.mcProgram.machine?.machineName ?? null,
      machine_sort:  s.mcProgram.machine?.sortOrder ?? 999,""",
"""      machine_code:  s.mcProgram.machining?.machine?.machineCode ?? null,
      machine_name:  s.mcProgram.machining?.machine?.machineName ?? null,
      machine_sort:  s.mcProgram.machining?.machine?.sortOrder ?? 999,""",
"dashboard: machine → machining.machine")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 残存エラー修正
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── search の include に machine が残っている ──
patch(MC_SVC,
"""        include: {
          part:    { select: { drawingNo: true, name: true, clientName: true, partId: true } },
          machine: { select: { machineCode: true, machineName: true } },
        },""",
"""        include: {
          part:     { select: { drawingNo: true, name: true, clientName: true, partId: true } },
          machining: { select: { version: true, oNumber: true, cycleTimeSec: true, commonPartCode: true,
                                machine: { select: { machineCode: true, machineName: true } } } },
        },""",
"search: include machine → machining")

# search の map: r.machine → r.machining.machine (まだ旧コードが残っている場合)
patch(MC_SVC,
"""        machine_code:  r.machine?.machineCode ?? null,
        machine_name:  r.machine?.machineName ?? null,
        version:       r.version,
        status:        r.status,
        o_number:      r.oNumber,
        cycle_time_sec: r.cycleTimeSec,
        common_part_code: r.commonPartCode,""",
"""        machine_code:  r.machining?.machine?.machineCode ?? null,
        machine_name:  r.machining?.machine?.machineName ?? null,
        version:       r.machining?.version ?? '1.0001',
        status:        r.status,
        o_number:      r.machining?.oNumber ?? null,
        cycle_time_sec: r.machining?.cycleTimeSec ?? null,
        common_part_code: r.machining?.commonPartCode ?? null,""",
"search: map machine/version → machining 経由（2回目）")

# ── recent の select が旧形式のまま（Step2がSKIPした箇所を修正）──
patch(MC_SVC,
"""      select: {
        createdAt: true,
        user:      { select: { name: true } },
        mcProgram: {
          select: {
            id: true, legacyMcid: true, version: true, status: true, oNumber: true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },
      },""",
"""      include: {
        user:      { select: { name: true } },
        mcProgram: {
          include: {
            part:     { select: { drawingNo: true, name: true } },
            machining: { select: { version: true, oNumber: true,
                                   machine: { select: { machineCode: true } } } },
          },
        },
      },""",
"recent: select → include 変更")

# recent の map（旧形式が残っている場合）
patch(MC_SVC,
"""      mc_id:        l.mcProgram?.id,
      legacy_mcid:  l.mcProgram?.legacyMcid ?? null,
      drawing_no:   l.mcProgram?.part.drawingNo,
      part_name:    l.mcProgram?.part.name,
      machine_code: l.mcProgram?.machine?.machineCode,
      version:      l.mcProgram?.version,
      status:       l.mcProgram?.status,""",
"""      mc_id:        l.mcProgram?.id,
      legacy_mcid:  l.mcProgram?.legacyMcid ?? null,
      drawing_no:   l.mcProgram?.part?.drawingNo ?? null,
      part_name:    l.mcProgram?.part?.name ?? null,
      machine_code: l.mcProgram?.machining?.machine?.machineCode ?? null,
      version:      l.mcProgram?.machining?.version ?? null,
      status:       l.mcProgram?.status,""",
"recent: map 旧形式修正")

# ── findOne: include に machine が残っている ──
patch(MC_SVC,
"""      include: {
        part:      true,
        machine:   true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },""",
"""      include: {
        part:      true,
        machining: {
          include: {
            machine:   true,
            pgCreator: { select: { id: true, name: true } },
            creator:   { select: { id: true, name: true } },
            tooling:        { orderBy: { sortOrder: 'asc' } },
            workOffsets:    { orderBy: { gCode: 'asc' } },
            indexPrograms:  { orderBy: { sortOrder: 'asc' } },
          },
        },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        files:     { orderBy: { uploadedAt: 'desc' } },""",
"findOne: include 完全版（machine/files/tooling含む）")

# findOne の pgCreator/creator が McProgram に直接ついている残骸を削除
patch(MC_SVC,
"""        pgCreator: { select: { id: true, name: true } },
        creator:   { select: { id: true, name: true } },
        tooling:        { orderBy: { sortOrder: 'asc' } },
        workOffsets:    { orderBy: { gCode: 'asc' } },
        indexPrograms:  { orderBy: { sortOrder: 'asc' } },
        files:     { orderBy: { uploadedAt: 'desc' } },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        files:     { orderBy: { uploadedAt: 'desc' } },""",
"""        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        files:     { orderBy: { uploadedAt: 'desc' } },""",
"findOne: 重複include削除")

# ── findOne 内の processes select に part が必要 ──
patch(MC_SVC,
"""      select: {
        id: true, legacyMcid: true, machiningId: true, status: true,
        machining: { select: { version: true, mcProcessNo: true, machine: { select: { machineCode: true } } } },
      },""",
"""      select: {
        id: true, legacyMcid: true, machiningId: true, status: true,
        part:     { select: { drawingNo: true, name: true } },
        machining: { select: { version: true, mcProcessNo: true, machine: { select: { machineCode: true } } } },
      },""",
"findOne: processes select に part 追加")

# ── create: version が McProgramCreate に残っている場合 ──
patch(MC_SVC,
"""              legacyMcid:    dto.machining_id,
              registeredBy:  operatorId,
              status:        'NEW',
              version:       '1.0001',""",
"""              legacyMcid:    dto.machining_id,
              registeredBy:  operatorId,
              status:        'NEW',""",
"create: version 削除")

# create の changeHistory versionAfter
patch(MC_SVC,
"""              changeType:   'NEW_REGISTRATION',
              operatorId,
              versionAfter: created.version,
              content:      '新規登録',""",
"""              changeType:   'NEW_REGISTRATION',
              operatorId,
              versionAfter: '1.0001',
              content:      '新規登録',""",
"create: versionAfter 修正")

# ── createAndPrint: version が McProgramCreate に残っている場合 ──
patch(MC_SVC,
"""              legacyMcid:    machiningId,
              registeredBy:  operatorId,
              status:        'NEW',
              version:       '0.0001',""",
"""              legacyMcid:    machiningId,
              registeredBy:  operatorId,
              status:        'NEW',""",
"createAndPrint: version 削除")

# ── finalize の findUnique に machining がない場合 ──
patch(MC_SVC,
"""    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const verStr = (mc as any).machining?.version ?? '1.0001';""",
"""    const mc = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const verStr = (mc as any).machining?.version ?? '1.0001';""",
"finalize: machining include 追加")

# ── approve の version 参照 (mc.version が残っている場合) ──
patch(MC_SVC,
"""          versionBefore: mc.version,
          versionAfter:  mc.version,""",
"""          versionBefore: (mc as any).machining?.version ?? null,
          versionAfter:  (mc as any).machining?.version ?? null,""",
"approve: version 修正")

patch(MC_SVC,
"""      return { mc_id: id, message: '承認しました', version: mc.version };""",
"""      return { mc_id: id, message: '承認しました', version: (mc as any).machining?.version ?? '1.0001' };""",
"approve: return version 修正")

# ── update の rc フィールド（McMachiningDetail に rc がある）──
# 実際には rc は McMachiningDetail にあるので update に含めて OK
# エラー行585: update data に rc がある
patch(MC_SVC,
"""          hasIndexProgram: mach.hasIndexProgram ?? false,
          hasWorkOffset:   mach.hasWorkOffset   ?? false,
          rc:             mach.rc             ?? 0,
          pgIsFolder:     mach.pgIsFolder     ?? false,""",
"""          hasIndexProgram: mach.hasIndexProgram ?? false,
          hasWorkOffset:   mach.hasWorkOffset   ?? false,
          pgIsFolder:     mach.pgIsFolder     ?? false,""",
"update: rc 除去")

# ── createWorkRecord: machineId ──
patch(MC_SVC,
"""        machineId:        dto.machine_id    ?? mc.machineId ?? null,""",
"""        machineId:        dto.machine_id    ?? (mc as any).machining?.machineId ?? null,""",
"createWorkRecord: machineId 修正")

# createWorkRecord で machining include が必要
patch(MC_SVC,
"""    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    const jst""",
"""    const mc = await this.prisma.mcProgram.findUnique({
      where: { id: mcId },
      include: { machining: { select: { machineId: true } } },
    });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    const jst""",
"createWorkRecord: machining include 追加")

# ── getPrintData: 旧 include を完全に修正 ──
patch(MC_SVC,
"""  async getPrintData(mcId: number) {
    const r = await this.prisma.mcProgram.findUnique({
      where: { id: mcId },
      include: {
        part:    true,
        machine: true,
        registrar: { select: { name: true } },
        approver:  { select: { name: true } },
        tooling:   { orderB""",
"""  async getPrintData(mcId: number) {
    const r = await this.prisma.mcProgram.findUnique({
      where: { id: mcId },
      include: {
        part:    true,
        machining: {
          include: {
            machine:      true,
            tooling:      { orderBy: { sortOrder: 'asc' } },
            workOffsets:  { orderBy: { gCode: 'asc' } },
            indexPrograms: { orderBy: { sortOrder: 'asc' } },
            creator:      { select: { name: true } },
            pgCreator:    { select: { name: true } },
          },
        },
        registrar: { select: { name: true } },
        approver:  { select: { name: true } },
        getPrintData_SENTINEL: { orderB""",
"getPrintData: include 書き換え")

# getPrintData_SENTINEL 以降（旧 tooling/workOffsets 等）を削除
src = MC_SVC.read_text(encoding="utf-8")
if "getPrintData_SENTINEL" in src:
    # SENTINEL から include の閉じ括弧まで削除
    import re
    # 旧 include の残骸パターン
    src = re.sub(
        r"getPrintData_SENTINEL: \{ orderBy: \{ sortOrder: 'asc' \} \},\s*"
        r"workOffsets: \{ orderBy: \{ gCode: 'asc' \} \},\s*"
        r"indexPrograms: \{ orderBy: \{ sortOrder: 'asc' \} \},\s*"
        r"creator:\s*\{ select: \{ name: true \} \},\s*"
        r"pgCreator:\s*\{ select: \{ name: true \} \},\s*",
        "",
        src
    )
    # 万が一残っていれば別パターンで削除
    src = src.replace("getPrintData_SENTINEL: { orderBy: { sortOrder: 'asc' } },", "")
    MC_SVC.write_text(src, encoding="utf-8")
    log("OK: getPrintData: SENTINEL 削除")

# getPrintData の return 展開（旧コードが残っている場合のみ）
patch(MC_SVC,
"""    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);
    return r;
  }""",
"""    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);
    const mach = (r as any).machining ?? {};
    return {
      ...r,
      version:        mach.version        ?? '1.0001',
      machineId:      mach.machineId      ?? null,
      machine:        mach.machine        ?? null,
      oNumber:        mach.oNumber        ?? null,
      clampNote:      mach.clampNote      ?? null,
      cycleTimeSec:   mach.cycleTimeSec   ?? null,
      mcProcessNo:    mach.mcProcessNo    ?? null,
      commonPartCode: mach.commonPartCode ?? null,
      folder1:        mach.folder1        ?? null,
      folder2:        mach.folder2        ?? null,
      fileName:       mach.fileName       ?? null,
      hasIndexProgram: mach.hasIndexProgram ?? false,
      hasWorkOffset:   mach.hasWorkOffset   ?? false,
      rc:             mach.rc             ?? 0,
      pgIsFolder:     mach.pgIsFolder     ?? false,
      pgFolderName:   mach.pgFolderName   ?? null,
      pgCreatedBy:    mach.pgCreatedBy    ?? null,
      pgUpdatedAt:    mach.pgUpdatedAt    ?? null,
      creatorId:      mach.creatorId      ?? null,
      sheetCreatedAt: mach.sheetCreatedAt ?? null,
      creator:        mach.creator        ?? null,
      pgCreator:      mach.pgCreator      ?? null,
      tooling:        mach.tooling        ?? [],
      workOffsets:    mach.workOffsets    ?? [],
      indexPrograms:  mach.indexPrograms  ?? [],
    };
  }""",
"getPrintData: return machining フラット展開")

# generateRepeatSetupSheetPdf の version 参照（data.version → machining.version）
patch(MC_SVC,
"""      data: { mcProgramId: mcId, operatorId, version: data.version ?? null,""",
"""      data: { mcProgramId: mcId, operatorId, version: (data as any).machining?.version ?? (data as any).version ?? null,""",
"generateSetupSheetPdf: setupSheetLog version")

# ── TSC 確認 ──
log("TSC コンパイル確認中...")
result = subprocess.run(
    ["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"),
    capture_output=True, text=True
)
print(result.stdout)
print(result.stderr)
if result.returncode == 0:
    log("TSC OK: コンパイルエラー 0")
else:
    log(f"TSC エラー残存 (rc={result.returncode})")
