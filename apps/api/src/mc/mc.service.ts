import { Injectable, NotFoundException } from '@nestjs/common';
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
  ) {
    const where: any = {};
    if (q && q.trim()) {
      const kw = q.trim();
      if (key === 'mcid') {
        const n = parseInt(kw);
        if (!isNaN(n)) where.id = n;
      } else if (key === 'machining_id') {
        const n = parseInt(kw);
        if (!isNaN(n)) where.machiningId = n;
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

    const [rows, total] = await Promise.all([
      this.prisma.mcProgram.findMany({
        where, skip: offset, take: limit,
        orderBy: { id: 'asc' },
        include: {
          part:    { select: { drawingNo: true, name: true, clientName: true } },
          machine: { select: { machineCode: true, machineName: true } },
        },
      }),
      this.prisma.mcProgram.count({ where }),
    ]);

    return {
      total, limit, offset,
      rows: rows.map(r => ({
        mc_id:         r.id,
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
            id: true, version: true, status: true, oNumber: true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },
      },
    });
    return logs.map(l => ({
      mc_id:        l.mcProgram?.id,
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
        tooling:   { orderBy: { sortOrder: 'asc' } },
        workOffsets: { orderBy: { gCode: 'asc' } },
        indexPrograms: { orderBy: { sortOrder: 'asc' } },
        files:     { orderBy: { uploadedAt: 'desc' } },
      },
    });
    if (!r) throw new NotFoundException(`MC_id ${id} が存在しません`);

    // 共通加工グループ（同一machining_idを持つ全レコード）
    const commonGroup = await this.prisma.mcProgram.findMany({
      where:   { machiningId: r.machiningId },
      orderBy: { id: 'asc' },
      select: {
        id: true, version: true, status: true,
        part: { select: { drawingNo: true, name: true, clientName: true } },
      },
    });

    return { ...r, commonGroup };
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
          machineId:     dto.machine_id     ?? null,
          oNumber:       dto.o_number       ?? null,
          clampNote:     dto.clamp_note     ?? null,
          cycleTimeSec:  dto.cycle_time_sec ?? null,
          machiningQty:  dto.machining_qty  ?? 1,
          commonPartCode: dto.common_part_code ?? null,
          note:          dto.note           ?? null,
          registeredBy:  operatorId,
          status:        'NEW',
          version:       '1.0001',
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
  // MC-05: 更新
  // ══════════════════════════════════════════
  async update(id: number, dto: UpdateMcDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id } });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);

    const verParts = mc.version.split('.');
    const newMinor = (parseInt(verParts[1] ?? '0', 10) + 1).toString().padStart(4, '0');
    const newVersion = `${verParts[0]}.${newMinor}`;

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
          version:       newVersion,
          status:        'CHANGING',
        },
      });
      await tx.mcChangeHistory.create({
        data: {
          mcProgramId:   id,
          changeType:    'CHANGE',
          operatorId,
          versionBefore: mc.version,
          versionAfter:  newVersion,
          content:       'データ変更',
        },
      });
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'update' } },
      });
      return { mc_id: id, version: newVersion, message: '更新しました' };
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
      for (const item of dto.items) {
        await tx.mcWorkOffset.upsert({
          where:  { mcProgramId_gCode: { mcProgramId: mcId, gCode: item.g_code } },
          update: { xOffset: item.x_offset ?? null, yOffset: item.y_offset ?? null,
                    zOffset: item.z_offset ?? null, aOffset: item.a_offset ?? null,
                    rOffset: item.r_offset ?? null, note: item.note ?? null },
          create: { mcProgramId: mcId, gCode: item.g_code,
                    xOffset: item.x_offset ?? null, yOffset: item.y_offset ?? null,
                    zOffset: item.z_offset ?? null, aOffset: item.a_offset ?? null,
                    rOffset: item.r_offset ?? null, note: item.note ?? null },
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
    return this.prisma.mcChangeHistory.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { changedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
  }

  // ══════════════════════════════════════════
  // 段取シートログ
  // ══════════════════════════════════════════
  async setupSheetLogs(mcId: number) {
    return this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
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
  async getTimecards(machineId: number, workDate: string) {
    return this.prisma.machineTimecard.findMany({
      where:   { machineId, workDate: new Date(workDate) },
      orderBy: { startTime: 'asc' },
      include: { operator: { select: { name: true } } },
    });
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
}
