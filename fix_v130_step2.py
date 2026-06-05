# fix_v130_step2.py
# Step2: mc.service.ts / mc-files.service.ts / dashboard.service.ts の正規化対応
# 正規化後のスキーマに合わせて全メソッドを修正
# 変更方針:
#   McProgram の machine/version/oNumber 等 → machining: McMachiningDetail 経由でアクセス
#   mcProgramId → machiningId (tooling/WO/IP)
#   pgUpdatedAt/pgCreatedBy → McMachiningDetail に移動

import subprocess, sys, shutil
from pathlib import Path

BASE = Path("/home/karkyon/projects/machcore")
API  = BASE / "apps/api/src"

def log(msg): print(f"[step2] {msg}")

def patch(filepath, old, new, desc):
    p = Path(filepath)
    src = p.read_text(encoding="utf-8")
    if old not in src:
        log(f"SKIP ({desc}): 置換元が見つかりません")
        return False
    p.write_text(src.replace(old, new, 1), encoding="utf-8")
    log(f"OK: {desc}")
    return True

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MC_SVC = API / "mc/mc.service.ts"
shutil.copy(MC_SVC, str(MC_SVC) + ".bak_v130")
log("mc.service.ts バックアップ完了")

# ── 1. search: r.machine / r.version / r.oNumber 等 → r.machining.xxx ──
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
"search: r.machine/version/oNumber → r.machining.xxx")

# ── 2. recent: OperationLog の select で mcProgram.machine / mcProgram.version ──
patch(MC_SVC,
"""        mcProgram: {
          select: {
            id: true, legacyMcid: true, version: true, status: true, oNumber: true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },""",
"""        mcProgram: {
          select: {
            id: true, legacyMcid: true, status: true,
            part:     { select: { drawingNo: true, name: true } },
            machining: { select: { version: true, oNumber: true, machine: { select: { machineCode: true } } } },
          },
        },""",
"recent: OperationLog select 修正")

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
      drawing_no:   l.mcProgram?.part.drawingNo,
      part_name:    l.mcProgram?.part.name,
      machine_code: l.mcProgram?.machining?.machine?.machineCode ?? null,
      version:      l.mcProgram?.machining?.version ?? null,
      status:       l.mcProgram?.status,""",
"recent: map 修正")

# ── 3. findOne: include 修正 (machine → machining.machine) ──
patch(MC_SVC,
"""      include: {
        part:      true,
        machine:   true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        pgCreator: { select: { id""",
"""      include: {
        part:      true,
        machining: {
          include: {
            machine:   true,
            pgCreator: { select: { id: true, name: true } },
            creator:   { select: { id: true, name: true } },
          },
        },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        pgCreator_REMOVED: { select: { id""",
"findOne: include 修正（pgCreator/creator を machining 配下に移動）")

# pgCreator_REMOVED の残骸を削除（実際のコードにある pgCreator select を削除）
patch(MC_SVC,
"""        pgCreator_REMOVED: { select: { id: true, name: true } },
        creator:   { select: { id: true, name: true } },""",
"",
"findOne: pgCreator_REMOVED 残骸削除")

# ── 4. findOne の processes select: version / mcProcessNo / machine ──
patch(MC_SVC,
"""      select: {
        id: true, legacyMcid: true, machiningId: true, mcProcessNo: true,
        version: true, status: true,
        machine: { select: { machineCode: true } },
      },""",
"""      select: {
        id: true, legacyMcid: true, machiningId: true, status: true,
        machining: { select: { version: true, mcProcessNo: true, machine: { select: { machineCode: true } } } },
      },""",
"findOne: processes select 修正")

# ── 5. findOne の commonGroup select ──
patch(MC_SVC,
"""      select: {
        id: true, legacyMcid: true, machiningId: true, version: true, status: true,
        part: { select: { drawingNo: true, name: true, clientName: true, partId: true } },
      },""",
"""      select: {
        id: true, legacyMcid: true, machiningId: true, status: true,
        part:     { select: { drawingNo: true, name: true, clientName: true, partId: true } },
        machining: { select: { version: true } },
      },""",
"findOne: commonGroup select 修正")

# ── 6. findOne の return: r.files を正規化後のフォームに、processes/commonGroup のフィールドも修正 ──
patch(MC_SVC,
"""      processes,
      commonGroup,
    };
  }""",
"""      processes: processes.map(p => ({
        id:           p.id,
        legacyMcid:   p.legacyMcid ?? null,
        machiningId:  p.machiningId,
        mcProcessNo:  p.machining?.mcProcessNo ?? null,
        version:      p.machining?.version ?? '1.0001',
        status:       p.status,
        machine:      p.machining?.machine ? { machineCode: p.machining.machine.machineCode } : null,
      })),
      commonGroup: commonGroup.map(g => ({
        id:          g.id,
        legacyMcid:  g.legacyMcid ?? null,
        machiningId: g.machiningId,
        version:     g.machining?.version ?? '1.0001',
        status:      g.status,
        part:        g.part,
      })),
    };
  }""",
"findOne: processes/commonGroup map 修正")

# ── 7. findOne の return の上部: r.machine/r.version 等 → r.machining.xxx ──
patch(MC_SVC,
"""    return {
      ...r,
      files: r.files.map(f => ({""",
"""    const m = (r as any).machining ?? {};
    return {
      ...r,
      // McMachiningDetail フィールドをフラットに展開（APIレスポンス後方互換）
      version:        m.version        ?? '1.0001',
      machineId:      m.machineId      ?? null,
      machine:        m.machine        ?? null,
      oNumber:        m.oNumber        ?? null,
      clampNote:      m.clampNote      ?? null,
      cycleTimeSec:   m.cycleTimeSec   ?? null,
      mcProcessNo:    m.mcProcessNo    ?? null,
      commonPartCode: m.commonPartCode ?? null,
      folder1:        m.folder1        ?? null,
      folder2:        m.folder2        ?? null,
      fileName:       m.fileName       ?? null,
      hasIndexProgram: m.hasIndexProgram ?? false,
      hasWorkOffset:   m.hasWorkOffset   ?? false,
      rc:             m.rc             ?? 0,
      pgIsFolder:     m.pgIsFolder     ?? false,
      pgFolderName:   m.pgFolderName   ?? null,
      pgCreatedBy:    m.pgCreatedBy    ?? null,
      pgUpdatedAt:    m.pgUpdatedAt    ?? null,
      creatorId:      m.creatorId      ?? null,
      sheetCreatedAt: m.sheetCreatedAt ?? null,
      pgCreator:      m.pgCreator      ?? null,
      creator:        m.creator        ?? null,
      files: r.files.map(f => ({""",
"findOne: return の machining フィールド展開")

# ── 8. create: mcProcessNo → machining_id FK + McMachiningDetail INSERT ──
patch(MC_SVC,
"""    return this.prisma.$transaction(async (tx) => {
      const mc = await tx.mcProgram.create({
        data: {
          partId:        dto.part_id,
          machiningId:   dto.machining_id,
          mcProcessNo:   dto.mc_process_no   ?? null,
          fileName:      dto.file_name       ?? null,
          machineId:     dto.machine_id     ?? null,
          oNumber:       dto.o_number       ?? null,
          clampNote:     dto.clamp_note     ?? null,
          cycleTimeSec:  dto.cycle_time_sec ?? null,
          machiningQty:  dto.machining_qty  ?? 1,
          commonPartCode: dto.common_part_code ?? null,
          note:          dto.note           ??""",
"""    return this.prisma.$transaction(async (tx) => {
      // McMachiningDetail（加工プログラム本体）を upsert
      await tx.mcMachiningDetail.upsert({
        where:  { machiningId: dto.machining_id },
        create: {
          machiningId:  dto.machining_id,
          version:      '1.0001',
          machineId:    dto.machine_id     ?? null,
          oNumber:      dto.o_number       ?? null,
          clampNote:    dto.clamp_note     ?? null,
          cycleTimeSec: dto.cycle_time_sec ?? null,
          mcProcessNo:  dto.mc_process_no  ?? null,
          fileName:     dto.file_name      ?? null,
          commonPartCode: dto.common_part_code ?? null,
        },
        update: {},  // 既存の場合は更新しない（共通部品登録時）
      });
      const mc = await tx.mcProgram.create({
        data: {
          partId:        dto.part_id,
          machiningId:   dto.machining_id,
          machiningQty:  dto.machining_qty  ?? 1,
          note:          dto.note           ??""",
"create: McMachiningDetail upsert + McProgram create")

# ── 9. createAndPrint: 競合チェック除去 + McMachiningDetail upsert 追加 ──
patch(MC_SVC,
"""    for (let attempt = 0; attempt < 3; attempt++) {
      // 加工IDの競合チェック
      const existing = await this.prisma.mcProgram.findFirst({
        where: { machiningId },
      });
      if (existing) {
        // 競合 → 次の加工IDを取得
        const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
        machiningId = (agg._max.machiningId ?? 0) + 1;
        retried = true;
        continue;
      }

      try {
        const mc = await this.prisma.$transaction(async (tx) => {
          const created = await tx.mcProgram.create({
            data: {
              partId:        dto.part_id,
              machiningId,
              mcProcessNo:   dto.mc_process_no   ?? null,
              machineId:     dto.machine_id      ?? null,
              oNumber:       dto.o_number        ?? null,
              machiningQty:  dto.machining_qty   ?? 1,
              note:          dto.note            ?? null,
              legacyMcid:    machiningId,
              registeredBy:  operatorId,
              status:        'NEW',
              version:       '0.0001',
            },
          });""",
"""    for (let attempt = 0; attempt < 3; attempt++) {
      // machining_id 重複チェック（通常登録のみ、共通部品登録時はスキップ）
      if (!dto.is_common_part) {
        const existing = await this.prisma.mcProgram.findFirst({ where: { machiningId } });
        if (existing) {
          const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
          machiningId = (agg._max.machiningId ?? 0) + 1;
          retried = true;
          continue;
        }
      }

      try {
        const mc = await this.prisma.$transaction(async (tx) => {
          // McMachiningDetail upsert
          await tx.mcMachiningDetail.upsert({
            where:  { machiningId },
            create: {
              machiningId,
              version:      '0.0001',
              machineId:    dto.machine_id  ?? null,
              oNumber:      dto.o_number    ?? null,
              mcProcessNo:  dto.mc_process_no ?? null,
            },
            update: {},  // 共通部品登録時は既存を更新しない
          });
          const created = await tx.mcProgram.create({
            data: {
              partId:        dto.part_id,
              machiningId,
              machiningQty:  dto.machining_qty   ?? 1,
              note:          dto.note            ?? null,
              legacyMcid:    machiningId,
              registeredBy:  operatorId,
              status:        'NEW',
            },
          });""",
"createAndPrint: 競合チェック修正 + McMachiningDetail upsert")

# createAndPrint の version 参照修正
patch(MC_SVC,
"""              versionAfter: created.version,""",
"""              versionAfter: '0.0001',""",
"createAndPrint: versionAfter 修正")

# ── 10. previewNew: McMachiningDetail upsert 追加 ──
patch(MC_SVC,
"""    // 一時MCレコードを作成してPDF生成し、その後削除
    const tempMc = await this.prisma.mcProgram.create({
      data: {
        partId:       dto.part_id,
        machiningId:  dto.machining_id,
        mcProcessNo:  dto.mc_process_no ?? null,
        machineId:    dto.machine_id    ?? null,
        oNumber:      dto.o_number      ?? null,
        machiningQty: dto.machining_qty ?? 1,
        note:         dto.note          ?? null,
        legacyMcid:   dto.machining_id,
        registeredBy: operatorId,
        status:       'NEW',
        version:      '0.0001',
      },
    });""",
"""    // 一時McMachiningDetail + McProgram を作成してPDF生成し、その後削除
    await this.prisma.mcMachiningDetail.upsert({
      where:  { machiningId: dto.machining_id },
      create: {
        machiningId:  dto.machining_id,
        version:      '0.0001',
        machineId:    dto.machine_id ?? null,
        oNumber:      dto.o_number   ?? null,
        mcProcessNo:  dto.mc_process_no ?? null,
      },
      update: {},
    });
    const tempMc = await this.prisma.mcProgram.create({
      data: {
        partId:       dto.part_id,
        machiningId:  dto.machining_id,
        machiningQty: dto.machining_qty ?? 1,
        note:         dto.note          ?? null,
        legacyMcid:   dto.machining_id,
        registeredBy: operatorId,
        status:       'NEW',
      },
    });""",
"previewNew: McMachiningDetail upsert 追加")

# ── 11. finalize: mc.version → machining.version ──
patch(MC_SVC,
"""    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const verStr = mc.version ?? '1.0001';""",
"""    const mc = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const verStr = (mc as any).machining?.version ?? '1.0001';""",
"finalize: version を machining.version から取得")

patch(MC_SVC,
"""      await tx.mcProgram.update({
        where: { id },
        data:  { version: newVersion, status: 'CHANGING' },
      });""",
"""      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { version: newVersion },
      });
      await tx.mcProgram.update({
        where: { id },
        data:  { status: 'CHANGING' },
      });""",
"finalize: version を McMachiningDetail に更新")

# ── 12. update: mc.version / mc.machineId 等 → machining 経由 ──
patch(MC_SVC,
"""    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);

    // VBA 終了確認ロジック準拠バージョンインクリ""",
"""    const mc = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const mach = (mc as any).machining ?? {};

    // VBA 終了確認ロジック準拠バージョンインクリ""",
"update: machining include 追加")

patch(MC_SVC,
"""    const verStr = mc.version ?? '1.0001';""",
"""    const verStr = mach.version ?? '1.0001';""",
"update: verStr を mach.version から取得")

patch(MC_SVC,
"""    return this.prisma.$transaction(async (tx) => {
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
      });""",
"""    return this.prisma.$transaction(async (tx) => {
      // McMachiningDetail: 加工プログラム本体フィールドを更新
      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data: {
          machineId:     dto.machine_id     !== undefined ? dto.machine_id     : mach.machineId,
          oNumber:       dto.o_number       !== undefined ? dto.o_number       : mach.oNumber,
          clampNote:     dto.clamp_note     !== undefined ? dto.clamp_note     : mach.clampNote,
          cycleTimeSec:  dto.cycle_time_sec !== undefined ? dto.cycle_time_sec : mach.cycleTimeSec,
          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,
          creatorId:     dto.creator_id     !== undefined ? dto.creator_id     : mach.creatorId,
          version:       newVersion,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : mach.sheetCreatedAt,
        },
      });
      await tx.mcProgram.update({
        where: { id },
        data: {
          machiningQty:  dto.machining_qty  !== undefined ? dto.machining_qty  : mc.machiningQty,
          note:          dto.note           !== undefined ? dto.note           : mc.note,
          status:        'CHANGING',
        },
      });""",
"update: McMachiningDetail/McProgram 分離更新")

# ── 13. approve: mc.version → machining.version ──
patch(MC_SVC,
"""    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    if (mc.status === 'APPROVED') {""",
"""    const mc = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    if (mc.status === 'APPROVED') {""",
"approve: machining include 追加")

patch(MC_SVC,
"""          versionBefore: mc.version,
          versionAfter:  mc.version,
          content:       '承認',""",
"""          versionBefore: (mc as any).machining?.version ?? null,
          versionAfter:  (mc as any).machining?.version ?? null,
          content:       '承認',""",
"approve: version を machining から取得")

patch(MC_SVC,
"""      return { mc_id: id, message: '承認しました', version: mc.version };""",
"""      return { mc_id: id, message: '承認しました', version: (mc as any).machining?.version ?? '1.0001' };""",
"approve: return version 修正")

# ── 14. updatePgMeta: pgCreatedBy/pgUpdatedAt → McMachiningDetail へ ──
patch(MC_SVC,
"""  async updatePgMeta(id: number, pgCreatedBy: number) {
    return this.prisma.mcProgram.update({
      where: { id },
      data:  { pgCreatedBy, pgUpdatedAt: new Date() },
    });
  }""",
"""  async updatePgMeta(id: number, pgCreatedBy: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id }, select: { machiningId: true } });
    if (!mc) return;
    return this.prisma.mcMachiningDetail.update({
      where: { machiningId: mc.machiningId },
      data:  { pgCreatedBy, pgUpdatedAt: new Date() },
    });
  }""",
"updatePgMeta: McMachiningDetail へ")

# ── 15. getTooling: mcProgramId → machiningId ──
patch(MC_SVC,
"""  async getTooling(mcId: number) {
    return this.prisma.mcTooling.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { sortOrder: 'asc' },
    });
  }""",
"""  async getTooling(mcId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });
    if (!mc) return [];
    return this.prisma.mcTooling.findMany({
      where:   { machiningId: mc.machiningId },
      orderBy: { sortOrder: 'asc' },
    });
  }""",
"getTooling: machiningId 経由")

# ── 16. saveTooling: mcProgramId → machiningId ──
patch(MC_SVC,
"""    return this.prisma.$transaction(async (tx) => {
      await tx.mcTooling.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcTooling.createMany({
          data: dto.items.map(item => ({
            mcProgramId:    mcId,""",
"""    return this.prisma.$transaction(async (tx) => {
      await tx.mcTooling.deleteMany({ where: { machiningId: mc.machiningId } });
      if (dto.items.length > 0) {
        await tx.mcTooling.createMany({
          data: dto.items.map(item => ({
            machiningId:    mc.machiningId,""",
"saveTooling: machiningId 使用")

# ── 17. getWorkOffsets: mcProgramId → machiningId ──
patch(MC_SVC,
"""  async getWorkOffsets(mcId: number) {
    return this.prisma.mcWorkOffset.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { gCode: 'asc' },
    });
  }""",
"""  async getWorkOffsets(mcId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });
    if (!mc) return [];
    return this.prisma.mcWorkOffset.findMany({
      where:   { machiningId: mc.machiningId },
      orderBy: { gCode: 'asc' },
    });
  }""",
"getWorkOffsets: machiningId 経由")

# ── 18. saveWorkOffsets: mcProgramId → machiningId ──
patch(MC_SVC,
"""      await tx.mcWorkOffset.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcWorkOffset.createMany({
          data: dto.items.map(item => ({
            mcProgramId: mcId,""",
"""      await tx.mcWorkOffset.deleteMany({ where: { machiningId: mc.machiningId } });
      if (dto.items.length > 0) {
        await tx.mcWorkOffset.createMany({
          data: dto.items.map(item => ({
            machiningId: mc.machiningId,""",
"saveWorkOffsets: machiningId 使用")

# ── 19. getIndexPrograms: mcProgramId → machiningId ──
patch(MC_SVC,
"""  async getIndexPrograms(mcId: number) {
    return this.prisma.mcIndexProgram.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { sortOrder: 'asc' },
    });
  }""",
"""  async getIndexPrograms(mcId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });
    if (!mc) return [];
    return this.prisma.mcIndexProgram.findMany({
      where:   { machiningId: mc.machiningId },
      orderBy: { sortOrder: 'asc' },
    });
  }""",
"getIndexPrograms: machiningId 経由")

# ── 20. saveIndexPrograms: mcProgramId → machiningId ──
patch(MC_SVC,
"""      await tx.mcIndexProgram.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcIndexProgram.createMany({
          data: dto.items.map(item => ({
            mcProgramId: mcId,""",
"""      await tx.mcIndexProgram.deleteMany({ where: { machiningId: mc.machiningId } });
      if (dto.items.length > 0) {
        await tx.mcIndexProgram.createMany({
          data: dto.items.map(item => ({
            machiningId: mc.machiningId,""",
"saveIndexPrograms: machiningId 使用")

# ── 21. createWorkRecord: mc.machineId → machining.machineId ──
patch(MC_SVC,
"""        machineId:        dto.machine_id    ?? mc.machineId ?? null,""",
"""        machineId:        dto.machine_id    ?? (mc as any).machining?.machineId ?? null,""",
"createWorkRecord: machineId → machining 経由")

# ── 22. getPrintData: include 修正 ──
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
            machine:   true,
            tooling:   { orderBy: { sortOrder: 'asc' } },
            workOffsets: { orderBy: { gCode: 'asc' } },
            indexPrograms: { orderBy: { sortOrder: 'asc' } },
            creator:   { select: { name: true } },
            pgCreator: { select: { name: true } },
          },
        },
        registrar: { select: { name: true } },
        approver:  { select: { name: true } },
        tooling_REMOVED:   { orderB""",
"getPrintData: include 修正")

# getPrintData の旧 tooling/workOffsets/indexPrograms include を削除
patch(MC_SVC,
"""        tooling_REMOVED:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },
        indexPrograms: { orderBy: { sortOrder: 'asc' } },
        creator:   { select: { name: true } },
        pgCreator: { select: { name: true } },""",
"",
"getPrintData: 旧 tooling/workOffsets/indexPrograms include 削除")

# getPrintData の return にフラット展開を追加
patch(MC_SVC,
"""    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);
    return r;
  }""",
"""    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);
    const mach = (r as any).machining ?? {};
    return {
      ...r,
      version:        mach.version        ?? '1.0001',
      machine:        mach.machine        ?? null,
      oNumber:        mach.oNumber        ?? null,
      clampNote:      mach.clampNote      ?? null,
      cycleTimeSec:   mach.cycleTimeSec   ?? null,
      fileName:       mach.fileName       ?? null,
      folder1:        mach.folder1        ?? null,
      folder2:        mach.folder2        ?? null,
      mcProcessNo:    mach.mcProcessNo    ?? null,
      hasIndexProgram: mach.hasIndexProgram ?? false,
      hasWorkOffset:   mach.hasWorkOffset   ?? false,
      rc:             mach.rc             ?? 0,
      pgIsFolder:     mach.pgIsFolder     ?? false,
      pgFolderName:   mach.pgFolderName   ?? null,
      pgCreatedBy:    mach.pgCreatedBy    ?? null,
      pgUpdatedAt:    mach.pgUpdatedAt    ?? null,
      creatorId:      mach.creatorId      ?? null,
      sheetCreatedAt: mach.sheetCreatedAt ?? null,
      commonPartCode: mach.commonPartCode ?? null,
      creator:        mach.creator        ?? null,
      pgCreator:      mach.pgCreator      ?? null,
      tooling:        mach.tooling        ?? [],
      workOffsets:    mach.workOffsets    ?? [],
      indexPrograms:  mach.indexPrograms  ?? [],
    };
  }""",
"getPrintData: machining フィールドをフラットに展開")

# ── 23. uncollectedByLegacy: mcProcessNo → machining.mcProcessNo ──
patch(MC_SVC,
"""      select: { id: true, machiningId: true, mcProcessNo: true,
                part: { select: { drawingNo: true, name: true } } },""",
"""      select: { id: true, machiningId: true,
                part:     { select: { drawingNo: true, name: true } },
                machining: { select: { mcProcessNo: true } } },""",
"uncollectedByLegacy: mcProcessNo → machining 経由")

patch(MC_SVC,
"""        mc_process_no:  p.mcProcessNo,""",
"""        mc_process_no:  (p as any).machining?.mcProcessNo ?? null,""",
"uncollectedByLegacy: map mcProcessNo 修正")

# ── 24. getCommonGroup: machine/version → machining 経由 ──
patch(MC_SVC,
"""      include: {
        part:    { select: { drawingNo: true, name: true, clientName: true } },
        machine: { select: { machineCode: true } },
      },""",
"""      include: {
        part:     { select: { drawingNo: true, name: true, clientName: true } },
        machining: { select: { version: true, machine: { select: { machineCode: true } } } },
      },""",
"getCommonGroup: machining 経由")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc-files.service.ts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MC_FILES_SVC = API / "mc/mc-files.service.ts"
shutil.copy(MC_FILES_SVC, str(MC_FILES_SVC) + ".bak_v130")
log("mc-files.service.ts バックアップ完了")

# pgUpdatedAt/pgCreatedBy → McMachiningDetail へ (savePgContent 内)
patch(MC_FILES_SVC,
"""      // 既存ファイルを上書き
      fs.writeFileSync(existing.filePath, buf);
      // pg_updated_at を更新
      await this.prisma.mcProgram.update({
        where: { id: mcProgramId },
        data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
      });""",
"""      // 既存ファイルを上書き
      fs.writeFileSync(existing.filePath, buf);
      // pg_updated_at を更新 (McMachiningDetail)
      await this.prisma.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
      });""",
"mc-files.service.ts: savePgContent pgUpdatedAt → McMachiningDetail")

# 新規保存時の pgUpdatedAt → McMachiningDetail
patch(MC_FILES_SVC,
"""    await this.prisma.mcProgram.update({
      where: { id: mcProgramId },
      data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
    });
    return { message: 'PGファイルを新規保存しました' };""",
"""    await this.prisma.mcMachiningDetail.update({
      where: { machiningId: mc.machiningId },
      data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
    });
    return { message: 'PGファイルを新規保存しました' };""",
"mc-files.service.ts: 新規保存 pgUpdatedAt → McMachiningDetail")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dashboard.service.ts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DASH_SVC = API / "dashboard/dashboard.service.ts"
shutil.copy(DASH_SVC, str(DASH_SVC) + ".bak_v130")
log("dashboard.service.ts バックアップ完了")

# orderBy machine → machining.machine
patch(DASH_SVC,
"""          machine: { machineCode: 'asc' },""",
"""          machining: { machine: { machineCode: 'asc' } },""",
"dashboard: orderBy machine 修正")

# include machine → machining.machine
patch(DASH_SVC,
"""          machine: { select: { machineCode: true, machineName: true } },""",
"""          machining: { select: { version: true, machine: { select: { machineCode: true, machineName: true } } } },""",
"dashboard: include machine → machining 修正")

# mcProgram.machine / .version / .oNumber 等 → mcProgram.machining.xxx
patch(DASH_SVC,
"""        r.mcProgram?.machine?.machineCode,""",
"""        r.mcProgram?.machining?.machine?.machineCode ?? null,""",
"dashboard: mcProgram.machine.machineCode 修正")

# mcProgram 展開の全フィールドを一括修正
patch(DASH_SVC,
"""      mc_id:          r.mcProgram?.id,""",
"""      mc_id:          r.mcProgram?.id ?? (r as any).mcProgramId,""",
"dashboard: mc_id フォールバック追加")

# include 内の mcProgram リレーション修正（setupSheetLogs が mcProgram を include している場合）
patch(DASH_SVC,
"""          mcProgram: {
            select: {""",
"""          mcProgram_info: {
            select: {""",
"dashboard: mcProgram select キー名変更（競合回避）")

# mcProgram → mcProgram_info の参照修正
patch(DASH_SVC,
"""        r.mcProgram?.id,""",
"""        (r as any).mcProgram_info?.id ?? (r as any).mcProgramId,""",
"dashboard: mcProgram_info 参照修正")

patch(DASH_SVC,
"""        r.mcProgram?.part?.drawingNo,""",
"""        (r as any).mcProgram_info?.part?.drawingNo ?? null,""",
"dashboard: mcProgram_info.part.drawingNo")

patch(DASH_SVC,
"""        r.mcProgram?.part?.name,""",
"""        (r as any).mcProgram_info?.part?.name ?? null,""",
"dashboard: mcProgram_info.part.name")

patch(DASH_SVC,
"""        r.mcProgram?.part?.partId,""",
"""        (r as any).mcProgram_info?.part?.partId ?? null,""",
"dashboard: mcProgram_info.part.partId")

patch(DASH_SVC,
"""        r.mcProgram?.legacyMcid,""",
"""        (r as any).mcProgram_info?.legacyMcid ?? null,""",
"dashboard: mcProgram_info.legacyMcid")

patch(DASH_SVC,
"""        r.mcProgram?.machine?.machineCode,""",
"""        (r as any).mcProgram_info?.machining?.machine?.machineCode ?? null,""",
"dashboard: mcProgram_info.machining.machine.machineCode")

patch(DASH_SVC,
"""        r.mcProgram?.machine?.machineName,""",
"""        (r as any).mcProgram_info?.machining?.machine?.machineName ?? null,""",
"dashboard: mcProgram_info.machining.machine.machineName")

patch(DASH_SVC,
"""        r.mcProgram?.status,""",
"""        (r as any).mcProgram_info?.status ?? null,""",
"dashboard: mcProgram_info.status")

patch(DASH_SVC,
"""        r.mcProgram?.version,""",
"""        (r as any).mcProgram_info?.machining?.version ?? null,""",
"dashboard: mcProgram_info.machining.version")

patch(DASH_SVC,
"""        r.operator?.name,""",
"""        (r as any).operator?.name ?? null,""",
"dashboard: operator.name")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSC コンパイル確認
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    log(f"TSC エラーあり (rc={result.returncode}) — 残りのエラーを確認してください")

print("\n[step2] 完了")
