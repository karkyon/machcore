import { Injectable, NotFoundException } from "@nestjs/common";
import { CreateWorkRecordDto } from './dto/create-work-record.dto';
import { PrismaService } from "../prisma/prisma.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";

@Injectable()
export class NcService {
  constructor(private readonly prisma: PrismaService) {}

  /** NC-01: 部品検索 */
  async search(key: string, q: string, limit = 50, offset = 0) {
    const where: any = {};
    if (q && q.trim()) {
      const trimQ = q.trim();
      switch (key) {
        case "nc_id":
          const ncId = parseInt(trimQ);
          if (!isNaN(ncId)) where.id = ncId;
          break;
        case "part_id":
          where.part = { partId: trimQ };
          break;
        case "drawing_no":
          where.part = { drawingNo: { contains: trimQ, mode: "insensitive" } };
          break;
        case "name":
          where.part = { name: { contains: trimQ, mode: "insensitive" } };
          break;
        default:
          where.OR = [
            { part: { drawingNo: { contains: trimQ, mode: "insensitive" } } },
            { part: { name:      { contains: trimQ, mode: "insensitive" } } },
          ];
      }
    }
    const [total, data] = await Promise.all([
      this.prisma.ncProgram.count({ where }),
      this.prisma.ncProgram.findMany({
        where,
        take: limit,
        skip: offset,
        select: {
          id: true, processL: true, version: true, status: true,
          folderName: true, fileName: true, machiningTime: true,
          part:    { select: { id: true, partId: true, drawingNo: true, name: true, clientName: true } },
          machine: { select: { machineCode: true } },
        },
        orderBy: [{ part: { drawingNo: "asc" } }, { processL: "asc" }],
      }),
    ]);
    return {
      total,
      data: data.map(r => ({
        nc_id: r.id, part_db_id: r.part.id, part_id: r.part.partId,
        drawing_no: r.part.drawingNo, part_name: r.part.name,
        client_name: r.part.clientName, process_l: r.processL,
        machine_code: r.machine?.machineCode ?? null,
        status: r.status, version: r.version,
        folder_name: r.folderName, file_name: r.fileName,
        machining_time: r.machiningTime,
      })),
    };
  }

  /** NC-02: 最近のアクセス5件 */
  async recent() {
    const logs = await this.prisma.operationLog.findMany({
      where:   { ncProgramId: { not: null } },
      take:    5,
      orderBy: { createdAt: "desc" },
      select: {
        actionType: true, createdAt: true,
        user: { select: { name: true } },
        ncProgram: {
          select: {
            id: true, processL: true, version: true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },
      },
    });
    return logs.map(l => ({
      nc_id: l.ncProgram?.id, drawing_no: l.ncProgram?.part.drawingNo,
      part_name: l.ncProgram?.part.name, process_l: l.ncProgram?.processL,
      machine_code: l.ncProgram?.machine?.machineCode,
      version: l.ncProgram?.version, action_type: l.actionType,
      operator_name: l.user?.name, accessed_at: l.createdAt,
    }));
  }

  /** NC-03: NC詳細 */
  async findOne(id: number) {
    const r = await this.prisma.ncProgram.findUnique({
      where: { id },
      include: {
        part: true, machine: true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        tools: { orderBy: { sortOrder: "asc" } },
      },
    });
    if (!r) throw new NotFoundException(`NC_id ${id} が存在しません`);
    return r;
  }

  /** NC-04: 新規登録 */
  async create(dto: CreateNcDto, operatorId: number) {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);

    const nc = await this.prisma.$transaction(async (tx) => {
      const created = await tx.ncProgram.create({
        data: {
          partId:        dto.part_id,
          processL:      dto.process_l,
          machineId:     dto.machine_id     ?? null,
          machiningTime: dto.machining_time ?? null,
          folderName:    dto.folder_name,
          fileName:      dto.file_name,
          version:       dto.version,
          clampNote:     dto.clamp_note     ?? null,
          status:        "NEW",
          registeredBy:  operatorId,
        },
      });
      await tx.changeHistory.create({
        data: {
          ncProgramId:   created.id,
          operatorId,
          changeType:    "NEW_REGISTRATION",
          versionBefore: null,
          versionAfter:  dto.version,
          content:       `新規登録: ${part.drawingNo} L${dto.process_l}`,
        },
      });
      return created;
    });

    return { nc_id: nc.id, message: "新規登録が完了しました" };
  }

  /** NC-05: 更新 */
  async update(id: number, dto: UpdateNcDto, operatorId: number) {
    const existing = await this.prisma.ncProgram.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`NC_id ${id} が存在しません`);

    const versionBefore = existing.version;
    const versionAfter  = dto.version ?? existing.version;

    const updated = await this.prisma.$transaction(async (tx) => {
      const result = await tx.ncProgram.update({
        where: { id },
        data: {
          machineId:     dto.machine_id     !== undefined ? dto.machine_id     : existing.machineId,
          machiningTime: dto.machining_time !== undefined ? dto.machining_time : existing.machiningTime,
          folderName:    dto.folder_name    ?? existing.folderName,
          fileName:      dto.file_name      ?? existing.fileName,
          version:       versionAfter,
          clampNote:     dto.clamp_note     !== undefined ? dto.clamp_note     : existing.clampNote,
          status:        "CHANGING",
        },
      });
      const changedFields: string[] = [];
      if (dto.machine_id     !== undefined) changedFields.push("機械");
      if (dto.machining_time !== undefined) changedFields.push("加工時間");
      if (dto.folder_name    !== undefined) changedFields.push("フォルダ名");
      if (dto.file_name      !== undefined) changedFields.push("ファイル名");
      if (dto.version        !== undefined) changedFields.push(`Ver ${versionBefore}→${versionAfter}`);
      if (dto.clamp_note     !== undefined) changedFields.push("クランプ備考");

      await tx.changeHistory.create({
        data: {
          ncProgramId:   id,
          operatorId,
          changeType:    "CHANGE",
          versionBefore,
          versionAfter,
          content: changedFields.length > 0
            ? `変更項目: ${changedFields.join(", ")}`
            : "内容変更",
        },
      });
      return result;
    });

    return { nc_id: updated.id, message: "更新が完了しました" };
  }
  
  /** NC-09: 変更履歴一覧 */
  async changeHistory(ncProgramId: number) {
    const rows = await this.prisma.changeHistory.findMany({
      where:   { ncProgramId },
      orderBy: { changedAt: "desc" },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id: r.id, changed_at: r.changedAt, change_type: r.changeType,
      change_detail: r.content, ver_before: r.versionBefore,
      ver_after: r.versionAfter, operator_name: r.operator?.name ?? null,
    }));
  }

  /** NC-10: 印刷履歴一覧 */
  async setupSheetLogs(ncProgramId: number) {
    const rows = await this.prisma.setupSheetLog.findMany({
      where:   { ncProgramId },
      orderBy: { printedAt: "desc" },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id: r.id, printed_at: r.printedAt, version: null,
      printer_name: r.operator?.name ?? null,
    }));
  }

  /** WR-01: 作業記録一覧 */
  async workRecords(ncProgramId: number) {
    const rows = await this.prisma.workRecord.findMany({
      where:   { ncProgramId },
      orderBy: { workDate: "desc" },
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    return rows.map(r => ({
      id: r.id, work_date: r.workDate, operator_name: r.operator?.name ?? null,
      machine_code: r.machine?.machineCode ?? null,
      setup_time: r.setupTimeMin, machining_time: r.machiningTimeMin,
      quantity: r.quantity, note: r.note,
    }));
  }
 
  /** WR-02: 作業記録 新規登録 */
  async createWorkRecord(
    ncProgramId: number,
    dto: CreateWorkRecordDto,
    operatorId: number,
  ) {
    // nc_program が存在するか確認
    const nc = await this.prisma.ncProgram.findUnique({
      where: { id: ncProgramId },
    });
    if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);
 
    // 使用機械: dto.machine_id → nc.machineId → null の優先順
    const machineId = dto.machine_id ?? nc.machineId ?? null;
 
    const record = await this.prisma.workRecord.create({
      data: {
        ncProgramId,
        operatorId,
        machineId,
        workDate:            new Date(),
        setupTimeMin:        dto.setup_time_min        ?? null,
        machiningTimeMin:    dto.machining_time_min    ?? null,
        cycleTimeSec:        dto.cycle_time_sec        ?? null,
        quantity:            dto.quantity              ?? null,
        interruptionTimeMin: dto.interruption_time_min ?? null,
        workType:            dto.work_type             ?? null,
        note:                dto.note                  ?? null,
      },
    });
 
    return {
      id:      record.id,
      message: '作業記録を登録しました',
    };
  }
}
