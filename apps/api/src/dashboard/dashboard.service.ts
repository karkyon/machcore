import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class DashboardService {
  constructor(private readonly prisma: PrismaService) {}

  async uncollectedNc() {
    const rows = await this.prisma.setupSheetLog.findMany({
      where: { workCollected: false, isLost: false },
      orderBy: [
        { ncProgram: { machining: { machine: { sortOrder: 'asc' } } } },
        { printedAt: 'asc' },
      ],
      include: {
        operator:  { select: { name: true } },
        ncProgram: {
          include: {
            part:     { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },
            machining: {
              include: {
                machine: { select: { machineCode: true, machineName: true, sortOrder: true } },
              },
            },
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
      process_l:     s.ncProgram.machining?.processL ?? null,
      machine_code:  s.ncProgram.machining?.machine?.machineCode ?? null,
      machine_name:  s.ncProgram.machining?.machine?.machineName ?? null,
      machine_sort:  s.ncProgram.machining?.machine?.sortOrder ?? 999,
      version:       s.version ?? null,
      printed_at:    s.printedAt,
      operator_name: s.operator.name,
    }));
    return { total: items.length, items };
  }

  async uncollectedMc() {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where: { workCollected: false, isLost: false },
      orderBy: [
        // machine_id_log（変更履歴の印刷時機械）でソート
        // machiningの機械ではなく印刷時に実際に使った機械で並べる
        { machine: { id: 'asc' } },
        { printedAt: 'asc' },
      ],
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true, machineName: true, sortOrder: true } },
        mcProgram: {
          include: {
            part:     { select: { partId: true, drawingNo: true, name: true, clientName: true, mainModel: true } },
            machining: { select: { mcProcessNo: true, version: true } },
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
      mc_process_no:  s.mcProgram?.machining?.mcProcessNo ?? null,
      // machine_id_log（変更履歴の印刷時機械）を使用 = 旧DBのNow段取シートクエリと同一
      machine_code:   s.machine?.machineCode ?? null,
      machine_name:   s.machine?.machineName ?? null,
      machine_sort:   s.machine?.sortOrder ?? 999,
      version:        s.version ?? null,
      printed_at:     s.printedAt,
      operator_name:  s.operator.name,
      is_reference:   (s as any).isReference ?? false,
      sheet_type:     (s as any).sheetType ?? null,
    }));
    return { total: items.length, items };
  }

  async summary() {
    const [ncTotal, mcTotal, ncPending, mcPending, ncUncollected, mcUncollected] = await Promise.all([
      this.prisma.ncProgram.count(),
      this.prisma.mcProgram.count(),
      this.prisma.ncProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.mcProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.setupSheetLog.count({ where: { workCollected: false, isLost: false } }),
      this.prisma.mcSetupSheetLog.count({ where: { workCollected: false, isLost: false } }),
    ]);
    return {
      nc_total: ncTotal, mc_total: mcTotal,
      nc_pending: ncPending, mc_pending: mcPending,
      nc_uncollected: ncUncollected, mc_uncollected: mcUncollected,
    };
  }

  /** ⑦段取シート行方不明処理(論理削除・理由記録) — MC */
  async markMcSetupSheetLost(id: number, reason: string, detail: string | null, userId: number | null) {
    await this.prisma.mcSetupSheetLog.update({
      where: { id },
      data: { isLost: true, lostReason: reason, lostDetail: detail, lostAt: new Date(), lostBy: userId },
    });
    return { message: '行方不明として処理しました' };
  }

  /** ⑦段取シート行方不明処理(論理削除・理由記録) — NC */
  async markNcSetupSheetLost(id: number, reason: string, detail: string | null, userId: number | null) {
    await this.prisma.setupSheetLog.update({
      where: { id },
      data: { isLost: true, lostReason: reason, lostDetail: detail, lostAt: new Date(), lostBy: userId },
    });
    return { message: '行方不明として処理しました' };
  }
}
