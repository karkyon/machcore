import { Injectable, NotFoundException } from '@nestjs/common';
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
          creatorId:     dto.creator_id      !== undefined ? dto.creator_id      : mc.creatorId,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : mc.sheetCreatedAt,
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
    return rows.map(r => ({
      id:             r.id,
      printed_at:     r.printedAt,
      version:        r.version ?? null,
      operator_name:  r.operator?.name ?? null,
      work_collected: r.workCollected,
      is_reference:   r.isReference,
    }));
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
        is_reference:   s.isReference,
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
    const p1Fields = templates.filter(f => f.name === 'mc_setup_p1');
    for (const f of p1Fields) {
      const text = resolve(f.data_source);
      if (!text) continue;
      p1Page.drawText(text, {
        x: Number(f.x),
        y: Number(f.y),
        size: Number(f.font_size),
        font: font1,
        color: rgb(0, 0, 0),
      });
    }

    // ツーリングリスト差し込み（DB定義がない場合のフォールバック）
    if (options.include_tooling !== false && data.tooling?.length > 0) {
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
      const text = resolve(f.data_source);
      if (!text) continue;
      p2Page.drawText(text, {
        x: Number(f.x),
        y: Number(f.y),
        size: Number(f.font_size),
        font: font2,
        color: rgb(0, 0, 0),
      });
    }

    // P1+P2を結合して2ページPDFに
    const finalDoc = await PDFDocument.create();
    finalDoc.registerFontkit(fontkit.default ?? fontkit);
    const [copiedP1] = await finalDoc.copyPages(p1Doc, [0]);
    const [copiedP2] = await finalDoc.copyPages(p2Doc, [0]);
    finalDoc.addPage(copiedP1);
    finalDoc.addPage(copiedP2);

    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

    await this.prisma.mcSetupSheetLog.create({
      data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
              isReference: (options as any).is_reference ?? false },
    }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));

    return pdfBuffer;
  }

  // ══════════════════════════════════════════
  // ダイレクト印刷
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
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true } });
    const printerName = setting?.printerName;
    if (!printerName) throw new Error('プリンタが設定されていません。管理者設定で設定してください。');
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

  // ══════════════════════════════════════════
  // 修正フラグ（個別切り戻し用）
  // True=修正版ON / False=修正前に戻す
  // ══════════════════════════════════════════
  private FIX: Record<number,boolean> = {
    2:  false,  // P1外枠
    3:  true,   // 日付欄位置
    4:  true,   // MC ID値フォント
    5:  true,   // ヘッダーラベル列幅
    6:  true,   // 納入先・名称値列
    7:  true,   // インデックス/テールストック/治具列構成
    8:  true,   // 備考縦結合
    9:  true,   // ツーリングN列幅
    11: true,   // ページ番号縦書き
    13: true,   // P1全体外枠
    14: true,   // P2写真枚数行
    15: true,   // P2行1外枠
    17: true,   // P2行3HM構成
    18: true,   // タイムチャート時刻ラベル
    19: true,   // グレーゾーン範囲
    21: true,   // タイムチャート2セット目y位置
    23: true,   // P2全体外枠
  };

  // ══════════════════════════════════════════
  // P1: WS000000完全再現
  // ══════════════════════════════════════════
  private buildP1(doc: any, data: any, opts: any): void {
    const F  = 'IPA';
    const FX = this.FIX;
    doc.addPage({ size: 'A4', margin: 0 });
    const d       = data as any;
    const part    = d.part    ?? {};
    const machine = d.machine ?? {};
    const tooling = opts.include_tooling !== false ? (d.tooling ?? []) : [];

    // 座標定数（画像解析値）
    const ML  = 30.4;   // 左端
    const PW  = 526.2;  // 印刷幅
    const MR  = ML + PW; // 556.6

    const lw0 = 0.5;    // 通常罫線
    const lw1 = 1.0;    // 外枠罫線

    const strokeN = () => doc.strokeColor('#000000').lineWidth(lw0);
    const strokeB = () => doc.strokeColor('#000000').lineWidth(lw1);

    // ── セル描画ヘルパー ──────────────────────
    const cellR = (x:number,y:number,w:number,h:number) => { strokeN(); doc.rect(x,y,w,h).stroke(); };
    const cellT = (x:number,y:number,w:number,h:number,t:string,fs:number,al:'left'|'center'='left') => {
      if(!t) return;
      doc.font(F).fontSize(fs).fillColor('#000000');
      const ty = y+(h-fs*0.72)/2;
      if(al==='center') doc.text(t,x,ty,{width:w,align:'center',lineBreak:false});
      else doc.text(t,x+2,ty,{width:w-4,lineBreak:false});
    };
    const grayCell = (x:number,y:number,w:number,h:number,t:string,fs=6.0) => {
      strokeN();
      doc.rect(x,y,w,h).fillAndStroke('#e8e8e8','#000000');
      doc.font(F).fontSize(fs).fillColor('#000000');
      const ty = y+(h-fs*0.72)/2;
      doc.text(t,x+1.5,ty,{width:w-3,lineBreak:false});
    };
    const labelVal = (x:number,y:number,lw:number,vw:number,h:number,
                      label:string,val:string,lfs=6.0,vfs=7.0) => {
      grayCell(x,y,lw,h,label,lfs);
      cellR(x+lw,y,vw,h);
      cellT(x+lw,y,vw,h,val,vfs);
    };

    // ─────────────────────────────────────────
    // #2/#13: 全体外枠
    // ─────────────────────────────────────────
    // #13: P1外枠
    if(FX[13]) {
      strokeB();
      doc.rect(ML, 39.7, PW, 759.3).stroke();
    }

    // ─────────────────────────────────────────
    // タイトル行  y=39.7  h=28.6
    // ─────────────────────────────────────────
    const T_Y=39.7; const T_H=28.6;
    const verVer = String(d.version??'1.0001'); const verDisp = verVer.replace(/^(\d+)\.(\d{4})$/,(_,a,b)=>a+'.'+b.slice(0,2)+' '+b.slice(2)); const verText = `新規段取シート　Ver. ${verDisp}`;
    doc.font(F).fontSize(13.5).fillColor('#000000');
    doc.text(verText, ML+4, T_Y+(T_H-13.5*0.72)/2, {lineBreak:false});

    // #3: 日付欄（タイトル行内、参照に合わせた位置・幅）
    const dateBoxX = FX[3] ? ML+220 : ML+PW*0.40;
    const dateBoxW = FX[3] ? 55      : 80;
    strokeN();
    doc.rect(dateBoxX, T_Y, dateBoxW, T_H).stroke();
    doc.font(F).fontSize(7).fillColor('#000000');
    doc.text(' /  / ', dateBoxX+4, T_Y+(T_H-7*0.72)/2, {lineBreak:false});

    // 承認ボックス（右端）
    const apvX = MR-46.1;
    strokeN(); doc.rect(apvX, T_Y, 46.1, T_H).stroke();
    doc.font(F).fontSize(7).fillColor('#000000');
    doc.text('承認', apvX+2, T_Y+(T_H-7*0.72)/2, {lineBreak:false});

    // ─────────────────────────────────────────
    // ID行  y=68.4  h=14.8
    // ─────────────────────────────────────────
    const ID_Y=68.4; const ID_H=14.8;
    strokeN(); doc.rect(ML, ID_Y, PW, ID_H).stroke();

    // 部品ID
    labelVal(ML, ID_Y, 35, 171, ID_H, '部品ID', String(part.partId??d.partId??''));
    // 加工ID
    labelVal(235.9, ID_Y, 35, 70, ID_H, '加工 ID', String(d.machiningId??''));
    // MC ID: #4=太字大きめフォント
    const mcIdVfs = FX[4] ? 9.5 : 7.0;
    labelVal(340.0, ID_Y, 35, 181.6, ID_H, 'MC ID', String(d.id??''), 6.0, mcIdVfs);

    // ─────────────────────────────────────────
    // ヘッダー情報グリッド  y=83.2
    // col_boundaries(pt): CB[0..9]
    // ─────────────────────────────────────────
    // #5: ラベル列幅修正
    // 参照: 左ラベル=「納入先」「名称」は17.5pt、他は可変
    // 修正: 各行のラベル幅を参照に合わせる
    const CB = [30.4, 117.9, 209.0, 282.6, 323.5, 332.3, 397.9, 406.0, 454.8, 554.7];
    // #修正: 左ラベル幅5倍=87.5, 値幅1.3倍=91.1
    const LBL_W  = 87.5;  // CB[0]→CB[1]相当(修正後)
    const VAL_W  = 91.1;  // CB[1]→CB[2]相当(修正後)
    const LBL_FS = 12.0;  // ラベルフォント
    const VAL_FS = 14.0;  // 値フォント
    const cw = (i:number) => CB[i+1]-CB[i];
    const RH = 18.5;

    // 参照のラベル幅（#5修正値）
    const LW_LEFT  = FX[5] ? cw(0)  : cw(0);     // 17.5pt (変わらず正確)
    const LW_MID1  = FX[5] ? 38.0   : 52.0;       // バイス等
    const LW_MID2  = FX[5] ? 38.0   : 52.0;       // チャック等
    const LW_RIGHT1= FX[5] ? 42.0   : 52.0;       // インデックス等

    let hy = 83.2;

    // 行0: 納入先 | 値(広) | 図面番号 | 値(右端まで)
    // #6: 納入先の値列を右端（図面番号手前）まで
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'納入先',LBL_FS);
      // #6: 値幅
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,part.clientName??'',VAL_FS);
      grayCell(CB[2],hy,38,h,'図面番号',6.0);
      cellR(CB[2]+38,hy,CB[9]-CB[2]-38,h); cellT(CB[2]+38,hy,CB[9]-CB[2]-38,h,part.drawingNo??'',7.0);
      hy+=h;
    }
    // 行1: 名称 | 値(広) | 主機種型式 | 値(右端まで)
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'名 称',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,part.name??'',VAL_FS);
      grayCell(CB[2],hy,38,h,'主機種・型式',5.5);
      cellR(CB[2]+38,hy,CB[9]-CB[2]-38,h); cellT(CB[2]+38,hy,CB[9]-CB[2]-38,h,d.mainMachineType??'',7.0);
      hy+=h;
    }
    // 行2: 工程No | バイス | インデックス(+値)
    // #7: インデックス列を独立セルで
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'工程 No',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,String(d.processNo??''),VAL_FS);
      grayCell(CB[2],hy,LW_MID1,h,'バ イ ス');
      cellR(CB[2]+LW_MID1,hy,CB[4]-CB[2]-LW_MID1,h); cellT(CB[2]+LW_MID1,hy,CB[4]-CB[2]-LW_MID1,h,d.vise??'',7.0);
      if(FX[7]) {
        grayCell(CB[4],hy,LW_RIGHT1,h,'インデックス',5.5);
        cellR(CB[4]+LW_RIGHT1,hy,cw(5),h); cellT(CB[4]+LW_RIGHT1,hy,cw(5),h,d.index_??'',7.0);
        cellR(CB[6],hy,cw(6)+cw(7)+cw(8),h);
      } else {
        grayCell(CB[4],hy,52,h,'インデックス',5.5);
        cellR(CB[4]+52,hy,CB[9]-CB[4]-52,h);
      }
      hy+=h;
    }
    // 行3: フォルダ名 | 敷板 | テールストック | 治具(+値)
    // #7: テールストック・治具を独立セルで
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'フォルダ名',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,d.folderName??'',VAL_FS);
      grayCell(CB[2],hy,LW_MID1,h,'敷 板');
      cellR(CB[2]+LW_MID1,hy,CB[4]-CB[2]-LW_MID1,h); cellT(CB[2]+LW_MID1,hy,CB[4]-CB[2]-LW_MID1,h,d.kickPlate??'',7.0);
      if(FX[7]) {
        grayCell(CB[4],hy,LW_RIGHT1,h,'テールストック',5.0);
        cellR(CB[4]+LW_RIGHT1,hy,cw(5),h); cellT(CB[4]+LW_RIGHT1,hy,cw(5),h,d.tailstock??'',7.0);
        grayCell(CB[6],hy,cw(6),h,'治具',6.0);
        cellR(CB[6]+cw(6),hy,cw(7)+cw(8),h); cellT(CB[6]+cw(6),hy,cw(7)+cw(8),h,d.jig??'',7.0);
      } else {
        grayCell(CB[4],hy,52,h,'テールストック',5.0);
        cellR(CB[4]+52,hy,52,h);
        grayCell(CB[6],hy,25,h,'治具',6.0);
        cellR(CB[6]+25,hy,CB[9]-CB[6]-25,h);
      }
      hy+=h;
    }
    // 行4: ファイル名 | チャック1 | その他
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'ファイル名',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,d.fileName??'',VAL_FS);
      grayCell(CB[2],hy,LW_MID2,h,'チャック１',5.5);
      cellR(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h); cellT(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h,d.chuck1??'',7.0);
      grayCell(CB[4],hy,LW_RIGHT1,h,'その他',6.0);
      cellR(CB[4]+LW_RIGHT1,hy,CB[9]-CB[4]-LW_RIGHT1,h); cellT(CB[4]+LW_RIGHT1,hy,CB[9]-CB[4]-LW_RIGHT1,h,d.other??'',7.0);
      hy+=h;
    }

    // 行5～7の備考エリアy値を記録
    const bikoStartY = hy;

    // 行5: メインOナンバ | 爪1 | 備考(上端)
    // #8: 備考は行5ラベルのみ、値エリアは縦結合
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'メインOナンバ',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,d.mainONumber??'',VAL_FS);
      grayCell(CB[2],hy,LW_MID2,h,'爪 1');
      cellR(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h); cellT(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h,d.jaw1??'',7.0);
      // 備考ラベル（行5だけ）
      grayCell(CB[4],hy,cw(4),h,'備考',6.0);
      // 備考値エリアはまだ描画しない（後で縦結合）
      hy+=h;
    }
    // 行6: 機械 | チャック2 | (備考エリア継続)
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'機 械',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,machine.machineName??machine.machineCode??'',VAL_FS);
      grayCell(CB[2],hy,LW_MID2,h,'チャック２',5.5);
      cellR(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h); cellT(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h,d.chuck2??'',7.0);
      if(!FX[8]) {
        grayCell(CB[4],hy,cw(4),h,'',6.0);
      }
      hy+=h;
    }
    // 行7: タイム | 爪2 | (備考エリア継続)
    {
      const h=RH;
      grayCell(CB[0],hy,LBL_W,h,'タ イ ム',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,d.cycleTimeStr??'H  M  S',VAL_FS);
      grayCell(CB[2],hy,LW_MID2,h,'爪 2');
      cellR(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h); cellT(CB[2]+LW_MID2,hy,CB[4]-CB[2]-LW_MID2,h,d.jaw2??'',7.0);
      if(!FX[8]) {
        grayCell(CB[4],hy,cw(4),h,'',6.0);
      }
      hy+=h;
    }
    // 行8: 個数
    {
      const h=16.6;
      grayCell(CB[0],hy,LBL_W,h,'個 数',LBL_FS);
      cellR(CB[0]+LBL_W,hy,VAL_W,h); cellT(CB[0]+LBL_W,hy,VAL_W,h,String(d.quantity??''),VAL_FS);
      cellR(CB[2],hy,CB[9]-CB[2],h);
      hy+=h;
    }

    // #8: 備考縦結合エリア（行5～7の右側 CB[4]+cw(4)～CB[9]）
    {
      const bikoH = FX[8] ? RH*3 : RH*3;
      const bikoX = CB[4]+cw(4);
      const bikoW = CB[9]-bikoX;
      strokeN();
      doc.rect(bikoX, bikoStartY, bikoW, bikoH).stroke();
      if(d.note) {
        doc.font(F).fontSize(7.0).fillColor('#000000');
        doc.text(d.note, bikoX+2, bikoStartY+4, {width:bikoW-4,lineBreak:true});
      }
    }

    // ─────────────────────────────────────────
    // ツーリングリスト
    // ─────────────────────────────────────────
    const TBL_Y = hy;
    const TH    = 21.3;

    // #9: N列幅修正（参照=29.5pt）
    const N_W   = FX[9] ? 29.5 : 40.6;
    // 工具列: 残り幅を吸収
    const TOOL_W= FX[9] ? (95.8+(40.6-29.5)) : 95.8;  // 106.9 or 95.8

    const TCOLS = [
      {label:'N',        x:ML,            w:N_W,    al:'center' as const},
      {label:'工 具',    x:ML+N_W,        w:TOOL_W, al:'left'   as const},
      {label:'T',        x:ML+N_W+TOOL_W, w:38.7,   al:'center' as const},
      {label:'H',        x:0,             w:38.7,   al:'center' as const},
      {label:'D',        x:0,             w:38.7,   al:'center' as const},
      {label:'D値',      x:0,             w:46.1,   al:'center' as const},
      {label:'SUB',      x:0,             w:45.1,   al:'center' as const},
      {label:'コメント', x:0,             w:0,      al:'left'   as const},
    ];
    // x座標を累積計算
    let cx = ML;
    for(const col of TCOLS) {
      if(col.x === 0) col.x = cx;
      cx = col.x + col.w;
    }
    // コメント列は右端まで
    TCOLS[7].w = MR - TCOLS[7].x;

    // ヘッダー行
    for(const col of TCOLS) {
      strokeN();
      doc.rect(col.x, TBL_Y, col.w, TH).fillAndStroke('#d8d8d8','#000000');
      doc.font(F).fontSize(7.0).fillColor('#000000');
      const ty = TBL_Y+(TH-7*0.72)/2;
      doc.text(col.label, col.x, ty, {width:col.w, align:'center', lineBreak:false});
    }

    // データ行（最大24行）
    for(let ri=0; ri<24; ri++) {
      const t   = tooling[ri];
      const ry  = TBL_Y + TH + ri*TH;
      const vals: string[] = t ? [
        String(t.toolNo??ri+1), t.toolName??'',
        String(t.tNumber??''),
        t.hValue!=null?String(t.hValue):'',
        t.dRegister??'',
        t.dValue!=null?String(t.dValue):'',
        t.subProgram??'',
        t.comment??t.note??'',
      ] : ['','','','','','','',''];
      for(let ci=0; ci<TCOLS.length; ci++) {
        const col = TCOLS[ci];
        strokeN(); doc.rect(col.x, ry, col.w, TH).stroke();
        if(vals[ci]) {
          doc.font(F).fontSize(6.5).fillColor('#000000');
          const ty = ry+(TH-6.5*0.72)/2;
          if(col.al==='center') doc.text(vals[ci],col.x,ty,{width:col.w,align:'center',lineBreak:false});
          else doc.text(vals[ci],col.x+2,ty,{width:col.w-4,lineBreak:false});
        }
      }
    }

    // ─────────────────────────────────────────
    // ページ番号ボックス（右下）
    // ─────────────────────────────────────────
    const PG_Y=778.1; const PG_H=21.3;
    const PG_X=MR-44.2;
    // #11: ページラベル「ペ－ジ」（縦書き近似）
    strokeN();
    doc.rect(PG_X, PG_Y, 22.1, PG_H).fillAndStroke('#e8e8e8','#000000');
    if(FX[11]) {
      // 縦書き3文字
      doc.font(F).fontSize(5.5).fillColor('#000000');
      doc.text('ペ', PG_X+1, PG_Y+1,    {width:20,lineBreak:false});
      doc.text('ー', PG_X+1, PG_Y+7,    {width:20,lineBreak:false});
      doc.text('ジ', PG_X+1, PG_Y+13,   {width:20,lineBreak:false});
    } else {
      doc.font(F).fontSize(5.5).fillColor('#000000');
      doc.text('ページ', PG_X+1, PG_Y+(PG_H-5.5*0.72)/2, {width:20,lineBreak:false});
    }
    strokeN();
    doc.rect(PG_X+22.1, PG_Y, 22.1, PG_H).stroke();
    doc.font(F).fontSize(6.5).fillColor('#000000');
    doc.text('1 / 2', PG_X+22.1, PG_Y+(PG_H-6.5*0.72)/2,
             {width:22, align:'center', lineBreak:false});
  }

  // ══════════════════════════════════════════
  // P2: WS000001完全再現
  // ══════════════════════════════════════════
  private buildP2(doc: any, _data: any): void {
    const F  = 'IPA';
    const FX = this.FIX;
    doc.addPage({ size: 'A4', margin: 0 });

    const ML = 28.6;
    const PW = 525.1;
    const MR = ML + PW; // 553.7

    const lw0=0.5; const lw1=1.0;
    const strokeN = () => doc.strokeColor('#000000').lineWidth(lw0);
    const strokeB = () => doc.strokeColor('#000000').lineWidth(lw1);

    const lbl = (x:number,y:number,w:number,h:number,t:string,fs=6.5) => {
      strokeN();
      doc.rect(x,y,w,h).fillAndStroke('#e8e8e8','#000000');
      doc.font(F).fontSize(fs).fillColor('#000000');
      doc.text(t, x+1.5, y+(h-fs*0.72)/2, {width:w-3, lineBreak:false});
    };
    const val = (x:number,y:number,w:number,h:number,t='') => {
      strokeN(); doc.rect(x,y,w,h).stroke();
      if(t){ doc.font(F).fontSize(6.5).fillColor('#000000');
        doc.text(t,x+2,y+(h-6.5*0.72)/2,{width:w-4,lineBreak:false}); }
    };
    const plain = (x:number,y:number,w:number,h:number,t='',fs=6.5) => {
      strokeN(); doc.rect(x,y,w,h).stroke();
      if(t){ doc.font(F).fontSize(fs).fillColor('#000000');
        doc.text(t,x+2,y+(h-fs*0.72)/2,{width:w-4,lineBreak:false}); }
    };

    // #23: P2全体外枠
    if(FX[23]) {
      strokeB();
      const infoH = FX[21] ? (501.1-38.9) : (477.0-38.9);
      doc.rect(ML, 38.9, PW, 790.0).stroke();
    }

    const DIV = 287.9;
    const LW  = DIV - ML;  // 259.3
    const RW  = MR  - DIV; // 265.8

    // ─── 行1: 段取/チェック/量産  y=50.0  h=22.2 ───
    // #15: セル間に明確な仕切り線
    {
      const y=50.0; const h=22.2;
      if(FX[15]) {
        // 外枠+内部仕切り線
        strokeN(); doc.rect(ML,y,PW,h).stroke();
        doc.moveTo(ML+175.0,y).lineTo(ML+175.0,y+h).stroke();
        doc.moveTo(ML+330.0,y).lineTo(ML+330.0,y+h).stroke();
      } else {
        strokeN();
        doc.rect(ML,y,175.0,h).stroke();
        doc.rect(ML+175.0,y,155.0,h).stroke();
        doc.rect(ML+330.0,y,MR-(ML+330.0),h).stroke();
      }
      doc.font(F).fontSize(8.0).fillColor('#000000');
      doc.text('段取',    ML+3,        y+(h-8*0.72)/2, {lineBreak:false});
      doc.text('チェック',ML+175.0+3,  y+(h-8*0.72)/2, {lineBreak:false});
      doc.text('量産',    ML+330.0+3,  y+(h-8*0.72)/2, {lineBreak:false});
    }

    // ─── 行2: プログラム / Tool  y=74.1  h=22.2 ───
    {
      const y=74.1; const h=22.2;
      lbl(ML,y,52,h,'プログラム',6.0);
      val(ML+52,y,LW-52,h,'＋ ー  H  M保存');
      lbl(DIV,y,40,h,'Tool',6.5);
      val(DIV+40,y,RW-40,h,'＋ ー  H  M');
    }

    // ─── 行3: 段取時の中断 / 量産時の中断  y=98.2  h=23.2 ───
    // #17: HとMの欄を正確に再現
    {
      const y=98.2; const h=23.2;
      if(FX[17]) {
        lbl(ML,y,62,h,'段取時の中断',5.5);
        val(ML+62,y,LW-62-42,h);
        lbl(MR/2-42,y,20,h,'H',6.5);
        val(MR/2-22,y,22,h);
        lbl(DIV,y,62,h,'量産時の中断',5.5);
        val(DIV+62,y,RW-62-42,h);
        lbl(MR-42,y,20,h,'H',6.5);
        val(MR-22,y,22,h);
      } else {
        lbl(ML,y,62,h,'段取時の中断',5.5);
        val(ML+62,y,LW-62-20-20,h);
        lbl(ML+LW-40,y,20,h,'H',6.5);
        val(ML+LW-20,y,20,h);
        lbl(DIV,y,62,h,'量産時の中断',5.5);
        val(DIV+62,y,RW-62-20-20,h);
        lbl(DIV+RW-40,y,20,h,'H',6.5);
        val(DIV+RW-20,y,20,h);
      }
    }

    // ─── 行4: M  y=123.2  h=21.3 ───
    {
      const y=123.2; const h=21.3;
      plain(ML,y,LW,h,'M');
      plain(DIV,y,RW,h,'M');
    }

    // ─── 行5: 段取良品数 / 全良品数  y=144.5  h=22.2 ───
    {
      const y=144.5; const h=22.2;
      lbl(ML,y,52,h,'段取良品数',6.0);
      val(ML+52,y,LW-52,h);
      lbl(DIV,y,52,h,'全良品数',6.0);
      val(DIV+52,y,RW-52,h);
    }

    // ─── 行6: 写真枚数 / 登録者  y=166.7  h=22.2 ───
    // #14: 写真枚数行を正確に表示
    {
      const y=166.7; const h=22.2;
      if(FX[14]) {
        lbl(ML,y,52,h,'写真枚数',6.0);
        val(ML+52,y,LW-52,h,'枚  Rim    ～Rim');
        lbl(DIV,y,52,h,'登録者',6.0);
        val(DIV+52,y,RW-52,h);
      } else {
        plain(ML,y,LW,h,'写真枚数  枚  Rim  ～Rim');
        lbl(DIV,y,52,h,'登録者',6.0);
        val(DIV+52,y,RW-52,h);
      }
    }

    // ─────────────────────────────────────────
    // タイムチャート描画
    // ─────────────────────────────────────────
    const DATE_W  = 38.7;
    const GRID_X  = ML + DATE_W;
    const GRID_W  = MR - GRID_X;
    const SLOT_W  = GRID_W / 27;
    const HDR_H   = 20.4;
    const ROW_H   = 20.4;
    const ROWS    = 15;

    // #19: グレースロット（参照=12:00-13:00=index 8,9のみ2スロット）
    const GRAY_IDX = FX[19] ? new Set([8,9]) : new Set([8,9,10,11]);

    const TIME_LABELS = [
      '8:00','8:30','9:00','9:30','10:00','10:30','11:00','11:30',
      '12:00','12:30','13:00','13:30','14:00','14:30','15:00','15:30',
      '16:00','16:30','17:00','17:30','18:00','18:30','19:00','19:30',
      '20:00','—','7:00',
    ];

    const drawChart = (startY: number) => {
      // 日付ラベル
      strokeN();
      doc.rect(ML, startY, DATE_W, HDR_H).fillAndStroke('#d8d8d8','#000000');
      doc.font(F).fontSize(5.5).fillColor('#000000');
      doc.text('日付', ML, startY+(HDR_H-5.5*0.72)/2, {width:DATE_W, align:'center', lineBreak:false});

      // #18: 時刻スロットヘッダー（縦書きラベル）
      for(let i=0; i<TIME_LABELS.length; i++) {
        const sx  = GRID_X + i*SLOT_W;
        const bg  = GRAY_IDX.has(i) ? '#b8b8b8' : '#d8d8d8';
        strokeN();
        doc.rect(sx, startY, SLOT_W, HDR_H).fillAndStroke(bg,'#000000');
        if(FX[18]) {
          // 縦書き: rotate -90度
          doc.save();
          doc.translate(sx + SLOT_W*0.65, startY + HDR_H - 1.5);
          doc.rotate(-90);
          doc.font(F).fontSize(4.5).fillColor('#000000');
          doc.text(TIME_LABELS[i], 0, 0, {lineBreak:false});
          doc.restore();
        }
      }

      // データ行
      for(let row=0; row<ROWS; row++) {
        const ry = startY + HDR_H + row*ROW_H;
        strokeN(); doc.rect(ML, ry, DATE_W, ROW_H).stroke();
        doc.font(F).fontSize(7.0).fillColor('#000000');
        doc.text('/', ML, ry+(ROW_H-7*0.72)/2, {width:DATE_W, align:'center', lineBreak:false});
        for(let i=0; i<TIME_LABELS.length; i++) {
          const sx = GRID_X + i*SLOT_W;
          strokeN();
          if(GRAY_IDX.has(i)) doc.rect(sx,ry,SLOT_W,ROW_H).fillAndStroke('#e0e0e0','#000000');
          else doc.rect(sx,ry,SLOT_W,ROW_H).stroke();
        }
      }
    };

    // #21: 2セット目y位置（参照から正確に再計算）
    // 1セット目: 188.9pt開始, HDR_H+15*ROW_H = 20.4+306 = 326.4pt
    // 1セット目終端: 188.9+326.4 = 515.3pt
    // 2セット目開始: FX[21]=true → 515.3pt+5 = 520.3pt
    const SET1_Y = 188.9;
    const SET2_Y = FX[21] ? (SET1_Y + HDR_H + ROWS*ROW_H + 5) : 501.1;

    drawChart(SET1_Y);
    drawChart(SET2_Y);

    // ページ番号
    doc.font(F).fontSize(7.0).fillColor('#000000');
    doc.text('2 / 2', 0, 828, {width:595.28, align:'center', lineBreak:false});
  }

}