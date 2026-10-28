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
      // [段取シートバック] 一覧表示・手動検索用に旧ACC_NC.NC_id(legacyNcId)と
      // 加工ID(machiningId)、シート種別を追加(MC側uncollectedMcと同一仕様)。
      legacy_nc_id:  s.ncProgram.legacyNcId ?? null,
      machining_id:  s.ncProgram.machiningId,
      sheet_type:    (s as any).sheetType ?? null,
      is_reference:  (s as any).isReference ?? false,
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
      operator_name: s.operator?.name ?? null,
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
            machining: { select: { mcProcessNo: true, version: true,
                                   machine: { select: { machineCode: true, machineName: true, sortOrder: true } } } },
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
      // [No.57] ①段取シート印刷時に機械を選んだ → その機械(machine_id_log。旧DBのNow段取シートクエリと同一)
      //         ②選んでいない → マシニング情報に登録した機械で表示し、「機械未選択」バッジを出す
      machine_code:   s.machine?.machineCode ?? (s.mcProgram?.machining as any)?.machine?.machineCode ?? null,
      machine_name:   s.machine?.machineName ?? (s.mcProgram?.machining as any)?.machine?.machineName ?? null,
      machine_sort:   s.machine?.sortOrder   ?? (s.mcProgram?.machining as any)?.machine?.sortOrder   ?? 999,
      machine_unselected: s.machineIdLog == null,
      version:        s.version ?? null,
      printed_at:     s.printedAt,
      operator_name:  s.operator?.name ?? null,
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
    return { message: this.lostMessage(reason) };
  }

  /** [No.60] 作業記録なしで回収済みにしたときのメッセージ(回収理由に合わせる。従来は常に「行方不明」) */
  private lostMessage(reason: string | null | undefined) {
    return reason ? `作業記録なしで回収済みにしました(${reason})` : '作業記録なしで回収済みにしました';
  }

  /** ⑦段取シート行方不明処理(論理削除・理由記録) — NC */
  async markNcSetupSheetLost(id: number, reason: string, detail: string | null, userId: number | null) {
    await this.prisma.setupSheetLog.update({
      where: { id },
      data: { isLost: true, lostReason: reason, lostDetail: detail, lostAt: new Date(), lostBy: userId },
    });
    return { message: this.lostMessage(reason) };
  }
}
