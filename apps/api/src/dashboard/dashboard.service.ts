import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class DashboardService {
  constructor(private readonly prisma: PrismaService) {}

  async uncollectedNc() {
    const rows = await this.prisma.setupSheetLog.findMany({
      where: { workCollected: false },
      orderBy: [
        { ncProgram: { machine: { sortOrder: 'asc' } } },
        { printedAt: 'asc' },
      ],
      include: {
        operator:  { select: { name: true } },
        ncProgram: {
          include: {
            part:    { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },
            machine: { select: { machineCode: true, machineName: true, sortOrder: true } },
          },
        },
      },
    });
    const items = rows.map(s => ({
      id:            s.id,
      nc_id:         s.ncProgramId,
      part_id:       s.ncProgram.part.partId,
      drawing_no:    s.ncProgram.part.drawingNo,
      part_name:     s.ncProgram.part.name,
      client_name:   s.ncProgram.part.clientName ?? null,
      main_model:    s.ncProgram.part.mainModel ?? null,
      process_l:     s.ncProgram.processL,
      machine_code:  s.ncProgram.machine?.machineCode ?? null,
      machine_name:  s.ncProgram.machine?.machineName ?? null,
      machine_sort:  s.ncProgram.machine?.sortOrder ?? 999,
      version:       s.version ?? null,
      printed_at:    s.printedAt,
      operator_name: s.operator.name,
    }));
    return { total: items.length, items };
  }

  async uncollectedMc() {
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
    });
    const items = rows.map(s => ({
      id:             s.id,
      mc_id:          s.mcProgramId,
      legacy_mcid:    s.mcProgram.legacyMcid ?? null,
      machining_id:   s.mcProgram.machiningId,
      part_id:        s.mcProgram.part.partId,
      drawing_no:     s.mcProgram.part.drawingNo,
      part_name:      s.mcProgram.part.name,
      client_name:    s.mcProgram.part.clientName ?? null,
      main_model:     s.mcProgram.part.mainModel ?? null,
      mc_process_no:  s.mcProgram.mcProcessNo ?? null,
      machine_code:   s.mcProgram.machine?.machineCode ?? null,
      machine_name:   s.mcProgram.machine?.machineName ?? null,
      machine_sort:   s.mcProgram.machine?.sortOrder ?? 999,
      version:        s.version ?? null,
      printed_at:     s.printedAt,
      operator_name:  s.operator.name,
    }));
    return { total: items.length, items };
  }

  async summary() {
    const [ncTotal, mcTotal, ncPending, mcPending, ncUncollected, mcUncollected] = await Promise.all([
      this.prisma.ncProgram.count(),
      this.prisma.mcProgram.count(),
      this.prisma.ncProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.mcProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.setupSheetLog.count({ where: { workCollected: false } }),
      this.prisma.mcSetupSheetLog.count({ where: { workCollected: false } }),
    ]);
    return {
      nc_total: ncTotal, mc_total: mcTotal,
      nc_pending: ncPending, mc_pending: mcPending,
      nc_uncollected: ncUncollected, mc_uncollected: mcUncollected,
    };
  }
}
