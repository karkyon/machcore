import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class DashboardService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * DASH-01: 未回収段取シート一覧
   * NC / MC の work_collected=false を機械IDソートで返す
   */
  async uncollectedSheets() {
    const [ncSheets, mcSheets] = await Promise.all([
      this.prisma.setupSheetLog.findMany({
        where: { workCollected: false },
        orderBy: [
          { ncProgram: { machine: { sortOrder: 'asc' } } },
          { printedAt: 'asc' },
        ],
        include: {
          operator: { select: { id: true, name: true } },
          ncProgram: {
            include: {
              part:    { select: { drawingNo: true, name: true, partId: true } },
              machine: { select: { id: true, machineCode: true, machineName: true, sortOrder: true } },
            },
          },
        },
      }),
      this.prisma.mcSetupSheetLog.findMany({
        where: { workCollected: false },
        orderBy: [
          { mcProgram: { machine: { sortOrder: 'asc' } } },
          { printedAt: 'asc' },
        ],
        include: {
          operator: { select: { id: true, name: true } },
          mcProgram: {
            include: {
              part:    { select: { drawingNo: true, name: true, partId: true } },
              machine: { select: { id: true, machineCode: true, machineName: true, sortOrder: true } },
            },
          },
        },
      }),
    ]);

    const ncRows = ncSheets.map(s => ({
      id:           s.id,
      system:       'NC' as const,
      program_id:   s.ncProgramId,
      drawing_no:   s.ncProgram.part.drawingNo,
      part_name:    s.ncProgram.part.name,
      part_id:      s.ncProgram.part.partId ?? null,
      machine_code: s.ncProgram.machine?.machineCode ?? null,
      machine_name: s.ncProgram.machine?.machineName ?? null,
      machine_sort: s.ncProgram.machine?.sortOrder ?? 999,
      printed_at:   s.printedAt,
      operator_name: s.operator.name,
      version:      s.version ?? null,
    }));

    const mcRows = mcSheets.map(s => ({
      id:           s.id,
      system:       'MC' as const,
      program_id:   s.mcProgramId,
      drawing_no:   s.mcProgram.part.drawingNo,
      part_name:    s.mcProgram.part.name,
      part_id:      s.mcProgram.part.partId ?? null,
      machine_code: s.mcProgram.machine?.machineCode ?? null,
      machine_name: s.mcProgram.machine?.machineName ?? null,
      machine_sort: s.mcProgram.machine?.sortOrder ?? 999,
      printed_at:   s.printedAt,
      operator_name: s.operator.name,
      version:      s.version ?? null,
    }));

    // 機械sortOrder → 印刷日時でソート
    const all = [...ncRows, ...mcRows].sort((a, b) => {
      if (a.machine_sort !== b.machine_sort) return a.machine_sort - b.machine_sort;
      return new Date(a.printed_at).getTime() - new Date(b.printed_at).getTime();
    });

    return {
      total: all.length,
      nc_count: ncRows.length,
      mc_count: mcRows.length,
      items: all,
    };
  }

  /**
   * DASH-02: サマリーカウント（ダッシュボード上部カード用）
   */
  async summary() {
    const [
      ncTotal, mcTotal,
      ncPending, mcPending,
      uncollectedCount,
    ] = await Promise.all([
      this.prisma.ncProgram.count(),
      this.prisma.mcProgram.count(),
      this.prisma.ncProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.mcProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.setupSheetLog.count({ where: { workCollected: false } }).then(nc =>
        this.prisma.mcSetupSheetLog.count({ where: { workCollected: false } }).then(mc => nc + mc)
      ),
    ]);

    return {
      nc_total:         ncTotal,
      mc_total:         mcTotal,
      nc_pending:       ncPending,
      mc_pending:       mcPending,
      uncollected_sheets: uncollectedCount,
    };
  }
}
