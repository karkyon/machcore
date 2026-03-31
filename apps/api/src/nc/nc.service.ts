import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class NcService {
  constructor(private readonly prisma: PrismaService) {}

  /** NC-01: 部品検索 */
  async search(key: string, q: string, limit = 50, offset = 0) {
    const where: any = {};
    if (q) {
      if (key === 'nc_id') {
        where.id = parseInt(q) || 0;
      } else if (key === 'part_id') {
        where.part = { partId: q };
      } else if (key === 'drawing_no') {
        where.part = { drawingNo: { contains: q } };
      } else if (key === 'name') {
        where.part = { name: { contains: q } };
      }
    }
    const [total, data] = await Promise.all([
      this.prisma.ncProgram.count({ where }),
      this.prisma.ncProgram.findMany({
        where, take: limit, skip: offset,
        select: {
          id: true, processL: true, version: true, status: true,
          part:    { select: { drawingNo: true, name: true } },
          machine: { select: { machineCode: true } },
        },
        orderBy: [{ part: { drawingNo: 'asc' } }, { processL: 'asc' }],
      }),
    ]);
    return {
      total,
      data: data.map(r => ({
        nc_id:        r.id,
        drawing_no:   r.part.drawingNo,
        part_name:    r.part.name,
        process_l:    r.processL,
        machine_code: r.machine?.machineCode ?? null,
        status:       r.status,
        version:      r.version,
      })),
    };
  }

  /** NC-02: 最近のアクセス */
  async recent() {
    const logs = await this.prisma.operationLog.findMany({
      where:   { ncProgramId: { not: null } },
      take:    5,
      orderBy: { createdAt: 'desc' },
      select: {
        actionType: true, createdAt: true,
        user:      { select: { name: true } },
        ncProgram: {
          select: {
            id: true, processL: true,
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
      action_type:   l.actionType,
      operator_name: l.user?.name,
      accessed_at:   l.createdAt,
    }));
  }

  /** NC-03: NC詳細 */
  async findOne(id: number) {
    const r = await this.prisma.ncProgram.findUnique({
      where: { id },
      include: {
        part:      true,
        machine:   true,
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
        tools:     { orderBy: { sortOrder: 'asc' } },
      },
    });
    if (!r) throw new NotFoundException(`NC_id ${id} が存在しません`);
    return r;
  }
}
