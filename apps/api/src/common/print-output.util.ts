import { PrismaService } from '../prisma/prisma.service';

/**
 * 段取シートの出力方式(マスタ: company_settings.print_mode。インスタンスごとのDBに持つ)
 *   DIRECT: サーバからプリンタへ直接印刷(lp)
 *   MANUAL: 正式な段取シートPDF(透かしなし)を画面に表示し、利用者がブラウザから手動で印刷する
 *           (サーバから事務所のプリンタへ直接印刷できない拠点用)
 * どちらでも発行履歴(setup_sheet_logs / mc_setup_sheet_logs)は同じく記録し、print_method に方式を残す。
 * 方式はサーバがDBの設定で決める(画面から送られた値は使わない)。
 */
export type PrintMethod = 'DIRECT' | 'MANUAL';
export const PRINT_METHODS: PrintMethod[] = ['DIRECT', 'MANUAL'];

export async function getPrintMode(prisma: PrismaService): Promise<PrintMethod> {
  const s = await prisma.companySetting.findFirst({ select: { printMode: true } });
  return s?.printMode === 'MANUAL' ? 'MANUAL' : 'DIRECT';
}

/** system_logs(category=PRINT)へ出力方式付きで記録(失敗しても本処理は止めない) */
export function logPrintOutput(
  prisma: PrismaService, level: 'INFO' | 'ERROR', message: string, detail: Record<string, unknown>,
): void {
  prisma.systemLog.create({ data: { level, category: 'PRINT', message, detail: detail as any } }).catch(() => {});
}

/** 手動印刷の応答: 画面で表示・印刷する段取シートPDFを base64 で返す */
export function manualPrintResult(pdf: Buffer, message: string, extra: Record<string, unknown> = {}) {
  return { ...extra, print_method: 'MANUAL' as PrintMethod, message, pdf_base64: pdf.toString('base64') };
}

export const MANUAL_PRINT_MESSAGE = '段取シートを画面に表示しました。内容を確認して印刷してください（手動印刷）';
