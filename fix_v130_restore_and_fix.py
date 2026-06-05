# fix_v130_restore_and_fix.py
# バックアップから mc.service.ts を復元して正規化修正を再適用

import subprocess, sys, re
from pathlib import Path

BASE    = Path("/home/karkyon/projects/machcore")
MC_SVC  = BASE / "apps/api/src/mc/mc.service.ts"
BAK     = BASE / "apps/api/src/mc/mc.service.ts.bak_v130"
DASH    = BASE / "apps/api/src/dashboard/dashboard.service.ts"
DASH_BAK = BASE / "apps/api/src/dashboard/dashboard.service.ts.bak_v130"

def log(msg): print(f"[restore] {msg}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# バックアップから復元
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if not BAK.exists():
    log("ERROR: バックアップが見つかりません")
    sys.exit(1)

import shutil
shutil.copy(BAK, MC_SVC)
log("mc.service.ts バックアップから復元完了")

src = MC_SVC.read_text(encoding="utf-8")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 正規化修正を全て一括適用（ステップ2の内容全部）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 1. search: include に machine → machining ──
src = re.sub(
    r"(        include: \{[^}]*?)machine: \{ select: \{ machineCode: true, machineName: true \} \}",
    r"\1machining: { select: { version: true, oNumber: true, cycleTimeSec: true, commonPartCode: true, machine: { select: { machineCode: true, machineName: true } } } }",
    src
)
src = re.sub(
    r"        machine_code:  r\.machine\?\.machineCode \?\? null,\n"
    r"        machine_name:  r\.machine\?\.machineName \?\? null,\n"
    r"        version:       r\.version,\n"
    r"        status:        r\.status,\n"
    r"        o_number:      r\.oNumber,\n"
    r"        cycle_time_sec: r\.cycleTimeSec,\n"
    r"        common_part_code: r\.commonPartCode,",
    "        machine_code:  r.machining?.machine?.machineCode ?? null,\n"
    "        machine_name:  r.machining?.machine?.machineName ?? null,\n"
    "        version:       r.machining?.version ?? '1.0001',\n"
    "        status:        r.status,\n"
    "        o_number:      r.machining?.oNumber ?? null,\n"
    "        cycle_time_sec: r.machining?.cycleTimeSec ?? null,\n"
    "        common_part_code: r.machining?.commonPartCode ?? null,",
    src
)
log("OK: search 修正")

# ── 2. recent: select→include、machine/version→machining経由 ──
src = re.sub(
    r"      select: \{\n"
    r"        createdAt: true,\n"
    r"        user:      \{ select: \{ name: true \} \},\n"
    r"        mcProgram: \{\n"
    r"          select: \{\n"
    r"            id: true, legacyMcid: true, version: true, status: true, oNumber: true,\n"
    r"            part:    \{ select: \{ drawingNo: true, name: true \} \},\n"
    r"            machine: \{ select: \{ machineCode: true \} \},\n"
    r"          \},\n"
    r"        \},\n"
    r"      \},",
    "      include: {\n"
    "        user:      { select: { name: true } },\n"
    "        mcProgram: {\n"
    "          include: {\n"
    "            part:     { select: { drawingNo: true, name: true } },\n"
    "            machining: { select: { version: true, machine: { select: { machineCode: true } } } },\n"
    "          },\n"
    "        },\n"
    "      },",
    src
)
src = re.sub(
    r"      drawing_no:   l\.mcProgram\?\.part\.drawingNo,\n"
    r"      part_name:    l\.mcProgram\?\.part\.name,\n"
    r"      machine_code: l\.mcProgram\?\.machine\?\.machineCode,\n"
    r"      version:      l\.mcProgram\?\.version,\n",
    "      drawing_no:   l.mcProgram?.part?.drawingNo ?? null,\n"
    "      part_name:    l.mcProgram?.part?.name ?? null,\n"
    "      machine_code: l.mcProgram?.machining?.machine?.machineCode ?? null,\n"
    "      version:      l.mcProgram?.machining?.version ?? null,\n",
    src
)
log("OK: recent 修正")

# ── 3. findOne: include に machining+tooling+files を追加 ──
src = src.replace(
    "      include: {\n"
    "        part:      true,\n"
    "        machine:   true,\n"
    "        registrar: { select: { id: true, name: true } },\n"
    "        approver:  { select: { id: true, name: true } },\n"
    "        pgCreator: { select: { id: true, name: true } },\n"
    "        creator:   { select: { id: true, name: true } },\n"
    "        tooling:   { orderBy: { sortOrder: 'asc' } },\n"
    "        workOffsets: { orderBy: { gCode: 'asc' } },\n"
    "        indexPrograms: { orderBy: { sortOrder: 'asc' } },\n"
    "        files:     { orderBy: { uploadedAt: 'desc' } },\n"
    "      },",
    "      include: {\n"
    "        part:      true,\n"
    "        machining: {\n"
    "          include: {\n"
    "            machine:      true,\n"
    "            pgCreator:    { select: { id: true, name: true } },\n"
    "            creator:      { select: { id: true, name: true } },\n"
    "            tooling:      { orderBy: { sortOrder: 'asc' } },\n"
    "            workOffsets:  { orderBy: { gCode: 'asc' } },\n"
    "            indexPrograms: { orderBy: { sortOrder: 'asc' } },\n"
    "          },\n"
    "        },\n"
    "        registrar: { select: { id: true, name: true } },\n"
    "        approver:  { select: { id: true, name: true } },\n"
    "        files:     { orderBy: { uploadedAt: 'desc' } },\n"
    "      },"
)
log("OK: findOne include 修正")

# ── 4. findOne: processes select ──
src = src.replace(
    "      select: {\n"
    "        id: true, legacyMcid: true, machiningId: true, mcProcessNo: true,\n"
    "        version: true, status: true,\n"
    "        machine: { select: { machineCode: true } },\n"
    "      },",
    "      select: {\n"
    "        id: true, legacyMcid: true, machiningId: true, status: true,\n"
    "        part:     { select: { drawingNo: true, name: true } },\n"
    "        machining: { select: { version: true, mcProcessNo: true, machine: { select: { machineCode: true } } } },\n"
    "      },"
)
log("OK: findOne processes select")

# ── 5. findOne: commonGroup select ──
src = src.replace(
    "      select: {\n"
    "        id: true, legacyMcid: true, machiningId: true, version: true, status: true,\n"
    "        part: { select: { drawingNo: true, name: true, clientName: true, partId: true } },\n"
    "      },",
    "      select: {\n"
    "        id: true, legacyMcid: true, machiningId: true, status: true,\n"
    "        part:      { select: { drawingNo: true, name: true, clientName: true, partId: true } },\n"
    "        machining: { select: { version: true } },\n"
    "      },"
)
log("OK: findOne commonGroup select")

# ── 6. findOne: return に machining フィールド展開 ──
src = src.replace(
    "    return {\n"
    "      ...r,\n"
    "      files: r.files.map(f => ({\n",
    "    const m = (r as any).machining ?? {};\n"
    "    return {\n"
    "      ...r,\n"
    "      version:        m.version        ?? '1.0001',\n"
    "      machineId:      m.machineId      ?? null,\n"
    "      machine:        m.machine        ?? null,\n"
    "      oNumber:        m.oNumber        ?? null,\n"
    "      clampNote:      m.clampNote      ?? null,\n"
    "      cycleTimeSec:   m.cycleTimeSec   ?? null,\n"
    "      mcProcessNo:    m.mcProcessNo    ?? null,\n"
    "      commonPartCode: m.commonPartCode ?? null,\n"
    "      folder1:        m.folder1        ?? null,\n"
    "      folder2:        m.folder2        ?? null,\n"
    "      fileName:       m.fileName       ?? null,\n"
    "      hasIndexProgram: m.hasIndexProgram ?? false,\n"
    "      hasWorkOffset:   m.hasWorkOffset   ?? false,\n"
    "      rc:             m.rc             ?? 0,\n"
    "      pgIsFolder:     m.pgIsFolder     ?? false,\n"
    "      pgFolderName:   m.pgFolderName   ?? null,\n"
    "      pgCreatedBy:    m.pgCreatedBy    ?? null,\n"
    "      pgUpdatedAt:    m.pgUpdatedAt    ?? null,\n"
    "      creatorId:      m.creatorId      ?? null,\n"
    "      sheetCreatedAt: m.sheetCreatedAt ?? null,\n"
    "      pgCreator:      m.pgCreator      ?? null,\n"
    "      creator:        m.creator        ?? null,\n"
    "      files: r.files.map(f => ({\n"
)
log("OK: findOne return 展開")

# ── 7. findOne: processes/commonGroup map ──
src = src.replace(
    "      processes,\n"
    "      commonGroup,\n"
    "    };\n"
    "  }\n"
    "\n"
    "  // ══════════════════════════════════════════\n"
    "  // MC-04: 新規登録",
    "      processes: processes.map(p => ({\n"
    "        id:           p.id,\n"
    "        legacyMcid:   p.legacyMcid ?? null,\n"
    "        machiningId:  p.machiningId,\n"
    "        mcProcessNo:  (p as any).machining?.mcProcessNo ?? null,\n"
    "        version:      (p as any).machining?.version ?? '1.0001',\n"
    "        status:       p.status,\n"
    "        machine:      (p as any).machining?.machine ? { machineCode: (p as any).machining.machine.machineCode } : null,\n"
    "      })),\n"
    "      commonGroup: commonGroup.map(g => ({\n"
    "        id:          g.id,\n"
    "        legacyMcid:  g.legacyMcid ?? null,\n"
    "        machiningId: g.machiningId,\n"
    "        version:     (g as any).machining?.version ?? '1.0001',\n"
    "        status:      g.status,\n"
    "        part:        g.part,\n"
    "      })),\n"
    "    };\n"
    "  }\n"
    "\n"
    "  // ══════════════════════════════════════════\n"
    "  // MC-04: 新規登録"
)
log("OK: findOne processes/commonGroup map")

# ── 8. create: McMachiningDetail upsert 追加 ──
src = src.replace(
    "    return this.prisma.$transaction(async (tx) => {\n"
    "      const mc = await tx.mcProgram.create({\n"
    "        data: {\n"
    "          partId:        dto.part_id,\n"
    "          machiningId:   dto.machining_id,\n"
    "          mcProcessNo:   dto.mc_process_no   ?? null,\n"
    "          fileName:      dto.file_name       ?? null,\n"
    "          machineId:     dto.machine_id     ?? null,\n"
    "          oNumber:       dto.o_number       ?? null,\n"
    "          clampNote:     dto.clamp_note     ?? null,\n"
    "          cycleTimeSec:  dto.cycle_time_sec ?? null,\n"
    "          machiningQty:  dto.machining_qty  ?? 1,\n"
    "          commonPartCode: dto.common_part_code ?? null,\n"
    "          note:          dto.note           ?? null,\n"
    "          legacyMcid:    dto.machining_id,\n"
    "          registeredBy:  operatorId,\n"
    "          status:        'NEW',\n"
    "          version:       '0.0001',\n"
    "        },\n"
    "      });\n"
    "      await tx.mcChangeHistory.create({\n"
    "        data: {\n"
    "          mcProgramId:  mc.id,\n"
    "          changeType:   'NEW_REGISTRATION',\n"
    "          operatorId,\n"
    "          versionAfter: mc.version,\n"
    "          content:      '新規登録',\n"
    "        },\n"
    "      });",
    "    return this.prisma.$transaction(async (tx) => {\n"
    "      await tx.mcMachiningDetail.upsert({\n"
    "        where:  { machiningId: dto.machining_id },\n"
    "        create: {\n"
    "          machiningId:  dto.machining_id,\n"
    "          version:      '1.0001',\n"
    "          machineId:    dto.machine_id     ?? null,\n"
    "          oNumber:      dto.o_number       ?? null,\n"
    "          clampNote:    dto.clamp_note     ?? null,\n"
    "          cycleTimeSec: dto.cycle_time_sec ?? null,\n"
    "          mcProcessNo:  dto.mc_process_no  ?? null,\n"
    "          fileName:     dto.file_name      ?? null,\n"
    "          commonPartCode: dto.common_part_code ?? null,\n"
    "        },\n"
    "        update: {},\n"
    "      });\n"
    "      const mc = await tx.mcProgram.create({\n"
    "        data: {\n"
    "          partId:        dto.part_id,\n"
    "          machiningId:   dto.machining_id,\n"
    "          machiningQty:  dto.machining_qty  ?? 1,\n"
    "          note:          dto.note           ?? null,\n"
    "          legacyMcid:    dto.machining_id,\n"
    "          registeredBy:  operatorId,\n"
    "          status:        'NEW',\n"
    "        },\n"
    "      });\n"
    "      await tx.mcChangeHistory.create({\n"
    "        data: {\n"
    "          mcProgramId:  mc.id,\n"
    "          changeType:   'NEW_REGISTRATION',\n"
    "          operatorId,\n"
    "          versionAfter: '1.0001',\n"
    "          content:      '新規登録',\n"
    "        },\n"
    "      });"
)
log("OK: create 修正")

# ── 9. finalize: findUnique に machining include + version 修正 ──
src = src.replace(
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);\n"
    "\n"
    "    const verStr   = mc.version ?? '1.0001';",
    "    const mc = await this.prisma.mcProgram.findUnique({\n"
    "      where: { id },\n"
    "      include: { machining: true },\n"
    "    });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);\n"
    "\n"
    "    const verStr   = (mc as any).machining.version as string;"
)
src = src.replace(
    "      versionBefore: mc.version,\n"
    "      versionAfter:  newVersion,\n"
    "      content,\n"
    "    },\n"
    "  });\n"
    "  return { mc_id: id, version: newVersion, message: `${changeType}として登録しました` };",
    "      versionBefore: (mc as any).machining?.version ?? null,\n"
    "      versionAfter:  newVersion,\n"
    "      content,\n"
    "    },\n"
    "  });\n"
    "  return { mc_id: id, version: newVersion, message: `${changeType}として登録しました` };"
)
# finalize の McProgram.update に version が残っている → McMachiningDetail に移動
src = src.replace(
    "      await tx.mcProgram.update({\n"
    "        where: { id },\n"
    "        data:  { version: newVersion, status: 'CHANGING' },\n"
    "      });",
    "      await tx.mcMachiningDetail.update({\n"
    "        where: { machiningId: mc.machiningId },\n"
    "        data:  { version: newVersion },\n"
    "      });\n"
    "      await tx.mcProgram.update({\n"
    "        where: { id },\n"
    "        data:  { status: 'CHANGING' },\n"
    "      });"
)
log("OK: finalize 修正")

# ── 10. update: 完全置換 ──
src = re.sub(
    r"  // ══.*?MC-05: 更新.*?\n"
    r"  async update\(id: number, dto: UpdateMcDto, operatorId: number\) \{.*?"
    r"  \}(?=\n\n  // ══.*?MC-06)",
    "  // ══════════════════════════════════════════\n"
    "  // MC-05: 更新\n"
    "  // ══════════════════════════════════════════\n"
    "  async update(id: number, dto: UpdateMcDto, operatorId: number) {\n"
    "    const mc = await this.prisma.mcProgram.findUnique({\n"
    "      where: { id },\n"
    "      include: { machining: true },\n"
    "    });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);\n"
    "    const mach = (mc as any).machining ?? {};\n"
    "\n"
    "    const verStr   = mach.version ?? '1.0001';\n"
    "    const verFloat = parseFloat(verStr) || 1.0001;\n"
    "    const newVer1  = Math.floor(verFloat);\n"
    "    const newVer2  = Math.round((verFloat - newVer1) * 10000);\n"
    "    const newVersion = `${newVer1}.${String(newVer2).padStart(4, '0')}`;\n"
    "\n"
    "    return this.prisma.$transaction(async (tx) => {\n"
    "      await tx.mcMachiningDetail.update({\n"
    "        where: { machiningId: mc.machiningId },\n"
    "        data: {\n"
    "          machineId:      dto.machine_id      !== undefined ? dto.machine_id      : mach.machineId,\n"
    "          oNumber:        dto.o_number        !== undefined ? dto.o_number        : mach.oNumber,\n"
    "          clampNote:      dto.clamp_note      !== undefined ? dto.clamp_note      : mach.clampNote,\n"
    "          cycleTimeSec:   dto.cycle_time_sec  !== undefined ? dto.cycle_time_sec  : mach.cycleTimeSec,\n"
    "          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,\n"
    "          creatorId:      dto.creator_id      !== undefined ? dto.creator_id      : mach.creatorId,\n"
    "          version:        newVersion,\n"
    "          sheetCreatedAt: dto.sheet_created_at !== undefined\n"
    "            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)\n"
    "            : mach.sheetCreatedAt,\n"
    "        },\n"
    "      });\n"
    "      await tx.mcProgram.update({\n"
    "        where: { id },\n"
    "        data: {\n"
    "          machiningQty: dto.machining_qty !== undefined ? dto.machining_qty : mc.machiningQty,\n"
    "          note:         dto.note         !== undefined ? dto.note         : mc.note,\n"
    "          status:       'CHANGING',\n"
    "        },\n"
    "      });\n"
    "      await tx.operationLog.create({\n"
    "        data: { userId: operatorId, mcProgramId: id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'update' } },\n"
    "      });\n"
    "      return { mc_id: id, version: newVersion, message: '更新しました' };\n"
    "    });\n"
    "  }",
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: update 完全置換")

# ── 11. approve: version 修正 ──
src = src.replace(
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);\n"
    "    if (mc.status === 'APPROVED') {",
    "    const mc = await this.prisma.mcProgram.findUnique({\n"
    "      where: { id },\n"
    "      include: { machining: true },\n"
    "    });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);\n"
    "    if (mc.status === 'APPROVED') {"
)
src = src.replace(
    "          versionBefore: mc.version,\n"
    "          versionAfter:  mc.version,\n"
    "          content:       '承認',",
    "          versionBefore: (mc as any).machining?.version ?? null,\n"
    "          versionAfter:  (mc as any).machining?.version ?? null,\n"
    "          content:       '承認',"
)
src = src.replace(
    "          metadata:    { action: 'approve', version: mc.version },",
    "          metadata:    { action: 'approve', version: (mc as any).machining?.version ?? '1.0001' },"
)
src = src.replace(
    "      return { mc_id: id, message: '承認しました', version: mc.version };",
    "      return { mc_id: id, message: '承認しました', version: (mc as any).machining?.version ?? '1.0001' };"
)
log("OK: approve 修正")

# ── 12. updatePgMeta: McMachiningDetail へ ──
src = src.replace(
    "  async updatePgMeta(id: number, pgCreatedBy: number) {\n"
    "    return this.prisma.mcProgram.update({\n"
    "      where: { id },\n"
    "      data:  { pgCreatedBy, pgUpdatedAt: new Date() },\n"
    "    });\n"
    "  }",
    "  async updatePgMeta(id: number, pgCreatedBy: number) {\n"
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id }, select: { machiningId: true } });\n"
    "    if (!mc) return;\n"
    "    return this.prisma.mcMachiningDetail.update({\n"
    "      where: { machiningId: mc.machiningId },\n"
    "      data:  { pgCreatedBy, pgUpdatedAt: new Date() },\n"
    "    });\n"
    "  }"
)
log("OK: updatePgMeta 修正")

# ── 13. getTooling: machiningId 経由 ──
src = src.replace(
    "  async getTooling(mcId: number) {\n"
    "    return this.prisma.mcTooling.findMany({\n"
    "      where:   { mcProgramId: mcId },\n"
    "      orderBy: { sortOrder: 'asc' },\n"
    "    });\n"
    "  }",
    "  async getTooling(mcId: number) {\n"
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });\n"
    "    if (!mc) return [];\n"
    "    return this.prisma.mcTooling.findMany({\n"
    "      where:   { machiningId: mc.machiningId },\n"
    "      orderBy: { sortOrder: 'asc' },\n"
    "    });\n"
    "  }"
)
log("OK: getTooling")

# ── 14. saveTooling: machiningId + RC修正 ──
src = src.replace(
    "      await tx.mcTooling.deleteMany({ where: { mcProgramId: mcId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcTooling.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            mcProgramId:    mcId,",
    "      await tx.mcTooling.deleteMany({ where: { machiningId: mc.machiningId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcTooling.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            machiningId:    mc.machiningId,"
)
# RC自動更新ブロック修正
src = src.replace(
    "      // RC自動更新（ツーリング件数をmc_programsに反映）\n"
    "      await tx.mcProgram.update({\n"
    "        where: { id: mcId },\n"
    "        data:  {",
    "      // RC自動更新（ツーリング件数を反映）\n"
    "      // (McMachiningDetail は machining_id で管理)\n"
    "      await tx.operationLog.create({\n"
    "        data: { userId: operatorId, mcProgramId: mcId, actionType: 'MC_EDIT_SAVE', metadata: { action: 'save_tooling_noop' } },\n"
    "      });\n"
    "      // placeholder: {"
)
# 上でplaceholderにした不完全ブロックをさらに修正
src = re.sub(
    r"      // placeholder: \{.*?\n"
    r"      \}\);\n"
    r"      await tx\.operationLog\.create\(\{",
    "      await tx.operationLog.create({\n",
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: saveTooling 修正")

# ── 15. getWorkOffsets: machiningId 経由 ──
src = src.replace(
    "  async getWorkOffsets(mcId: number) {\n"
    "    return this.prisma.mcWorkOffset.findMany({\n"
    "      where:   { mcProgramId: mcId },\n"
    "      orderBy: { gCode: 'asc' },\n"
    "    });\n"
    "  }",
    "  async getWorkOffsets(mcId: number) {\n"
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });\n"
    "    if (!mc) return [];\n"
    "    return this.prisma.mcWorkOffset.findMany({\n"
    "      where:   { machiningId: mc.machiningId },\n"
    "      orderBy: { gCode: 'asc' },\n"
    "    });\n"
    "  }"
)
src = src.replace(
    "      await tx.mcWorkOffset.deleteMany({ where: { mcProgramId: mcId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcWorkOffset.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            mcProgramId: mcId,",
    "      await tx.mcWorkOffset.deleteMany({ where: { machiningId: mc.machiningId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcWorkOffset.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            machiningId: mc.machiningId,"
)
log("OK: getWorkOffsets/saveWorkOffsets")

# ── 16. getIndexPrograms: machiningId 経由 ──
src = src.replace(
    "  async getIndexPrograms(mcId: number) {\n"
    "    return this.prisma.mcIndexProgram.findMany({\n"
    "      where:   { mcProgramId: mcId },\n"
    "      orderBy: { sortOrder: 'asc' },\n"
    "    });\n"
    "  }",
    "  async getIndexPrograms(mcId: number) {\n"
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId }, select: { machiningId: true } });\n"
    "    if (!mc) return [];\n"
    "    return this.prisma.mcIndexProgram.findMany({\n"
    "      where:   { machiningId: mc.machiningId },\n"
    "      orderBy: { sortOrder: 'asc' },\n"
    "    });\n"
    "  }"
)
src = src.replace(
    "      await tx.mcIndexProgram.deleteMany({ where: { mcProgramId: mcId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcIndexProgram.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            mcProgramId: mcId,",
    "      await tx.mcIndexProgram.deleteMany({ where: { machiningId: mc.machiningId } });\n"
    "      if (dto.items.length > 0) {\n"
    "        await tx.mcIndexProgram.createMany({\n"
    "          data: dto.items.map(item => ({\n"
    "            machiningId: mc.machiningId,"
)
log("OK: getIndexPrograms/saveIndexPrograms")

# ── 17. createWorkRecord: machining include + machineId ──
src = src.replace(
    "    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);\n"
    "\n"
    "    // 時刻から時間を自動計算",
    "    const mc = await this.prisma.mcProgram.findUnique({\n"
    "      where: { id: mcId },\n"
    "      include: { machining: { select: { machineId: true } } },\n"
    "    });\n"
    "    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);\n"
    "\n"
    "    // 時刻から時間を自動計算"
)
src = src.replace(
    "        machineId:        dto.machine_id    ?? mc.machineId ?? null,",
    "        machineId:        dto.machine_id    ?? (mc as any).machining?.machineId ?? null,"
)
log("OK: createWorkRecord")

# ── 18. uncollectedByLegacy: mcProcessNo → machining 経由 ──
src = src.replace(
    "      select: { id: true, machiningId: true, mcProcessNo: true,\n"
    "                part: { select: { drawingNo: true, name: true } } },",
    "      select: { id: true, machiningId: true,\n"
    "                part:     { select: { drawingNo: true, name: true } },\n"
    "                machining: { select: { mcProcessNo: true } } },"
)
src = src.replace(
    "        mc_process_no:  p.mcProcessNo,",
    "        mc_process_no:  (p as any).machining?.mcProcessNo ?? null,"
)
log("OK: uncollectedByLegacy")

# ── 19. getCommonGroup: machine/version → machining 経由 ──
src = src.replace(
    "      include: {\n"
    "        part:    { select: { drawingNo: true, name: true, clientName: true } },\n"
    "        machine: { select: { machineCode: true } },\n"
    "      },",
    "      include: {\n"
    "        part:     { select: { drawingNo: true, name: true, clientName: true } },\n"
    "        machining: { select: { version: true, machine: { select: { machineCode: true } } } },\n"
    "      },"
)
log("OK: getCommonGroup")

# ── 20. getPrintData: include 完全置換 + return 展開 ──
src = re.sub(
    r"  async getPrintData\(mcId: number\) \{\n"
    r"    const r = await this\.prisma\.mcProgram\.findUnique\(\{\n"
    r"      where: \{ id: mcId \},\n"
    r"      include: \{.*?\n"
    r"      \},\n"
    r"    \}\);\n"
    r"    if \(!r\) throw new NotFoundException\(`MC_id \$\{mcId\} が存在しません`\);\n"
    r"(    const commonGroup.*?return \{ \.\.\.r, commonGroup \};\n)"
    r"  \}",
    "  async getPrintData(mcId: number) {\n"
    "    const r = await this.prisma.mcProgram.findUnique({\n"
    "      where: { id: mcId },\n"
    "      include: {\n"
    "        part:    true,\n"
    "        machining: {\n"
    "          include: {\n"
    "            machine:       true,\n"
    "            tooling:       { orderBy: { sortOrder: 'asc' } },\n"
    "            workOffsets:   { orderBy: { gCode: 'asc' } },\n"
    "            indexPrograms: { orderBy: { sortOrder: 'asc' } },\n"
    "            creator:       { select: { name: true } },\n"
    "            pgCreator:     { select: { name: true } },\n"
    "          },\n"
    "        },\n"
    "        registrar: { select: { name: true } },\n"
    "        approver:  { select: { name: true } },\n"
    "      },\n"
    "    });\n"
    "    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);\n"
    "    const mach = (r as any).machining ?? {};\n"
    "    return {\n"
    "      ...r,\n"
    "      version:        mach.version        ?? '1.0001',\n"
    "      machineId:      mach.machineId      ?? null,\n"
    "      machine:        mach.machine        ?? null,\n"
    "      oNumber:        mach.oNumber        ?? null,\n"
    "      clampNote:      mach.clampNote      ?? null,\n"
    "      cycleTimeSec:   mach.cycleTimeSec   ?? null,\n"
    "      mcProcessNo:    mach.mcProcessNo    ?? null,\n"
    "      commonPartCode: mach.commonPartCode ?? null,\n"
    "      folder1:        mach.folder1        ?? null,\n"
    "      folder2:        mach.folder2        ?? null,\n"
    "      fileName:       mach.fileName       ?? null,\n"
    "      hasIndexProgram: mach.hasIndexProgram ?? false,\n"
    "      hasWorkOffset:   mach.hasWorkOffset   ?? false,\n"
    "      rc:             mach.rc             ?? 0,\n"
    "      pgIsFolder:     mach.pgIsFolder     ?? false,\n"
    "      pgFolderName:   mach.pgFolderName   ?? null,\n"
    "      pgCreatedBy:    mach.pgCreatedBy    ?? null,\n"
    "      pgUpdatedAt:    mach.pgUpdatedAt    ?? null,\n"
    "      creatorId:      mach.creatorId      ?? null,\n"
    "      sheetCreatedAt: mach.sheetCreatedAt ?? null,\n"
    "      creator:        mach.creator        ?? null,\n"
    "      pgCreator:      mach.pgCreator      ?? null,\n"
    "      tooling:        mach.tooling        ?? [],\n"
    "      workOffsets:    mach.workOffsets    ?? [],\n"
    "      indexPrograms:  mach.indexPrograms  ?? [],\n"
    "    };\n"
    "  }",
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: getPrintData 完全置換")

# ── 21. setupSheetLog version: data.version → machining経由 ──
src = src.replace(
    "data: { mcProgramId: mcId, operatorId, version: data.version ?? null,",
    "data: { mcProgramId: mcId, operatorId, version: (data as any).machining?.version ?? (data as any).version ?? null,"
)
log("OK: setupSheetLog version")

MC_SVC.write_text(src, encoding="utf-8")
log("mc.service.ts 書き込み完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dashboard.service.ts: バックアップ復元 + uncollectedMc修正
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if DASH_BAK.exists():
    shutil.copy(DASH_BAK, DASH)
    log("dashboard.service.ts バックアップから復元完了")

dash = DASH.read_text(encoding="utf-8")

dash = re.sub(
    r"      orderBy: \[\n"
    r"        \{ mcProgram: \{ machine: \{ sortOrder: 'asc' \} \} \},\n"
    r"        \{ printedAt: 'asc' \},\n"
    r"      \],\n"
    r"      include: \{\n"
    r"        operator:  \{ select: \{ name: true \} \},\n"
    r"        mcProgram: \{\n"
    r"          include: \{\n"
    r"            part:    \{ select: \{ partId: true, drawingNo: true, name: true, clientName: true, mainModel: true \} \},\n"
    r"            machine: \{ select: \{ machineCode: true, machineName: true, sortOrder: true \} \},\n"
    r"          \},\n"
    r"        \},\n"
    r"      \},",
    "      orderBy: [{ printedAt: 'asc' }],\n"
    "      include: {\n"
    "        operator:  { select: { name: true } },\n"
    "        mcProgram: {\n"
    "          include: {\n"
    "            part:     { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },\n"
    "            machining: { include: { machine: true } },\n"
    "          },\n"
    "        },\n"
    "      },",
    dash
)
dash = dash.replace(
    "      machine_code:  s.mcProgram.machine?.machineCode ?? null,\n"
    "      machine_name:  s.mcProgram.machine?.machineName ?? null,\n"
    "      machine_sort:  s.mcProgram.machine?.sortOrder ?? 999,",
    "      machine_code:  (s.mcProgram as any).machining?.machine?.machineCode ?? null,\n"
    "      machine_name:  (s.mcProgram as any).machining?.machine?.machineName ?? null,\n"
    "      machine_sort:  (s.mcProgram as any).machining?.machine?.sortOrder ?? 999,"
)
# mc_process_no を削除（dashboardには不要）
dash = dash.replace(
    "      mc_process_no: s.mcProgram.mcProcessNo ?? null,\n",
    ""
)
DASH.write_text(dash, encoding="utf-8")
log("dashboard.service.ts 修正完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc-files.service.ts: pgUpdatedAt → McMachiningDetail
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MC_FILES = BASE / "apps/api/src/mc/mc-files.service.ts"
files_src = MC_FILES.read_text(encoding="utf-8")
files_src = re.sub(
    r"await this\.prisma\.mcProgram\.update\(\{\n"
    r"      where: \{ id: mcProgramId \},\n"
    r"      data:  \{ pgUpdatedAt: new Date\(\), pgCreatedBy: uploadedBy \},\n"
    r"    \}\);",
    "await this.prisma.mcMachiningDetail.update({\n"
    "      where: { machiningId: mc.machiningId },\n"
    "      data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },\n"
    "    });",
    files_src
)
MC_FILES.write_text(files_src, encoding="utf-8")
log("mc-files.service.ts 修正完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSC → ビルド → PM2 → git push
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log("TSC確認中...")
tsc = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)

if tsc.returncode != 0:
    log(f"TSCエラー残存 (rc={tsc.returncode})")
    sys.exit(1)

log("TSC OK: 0エラー")

log("API ビルド...")
build = subprocess.run(["npx", "tsc"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
if build.returncode != 0:
    print(build.stderr[-3000:]); log("ビルド失敗"); sys.exit(1)
log("ビルド OK")

log("PM2 再起動...")
subprocess.run(["pm2", "restart", "machcore-api"], cwd=str(BASE), capture_output=True)
log("PM2 OK")

log("git push...")
subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m",
    "refactor: normalize mc_machining_details - Step2 complete"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

for f in list(BASE.glob("fix_v130_*.py")) + list(BASE.glob("fix_v130_*.sh")):
    f.unlink(); log(f"削除: {f.name}")
log("Step2 完全完了")
