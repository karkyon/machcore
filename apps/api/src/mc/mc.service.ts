import { Injectable, NotFoundException } from '@nestjs/common';
import { Cron } from '@nestjs/schedule';
import * as fs from 'fs';
import { execSync } from 'child_process';
import { PrismaService } from '../prisma/prisma.service';
import { CreateMcDto } from './dto/create-mc.dto';
import { UpdateMcDto } from './dto/update-mc.dto';
import { CreateMcWorkRecordDto } from './dto/create-mc-work-record.dto';
import { SaveToolingDto } from './dto/save-tooling.dto';
import { SaveWorkOffsetsDto } from './dto/save-work-offsets.dto';
import { SaveIndexProgramsDto } from './dto/save-index-programs.dto';
import { PrintMcDto } from './dto/print-mc.dto';

@Injectable()
export class McService {
  constructor(private readonly prisma: PrismaService) {}

  // ══════════════════════════════════════════
  // MC-01: 部品検索
  // ══════════════════════════════════════════
  async search(
    key: string,
    q: string,
    limit = 50,
    offset = 0,
    clientName?: string,
    machineId?: number,
    machineCode?: string,
  ) {
    const where: any = {};
    if (q && q.trim()) {
      const kw = q.trim();
      if (key === 'mcid') {
        const n = parseInt(kw);
        if (!isNaN(n)) where.legacyMcid = n;
      } else if (key === 'machining_id') {
        const n = parseInt(kw);
        if (!isNaN(n)) where.machiningId = n;
      } else if (key === 'part_id') {
        where.part = { partId: kw };
      } else if (key === 'drawing_no') {
        where.part = { drawingNo: { contains: kw, mode: 'insensitive' } };
      } else if (key === 'part_name') {
        where.part = { name: { contains: kw, mode: 'insensitive' } };
      } else {
        where.OR = [
          { part: { drawingNo: { contains: kw, mode: 'insensitive' } } },
          { part: { name:      { contains: kw, mode: 'insensitive' } } },
        ];
      }
    }
    if (clientName) where.part = { ...where.part, clientName: { contains: clientName, mode: 'insensitive' } };
    if (machineId)  where.machineId = machineId;
    if (machineCode) where.machine = { machineCode: { contains: machineCode, mode: 'insensitive' } };

    const [rows, total] = await Promise.all([
      this.prisma.mcProgram.findMany({
        where, skip: offset, take: limit,
        orderBy: { id: 'asc' },
        include: {
          part:    { select: { drawingNo: true, name: true, clientName: true, partId: true } },
          machine: { select: { machineCode: true, machineName: true } },
        },
      }),
      this.prisma.mcProgram.count({ where }),
    ]);

    return {
      total, limit, offset,
      rows: rows.map(r => ({
        mc_id:         r.id,
        legacy_mcid:   r.legacyMcid ?? null,
        part_id:       r.part.partId ?? null,
        part_db_id:    r.partId,
        machining_id:  r.machiningId,
        drawing_no:    r.part.drawingNo,
        part_name:     r.part.name,
        client_name:   r.part.clientName,
        machine_code:  r.machine?.machineCode ?? null,
        machine_name:  r.machine?.machineName ?? null,
        version:       r.version,
        status:        r.status,
        o_number:      r.oNumber,
        cycle_time_sec: r.cycleTimeSec,
        common_part_code: r.commonPartCode,
      })),
    };
  }

  // ══════════════════════════════════════════
  // MC-01b: 次の加工ID候補
  // ══════════════════════════════════════════
  async nextMachiningId() {
    const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
    const next = (agg._max.machiningId ?? 0) + 1;
    return { next_machining_id: next };
  }

  // ══════════════════════════════════════════
  // MC-02: 最近のアクセス
  // ══════════════════════════════════════════
  async recent() {
    const logs = await this.prisma.operationLog.findMany({
      where:   { mcProgramId: { not: null } },
      take:    5,
      orderBy: { createdAt: 'desc' },
      select: {
        createdAt: true,
        user:      { select: { name: true } },
        mcProgram: {
          select: {
            id: true, legacyMcid: true, version: true, status: true, oNumber: true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },
      },
    });
    return logs.map(l => ({
      mc_id:        l.mcProgram?.id,
      legacy_mcid:  l.mcProgram?.legacyMcid ?? null,
      drawing_no:   l.mcProgram?.part.drawingNo,
      part_name:    l.mcProgram?.part.name,
      machine_code: l.mcProgram?.machine?.machineCode,
      version:      l.mcProgram?.version,
      status:       l.mcProgram?.status,
      operator_name: l.user?.name,
      accessed_at:  l.createdAt,
    }));
  }

  // ══════════════════════════════════════════
  // MC-03: MC詳細取得
  // ══════════════════════════════════════════
  async findOne(id: number) {
    const r = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: {
        part:      true,
        machine:   true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        pgCreator: { select: { id: true, name: true } },
        creator:   { select: { id: true, name: true } },
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },
        indexPrograms: { orderBy: { sortOrder: 'asc' } },
        files:     { orderBy: { uploadedAt: 'desc' } },
      },
    });
    if (!r) throw new NotFoundException(`MC_id ${id} が存在しません`);

    // 同一部品の全工程（フローティングパネル用）
    // part.partId（部品ID文字列）で絞ることで移行バグの影響を受けない
    const processes = await this.prisma.mcProgram.findMany({
      where:   { part: { partId: r.part.partId } },
      orderBy: { id: 'asc' },
      select: {
        id: true, legacyMcid: true, machiningId: true, mcProcessNo: true,
        version: true, status: true,
        machine: { select: { machineCode: true } },
      },
    });

    // 共通加工グループ（同一machiningId＝参照表示のみ）
    const commonGroup = await this.prisma.mcProgram.findMany({
      where:   { machiningId: r.machiningId },
      orderBy: { id: 'asc' },
      select: {
        id: true, legacyMcid: true, machiningId: true, version: true, status: true,
        part: { select: { drawingNo: true, name: true, clientName: true, partId: true } },
      },
    });

    return {
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
    };
  }

  // ══════════════════════════════════════════
  // MC-04: 新規登録
  // ══════════════════════════════════════════
  async create(dto: CreateMcDto, operatorId: number) {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);

    return this.prisma.$transaction(async (tx) => {
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
          note:          dto.note           ?? null,
          legacyMcid:    dto.machining_id,
          registeredBy:  operatorId,
          status:        'NEW',
          version:       '0.0001',
        },
      });
      await tx.mcChangeHistory.create({
        data: {
          mcProgramId:  mc.id,
          changeType:   'NEW_REGISTRATION',
          operatorId,
          versionAfter: mc.version,
          content:      '新規登録',
        },
      });
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: mc.id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'create' } },
      });
      return { mc_id: mc.id, message: 'MCプログラムを登録しました' };
    });
  }

  // ══════════════════════════════════════════
  // MC-05b: 終了確認（バージョンインクリ + 変更履歴登録）
  // ══════════════════════════════════════════
  async finalize(id: number, changeType: string, changeDetail: string | undefined, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);

    const verStr   = mc.version ?? '1.0001';
    const verFloat = parseFloat(verStr) || 1.0001;
    const ver1 = Math.floor(verFloat);
    const ver2 = Math.floor(verFloat * 100) - ver1 * 100;
    const ver3 = Math.floor(verFloat * 10000) - ver1 * 10000 - ver2 * 100;
    const isMajor = ['大変更', '新規登録', '試作登録'].includes(changeType);
    const newVerFloat = isMajor
      ? ver1 + 1 + ver3 / 10000
      : ver1 + ver2 / 100 + 0.01 + ver3 / 10000;
    const newVer1    = Math.floor(newVerFloat);
    const newVer2    = Math.round((newVerFloat - newVer1) * 10000);
    const newVersion = `${newVer1}.${String(newVer2).padStart(4, '0')}`;
    const content    = `${changeType}${changeDetail ? ' ' + changeDetail : ''}`;

    return this.prisma.$transaction(async (tx) => {
      await tx.mcProgram.update({
        where: { id },
        data:  { version: newVersion, status: 'CHANGING' },
      });
      await tx.mcChangeHistory.create({
        data: {
          mcProgramId:   id,
          changeType:    'CHANGE',
          operatorId,
          versionBefore: mc.version,
          versionAfter:  newVersion,
          content,
        },
      });
      return { mc_id: id, version: newVersion, message: `${changeType}として登録しました` };
    });
  }

  // ══════════════════════════════════════════
  // MC-05: 更新
  // ══════════════════════════════════════════
  async update(id: number, dto: UpdateMcDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);

    // VBA 終了確認ロジック準拠バージョンインクリ
    // version format: "1.0001" (整数部.4桁小数)
    const verStr = mc.version ?? '1.0001';
    const verFloat = parseFloat(verStr) || 1.0001;
    const ver1 = Math.floor(verFloat);                           // 整数部
    const ver2 = Math.floor(verFloat * 100) - ver1 * 100;       // 100分の1
    const ver3 = Math.floor(verFloat * 10000) - ver1 * 10000 - ver2 * 100; // 10000分の1
    // update時はバージョンを変えない（finalizeで行う）
    const newVerFloat = verFloat; // 変更なし
    // フォーマット: "2.0000" 形式に
    const newVer1 = Math.floor(newVerFloat);
    const newVer2 = Math.round((newVerFloat - newVer1) * 10000);
    const newVersion = `${newVer1}.${String(newVer2).padStart(4, '0')}`;

    return this.prisma.$transaction(async (tx) => {
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
    });
  }

  // ══════════════════════════════════════════
  // MC-06: 承認
  // ══════════════════════════════════════════
  async approve(id: number, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    if (mc.status === 'APPROVED') {
      throw new Error('既に承認済みです');
    }
    return this.prisma.$transaction(async (tx) => {
      await tx.mcProgram.update({
        where: { id },
        data: {
          status:     'APPROVED',
          approvedBy: operatorId,
          approvedAt: new Date(),
        },
      });
      await tx.mcChangeHistory.create({
        data: {
          mcProgramId:   id,
          changeType:    'APPROVAL',
          operatorId,
          versionBefore: mc.version,
          versionAfter:  mc.version,
          content:       '承認',
        },
      });
      await tx.operationLog.create({
        data: {
          userId:      operatorId,
          mcProgramId: id,
          actionType:  'MC_APPROVE',
          metadata:    { action: 'approve', version: mc.version },
        },
      });
      return { mc_id: id, message: '承認しました', version: mc.version };
    });
  }

  // ══════════════════════════════════════════
  // PGメタ更新
  // ══════════════════════════════════════════
  async updatePgMeta(id: number, pgCreatedBy: number) {
    return this.prisma.mcProgram.update({
      where: { id },
      data:  { pgCreatedBy, pgUpdatedAt: new Date() },
    });
  }

  // ══════════════════════════════════════════
  // ツーリングデータ
  // ══════════════════════════════════════════
  async getTooling(mcId: number) {
    return this.prisma.mcTooling.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { sortOrder: 'asc' },
    });
  }

  async saveTooling(mcId: number, dto: SaveToolingDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    return this.prisma.$transaction(async (tx) => {
      await tx.mcTooling.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcTooling.createMany({
          data: dto.items.map(item => ({
            mcProgramId:    mcId,
            sortOrder:      item.sort_order,
            toolNo:         item.tool_no,
            toolName:       item.tool_name       ?? null,
            diameter:       item.diameter        ?? null,
            lengthOffsetNo: item.length_offset_no ?? null,
            diaOffsetNo:    item.dia_offset_no   ?? null,
            toolType:       item.tool_type       ?? null,
            note:           item.note            ?? null,
            rawProgramLine: item.raw_program_line ?? null,
          })),
        });
      }
      // RC自動更新（ツーリング件数をmc_programsに反映）
      await tx.mcProgram.update({
        where: { id: mcId },
        data:  { rc: dto.items.length },
      });
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: mcId, actionType: 'MC_EDIT_SAVE', metadata: { action: 'save_tooling' } },
      });
      return { mc_id: mcId, count: dto.items.length, message: 'ツーリングデータを保存しました' };
    });
  }

  /** ツーリングプログラムテキスト解析（プレビュー用）*/
  parseToolingProgram(text: string) {
    const lines = text.split(/\r?\n/);
    const tools: any[] = [];
    const tLineRe = /T(\d+)/i;
    const hRe = /H(\d+)/i;
    const dRe = /D(\d+)/i;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith('%') || line.startsWith('(')) continue;
      const tMatch = line.match(tLineRe);
      if (!tMatch) continue;
      const toolNo = `T${tMatch[1].padStart(2, '0')}`;
      const hMatch = line.match(hRe);
      const dMatch = line.match(dRe);
      // 次行にコメントがあれば工具名として使用
      const nextLine = (lines[i + 1] ?? '').trim();
      const toolName = nextLine.startsWith('(') ? nextLine.replace(/[()]/g, '').trim() : undefined;

      tools.push({
        sort_order:       tools.length,
        tool_no:          toolNo,
        tool_name:        toolName,
        length_offset_no: hMatch ? `H${hMatch[1]}` : null,
        dia_offset_no:    dMatch ? `D${dMatch[1]}` : null,
        raw_program_line: line,
      });
    }
    return { count: tools.length, items: tools };
  }

  // ══════════════════════════════════════════
  // ワークオフセット
  // ══════════════════════════════════════════
  async getWorkOffsets(mcId: number) {
    return this.prisma.mcWorkOffset.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { gCode: 'asc' },
    });
  }

  async saveWorkOffsets(mcId: number, dto: SaveWorkOffsetsDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    return this.prisma.$transaction(async (tx) => {
      await tx.mcWorkOffset.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcWorkOffset.createMany({
          data: dto.items.map(item => ({
            mcProgramId: mcId,
            gCode:       item.g_code,
            xOffset:     item.x_offset ?? null,
            yOffset:     item.y_offset ?? null,
            zOffset:     item.z_offset ?? null,
            aOffset:     item.a_offset ?? null,
            rOffset:     item.r_offset ?? null,
            note:        item.note ?? null,
          })),
        });
      }
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: mcId, actionType: 'MC_EDIT_SAVE', metadata: { action: 'save_work_offsets' } },
      });
      return { mc_id: mcId, message: 'ワークオフセットを保存しました' };
    });
  }

  // ══════════════════════════════════════════
  // インデックスプログラム
  // ══════════════════════════════════════════
  async getIndexPrograms(mcId: number) {
    return this.prisma.mcIndexProgram.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { sortOrder: 'asc' },
    });
  }

  async saveIndexPrograms(mcId: number, dto: SaveIndexProgramsDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    return this.prisma.$transaction(async (tx) => {
      await tx.mcIndexProgram.deleteMany({ where: { mcProgramId: mcId } });
      if (dto.items.length > 0) {
        await tx.mcIndexProgram.createMany({
          data: dto.items.map(item => ({
            mcProgramId: mcId,
            sortOrder:   item.sort_order,
            axis0:       item.axis_0 ?? null,
            axis1:       item.axis_1 ?? null,
            axis2:       item.axis_2 ?? null,
            note:        item.note   ?? null,
          })),
        });
      }
      return { mc_id: mcId, message: 'インデックスプログラムを保存しました' };
    });
  }

  // ══════════════════════════════════════════
  // 作業記録
  // ══════════════════════════════════════════
  async workRecords(mcId: number) {
    const rows = await this.prisma.workRecord.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { workDate: 'desc' },
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    return rows.map(r => ({
      id:              r.id,
      work_date:       r.workDate,
      work_type:       r.workType,
      operator_name:   r.operator?.name ?? null,
      machine_code:    r.machine?.machineCode ?? null,
      setup_time_min:    r.setupTimeMin,
      machining_time_min: r.machiningTimeMin,
      cycle_time_sec:  r.cycleTimeSec,
      quantity:        r.quantity,
      setup_work_count: r.setupWorkCount,
      started_at:      r.startedAt,
      checked_at:      r.checkedAt,
      finished_at:     r.finishedAt,
      interrupt_setup_min: r.interruptSetupMin,
      interrupt_work_min:  r.interruptWorkMin,
      note:            r.note,
      setup_operator_ids:      r.setupOperatorIds,
      production_operator_ids: r.productionOperatorIds,
      prg_man:         (r as any).prgMan      ?? null,
      prg_time_min:    (r as any).prgTimeMin  ?? null,
      prg_plas:        (r as any).prgPlas     ?? null,
    }));
  }

  async createWorkRecord(mcId: number, dto: CreateMcWorkRecordDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    // 時刻から時間を自動計算
    let setupMin = dto.setup_time_min ?? null;
    let machMin  = dto.machining_time_min ?? null;

    if (dto.started_at && dto.finished_at) {
      const start   = new Date(dto.started_at);
      const checked = dto.checked_at ? new Date(dto.checked_at) : null;
      const finish  = new Date(dto.finished_at);
      const interruptSetup = dto.interrupt_setup_min ?? 0;
      const interruptWork  = dto.interrupt_work_min  ?? 0;

      if (checked) {
        setupMin = Math.max(0, Math.round((checked.getTime() - start.getTime()) / 60000) - interruptSetup);
        machMin  = Math.max(0, Math.round((finish.getTime() - checked.getTime()) / 60000) - interruptWork);
      } else {
        const total = Math.max(0, Math.round((finish.getTime() - start.getTime()) / 60000) - interruptSetup - interruptWork);
        setupMin = total;
        machMin  = total;
      }
    }

    const record = await this.prisma.workRecord.create({
      data: {
        mcProgramId:      mcId,
        operatorId,
        machineId:        dto.machine_id ?? mc.machineId ?? null,
        workDate:         new Date(),
        workType:         dto.work_type  ?? null,
        setupTimeMin:     setupMin,
        machiningTimeMin: machMin,
        cycleTimeSec:     dto.cycle_time_sec   ?? null,
        quantity:         dto.quantity         ?? null,
        setupWorkCount:   dto.setup_work_count ?? null,
        startedAt:        dto.started_at  ? new Date(dto.started_at)  : null,
        checkedAt:        dto.checked_at  ? new Date(dto.checked_at)  : null,
        finishedAt:       dto.finished_at ? new Date(dto.finished_at) : null,
        interruptSetupMin: dto.interrupt_setup_min ?? null,
        interruptWorkMin:  dto.interrupt_work_min  ?? null,
        note:             dto.note ?? null,
        setupOperatorIds:      dto.setup_operator_ids      ?? [],
        productionOperatorIds: dto.production_operator_ids ?? [],
        prgMan:            dto.prg_man       ?? null,
        prgTimeMin:        dto.prg_time_min  ?? null,
        prgPlas:           dto.prg_plas      ?? null,
      },
    });
    await this.prisma.operationLog.create({
      data: { userId: operatorId, mcProgramId: mcId, actionType: 'MC_WORK_RECORD', metadata: { recordId: record.id } },
    });
    return { id: record.id, message: '作業記録を登録しました' };
  }

  // ══════════════════════════════════════════
  // 変更履歴
  // ══════════════════════════════════════════
  async changeHistory(mcId: number) {
    const rows = await this.prisma.mcChangeHistory.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { changedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      changed_at:     r.changedAt,
      change_type:    r.changeType,
      operator_name:  r.operator?.name ?? null,
      ver_before:     r.versionBefore ?? null,
      ver_after:      r.versionAfter  ?? null,
      change_detail:  r.content       ?? null,
    }));
  }

  // ══════════════════════════════════════════
  // 段取シートログ
  // ══════════════════════════════════════════
  async setupSheetLogs(mcId: number) {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    const logsAsc = [...rows].sort((a, b) => a.id - b.id);
    return rows.map(r => {
      const rank = logsAsc.findIndex(x => x.id === r.id) + 1;
      return {
        id:             r.id,
        printed_at:     r.printedAt,
        version:        r.version ?? null,
        operator_name:  r.operator?.name ?? null,
        work_collected: r.workCollected,
        is_reference:   (r as any).isReference ?? false,
        sheet_type:     rank === 1 ? 'NEW' : 'REPEAT',
      };
    });
  }

  /** 段取シートバック: legacy_mcid で未回収シート一覧取得 */
  async uncollectedByLegacy(legacyMcid: number) {
    // legacyMcid に一致する mc_programs を取得（複数の工程がある場合あり）
    const programs = await this.prisma.mcProgram.findMany({
      where: { legacyMcid },
      select: { id: true, machiningId: true, mcProcessNo: true,
                part: { select: { drawingNo: true, name: true } } },
    });
    if (programs.length === 0) {
      return { found: false, programs: [], sheets: [] };
    }
    const programIds = programs.map(p => p.id);
    const sheets = await this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: { in: programIds }, workCollected: false },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    // 印刷タイプ判別: 最初のシート印刷かどうか（当該プログラムの印刷回数）
    const allSheetCounts = await this.prisma.mcSetupSheetLog.groupBy({
      by: ['mcProgramId'],
      where: { mcProgramId: { in: programIds } },
      _count: { id: true },
    });
    const countMap = new Map(allSheetCounts.map(r => [r.mcProgramId, r._count.id]));
    return {
      found:    true,
      programs: programs.map(p => ({
        mc_id:          p.id,
        machining_id:   p.machiningId,
        mc_process_no:  p.mcProcessNo,
        drawing_no:     p.part.drawingNo,
        part_name:      p.part.name,
        total_sheets:   countMap.get(p.id) ?? 0,
        // total_sheets=1 かつ uncollected → 新規（初回印刷）
        // total_sheets>1 または 既収済みあり → リピート
        sheet_type:     (countMap.get(p.id) ?? 0) <= 1 ? 'NEW' : 'REPEAT',
      })),
      sheets: sheets.map(s => ({
        id:           s.id,
        mc_id:        s.mcProgramId,
        printed_at:   s.printedAt,
        version:      s.version ?? null,
        operator_name: s.operator?.name ?? null,
        work_collected: s.workCollected,
        is_reference:   (s as any).isReference ?? false,
      })),
    };
  }

  /** SSL-MC-01: 段取シート回収済みマーク */
  async collectSetupSheet(logId: number) {
    await this.prisma.mcSetupSheetLog.update({
      where: { id: logId },
      data:  { workCollected: true },
    });
    return { message: '段取シートを回収済みにしました' };
  }

  // ══════════════════════════════════════════
  // ファイル一覧
  // ══════════════════════════════════════════
  async listFiles(mcId: number) {
    const files = await this.prisma.mcFile.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { uploadedAt: 'desc' },
      include: { uploader: { select: { name: true } } },
    });
    return files.map(f => ({
      id:            f.id,
      file_type:     f.fileType,
      original_name: f.originalName,
      mime_type:     f.mimeType,
      file_path:     f.filePath,
      thumbnail_path: f.thumbnailPath,
      file_size:     f.fileSize,
      uploaded_by:   f.uploader.name,
      uploaded_at:   f.uploadedAt,
    }));
  }

  // ══════════════════════════════════════════
  // 段取シートデータ取得（PDF生成用）
  // ══════════════════════════════════════════
  async getPrintData(mcId: number) {
    const r = await this.prisma.mcProgram.findUnique({
      where: { id: mcId },
      include: {
        part:    true,
        machine: true,
        registrar: { select: { name: true } },
        approver:  { select: { name: true } },
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets:   { orderBy: { gCode: 'asc' } },
        indexPrograms: { orderBy: { sortOrder: 'asc' } },
        files: { where: { fileType: 'DRAWING' }, orderBy: { uploadedAt: 'desc' } },
      },
    });
    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);

    const commonGroup = await this.prisma.mcProgram.findMany({
      where:   { machiningId: r.machiningId },
      orderBy: { id: 'asc' },
      select:  { id: true, version: true, part: { select: { drawingNo: true, name: true } } },
    });
    return { ...r, commonGroup };
  }

  // ══════════════════════════════════════════
  // 機械タイムカード
  // ══════════════════════════════════════════
  async getTimecardsByDate(workDate: string) {
    return this.prisma.machineTimecard.findMany({
      where:   { workDate: new Date(workDate) },
      orderBy: [{ machineId: 'asc' }, { startTime: 'asc' }],
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true, machineName: true } },
      },
    });
  }

  async getTimecards(machineId: number, workDate: string) {
    return this.prisma.machineTimecard.findMany({
      where:   { machineId, workDate: new Date(workDate) },
      orderBy: { startTime: 'asc' },
      include: { operator: { select: { name: true } } },
    });
  }

  async deleteTimecard(id: number) {
    await this.prisma.machineTimecard.delete({ where: { id } });
    return { message: 'タイムカードを削除しました' };
  }

  async updateTimecard(id: number, startTime: string, endTime: string, note?: string) {
    const tc = await this.prisma.machineTimecard.findUnique({ where: { id }, select: { workDate: true } });
    if (!tc) throw new Error('タイムカードが見つかりません');
    // work_dateをYYYY-MM-DDに変換（UTC補正: toLocaleDateStringではなくISO+9h）
    const d = tc.workDate;
    const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    return this.prisma.machineTimecard.update({
      where: { id },
      data: {
        startTime: new Date(`${dateStr}T${startTime}`),
        endTime:   new Date(`${dateStr}T${endTime}`),
        note:      note ?? null,
      },
    });
  }

  // 毎朝5:00に全MC機械のデフォルトタイムカード自動生成
  @Cron('0 5 * * *')
  async cronInitTimecards() {
    const today = new Date();
    const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    try {
      await this.initTimecards(workDate, 1); // operatorId=1 (admin)
      console.log(`[Cron] ${workDate} 機械タイムカード自動生成完了`);
    } catch (e) {
      console.error('[Cron] タイムカード自動生成エラー', e);
    }
  }

  // 全activeマシンの当日デフォルトレコード一括生成（upsert: 既存があれば何もしない）
  async initTimecards(workDate: string, operatorId: number) {
    const machines = await this.prisma.machine.findMany({
      where: { isActive: true },
      orderBy: { sortOrder: 'asc' },
    });
    // UNIQUE(machine_id, work_date)制約を利用してupsert
    const created: number[] = [];
    for (const m of machines) {
      try {
        const tc = await this.prisma.machineTimecard.upsert({
          where: {
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-ignore — Prisma generates compound unique key after migration
            machine_timecards_machine_id_work_date_key: { machineId: m.id, workDate: new Date(workDate) },
          },
          update: {}, // 既存レコードは更新しない
          create: {
            machineId:  m.id,
            operatorId,
            workDate:   new Date(workDate),
            startTime:  new Date(`${workDate}T08:00:00`),
            endTime:    new Date(`${workDate}T17:00:00`),
          },
        });
        created.push(tc.id);
      } catch {
        // UNIQUE制約違反（既存あり）は無視
      }
    }
    return { created: created.length, message: `処理完了` };
  }

  async createTimecard(
    machineId: number, operatorId: number,
    workDate: string, startTime: string, endTime: string, note?: string,
  ) {
    const tc = await this.prisma.machineTimecard.create({
      data: {
        machineId,
        operatorId,
        workDate:  new Date(workDate),
        startTime: new Date(`${workDate}T${startTime}`),
        endTime:   new Date(`${workDate}T${endTime}`),
        note:      note ?? null,
      },
    });
    return { id: tc.id, message: 'タイムカードを登録しました' };
  }

  // ══════════════════════════════════════════
  // 共通加工グループ一覧
  // ══════════════════════════════════════════
  async getCommonGroup(machiningId: number) {
    return this.prisma.mcProgram.findMany({
      where:   { machiningId },
      orderBy: { id: 'asc' },
      include: {
        part:    { select: { drawingNo: true, name: true, clientName: true } },
        machine: { select: { machineCode: true } },
      },
    });
  }

  // ══════════════════════════════════════════
  // 段取シートPDF生成（pdf-lib テンプレ差し込み方式）
  // ══════════════════════════════════════════
  async generateSetupSheetPdf(
    mcId: number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
    },
  ): Promise<Buffer> {
    const data = await this.getPrintData(mcId) as any;

    // pdf-lib / fontkit
    const { PDFDocument, rgb } = await import('pdf-lib');
    const fontkit = await import('@pdf-lib/fontkit');
    const FONT_PATH = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
    const fontBytes = fs.readFileSync(FONT_PATH);

    // テンプレートPDFパス
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const p1Bytes = fs.readFileSync(`${ASSETS}/template_p1.pdf`);
    const p2Bytes = fs.readFileSync(`${ASSETS}/template_p2.pdf`);

    // DBからフィールド定義取得（pg直接クエリ）
    const { Pool } = await import('pg');
    const DB_URL = process.env.DATABASE_URL || 'postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public';
    const pool = new Pool({ connectionString: DB_URL });
    const qr = await pool.query(`
      SELECT t.id, t.name, t.page_number,
             f.field_key, f.label, f.x, f.y, f.font_size, f.data_source, f.sort_order, f.note
      FROM pdf_templates t
      JOIN pdf_field_definitions f ON f.template_id = t.id
      WHERE t.name IN ('mc_setup_p1','mc_setup_p2')
        AND t.is_active = true AND f.is_active = true
      ORDER BY t.page_number, f.sort_order
    `);
    await pool.end();
    const templates: any[] = qr.rows;

    // データ解決ヘルパー
    const resolve = (src: string): string => {
      const keys = src.split('.');
      let val: any = data;
      for (const k of keys) { val = val?.[k]; if (val === undefined || val === null) return ''; }
      if (src === 'version') {
        const v = String(val ?? '1.0001');
        return v.replace(/^(\d+)\.(\d{4})$/, (_,a,b) => a+'.'+b.slice(0,2)+' '+b.slice(2));
      }
      return String(val ?? '');
    };

    // P1生成
    const p1Doc = await PDFDocument.load(p1Bytes);
    p1Doc.registerFontkit(fontkit.default ?? fontkit);
    const font1 = await p1Doc.embedFont(fontBytes);
    const p1Page = p1Doc.getPage(0);
    const p1H = p1Page.getHeight();

    console.log('[PDF] templates count:', templates.length);

    // 備考の複数行描画ヘルパー
    const drawMultiLine = (page: any, text: string, x: number, y: number, size: number, font: any, lineH?: number) => {
      const lh = lineH ?? size * 1.4;
      const lines = text.split(/\n|\r\n/);
      lines.forEach((line: string, i: number) => {
        if (!line.trim()) return;
        page.drawText(line, { x, y: y - i * lh, size, font, color: rgb(0,0,0) });
      });
    };

    const p1Fields = templates.filter(f => f.name === 'mc_setup_p1');
    for (const f of p1Fields) {
      // __page_no__ は「1 / 2」固定
      if (f.field_key === '__page_no__') {
        p1Page.drawText('1 / 2', {
          x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: font1, color: rgb(0,0,0),
        });
        continue;
      }
      const text = resolve(f.data_source);
      if (!text) continue;
      // 備考フィールドは改行対応
      if (f.field_key === 'note' && text.includes('\n')) {
        drawMultiLine(p1Page, text, Number(f.x), Number(f.y), Number(f.font_size), font1);
      } else {
        p1Page.drawText(text, {
          x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: font1, color: rgb(0,0,0),
        });
      }
    }

    // ツーリングリスト差し込み（include_tooling=trueの場合のみ）
    if (options.include_tooling === true && data.tooling?.length > 0) {
      const { Pool: Pool2 } = await import('pg');
      const DB_URL2 = process.env.DATABASE_URL || 'postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public';
      const pool2 = new Pool2({ connectionString: DB_URL2 });
      const toolQr = await pool2.query(`
        SELECT * FROM pdf_field_definitions
        WHERE template_id = (SELECT id FROM pdf_templates WHERE name='mc_setup_p1')
          AND field_key LIKE 'tooling_%' AND is_active = true
        ORDER BY sort_order
      `);
      await pool2.end();
      const toolFields: any[] = toolQr.rows;
      // ツーリング行はfield_key='tooling_row'の定義を使用
      const rowDef = toolFields.find((f:any) => f.field_key === 'tooling_row');
      if (rowDef) {
        const ROW_H = Number(rowDef.note ?? '15'); // note列に行高を格納
        const COLS = ['toolNo','toolName','tNumber','hValue','dRegister','dValue','subProgram','note'];
        const COL_XS = String(rowDef.data_source).split(',').map(Number);
        data.tooling.slice(0, 24).forEach((t: any, ri: number) => {
          const ry = p1H - Number(rowDef.y) - ri * ROW_H;
          COLS.forEach((col, ci) => {
            const val = String(t[col] ?? '');
            if (!val || !COL_XS[ci]) return;
            p1Page.drawText(val, { x: COL_XS[ci], y: ry, size: 7, font: font1, color: rgb(0,0,0) });
          });
        });
      }
    }

    // P2生成
    const p2Doc = await PDFDocument.load(p2Bytes);
    p2Doc.registerFontkit(fontkit.default ?? fontkit);
    const font2 = await p2Doc.embedFont(fontBytes);
    const p2Page = p2Doc.getPage(0);
    const p2H = p2Page.getHeight();

    const p2Fields = templates.filter(f => f.name === 'mc_setup_p2');
    for (const f of p2Fields) {
      if (f.field_key === '__page_no__') {
        p2Page.drawText('2 / 2', {
          x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: font2, color: rgb(0,0,0),
        });
        continue;
      }
      const text = resolve(f.data_source);
      if (!text) continue;
      if (f.field_key === 'note' && text.includes('\n')) {
        const lh = Number(f.font_size) * 1.4;
        text.split(/\n|\r\n/).forEach((line: string, i: number) => {
          if (!line.trim()) return;
          p2Page.drawText(line, { x: Number(f.x), y: Number(f.y) - i * lh, size: Number(f.font_size), font: font2, color: rgb(0,0,0) });
        });
      } else {
        p2Page.drawText(text, {
          x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: font2, color: rgb(0,0,0),
        });
      }
    }

    // P1+P2を結合して2ページPDFに
    const finalDoc = await PDFDocument.create();
    finalDoc.registerFontkit(fontkit.default ?? fontkit);
    const [copiedP1] = await finalDoc.copyPages(p1Doc, [0]);
    const [copiedP2] = await finalDoc.copyPages(p2Doc, [0]);
    finalDoc.addPage(copiedP1);
    finalDoc.addPage(copiedP2);

    // ── プレビュー透かし処理 ──
    const isPreview = (options as any).is_preview === true;
    if (isPreview) {
      // 全ページに「プレビュー」透かしを描画
      const allPages = finalDoc.getPages();
      const fontkit2 = await import('@pdf-lib/fontkit');
      finalDoc.registerFontkit(fontkit2.default ?? fontkit2);
      const FONT_PATH2 = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
      const fontBytes2 = fs.readFileSync(FONT_PATH2);
      const wFont = await finalDoc.embedFont(fontBytes2);
      const { degrees } = await import('pdf-lib');
      for (const page of allPages) {
        const { width, height } = page.getSize();
        // 対角方向に「プレビュー」を薄いグレーで複数回描画
        const wText = 'プレビュー';
        const wSize = 60;
        const wColor = rgb(0.75, 0.75, 0.75);
        const positions = [
          { x: width * 0.15, y: height * 0.25 },
          { x: width * 0.35, y: height * 0.55 },
          { x: width * 0.55, y: height * 0.75 },
        ];
        for (const pos of positions) {
          page.drawText(wText, {
            x: pos.x, y: pos.y,
            size: wSize,
            font: wFont,
            color: wColor,
            rotate: degrees(35),
            opacity: 0.35,
          });
        }
      }
    }

    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

    // プレビューの場合はDB記録・ファイル保存をスキップ
    if (!isPreview) {
      await this.prisma.mcSetupSheetLog.create({
        data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
                ...(typeof (options as any).is_reference !== 'undefined' ? { isReference: (options as any).is_reference } : {}) },
      }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));
    }

    return pdfBuffer;
  }



  // ══════════════════════════════════════════
  // 新規仮データでプレビューPDF生成（DBに保存しない）
  // ══════════════════════════════════════════
  async previewNew(dto: any, operatorId: number): Promise<Buffer> {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);
    const machine = dto.machine_id
      ? await this.prisma.machine.findUnique({ where: { id: dto.machine_id } })
      : null;

    // 一時MCレコードを作成してPDF生成し、その後削除
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
    });

    try {
      const pdfBuffer = await this.generateSetupSheetPdf(tempMc.id, operatorId, {
        include_tooling:  false,
        include_clamp:    false,
        include_drawings: dto.include_drawings ?? false,
        is_preview:       true,
      } as any);
      return pdfBuffer;
    } finally {
      // 必ずDB削除（プレビューなのでデータ残さない）
      await this.prisma.mcProgram.delete({ where: { id: tempMc.id } }).catch(() => {});
    }
  }

  // ══════════════════════════════════════════
  // MC新規作成+段取シート印刷 (1トランザクション)
  // 競合時は次の加工IDで再試行
  // ══════════════════════════════════════════
  async createAndPrint(dto: any, operatorId: number): Promise<Buffer> {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);

    let machiningId: number = dto.machining_id;
    let mcId: number | null = null;
    let retried = false;

    for (let attempt = 0; attempt < 3; attempt++) {
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
          });
          await tx.mcChangeHistory.create({
            data: {
              mcProgramId:  created.id,
              changeType:   'NEW_REGISTRATION',
              operatorId,
              versionAfter: created.version,
              content:      '新規登録',
            },
          });
          await tx.operationLog.create({
            data: { userId: operatorId, mcProgramId: created.id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'create' } },
          });
          return created;
        });
        mcId = mc.id;
        break;
      } catch (e: any) {
        if (e.code === 'P2002') {
          // unique制約違反 → 次の加工IDで再試行
          const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
          machiningId = (agg._max.machiningId ?? 0) + 1;
          retried = true;
        } else {
          throw e;
        }
      }
    }

    if (mcId === null) throw new Error('加工IDの確定に失敗しました。再度お試しください。');

    // PDF生成 + 印刷ログ記録
    const pdfBuffer = await this.generateSetupSheetPdf(mcId, operatorId, {
      include_tooling: false,
      include_clamp:   false,
      include_drawings: dto.include_drawings ?? false,
    });

    // プリンタへ送信
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true, mcPrinter: true } });
    const printerName = setting?.mcPrinter || setting?.printerName;
    if (!printerName) throw new Error('MCプリンタが設定されていません。管理画面のシステム設定でMCチーム用プリンタを設定してください。');
    const tmpPath = `/tmp/machcore-mc-newprint-${mcId}-${Date.now()}.pdf`;
    fs.writeFileSync(tmpPath, pdfBuffer);
    try {
      execSync(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs.unlinkSync(tmpPath); } catch { /**/ }
    }

    return Buffer.from(JSON.stringify({
      mc_id:        mcId,
      machining_id: machiningId,
      retried,
      message:      retried
        ? `加工IDが競合したため ${machiningId} で登録しました。${printerName} に送信しました`
        : `${printerName} に送信しました`,
    }));
  }


  // ══════════════════════════════════════════════════════
  // リピート段取シートPDF生成 v2 (テンプレ+DB座標方式)
  // 構成: ①repeat_header.pdf ②repeat_tooling.pdf ③repeat_wo.pdf ④repeat_ip.pdf
  //       最終ページ: template_p2.pdf（作業記録ページ）
  // ══════════════════════════════════════════════════════
  async generateRepeatSetupSheetPdf(
    mcId:       number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
      is_reference?:           boolean;
      is_preview?:             boolean;
    } = {},
  ): Promise<Buffer> {
    const data = await this.getPrintData(mcId) as any;
    const d    = data as any;
    const part    = d.part    ?? {};
    const machine = d.machine ?? {};

    const FONT_PATH = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
    const ASSETS    = '/home/karkyon/projects/machcore/apps/api/assets';

    const { PDFDocument: PDFLib, rgb, degrees } = await import('pdf-lib');
    const fontkit = await import('@pdf-lib/fontkit');
    const fontBytes = fs.readFileSync(FONT_PATH);

    // ── DB からフィールド定義を一括取得 ──
    const { Pool } = await import('pg');
    const DB_URL = process.env.DATABASE_URL || 'postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public';
    const pool = new Pool({ connectionString: DB_URL });
    const qr = await pool.query(`
      SELECT t.name as tpl_name, f.field_key, f.label, f.x, f.y, f.font_size, f.data_source, f.sort_order, f.note
      FROM pdf_templates t
      JOIN pdf_field_definitions f ON f.template_id = t.id
      WHERE t.name IN ('repeat_header','repeat_tooling','repeat_wo','repeat_ip','mc_setup_p2')
        AND t.is_active = true AND f.is_active = true
      ORDER BY t.id, f.sort_order
    `);
    await pool.end();
    const allFields: any[] = qr.rows;
    const fieldsByTpl = (tpl: string) => allFields.filter((f: any) => f.tpl_name === tpl);

    // ── ヘルパー ──
    const fmtDate = (v: any) => {
      if (!v) return '';
      const dt = new Date(v);
      return `${dt.getFullYear()}/${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`;
    };
    const fmtVer = (v: string) => v.replace(/^(\d+)\.(\d{4})$/,(_:any,a:any,b:any)=>a+'.'+b.slice(0,2)+' '+b.slice(2));
    const fmtCycle = (sec: number|null) => {
      if (!sec) return '';
      const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;
      return `${h}H ${String(m).padStart(2,'0')}M ${String(s).padStart(2,'0')}S`;
    };
    const resolveHeader = (src2: string): string => {
      if (src2 === 'part.clientName')     return part.clientName   ?? '';
      if (src2 === 'part.drawingNo')      return part.drawingNo    ?? '';
      if (src2 === 'part.name')           return part.name         ?? '';
      if (src2 === 'part.mainModel')      return part.mainModel    ?? '';
      if (src2 === 'machine.machineCode') return machine.machineCode ?? '';
      if (src2 === 'mcProcessNo')         return d.mcProcessNo != null ? String(d.mcProcessNo) : '';
      if (src2 === 'oNumber')             return d.oNumber ?? '';
      if (src2 === 'version')             return fmtVer(String(d.version ?? '1.0001'));
      if (src2 === 'cycleTimeSec')        return fmtCycle(d.cycleTimeSec);
      if (src2 === 'machiningQty')        return d.machiningQty != null ? String(d.machiningQty) : '';
      if (src2 === 'approvedAt')          return fmtDate(d.approvedAt);
      if (src2 === 'registeredAt')        return fmtDate(d.registeredAt ?? d.createdAt);
      return '';
    };

    // ── pdfkit で ①〜④ のページ群を生成 ──
    const PDFKitMod  = await import('pdfkit');
    const PDFDocument: any = (PDFKitMod as any).default ?? PDFKitMod;
    const A4_H = 841.89;
    const ML   = 30.4;
    const PW   = 526.2;
    const MR   = ML + PW;
    const F    = 'IPA';
    const PAGE_TOP    = 25;
    const PAGE_BOTTOM = 25;
    const CONTENT_H   = A4_H - PAGE_TOP - PAGE_BOTTOM;

    const doc: any = new PDFDocument({ size: 'A4', margin: 0, autoFirstPage: false });
    doc.registerFont(F, FONT_PATH);
    const chunks: Buffer[] = [];
    doc.on('data', (c: Buffer) => chunks.push(c));

    const strokeN = () => doc.strokeColor('#000000').lineWidth(0.5);
    const strokeB = () => doc.strokeColor('#000000').lineWidth(1.0);
    const grayCell = (x:number,y:number,w:number,h:number,t:string,fs=6.0) => {
      strokeN(); doc.rect(x,y,w,h).fillAndStroke('#e8e8e8','#000000');
      doc.font(F).fontSize(fs).fillColor('#000000');
      doc.text(t, x+1.5, y+(h-fs*0.72)/2, {width:w-3, lineBreak:false});
    };
    const cellR = (x:number,y:number,w:number,h:number) => { strokeN(); doc.rect(x,y,w,h).stroke(); };
    const cellT = (x:number,y:number,w:number,h:number,t:string,fs:number,al:'left'|'center'='left') => {
      if (!t) return;
      doc.font(F).fontSize(fs).fillColor('#000000');
      const ty = y+(h-fs*0.72)/2;
      if (al==='center') doc.text(t, x, ty, {width:w, align:'center', lineBreak:false});
      else doc.text(t, x+2, ty, {width:w-4, lineBreak:false});
    };
    const drawPageNo = (cur: number) => {
      const PBW = 44.2, PBH = 21.3;
      const bx = MR - PBW, by = A4_H - PAGE_BOTTOM - PBH;
      strokeN();
      doc.rect(bx,       by, PBW/2, PBH).stroke();
      doc.rect(bx+PBW/2, by, PBW/2, PBH).stroke();
      doc.font(F).fontSize(6.5).fillColor('#000000');
      doc.text(String(cur), bx+1,       by+(PBH-6.5*0.72)/2, {width:PBW/2-2, align:'center', lineBreak:false});
      doc.text('N',         bx+PBW/2+1, by+(PBH-6.5*0.72)/2, {width:PBW/2-2, align:'center', lineBreak:false});
    };

    let curY    = PAGE_TOP;
    let pageNum = 0;
    const addPage = () => {
      doc.addPage({ size: 'A4', margin: 0 });
      pageNum++;
      curY = PAGE_TOP;
      strokeB(); doc.rect(ML, PAGE_TOP, PW, CONTENT_H - 21.3).stroke();
    };
    const ensureSpace = (need: number): boolean => {
      if (A4_H - PAGE_BOTTOM - 21.3 - curY < need) {
        drawPageNo(pageNum); addPage(); return true;
      }
      return false;
    };

    // ── ① 基本情報ヘッダ ──
    addPage();
    const H1 = 21.3, COL1 = 55;

    grayCell(ML, curY, PW, H1, 'リピート 段取シート', 9.0); curY += H1;

    // 行1: 納入先 + 図面番号
    grayCell(ML, curY, COL1, H1, '納入先', 6.0);
    cellR(ML+COL1, curY, 150, H1);
    cellT(ML+COL1, curY, 150, H1, resolveHeader('part.clientName'), 7.0);
    grayCell(ML+COL1+150, curY, COL1, H1, '図面番号', 6.0);
    const remW1 = PW - COL1 - 150 - COL1;
    cellR(ML+COL1+150+COL1, curY, remW1, H1);
    cellT(ML+COL1+150+COL1, curY, remW1, H1, resolveHeader('part.drawingNo'), 7.0);
    curY += H1;

    // 行2: 名称
    grayCell(ML, curY, COL1, H1, '名称', 6.0);
    cellR(ML+COL1, curY, PW-COL1, H1);
    cellT(ML+COL1, curY, PW-COL1, H1, resolveHeader('part.name'), 7.0);
    curY += H1;

    // 行3: 主機種型式 + 機械
    grayCell(ML, curY, COL1, H1, '主機種型式', 6.0);
    cellR(ML+COL1, curY, 120, H1);
    cellT(ML+COL1, curY, 120, H1, resolveHeader('part.mainModel'), 7.0);
    grayCell(ML+COL1+120, curY, COL1, H1, '機械', 6.0);
    const remW3 = PW - COL1 - 120 - COL1;
    cellR(ML+COL1+120+COL1, curY, remW3, H1);
    cellT(ML+COL1+120+COL1, curY, remW3, H1, resolveHeader('machine.machineCode'), 7.0);
    curY += H1;

    // 行4: 工程No / ONo / VER
    const C4 = [
      {lbl:'工程No', lw:COL1, vw:40,  key:'mcProcessNo'},
      {lbl:'ONo',    lw:COL1, vw:60,  key:'oNumber'},
      {lbl:'VER',    lw:COL1, vw:60,  key:'version'},
    ] as const;
    let x4 = ML;
    for (const c of C4) {
      grayCell(x4, curY, c.lw, H1, c.lbl, 6.0);
      cellR(x4+c.lw, curY, c.vw, H1);
      cellT(x4+c.lw, curY, c.vw, H1, resolveHeader(c.key), 7.0, 'center');
      x4 += c.lw + c.vw;
    }
    cellR(ML + C4.reduce((s,c)=>s+c.lw+c.vw,0), curY, PW - C4.reduce((s,c)=>s+c.lw+c.vw,0), H1);
    curY += H1;

    // 行5: CT / 数量 / 承認日 / 登録日
    const C5 = [
      {lbl:'CT',    lw:COL1, vw:60, key:'cycleTimeSec'},
      {lbl:'数量',  lw:COL1, vw:40, key:'machiningQty'},
      {lbl:'承認日',lw:COL1, vw:70, key:'approvedAt'},
    ] as const;
    const usedW5 = C5.reduce((s,c)=>s+c.lw+c.vw, 0);
    let x5 = ML;
    for (const c of C5) {
      grayCell(x5, curY, c.lw, H1, c.lbl, 6.0);
      cellR(x5+c.lw, curY, c.vw, H1);
      cellT(x5+c.lw, curY, c.vw, H1, resolveHeader(c.key), 7.0, 'center');
      x5 += c.lw + c.vw;
    }
    grayCell(x5, curY, COL1, H1, '登録日', 6.0);
    cellR(x5+COL1, curY, PW-usedW5-COL1, H1);
    cellT(x5+COL1, curY, PW-usedW5-COL1, H1, resolveHeader('registeredAt'), 7.0, 'center');
    curY += H1;

    // 備考・クランプ（可変高さ）
    const noteText  = d.note ?? '';
    const clampText = options.include_clamp !== false ? (d.clampNote ?? '') : '';
    const NOTE_FS = 7.0, NOTE_LH = NOTE_FS * 1.4;
    const NOTE_H  = Math.max(H1 * 2, (Math.max(noteText  ? noteText.split(/\n|\r\n/).length  : 1, 1) + 1) * NOTE_LH + 4);
    const CLAMP_H = Math.max(H1 * 2, (Math.max(clampText ? clampText.split(/\n|\r\n/).length : 1, 1) + 1) * NOTE_LH + 4);

    grayCell(ML, curY, COL1, NOTE_H, '備考', 6.0);
    cellR(ML+COL1, curY, PW-COL1, NOTE_H);
    if (noteText) { doc.font(F).fontSize(NOTE_FS).fillColor('#000000'); doc.text(noteText, ML+COL1+2, curY+3, {width:PW-COL1-4, lineBreak:true}); }
    curY += NOTE_H;

    grayCell(ML, curY, COL1, CLAMP_H, 'クランプ', 6.0);
    cellR(ML+COL1, curY, PW-COL1, CLAMP_H);
    if (clampText) { doc.font(F).fontSize(NOTE_FS).fillColor('#000000'); doc.text(clampText, ML+COL1+2, curY+3, {width:PW-COL1-4, lineBreak:true}); }
    curY += CLAMP_H + 4;

    // ── ② ツーリングリスト ──
    const tooling = (options.include_tooling !== false) ? (d.tooling ?? []) : [];
    if (tooling.length > 0) {
      const tCols = fieldsByTpl('repeat_tooling').filter((f: any) => f.field_key.startsWith('col_'));
      const rowCfg = fieldsByTpl('repeat_tooling').find((f: any) => f.field_key === '__row_cfg__');
      const TH = rowCfg ? parseFloat(rowCfg.font_size) : 14.0;
      const getColX = (key: string, def: number) => tCols.find((c:any)=>c.field_key===key)?.x ?? def;
      const getColW = (key: string, def: string) => parseFloat(tCols.find((c:any)=>c.field_key===key)?.note ?? def);
      const TCOLS = [
        {x:getColX('col_n',30),        w:getColW('col_n','20'),        key:'toolNo',   al:'center' as const},
        {x:getColX('col_tool_name',50), w:getColW('col_tool_name','105'),key:'toolName', al:'left'   as const},
        {x:getColX('col_t_no',155),    w:getColW('col_t_no','25'),     key:'tNumber',  al:'center' as const},
        {x:getColX('col_h_val',180),   w:getColW('col_h_val','25'),    key:'hValue',   al:'center' as const},
        {x:getColX('col_d_reg',205),   w:getColW('col_d_reg','30'),    key:'dRegister',al:'center' as const},
        {x:getColX('col_d_val',235),   w:getColW('col_d_val','30'),    key:'dValue',   al:'center' as const},
        {x:getColX('col_sub_pg',265),  w:getColW('col_sub_pg','55'),   key:'subPgNo',  al:'center' as const},
        {x:getColX('col_note',320),    w:getColW('col_note','236'),    key:'note',     al:'left'   as const},
      ] as const;
      const TLABELS = ['N','工具名称（加工種別）','T番号','H値','D登録','D値','サブPG','備考'];
      const SEC_H = 12;
      const drawTHdr = () => { for(let i=0;i<TCOLS.length;i++) grayCell(TCOLS[i].x,curY,TCOLS[i].w,TH,TLABELS[i],5.5); curY+=TH; };
      ensureSpace(SEC_H+TH*3);
      grayCell(ML,curY,PW,SEC_H,'■ ツーリングリスト',7.0); curY+=SEC_H;
      drawTHdr();
      const getV = (t:any,key:string) => {
        if(key==='toolNo')    return String(t.toolNo??t.sortOrder??'');
        if(key==='toolName')  return t.toolName??'';
        if(key==='tNumber')   return String(t.tNo??t.tNumber??'');
        if(key==='hValue')    return t.hValue!=null?String(t.hValue):(t.lengthOffsetNo??'');
        if(key==='dRegister') return t.diaOffsetNo??t.dRegister??'';
        if(key==='dValue')    return t.dValue!=null?String(t.dValue):(t.diameter!=null?String(t.diameter):'');
        if(key==='subPgNo')   return t.subPgNo??t.subProgram??'';
        if(key==='note')      return t.note??'';
        return '';
      };
      for(const t of tooling) {
        if(ensureSpace(TH)) drawTHdr();
        for(const col of TCOLS){ cellR(col.x,curY,col.w,TH); const v=getV(t,col.key); if(v) cellT(col.x,curY,col.w,TH,v,6.5,col.al); }
        curY+=TH;
      }
      curY+=4;
    }

    // ── ③ ワークオフセット ──
    const workOffsets = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woCfg = fieldsByTpl('repeat_wo').find((f:any) => f.field_key === '__wo_cfg__');
      const cfgMap = Object.fromEntries((woCfg?.note ?? 'label_w=28,col_w=175.4,row_h=14.0,start_y=37').split(',').map((kv:string)=>kv.split('=')));
      const WF_LW = parseFloat(cfgMap['label_w']??'28');
      const wColW = parseFloat(cfgMap['col_w']??'175.4');
      const WH    = parseFloat(cfgMap['row_h']??'14.0');
      const WF_LABELS = ['G','X','Y','Z','A/C','R/B'];
      const WF_KEYS   = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];
      const SEC_H = 12;
      ensureSpace(SEC_H+WH*4);
      grayCell(ML,curY,PW,SEC_H,'■ ワークオフセット',7.0); curY+=SEC_H;
      const groups: any[][] = [];
      for(let i=0;i<workOffsets.length;i+=3) groups.push(workOffsets.slice(i,i+3));
      for(const group of groups) {
        for(let fi=0;fi<WF_LABELS.length;fi++) {
          ensureSpace(WH);
          for(let ci=0;ci<3;ci++) {
            const wo=group[ci]; const x=ML+ci*wColW;
            const val=wo?(()=>{ const raw=wo[WF_KEYS[fi]]; if(raw==null)return ''; if(typeof raw==='number')return raw.toFixed(3); return String(raw); })():'';
            grayCell(x,curY,WF_LW,WH,WF_LABELS[fi],6.0);
            cellR(x+WF_LW,curY,wColW-WF_LW,WH);
            if(val) cellT(x+WF_LW,curY,wColW-WF_LW,WH,val,7.0,'center');
          }
          curY+=WH;
        }
        curY+=2;
      }
      curY+=4;
    }

    // ── ④ インデックスプログラム ──
    const indexPrograms = (options.include_index_programs !== false) ? (d.indexPrograms ?? []) : [];
    if (indexPrograms.length > 0) {
      const ipCols = fieldsByTpl('repeat_ip').filter((f:any) => f.field_key.startsWith('col_'));
      const rowCfgIP = fieldsByTpl('repeat_ip').find((f:any) => f.field_key === '__row_cfg__');
      const IH = rowCfgIP ? parseFloat(rowCfgIP.font_size) : 14.0;
      const getICX = (key:string,def:number) => ipCols.find((c:any)=>c.field_key===key)?.x??def;
      const getICW = (key:string,def:string) => parseFloat(ipCols.find((c:any)=>c.field_key===key)?.note??def);
      const ICOLS = [
        {x:getICX('col_no',30),    w:getICW('col_no','25'),    key:'sortOrder',al:'center' as const},
        {x:getICX('col_axis0',55), w:getICW('col_axis0','91'), key:'axis0',    al:'left'   as const},
        {x:getICX('col_axis1',146),w:getICW('col_axis1','150'),key:'axis1',    al:'left'   as const},
        {x:getICX('col_axis2',296),w:getICW('col_axis2','150'),key:'axis2',    al:'left'   as const},
        {x:getICX('col_note',446), w:getICW('col_note','110'), key:'note',     al:'left'   as const},
      ] as const;
      const ILABELS = ['No','軸0','軸1','軸2','備考'];
      const SEC_H = 12;
      const drawIHdr = () => { for(let i=0;i<ICOLS.length;i++) grayCell(ICOLS[i].x,curY,ICOLS[i].w,IH,ILABELS[i],5.5); curY+=IH; };
      ensureSpace(SEC_H+IH*3);
      grayCell(ML,curY,PW,SEC_H,'■ インデックスプログラム',7.0); curY+=SEC_H;
      drawIHdr();
      for(let i=0;i<indexPrograms.length;i++) {
        if(ensureSpace(IH)) drawIHdr();
        const ip=indexPrograms[i];
        const vals=[String(ip.sortOrder??i+1),ip.axis0??'',ip.axis1??'',ip.axis2??'',ip.note??''];
        for(let ci=0;ci<ICOLS.length;ci++){ cellR(ICOLS[ci].x,curY,ICOLS[ci].w,IH); if(vals[ci]) cellT(ICOLS[ci].x,curY,ICOLS[ci].w,IH,vals[ci],6.5,ICOLS[ci].al); }
        curY+=IH;
      }
    }

    drawPageNo(pageNum);
    doc.end();
    await new Promise<void>(r => { doc.once('end', r); });
    await new Promise(r => setTimeout(r, 50));
    const pdfkitBuf = Buffer.concat(chunks);

    // ── pdf-lib で P2（作業記録）をマージ ──
    const { PDFDocument: PDFDocLib2, rgb: rgb2 } = await import('pdf-lib');
    const fontkit2   = await import('@pdf-lib/fontkit');
    const fontBytes2 = fs.readFileSync(FONT_PATH);

    const mainDoc   = await PDFDocLib2.load(pdfkitBuf);
    const totalMain = mainDoc.getPageCount();

    const p2Bytes = fs.readFileSync(`${ASSETS}/template_p2.pdf`);
    const p2Doc   = await PDFDocLib2.load(p2Bytes);
    p2Doc.registerFontkit(fontkit2.default ?? fontkit2);
    const p2Font  = await p2Doc.embedFont(fontBytes2);
    const p2Page  = p2Doc.getPage(0);

    const resolve2 = (s2: string): string => {
      if (s2 === 'version') return fmtVer(String(d.version ?? '1.0001'));
      const keys = s2.split('.');
      let val: any = d;
      for (const k of keys) { val = val?.[k]; if (val == null) return ''; }
      return String(val);
    };
    const totalPages = totalMain + 1;
    for (const f of allFields.filter((f:any) => f.tpl_name === 'mc_setup_p2')) {
      if (f.field_key === '__page_no__') {
        p2Page.drawText(`${totalPages} / ${totalPages}`, { x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: p2Font, color: rgb2(0,0,0) });
        continue;
      }
      const text = resolve2(f.data_source);
      if (!text) continue;
      p2Page.drawText(text, { x: Number(f.x), y: Number(f.y), size: Number(f.font_size), font: p2Font, color: rgb2(0,0,0) });
    }

    // ページ番号を pdf-lib で上書き
    mainDoc.registerFontkit(fontkit2.default ?? fontkit2);
    const mainFont = await mainDoc.embedFont(fontBytes2);
    const PBW = 44.2, PBH = 21.3;
    for (let pi=0; pi<mainDoc.getPageCount(); pi++) {
      const pg   = mainDoc.getPage(pi);
      const pgSz = pg.getSize();
      const boxX = ML + PW - PBW;
      const boxY = 25;
      pg.drawRectangle({ x: boxX+PBW/2, y: boxY, width: PBW/2+2, height: PBH+2, color: rgb2(1,1,1), borderWidth: 0 });
      pg.drawText(`${pi+1} / ${totalPages}`, { x: boxX+PBW/2+1, y: boxY+(PBH-6.5*0.72)/2, size: 6.5, font: mainFont, color: rgb2(0,0,0) });
      pg.drawRectangle({ x: boxX+PBW/2, y: boxY, width: PBW/2, height: PBH, borderColor: rgb2(0,0,0), borderWidth: 0.5, color: rgb2(1,1,1), opacity: 0 });
    }

    const finalDoc = await PDFDocLib2.create();
    finalDoc.registerFontkit(fontkit2.default ?? fontkit2);
    for (let pi=0; pi<mainDoc.getPageCount(); pi++) {
      const [pg] = await finalDoc.copyPages(mainDoc, [pi]); finalDoc.addPage(pg);
    }
    const [copiedP2] = await finalDoc.copyPages(p2Doc, [0]); finalDoc.addPage(copiedP2);

    if ((options as any).is_preview === true) {
      const wFont = await finalDoc.embedFont(fontBytes2);
      const { degrees: degs } = await import('pdf-lib');
      for (const page of finalDoc.getPages()) {
        const { width, height } = page.getSize();
        for (const pos of [{x:width*0.15,y:height*0.25},{x:width*0.35,y:height*0.55},{x:width*0.55,y:height*0.75}]) {
          page.drawText('プレビュー', { x: pos.x, y: pos.y, size: 60, font: wFont, color: rgb2(0.75,0.75,0.75), rotate: degs(35), opacity: 0.35 });
        }
      }
    }

    const pdfBytes2 = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes2);

    if (!(options as any).is_preview) {
      await this.prisma.mcSetupSheetLog.create({
        data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
                ...(typeof (options as any).is_reference !== 'undefined' ? { isReference: (options as any).is_reference } : {}) },
      }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));
    }

    return pdfBuffer;
  }

  // ══════════════════════════════════════════
  async directPrint(
    mcId: number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
    },
  ): Promise<{ message: string }> {
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true, mcPrinter: true } });
    const printerName = setting?.mcPrinter || setting?.printerName;
    if (!printerName) throw new Error('MCプリンタが設定されていません。管理画面のシステム設定でMCチーム用プリンタを設定してください。');
    const pdfBuffer = await this.generateSetupSheetPdf(mcId, operatorId, options);
    const tmpPath = `/tmp/machcore-mc-print-${mcId}-${Date.now()}.pdf`;
    fs.writeFileSync(tmpPath, pdfBuffer);
    try {
      execSync(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs.unlinkSync(tmpPath); } catch { /**/ }
    }
    return { message: `${printerName} に送信しました` };
  }


}