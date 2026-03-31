import { Injectable, NotFoundException } from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";

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
          const partId = parseInt(trimQ);
          if (!isNaN(partId)) where.part = { partId: trimQ };
          break;
        case "drawing_no":
          where.part = { drawingNo: { contains: trimQ, mode: "insensitive" } };
          break;
        case "name":
          where.part = { name: { contains: trimQ, mode: "insensitive" } };
          break;
        default:
          // 複合検索（図面番号 OR 部品名称）
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
          id:       true,
          processL: true,
          version:  true,
          status:   true,
          folderName: true,
          fileName:   true,
          machiningTime: true,
          part:    { select: { id: true, partId: true, drawingNo: true, name: true, clientName: true } },
          machine: { select: { machineCode: true } },
        },
        orderBy: [
          { part:    { drawingNo: "asc" } },
          { processL: "asc" },
        ],
      }),
    ]);

    return {
      total,
      data: data.map(r => ({
        nc_id:         r.id,
        part_db_id:    r.part.id,
        part_id:       r.part.partId,
        drawing_no:    r.part.drawingNo,
        part_name:     r.part.name,
        client_name:   r.part.clientName,
        process_l:     r.processL,
        machine_code:  r.machine?.machineCode ?? null,
        status:        r.status,
        version:       r.version,
        folder_name:   r.folderName,
        file_name:     r.fileName,
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
        actionType: true,
        createdAt:  true,
        user: { select: { name: true } },
        ncProgram: {
          select: {
            id:       true,
            processL: true,
            version:  true,
            part:    { select: { drawingNo: true, name: true } },
            machine: { select: { machineCode: true } },
          },
        },
      },
    });
    return logs.map(l => ({
      nc_id:         l.ncProgram?.id,
      drawing_no:    l.ncProgram?.part.drawingNo,
      part_name:     l.ncProgram?.part.name,
      process_l:     l.ncProgram?.processL,
      machine_code:  l.ncProgram?.machine?.machineCode,
      version:       l.ncProgram?.version,
      action_type:   l.actionType,
      operator_name: l.user?.name,
      accessed_at:   l.createdAt,
    }));
  }

  /** NC-03: NC詳細（旋盤データ＋工具リスト） */
  async findOne(id: number) {
    const r = await this.prisma.ncProgram.findUnique({
      where: { id },
      include: {
        part:      true,
        machine:   true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        tools:     { orderBy: { sortOrder: "asc" } },
      },
    });
    if (!r) throw new NotFoundException(`NC_id ${id} が存在しません`);
    return r;
  }
  
  /** NC-09: 変更履歴一覧 */
  async changeHistory(ncProgramId: number) {
    const rows = await this.prisma.changeHistory.findMany({
      where:   { ncProgramId },
      orderBy: { changedAt: 'desc' },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id:            r.id,
      changed_at:    r.changedAt,
      change_type:   r.changeType,
      change_detail: r.content,
      ver_before:    r.versionBefore,
      ver_after:     r.versionAfter,
      operator_name: r.operator?.name ?? null,
    }));
  }

  /** NC-10: 印刷履歴一覧 */
  async setupSheetLogs(ncProgramId: number) {
    const rows = await this.prisma.setupSheetLog.findMany({
      where:   { ncProgramId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id:           r.id,
      printed_at:   r.printedAt,
      version:      null,
      printer_name: r.operator?.name ?? null,
    }));
  }

  /** WR-01: 作業記録一覧 */
  async workRecords(ncProgramId: number) {
    const rows = await this.prisma.workRecord.findMany({
      where:   { ncProgramId },
      orderBy: { workDate: 'desc' },
      include: {
        operator: { select: { id: true, name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    return rows.map(r => ({
      id:              r.id,
      work_date:       r.workDate,
      setup_time:      r.setupTimeMin,
      machining_time:  r.machiningTimeMin,
      quantity:        r.quantity,
      note:            r.note,
      operator_name:   r.operator?.name ?? null,
      machine_code:    r.machine?.machineCode ?? null,
    }));
  }
}
