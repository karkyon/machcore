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
  // リピート段取シートPDF生成 v5
  //
  // 生成方式:
  //   [P1] repeat_header.pdf をロードし基本情報(備考・クランプ除く)を差し込み
  //        → curY = __header_end_y__(pdfkit座標) から変換した位置
  //        → 備考ブロック: ラベル+外枠+テキストを動的高さで描画
  //        → クランプブロック: 同上
  //        → ツーリング明細(カラムヘッダ + 明細行 + 行罫線)
  //        → WO枠
  //        → IP列
  //        → ページが足りなければ空白ページ追加
  //   [最終P] template_repeat_p2.pdf を最終ページとして結合
  //
  //   pdf-lib座標系: Y=0が下, Y=pageHeightが上
  //   ページ下マージン: 30pt
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
      SELECT t.name as tpl_name, f.field_key, f.label, f.x, f.y, f.font_size,
             f.data_source, f.sort_order, f.note, f.is_active
      FROM pdf_templates t
      JOIN pdf_field_definitions f ON f.template_id = t.id
      WHERE t.name IN ('repeat_header','repeat_tooling','repeat_wo','repeat_ip','repeat_p2')
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
    const fmtVer = (v: string) => v ? v.replace(/^(\d+)\.(\d{4})$/,(_:any,a:any,b:any)=>a+'.'+b) : '';
    const resolveVal = (src: string): string => {
      if (!src || src.startsWith('__')) return '';
      if (src === 'approvedAt')   return fmtDate(d.approvedAt);
      if (src === 'registeredAt') return fmtDate(d.registeredAt);
      if (src === 'version')      return fmtVer(d.version ?? '');
      // (5) cycleTimeSec -> XH YM ZS 形式
      if (src === 'cycleTimeSec') {
        if (d.cycleTimeSec == null) return '';
        const totalSec = Math.round(Number(d.cycleTimeSec));
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        return `${h}H ${m}M ${s}S`;
      }
      if (src === 'part.partId')  return String(part.partId  ?? '');
      // (4) 加工ID
      if (src === 'machiningId')  return String(d.machiningId ?? '');
      // (4) MCIDは旧MCID(legacyMcid)を表示
      if (src === 'legacyMcid')   return String(d.legacyMcid ?? '');
      if (src === 'id')           return String(d.legacyMcid ?? mcId);
      // (6) ファイル名・フォルダ名
      if (src === 'fileName')  return d.fileName ?? '';
      if (src === 'folder1')   return d.folder1  ?? '';
      if (src === 'folder2')   return d.folder2  ?? '';
      const keys = src.split('.');
      let val: any = d;
      for (const k of keys) { val = val?.[k]; if (val == null) return ''; }
      return String(val ?? '');
    };

    // テンプレートPDFロード
    const loadTpl = async (filename: string) => {
      const p = `${ASSETS}/${filename}`;
      if (!fs.existsSync(p)) return null;
      const doc = await PDFLib.load(fs.readFileSync(p));
      doc.registerFontkit(fontkit.default ?? fontkit);
      return doc;
    };

    // ── 結合用ドキュメント ──
    const finalDoc = await PDFLib.create();
    finalDoc.registerFontkit(fontkit.default ?? fontkit);
    const finalFont = await finalDoc.embedFont(fontBytes);
    let totalPages = 0;

    // 定数
    const PAGE_BOTTOM_MARGIN = 50; // ページ番号(Y=15)から十分な余白
    const BLOCK_MARGIN       = 6;
    const ROW_LINE_COLOR     = rgb(0.6, 0.6, 0.6);
    const ROW_LINE_W         = 0.4;
    const BOX_LINE_COLOR     = rgb(0.3, 0.3, 0.3);
    const BOX_LINE_W         = 0.6;
    const LABEL_BG_COLOR     = rgb(0.92, 0.92, 0.92);

    // 現在の作業ページ・Y座標
    let curPage: any = null;
    let curPageH = 0;
    let curY = 0;

    // 新ページ追加（MediaBox/CropBoxをA4に強制設定でサイズ問題解決）
    const A4_W_PT = 595.28, A4_H_PT = 841.89;
    const { PDFName } = await import('pdf-lib');
    const addNewPage = async (tplDoc: any, tplPageIdx = 0) => {
      let pg: any;
      if (tplDoc) {
        [pg] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
        finalDoc.addPage(pg);
        // MediaBoxとCropBoxを強制的にA4に設定
        // （テンプレートPDFのページサイズに関わらずA4で表示される）
        try {
          const a4box = finalDoc.context.obj([0, 0, A4_W_PT, A4_H_PT]);
          pg.node.set(PDFName.of('MediaBox'), a4box);
          // CropBoxを削除（MediaBoxが優先される）
          pg.node.delete(PDFName.of('CropBox'));
        } catch(_) {}
      } else {
        pg = finalDoc.addPage([A4_W_PT, A4_H_PT]);
      }
      totalPages++;
      curPage  = finalDoc.getPage(finalDoc.getPageCount() - 1);
      curPageH = curPage.getSize().height;
      curY     = curPageH - PAGE_BOTTOM_MARGIN;
      return curPage;
    };

    // テキスト描画
    const drawTxt = (text: string, x: number, y: number, size: number, color = rgb(0,0,0)) => {
      if (!text || !curPage) return;
      try { curPage.drawText(text, { x, y, size, font: finalFont, color }); } catch(_) {}
    };

    // 水平罫線
    const drawHLine = (x1: number, x2: number, y: number, w = ROW_LINE_W, color = ROW_LINE_COLOR) => {
      if (!curPage) return;
      try { curPage.drawLine({ start:{x:x1,y}, end:{x:x2,y}, thickness:w, color }); } catch(_) {}
    };

    // 矩形描画（枠線のみ・塗りなし）
    const drawRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try { curPage.drawLine({ start:{x,y},       end:{x:x+w,y},       thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y:y+h},   end:{x:x+w,y:y+h},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y},        end:{x,y:y+h},       thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x:x+w,y},   end:{x:x+w,y:y+h},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
    };

    // 白塗り矩形（テキスト背景消し用）
    const drawWhiteRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try { curPage.drawRectangle({ x, y, width:w, height:h, color:rgb(1,1,1), borderWidth:0 }); } catch(_) {}
    };

    // ページ残高チェック
    const ensureSpace = async (needPt: number, tplDoc: any = null) => {
      if (!curPage) return;
      if (curY - needPt < PAGE_BOTTOM_MARGIN) {
        await addNewPage(tplDoc);
      }
    };

    // cfg文字列パース: "x=30,w=535,fs=7,label_w=28,min_h=20"
    const parseCfgStr = (s: string): Record<string,number> => {
      const m: Record<string,number> = {};
      (s||'').split(',').forEach(kv => {
        const [k,v] = kv.split('=');
        if (k && v) m[k.trim()] = parseFloat(v.trim());
      });
      return m;
    };

    // ─────────────────────────────────────────────────────
    // ① repeat_header.pdf に基本情報（備考・クランプ除く）を差し込み
    // ─────────────────────────────────────────────────────
    const headerTpl = await loadTpl('repeat_header.pdf');
    await addNewPage(headerTpl);

    const SKIP_KEYS_HEADER = new Set([
      '__note_start_y__', '__clamp_start_y__',
      '__note_cfg__', '__clamp_cfg__', '__header_end_y__', '__page_no__',
      'note', 'clamp_note',
    ]);

    if (headerTpl) {
      // 基本フィールドを差し込み（備考・クランプ・特殊キーは除外）
      for (const f of fieldsByTpl('repeat_header')) {
        if (SKIP_KEYS_HEADER.has(f.field_key)) continue;
        if (f.field_key.startsWith('__')) continue;
        const text = resolveVal(f.data_source);
        if (!text) continue;
        try {
          curPage.drawText(text, {
            x: Number(f.x), y: Number(f.y),
            size: Number(f.font_size) || 7,
            font: finalFont, color: rgb(0,0,0),
          });
        } catch(_) {}
      }

      // ヘッダ固定部の下端Y: DBの __header_end_y__ の y列（pdf-lib座標=下から）をそのまま curY に使用
      // PDFエディタでフィールドをドラッグするだけで反映される
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      curY = headerEndCfg ? Number(headerEndCfg.y) : (curPageH - 310);
    } else {
      curY = curPageH - 310;
    }

    // ─────────────────────────────────────────────────────────────
    // ①-B 備考ブロック（動的高さ・外枠・ラベル付き）
    // ─────────────────────────────────────────────────────────────
    // NOTE_X: x列から取得, NOTE_FS: font_size列から取得
    // note列: 'w=490,label_w=59,min_h=22' 形式
    const noteCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_cfg__');
    const noteCfgOpt = parseCfgStr(noteCfgF?.note || 'w=490,label_w=59,min_h=22');

    const NOTE_X     = noteCfgF ? Number(noteCfgF.x)         : 30;
    const NOTE_W     = noteCfgOpt.w       ?? 535;
    const NOTE_FS    = noteCfgF ? Number(noteCfgF.font_size)  : 7;
    const NOTE_LBL_W = noteCfgOpt.label_w ?? 59;
    const NOTE_MIN_H = noteCfgOpt.min_h   ?? 22;
    const NOTE_LH    = NOTE_FS * 1.55;
    const NOTE_PAD_V = 4;
    const NOTE_PAD_H = 3;

    const noteText  = d.note      ?? '';
    const clampText = d.clampNote ?? '';

    // テキストを指定幅で折り返して行配列を返す（全角文字幅対応）
    const wrapLines = (text: string, maxW: number, fs: number): string[] => {
      if (!text) return [];
      const result: string[] = [];
      const rows = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
      for (const raw of rows) {
        if (!raw) { result.push(''); continue; }
        let cur = ''; let curW = 0;
        for (const ch of [...raw]) {
          const cw = ch.charCodeAt(0) > 0xFF ? fs * 0.95 : fs * 0.55;
          if (curW + cw > maxW && cur) { result.push(cur); cur = ch; curW = cw; }
          else { cur += ch; curW += cw; }
        }
        if (cur) result.push(cur);
      }
      return result.length ? result : [];
    };

    // 備考ブロック描画関数
    const drawNoteBlock = async (
      label: string, text: string,
      x: number, w: number, fs: number,
      lblW: number, minH: number, lh: number,
      padV: number, padH: number,
    ) => {
      const bodyFs    = Math.max(5, fs - 1);   // 本文フォントサイズ = fs-1
      const lblFs     = Math.max(4, fs - 2);   // ラベルフォントサイズ = fs-2
      const textAreaW = w - lblW - padH * 2;
      const lines     = wrapLines(text, textAreaW, bodyFs);
      const blockH    = Math.max(minH, lines.length * lh + padV * 2);

      await ensureSpace(blockH + 2);

      const blockY = curY - blockH;

      // 外枠（4辺drawLine）
      drawRect(x, blockY, w, blockH);

      // ラベル列背景（薄いグレー・半透明）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0, opacity: 0.5,
        });
      } catch(_) {}

      // ラベル・テキスト列の仕切り縦線
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}

      // ラベルテキスト（縦中央・全角幅対応センタリング）
      const lblTxtY  = blockY + blockH / 2 - lblFs * 0.36;
      const lblTextW = [...label].reduce((acc, c) =>
        acc + (c.charCodeAt(0) > 0xFF ? lblFs * 1.0 : lblFs * 0.55), 0);
      const lblTxtX  = x + Math.max(2, (lblW - lblTextW) / 2);
      drawTxt(label, lblTxtX, lblTxtY, lblFs, rgb(0.15, 0.15, 0.15));

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        drawTxt(line, txtX0, lineY, bodyFs);
      });

      curY -= (blockH + BLOCK_MARGIN);
    };

    // 備考
    await drawNoteBlock(
      '備考', noteText,
      NOTE_X, NOTE_W, NOTE_FS, NOTE_LBL_W, NOTE_MIN_H, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );

    // ─────────────────────────────────────────────────────────────
    // ①-C クランプブロック（備考と同構造）
    // ─────────────────────────────────────────────────────────────
    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgOpt = parseCfgStr(clampCfgF?.note || 'w=490,label_w=59,min_h=22');
    const CLAMP_X     = clampCfgF ? Number(clampCfgF.x)        : NOTE_X;
    const CLAMP_W     = clampCfgOpt.w       ?? NOTE_W;
    const CLAMP_FS    = clampCfgF ? Number(clampCfgF.font_size) : NOTE_FS;
    const CLAMP_LBL_W = clampCfgOpt.label_w ?? NOTE_LBL_W;
    const CLAMP_MIN_H = clampCfgOpt.min_h   ?? NOTE_MIN_H;

    await drawNoteBlock(
      'クランプ', clampText,
      CLAMP_X, CLAMP_W, CLAMP_FS,
      CLAMP_LBL_W, CLAMP_MIN_H, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );

    curY -= BLOCK_MARGIN; // ブロック後の追加余白

    // ══════════════════════════════════════════════════════════
    // ② ツーリング明細（同ページ連続描画）
    // ══════════════════════════════════════════════════════════
    const tooling: any[] = (options.include_tooling !== false) ? (d.tooling ?? []) : [];
    if (tooling.length > 0) {
      const toolingTplDoc = await loadTpl('repeat_tooling.pdf');
      const tFields   = fieldsByTpl('repeat_tooling');
      const rowCfg    = tFields.find((f:any) => f.field_key === '__row_cfg__');
      const colFields = tFields.filter((f:any) => f.field_key.startsWith('col_'));

      const ROW_H       = rowCfg ? parseFloat(rowCfg.font_size) : 14.0;
      const ROW_MARGIN  = 2.0;
      const COL_HDR_H   = ROW_H + 2;
      const EFFECTIVE_ROW_H = ROW_H + ROW_MARGIN;

      const getColX = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f ? Number(f.x) : def;
      };

      // フォントサイズとカラム幅をDBから取得するヘルパー
      const getColFS = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f ? Number(f.font_size) : def;
      };
      const getColW = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f && f.note ? parseFloat(f.note) : def;
      };

      type TCol = { dataKey: string; x: number; label: string; fs: number; w: number };
      const T_COLS: TCol[] = [
        { dataKey:'toolNo',    x: getColX('col_n',37),         label:'N',       fs: getColFS('col_n',8),         w: getColW('col_n',20)   },
        { dataKey:'toolName',  x: getColX('col_tool_name',68), label:'工具',    fs: getColFS('col_tool_name',8), w: getColW('col_tool_name',105) },
        { dataKey:'tNumber',   x: getColX('col_t_no',169.7),   label:'T',       fs: getColFS('col_t_no',8),      w: getColW('col_t_no',25)  },
        { dataKey:'hValue',    x: getColX('col_h_val',223.3),  label:'H',       fs: getColFS('col_h_val',8),     w: getColW('col_h_val',25) },
        { dataKey:'dRegister', x: getColX('col_d_reg',278.4),  label:'D',       fs: getColFS('col_d_reg',8),     w: getColW('col_d_reg',30) },
        { dataKey:'dValue',    x: getColX('col_d_val',320.3),  label:'D値',     fs: getColFS('col_d_val',8),     w: getColW('col_d_val',30) },
        { dataKey:'subPgNo',   x: getColX('col_sub_pg',369.7), label:'SUB',     fs: getColFS('col_sub_pg',8),    w: getColW('col_sub_pg',55) },
        { dataKey:'note',      x: getColX('col_note',423.9),   label:'コメント', fs: getColFS('col_note',8),     w: getColW('col_note',236) },
      ];
      const LINE_X_START = T_COLS[0].x;
      // LINE_X_END: 最後のカラムX + そのカラムの幅(note列から取得)
      const lastCol = T_COLS[T_COLS.length - 1];
      // 罫線右端: A4幅(595.28)-右マージン(30)=565 を上限とする
      const LINE_X_END = Math.min(lastCol.x + lastCol.w, 565);

      const getTV = (t: any, key: string) => {
        // ①⑩ toolNo: t.toolNoが正しいフィールド(N30,N60等)
        if (key==='toolNo')    return t.toolNo ?? '';
        if (key==='toolName')  return t.toolName ?? '';
        if (key==='tNumber')   return String(t.tNo ?? t.tNumber ?? '');
        if (key==='hValue')    return t.lengthOffsetNo ?? '';
        if (key==='dRegister') return t.diaOffsetNo ?? '';
        // ①⑩ D値: dValueContent が正しいフィールド名
        if (key==='dValue')    return t.dValueContent ?? '';
        if (key==='subPgNo')   return t.subPgNo ?? '';
        if (key==='note')      return t.note ?? '';
        return '';
      };

      // カラムヘッダ描画関数
      const drawColHeader = async () => {
        await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H * 2, toolingTplDoc);
        T_COLS.forEach(col => {
          const hdrY = curY - COL_HDR_H + (COL_HDR_H - col.fs * 0.72) / 2;
          drawTxt(col.label, col.x + 2, hdrY, col.fs);
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - COL_HDR_H);
        curY -= COL_HDR_H;
      };

      await drawColHeader();

      // カラム幅: DBのnote設定値を優先。最終列はLINE_X_END基準で実際のページ幅に合わせる
      const colWidths: number[] = T_COLS.map((col, i) => {
        if (col.w > 0) {
          // 最終列かつ右端を超える場合はLINE_X_END - col.x に制限
          if (i === T_COLS.length - 1) return Math.min(col.w, LINE_X_END - col.x - 2);
          return col.w;
        }
        // w未設定: 次カラムXとの差 or 最終列はLINE_X_END基準
        return i < T_COLS.length - 1 ? T_COLS[i+1].x - col.x - 2 : LINE_X_END - col.x - 2;
      });

      // テキスト折り返し（全角考慮）
      const wrapTxt = (text: string, maxW: number, fs: number): string[] => {
        if (!text) return [];
        const result: string[] = [];
        const rows = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
        for (const raw of rows) {
          if (!raw) { result.push(''); continue; }
          let cur = ''; let curW = 0;
          for (const ch of [...raw]) {
            const cw = ch.charCodeAt(0) > 0xFF ? fs * 0.95 : fs * 0.55;
            if (curW + cw > maxW && cur) { result.push(cur); cur = ch; curW = cw; }
            else { cur += ch; curW += cw; }
          }
          if (cur) result.push(cur);
        }
        return result.length ? result : [''];
      };

      let needsColHdr = false;
      for (const t of tooling) {
        if (needsColHdr) { await drawColHeader(); needsColHdr = false; }
        // 各カラムの折り返し行を計算（カラムごとのフォントサイズ使用）
        const colLines = T_COLS.map((col, i) => wrapTxt(getTV(t, col.dataKey), colWidths[i], col.fs));
        const maxLines = Math.max(1, ...colLines.map(l => l.length));
        const maxFs = Math.max(...T_COLS.map(c => c.fs));
        const rowH = Math.max(ROW_H, maxLines * (maxFs * 1.4));
        const prevY = curY;
        await ensureSpace(rowH + ROW_MARGIN, null);
        if (curY > prevY) { needsColHdr = true; continue; }
        T_COLS.forEach((col, ci) => {
          // ③ 折り返し: 行上端からline_heightずつ下げる
          colLines[ci].forEach((line, li) => {
            if (line) drawTxt(line, col.x + 2, curY - col.fs * 1.2 - li * (col.fs * 1.4), col.fs);
          });
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - rowH);
        curY -= (rowH + ROW_MARGIN);
      }
      curY -= BLOCK_MARGIN;
    }


    // ③ WO枠（ワークオフセット）
    // ══════════════════════════════════════════════════════════
    // 方式: curY基準で相対描画（同ページ継続 + スペース不足時のみページ追加）
    // テンプレートの枠・罫線はコードで再現
    // 4レコード横並び。各列はcol_w幅
    // ──────────────────────────────────────────────────────────
    // テンプレートのDB座標（参考値）:
    //   G行: x=103, y=744  X行: x=104, y=731
    //   Y行: x=102.7, y=716  Z行: x=103.3, y=702
    //   A/C行: x=102, y=688.7  R/B行: x=102, y=674
    //   列幅(3列): x=201.3
    //   → 1列値のX=103, ラベル幅≒28, 行高≒(744-674)/5=14, 全体高≒(744-674+14)=84
    // ══════════════════════════════════════════════════════════
    const workOffsets: any[] = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woTplDoc  = await loadTpl('repeat_wo.pdf');
      const woFields  = fieldsByTpl('repeat_wo');

      // 値行フィールド（G行/X行/Y行/Z行/A/C行/R/B行）sort_order順
      const WO_ROW_FIELDS = woFields
        .filter((f:any) => {
          const k = f.field_key;
          if (k.startsWith('__')) return false;
          if (f.label === '\u5217\u5e45(3\u5217)' || k === '\u5217\u5e45(3\u5217)') return false;
          if (f.label === 'WO\u8a2d\u5b9a'  || k === 'WO\u8a2d\u5b9a') return false;
          return true;
        })
        .sort((a:any,b:any) => a.sort_order - b.sort_order);

      const woFs   = WO_ROW_FIELDS.length > 0 ? Number(WO_ROW_FIELDS[0].font_size) : 12;
      const N_ROWS = WO_ROW_FIELDS.length || 6; // G/X/Y/Z/A/C/R/B の行数

      // レイアウト定数（テンプレートDB座標から導出）
      const WO_ROW_H  = 14.0;   // 1行高さ(pt)
      const WO_LBL_W  = 28.0;   // ラベル列幅(pt)
      // 列幅フィールドのx値 = 1列分の幅（3列設計）
      const colWF = woFields.find((f:any) => f.label === '\u5217\u5e45(3\u5217)' || f.label === '__col_w__');
      // ② WO枠レイアウト: 左端30・右端565・4枠・GAP8で均等配置
      const WO_X0    = 30;     // ページ左端マージン固定
      const WO_X_END = 565;    // ページ右端
      const COLS     = 4;      // 横並び枠数
      const WO_GAP   = 8;      // 枠間ギャップ(pt)
      const COL_W    = Math.floor((WO_X_END - WO_X0 - WO_GAP * (COLS - 1)) / COLS); // (535-24)/4=127
      const BLK_H    = N_ROWS * WO_ROW_H + 2; // ブロック高さ（余白2pt含む）

      // 各行の値キー（sort_order順）
      const WO_DATA_KEYS = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];

      // 縦罫線ヘルパー
      const drawVLine = (x: number, yBot: number, yTop: number) => {
        if (!curPage) return;
        try { curPage.drawLine({ start:{x,y:yBot}, end:{x,y:yTop}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      };

      // WOブロック描画関数（curY位置に1ブロック描画）
      const drawWoBlock = (chunk: any[]) => {
        const topY = curY;
        const botY = topY - BLK_H;

        // 各列の枠・罫線・値を描画
        for (let ci = 0; ci < COLS; ci++) {
          const gx    = WO_X0 + ci * (COL_W + WO_GAP);
          const valX  = gx + WO_LBL_W;
          const valW  = COL_W - WO_LBL_W;

          // 列外枠
          drawRect(gx, botY, COL_W, BLK_H);
          // ラベル-値間縦罫線
          drawVLine(valX, botY, topY);

          if (ci >= chunk.length) continue; // データなし列はスキップ
          const wo = chunk[ci];

          // 各行
          for (let ri = 0; ri < N_ROWS; ri++) {
            const rowTopY = topY - ri * WO_ROW_H;
            const rowBotY = rowTopY - WO_ROW_H;
            const txtY    = rowBotY + (WO_ROW_H - woFs * 0.72) / 2;

            // 行下罫線（ラベル列・値列にまたがる）
            if (ri > 0) drawHLine(gx, gx + COL_W, rowTopY);

            // ラベルテキスト（DBのフィールドラベルを使用）
            if (ri < WO_ROW_FIELDS.length) {
              const lbl = WO_ROW_FIELDS[ri].label.replace('\u884c',''); // "G行"→"G"
              drawTxt(lbl, gx + 2, txtY, woFs);
            }

            // 値テキスト
            if (ri < WO_DATA_KEYS.length) {
              const raw = wo[WO_DATA_KEYS[ri]];
              if (raw != null && raw !== '') {
                const val = typeof raw === 'number' ? raw.toFixed(3) : (parseFloat(String(raw)) === parseFloat(String(raw)) ? parseFloat(String(raw)).toFixed(3) : String(raw)); // (7) 0->0.000
                drawTxt(val, valX + 2, txtY, woFs);
              }
            }
          }
        }

        curY -= (BLK_H + 4);
      };

      // 4レコードずつチャンクに分割
      const chunks: any[][] = [];
      for (let i = 0; i < workOffsets.length; i += COLS) {
        chunks.push(workOffsets.slice(i, i + COLS));
      }

      for (const chunk of chunks) {
        await ensureSpace(BLK_H + 4, woTplDoc);
        drawWoBlock(chunk);
      }

      curY -= BLOCK_MARGIN;
    }

    // ④ インデックスプログラム（同ページ継続）
    // ══════════════════════════════════════════════════════════
    const indexPrograms: any[] = (options.include_index_programs !== false) ? (d.indexPrograms ?? []) : [];
    if (indexPrograms.length > 0) {
      const ipTplDoc = await loadTpl('repeat_ip.pdf');
      const ipFields = fieldsByTpl('repeat_ip');
      const ipRowCfg = ipFields.find((f:any) => f.field_key === '__row_cfg__');
      const ipCols   = ipFields.filter((f:any) => f.field_key.startsWith('col_'));
      const IP_ROW_H = ipRowCfg ? parseFloat(ipRowCfg.font_size) : 14.0;
      const IP_MARGIN = 2.0;
      const getIPCX  = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f?Number(f.x):def; };

      const getIPCFS = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f?Number(f.font_size):def; };
      const getIPCW  = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f&&f.note?parseFloat(f.note):def; };

      // IP列: STEP/N=axis0, 第1軸=axis1, 第2軸=axis2, 備考=note
      // sortOrder列(No)は削除 - テンプレートのSTEP/Nにaxis0の値を使う
      type IPCol = { dataKey: string; x: number; label: string; fs: number; w: number };
      const IP_COLS: IPCol[] = [
        { dataKey:'axis0', x: getIPCX('col_no',30),     label:'STEP/N', fs: getIPCFS('col_no',8),    w: getIPCW('col_no',80)    },
        { dataKey:'axis1', x: getIPCX('col_axis1',130), label:'第1軸',  fs: getIPCFS('col_axis1',8), w: getIPCW('col_axis1',190)},
        { dataKey:'axis2', x: getIPCX('col_axis2',320), label:'第2軸',  fs: getIPCFS('col_axis2',8), w: getIPCW('col_axis2',150)},
        { dataKey:'note',  x: getIPCX('col_note',470),  label:'備考',   fs: getIPCFS('col_note',8),  w: getIPCW('col_note',90)  },
      ];
      const IP_LINE_X1 = IP_COLS[0].x;
      const ipLastCol  = IP_COLS[IP_COLS.length - 1];
      const IP_LINE_X2 = Math.min(ipLastCol.x + ipLastCol.w, 565);
      const IP_HDR_H   = IP_ROW_H + 2;

      // テンプレートPDFのヘッダ行下端Y: DBのcol_noフィールドのy座標を使用
      // (PDFエディタでcol_noのYをヘッダ行下端に合わせることで調整可能)
      const ipHdrEndY = ipCols.find((f:any) => f.field_key==='col_no')
        ? Number(ipCols.find((f:any) => f.field_key==='col_no')!.y)
        : 780; // デフォルト(テンプレートのヘッダ行下端)

      // カラムヘッダ描画関数（改ページ後の白紙ページ用）
      const drawIPHdr = async (useTpl: boolean) => {
        await addNewPage(useTpl ? ipTplDoc : null);
        if (useTpl) {
          // 初回: テンプレートPDFにヘッダ印刷済み
          // curYをテンプレートのヘッダ行下端に合わせる
          curY = ipHdrEndY;
        } else {
          // 改ページ後(白紙): コードでヘッダを描画
          const hdrY = curY - IP_HDR_H + (IP_HDR_H - IP_COLS[0].fs * 0.72) / 2;
          IP_COLS.forEach(col => drawTxt(col.label, col.x + 2, hdrY, col.fs));
          drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_HDR_H, 0.6, rgb(0,0,0));
          curY -= IP_HDR_H;
        }
      };

      // 初回: テンプレートページ(ヘッダ印刷済み、curYをヘッダ下端に設定)
      await drawIPHdr(true);

      for (let i=0; i<indexPrograms.length; i++) {
        // スペース不足時: 新ページ(白紙)+ヘッダ再描画
        if (curY - (IP_ROW_H + IP_MARGIN) < PAGE_BOTTOM_MARGIN) {
          await drawIPHdr(false);
        }
        const ip = indexPrograms[i];
        IP_COLS.forEach(col => {
          const val = String((ip as any)[col.dataKey] ?? '');
          if (!val) return;
          const txtY = curY - IP_ROW_H + (IP_ROW_H - col.fs * 0.72) / 2;
          drawTxt(val, col.x + 2, txtY, col.fs);
        });
        drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_ROW_H);
        curY -= (IP_ROW_H + IP_MARGIN);
      }
      curY -= BLOCK_MARGIN;
    }

    // ══════════════════════════════════════════
    // ⑤ template_repeat_p2.pdf を最終ページに結合
    // ══════════════════════════════════════════
    const p2Path = `${ASSETS}/template_repeat_p2.pdf`;
    if (fs.existsSync(p2Path)) {
      const p2Doc  = await PDFLib.load(fs.readFileSync(p2Path));
      p2Doc.registerFontkit(fontkit.default ?? fontkit);
      const p2Font = await p2Doc.embedFont(fontBytes);
      const p2Page = p2Doc.getPage(0);
      for (const f of fieldsByTpl('repeat_p2').filter((f:any) => !f.field_key.startsWith('__'))) {
        const text = resolveVal(f.data_source);
        if (!text) continue;
        try { p2Page.drawText(text, { x: Number(f.x), y: Number(f.y), size: Number(f.font_size)||7, font: p2Font, color: rgb(0,0,0) }); } catch(_) {}
      }
      const [pg] = await finalDoc.copyPages(p2Doc, [0]);
      finalDoc.addPage(pg);
      totalPages++;
    }

    // ── ページ番号書き込み ──
    const pnF = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__page_no__');
    if (pnF && totalPages > 0) {
      const pnX = Number(pnF.x), pnY = Number(pnF.y), pnSz = Number(pnF.font_size) || 6.5;
      finalDoc.getPages().forEach((pg, pi) => {
        try {
          pg.drawRectangle({ x: pnX-2, y: pnY-2, width: 65, height: pnSz*1.8+4, color: rgb(1,1,1), borderWidth: 0 });
          pg.drawText(`${pi+1} / ${totalPages}`, { x: pnX, y: pnY, size: pnSz, font: finalFont, color: rgb(0,0,0) });
        } catch(_) {}
      });
    }

    // ── プレビュー透かし ──
    if ((options as any).is_preview === true) {
      try {
        const { degrees: degs } = await import('pdf-lib');
        for (const page of finalDoc.getPages()) {
          const { width, height } = page.getSize();
          for (const pos of [{x:width*0.15,y:height*0.25},{x:width*0.35,y:height*0.55},{x:width*0.55,y:height*0.75}]) {
            page.drawText('プレビュー', { x:pos.x, y:pos.y, size:60, font:finalFont, color:rgb(0.75,0.75,0.75), rotate:degs(35), opacity:0.35 });
          }
        }
      } catch(_) {}
    }

    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

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