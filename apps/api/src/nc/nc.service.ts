import { Injectable, NotFoundException } from "@nestjs/common";
import { CreateWorkRecordDto } from './dto/create-work-record.dto';
import { PrismaService } from "../prisma/prisma.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";

import * as fs from 'fs';
import * as path from 'path';
import * as chardet from 'chardet';
import * as iconv from 'iconv-lite';
import { UpdateWorkRecordDto } from "./dto/update-work-record.dto";
@Injectable()
export class NcService {
  constructor(private readonly prisma: PrismaService) {}

  /** NC-01: 部品検索 */
  async search(key: string, q: string, limit = 50, offset = 0, clientName?: string, machineId?: number) {
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
    // 追加フィルタ
    if (clientName) {
      where.part = { ...(where.part ?? {}), clientName: { contains: clientName, mode: "insensitive" } };
    }
    if (machineId) {
      where.machineId = machineId;
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

  /** 納入先一覧（検索フォーム用） */
  async getClientNames(): Promise<string[]> {
    const rows = await this.prisma.part.findMany({
      where: { clientName: { not: null } },
      select: { clientName: true },
      distinct: ["clientName"],
      orderBy: { clientName: "asc" },
    });
    return rows.map(r => r.clientName!).filter(Boolean);
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
      id: r.id, printed_at: r.printedAt, version: r.version ?? null,
      printer_name: r.operator?.name ?? null,
    }));
  }

  /** 操作ログ一覧（USB_DOWNLOAD/FILE_UPLOAD/FILE_DELETE/SESSION_START/END のみ） */
  async operationLogs(ncProgramId: number) {
    const rows = await this.prisma.operationLog.findMany({
      where: {
        ncProgramId,
        actionType: { in: ['USB_DOWNLOAD', 'FILE_UPLOAD', 'FILE_DELETE', 'SESSION_START', 'SESSION_END'] as any[] },
      },
      orderBy: { createdAt: 'desc' },
      include: { user: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:          r.id,
      action_type: r.actionType,
      user_name:   r.user?.name ?? null,
      session_id:  r.sessionId,
      metadata:    r.metadata,
      created_at:  r.createdAt,
    }));
  }

  /** FIL-01: ファイル一覧 */
  async listFiles(ncProgramId: number) {
    const rows = await this.prisma.ncFile.findMany({
      where:   { ncProgramId },
      orderBy: { uploadedAt: 'desc' },
      include: { uploader: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      file_type:      r.fileType,
      original_name:  r.originalName,
      stored_name:    r.storedName,
      mime_type:      r.mimeType,
      file_size:      r.fileSize,
      file_path:      r.filePath,
      thumbnail_path: r.thumbnailPath,
      uploaded_by:    r.uploader?.name ?? null,
      uploaded_at:    r.uploadedAt,
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
 

  /** WR-単件: 作業記録1件取得（編集モード用） */
  async findWorkRecord(ncProgramId: number, recordId: number) {
    const r = await this.prisma.workRecord.findFirst({
      where:   { id: recordId, ncProgramId },
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    if (!r) throw new NotFoundException(`work_record id:${recordId} が存在しません`);
    return {
      id:                   r.id,
      work_date:            r.workDate,
      operator_name:        r.operator?.name ?? null,
      machine_code:         r.machine?.machineCode ?? null,
      machine_id:           r.machineId,
      setup_time:           r.setupTimeMin,
      machining_time:       r.machiningTimeMin,
      cycle_time_sec:       r.cycleTimeSec,
      quantity:             r.quantity,
      interruption_time_min: r.interruptionTimeMin,
      work_type:            r.workType,
      note:                 r.note,
      setup_operator_ids:      r.setupOperatorIds,
      production_operator_ids: r.productionOperatorIds,
    };
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
        setupOperatorIds:      dto.setup_operator_ids      ?? [],
        productionOperatorIds: dto.production_operator_ids ?? [],
      },
    });
 
    return {
      id:      record.id,
      message: '作業記録を登録しました',
    };
  }
  /** WR-03: 作業記録 更新 */
  async updateWorkRecord(
    ncProgramId: number,
    recordId: number,
    dto: UpdateWorkRecordDto,
    operatorId: number,
  ) {
    const record = await this.prisma.workRecord.findFirst({
      where: { id: recordId, ncProgramId },
    });
    if (!record) throw new NotFoundException(`work_record id:${recordId} が存在しません`);

    const updated = await this.prisma.workRecord.update({
      where: { id: recordId },
      data: {
        setupTimeMin:        dto.setup_time_min        !== undefined ? dto.setup_time_min        : record.setupTimeMin,
        machiningTimeMin:    dto.machining_time_min    !== undefined ? dto.machining_time_min    : record.machiningTimeMin,
        cycleTimeSec:        dto.cycle_time_sec        !== undefined ? dto.cycle_time_sec        : record.cycleTimeSec,
        quantity:            dto.quantity              !== undefined ? dto.quantity              : record.quantity,
        interruptionTimeMin: dto.interruption_time_min !== undefined ? dto.interruption_time_min : record.interruptionTimeMin,
        workType:            dto.work_type             !== undefined ? dto.work_type             : record.workType,
        note:                dto.note                 !== undefined ? dto.note                  : record.note,
        machineId:           dto.machine_id            !== undefined ? dto.machine_id            : record.machineId,
        setupOperatorIds:      dto.setup_operator_ids      !== undefined ? dto.setup_operator_ids      : (record.setupOperatorIds as any ?? []),
        productionOperatorIds: dto.production_operator_ids !== undefined ? dto.production_operator_ids : (record.productionOperatorIds as any ?? []),
      },
    });

    await this.prisma.operationLog.create({
      data: {
        userId:      operatorId,
        ncProgramId,
        actionType:  "EDIT_SAVE",
        metadata:    { action: "update_work_record", recordId },
      },
    });

    return { id: updated.id, message: "作業記録を更新しました" };
  }

  /** WR-04: 作業記録 削除 */
  async deleteWorkRecord(
    ncProgramId: number,
    recordId: number,
    operatorId: number,
  ) {
    const record = await this.prisma.workRecord.findFirst({
      where: { id: recordId, ncProgramId },
    });
    if (!record) throw new NotFoundException(`work_record id:${recordId} が存在しません`);

    await this.prisma.workRecord.delete({ where: { id: recordId } });

    await this.prisma.operationLog.create({
      data: {
        userId:      operatorId,
        ncProgramId,
        actionType:  "EDIT_SAVE",
        metadata:    { action: "delete_work_record", recordId },
      },
    });

    return { message: "作業記録を削除しました" };
  }

  // ── NC-07: 段取シートデータ取得 ─────────────────────────────────
async getPrintData(ncProgramId: number) {
  const nc = await this.prisma.ncProgram.findUnique({
    where: { id: ncProgramId },
    include: {
      part:      true,
      machine:   true,
      registrar: { select: { id: true, name: true } },
      approver:  { select: { id: true, name: true } },
      tools:     { orderBy: { sortOrder: 'asc' } },
      files: {
        where:   { fileType: 'DRAWING' },
        orderBy: { uploadedAt: 'desc' },
      },
    },
  });
  if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);
  return nc;
}

// ── NC-08: 段取シートPDF生成（Puppeteer） ───────────────────────
async generateSetupSheetPdf(
  ncProgramId: number,
  operatorId:  number,
  options:     { include_tools?: boolean; include_clamp?: boolean; include_drawings?: boolean },
): Promise<Buffer> {
  const data = await this.getPrintData(ncProgramId);

  // Puppeteer 動的インポート
  const puppeteer = (await import('puppeteer')).default;
  const browser   = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  try {
    const page = await browser.newPage();
    // 図ファイルをBase64に変換（include_drawings=true の場合）
    const drawingBase64s: string[] = [];
    if (options.include_drawings === true && data.files && data.files.length > 0) {
      const sharpLib = (await import('sharp')).default;
      for (const f of (data.files as any[]).slice(0, 3)) {
        try {
          const filePath: string = f.filePath ?? f.file_path ?? '';
          if (!filePath || !fs.existsSync(filePath)) continue;
          const buf = fs.readFileSync(filePath);
          const mime: string = f.mimeType ?? f.mime_type ?? '';
          if (mime.includes('tiff') || mime.includes('tif')) {
            const imgBuf = await sharpLib(buf).png().toBuffer();
            drawingBase64s.push('data:image/png;base64,' + imgBuf.toString('base64'));
          } else if (!mime.includes('pdf')) {
            drawingBase64s.push('data:' + mime + ';base64,' + buf.toString('base64'));
          }
        } catch (e: any) {
          console.warn('Drawing embed failed:', e?.message);
        }
      }
    }
    const html = this.buildSetupSheetHtml(data, { ...options, drawingBase64s });
    await page.setContent(html, { waitUntil: 'domcontentloaded', timeout: 15000 });

    const pdfUint8 = await page.pdf({
      format:          'A4',
      printBackground: true,
      margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' },
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `
        <div style="font-size:8px;width:100%;text-align:center;color:#888;font-family:sans-serif;">
          <span class="pageNumber"></span> / <span class="totalPages"></span>
        </div>`,
    });

    const pdfBuffer = Buffer.from(pdfUint8);

    // SetupSheetLog INSERT（エラーはログのみ）
    await this.prisma.setupSheetLog.create({
      data: { ncProgramId, operatorId, version: data?.version ?? null },
    }).catch(e => console.warn('SetupSheetLog insert failed:', e.message));

    return pdfBuffer;
  } finally {
    await browser.close();
  }
}

// ── HTMLテンプレートビルダー ────────────────────────────────────
private buildSetupSheetHtml(data: any, opts: any): string {
  const includeTools    = opts.include_tools    !== false;
  const includeClamp    = opts.include_clamp    !== false;
  const includeDrawings = opts.include_drawings === true;
  const drawingBase64s: string[] = opts.drawingBase64s ?? [];

  const now    = new Date();
  const fmtNow = `${now.getFullYear()}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const fmtDate = (d: string | null | undefined) => {
    if (!d) return '';
    try { const dt = new Date(d); return `${dt.getFullYear()}/${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`; }
    catch { return d; }
  };

  const toolRows = (includeTools && data.tools && data.tools.length > 0) ? data.tools.map((t: any) => `
    <tr style="page-break-inside:avoid;">
      <td class="c">${t.sortOrder ?? ''}</td>
      <td>${t.processType ?? ''}</td>
      <td class="mono">${t.chipModel ?? ''}</td>
      <td class="mono">${t.holderModel ?? ''}</td>
      <td class="c">${t.noseR ?? ''}</td>
      <td>${t.note ?? ''}</td>
    </tr>`).join('') : '<tr><td colspan="6" class="c" style="color:#aaa;font-size:8pt;padding:4px;">加工データなし</td></tr>';

  const drawingsHtml = (includeDrawings && drawingBase64s.length > 0)
    ? `<div style="margin-top:8px;page-break-inside:avoid;"><div class="sh">段取図</div>
       <div style="display:flex;flex-wrap:wrap;gap:8px;">
         ${drawingBase64s.map((src: string, i: number) => `<img src="${src}" alt="段取図${i+1}" style="max-width:49%;height:auto;border:1px solid #ccc;" />`).join('')}
       </div></div>` : '';

  const machTimeMin = data.machiningTime ?? 0;
  const machM = Math.floor(machTimeMin);
  const machS = Math.round((machTimeMin - machM) * 60);
  const machTimeStr = `${machM} M ${String(machS).padStart(2,'0')} S`;

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Noto Sans JP', sans-serif; font-size: 9pt; color: #000; background: #fff; padding: 8mm; }
  h1.title { font-size: 14pt; font-weight: 700; margin-bottom: 4px; }
  .id-row { font-size: 8pt; color: #444; margin-bottom: 6px; }
  table.info { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.info td { border: 1px solid #999; padding: 2px 5px; font-size: 9pt; vertical-align: middle; }
  table.info td.lbl { background: #e8e8e8; font-weight: 700; width: 80px; white-space: nowrap; }
  table.info td.val { }
  .備考box { background: #fffde7; border: 1px solid #ccc; padding: 4px 6px; font-size: 8.5pt;
              white-space: pre-wrap; min-height: 28px; margin-bottom: 4px; }
  table.sign { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.sign td { border: 1px solid #999; padding: 2px 5px; font-size: 8.5pt; }
  table.sign td.lbl { background: #e8e8e8; font-weight: 700; white-space: nowrap; }
  table.work { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.work td { border: 1px solid #999; padding: 3px 5px; font-size: 8.5pt; height: 22px; }
  table.work td.lbl { background: #e8e8e8; font-weight: 700; white-space: nowrap; width: 70px; }
  .sh { font-size: 8.5pt; font-weight: 700; background: #1e3a5f; color: #fff; padding: 2px 6px; margin-bottom: 1px; }
  table.tools { width: 100%; border-collapse: collapse; }
  table.tools th { background: #1e3a5f; color: #fff; font-weight: 700; padding: 3px 5px;
                   border: 1px solid #7a9cbf; font-size: 8.5pt; text-align: left; }
  table.tools td { border: 1px solid #ccc; padding: 2.5px 5px; font-size: 8.5pt; vertical-align: top; }
  table.tools tr:nth-child(even) td { background: #f5f5f5; }
  .c { text-align: center; }
  .mono { font-family: 'Courier New', monospace; }
  .foot { margin-top: 8px; padding-top: 4px; border-top: 1px solid #ccc;
          display: flex; justify-content: space-between; font-size: 7.5pt; color: #666; }
  @media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }
</style>
</head>
<body>
  <!-- タイトル行 -->
  <table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
    <tr>
      <td style="vertical-align:bottom;">
        <h1 class="title">NC段取シート</h1>
      </td>
      <td style="text-align:right;vertical-align:bottom;font-size:8pt;color:#555;">
        出力日時: ${fmtNow}
      </td>
    </tr>
  </table>

  <!-- ID行 -->
  <div class="id-row">
    NC_id <strong>${data.id}</strong>
    &nbsp;&nbsp;部品id <strong>${data.part?.partId ?? '—'}</strong>
    &nbsp;&nbsp;加工id <strong>${data.processingId ?? '—'}</strong>
  </div>

  <!-- 部品情報テーブル -->
  <table class="info">
    <tr>
      <td class="lbl">納入先</td>
      <td colspan="3">${data.part?.clientName ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">図面番号</td>
      <td>${data.part?.drawingNo ?? ''}</td>
      <td class="lbl" style="width:70px;">名　称</td>
      <td>${data.part?.name ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">主機種型式</td>
      <td colspan="3">${data.part?.machineType ?? data.machineType ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">Ｌ</td>
      <td style="width:60px;"><strong>${data.processL ?? ''}</strong></td>
      <td class="lbl">機　械</td>
      <td>${data.machine?.machineCode ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">タ イ ム</td>
      <td><strong>${machTimeStr}</strong></td>
      <td class="lbl">承認ステ</td>
      <td>${data.status === 'APPROVED' ? '承認済' : data.status === 'CHANGING' ? '変更中' : data.status === 'PENDING_APPROVAL' ? '未承認' : '新規'}</td>
    </tr>
    <tr>
      <td class="lbl">ﾌｧｲﾙ名</td>
      <td>${data.fileName ?? ''}</td>
      <td class="lbl">ｏﾅﾝﾊﾞｰ</td>
      <td><strong>${data.oNumber ?? ''}</strong></td>
    </tr>
    <tr>
      <td class="lbl">FD名 / USB</td>
      <td colspan="3">${data.folderName ?? ''}</td>
    </tr>
  </table>

  ${includeClamp && data.clampNote ? `
  <!-- 備考 -->
  <div style="margin-bottom:4px;">
    <div class="sh" style="margin-bottom:0;">備　考</div>
    <div class="備考box">${(data.clampNote ?? '').replace(/\n/g, '<br/>')}</div>
  </div>` : ''}


  ${includeTools ? `
  <!-- 加工リスト -->
  <div class="sh">加工リスト</div>
  <table class="tools">
    <thead>
      <tr>
        <th class="c" style="width:28px;">No</th>
        <th style="width:90px;">加　工</th>
        <th style="width:70px;">形　状</th>
        <th>ホルダー</th>
        <th class="c" style="width:50px;">ノーズR</th>
        <th>備　考</th>
      </tr>
    </thead>
    <tbody>${toolRows}</tbody>
  </table>` : ''}

  <!-- Ver / 承認者 -->
  <table class="sign">
    <tr>
      <td class="lbl">Ver</td>
      <td style="width:80px;">${data.version ?? ''}</td>
      <td class="lbl">承認者</td>
      <td>${data.approver?.name ?? ''}</td>
      <td class="lbl">承認日</td>
      <td>${fmtDate(data.approvedAt)}</td>
    </tr>
  </table>

  <!-- 段取担当 / 量産担当 -->
  <table class="work">
    <tr>
      <td class="lbl">段取担当</td>
      <td style="min-width:100px;">&nbsp;</td>
      <td class="lbl">量産担当</td>
      <td style="min-width:100px;">&nbsp;</td>
      <td class="lbl">個　数</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td class="lbl">段取時間</td>
      <td><span style="color:#aaa;font-size:8pt;">&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;&nbsp;&nbsp;&nbsp;m</span></td>
      <td class="lbl">量産時間</td>
      <td><span style="color:#aaa;font-size:8pt;">&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;&nbsp;&nbsp;&nbsp;m</span></td>
      <td class="lbl">入　力</td>
      <td>&nbsp;</td>
    </tr>
  </table>

  <!-- 変更届 -->
  <table class="work" style="margin-bottom:4px;">
    <tr>
      <td class="lbl" style="width:60px;">変更届</td>
      <td>
        シート&nbsp;□&nbsp;&nbsp;
        プログラム&nbsp;□&nbsp;&nbsp;
        図&nbsp;□&nbsp;&nbsp;
        写真&nbsp;□
      </td>
    </tr>
    <tr>
      <td class="lbl">内　容</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td class="lbl">掴　代</td>
      <td><span style="margin-right:30px;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; mm</span>FD名&nbsp;&nbsp;&nbsp;${data.folderName ?? ''}</td>
    </tr>
  </table>

  ${drawingsHtml}

  <!-- フッター -->
  <div class="foot">
    <span>NC旋盤プログラム管理システム MachCore</span>
    <span>図面番号: ${data.part?.drawingNo ?? ''} | 部品ID: ${data.part?.partId ?? ''} | NC_id: ${data.id}</span>
  </div>
</body>
</html>`;
}

  // ─────────────────────────────────────────────────────────
  // PG ファイル関連  NC-06 / NC-06b
  // ─────────────────────────────────────────────────────────

  /** ファイルパス解決（company_settings.upload_base_path / folderName / fileName） */
  private async resolvePgFilePath(
    nc: { id: number; fileName: string; folderName: string | null },
  ): Promise<string> {
    const setting = await this.prisma.companySetting.findFirst();
    const base =
      setting?.uploadBasePath ??
      '/home/karkyon/projects/machcore/uploads';
    if (nc.folderName) {
      return path.join(base, '\uff8c\uff9f\uff9b\uff78\uff9e\uff97\uff91', nc.folderName, nc.fileName);
    }
    return path.join(base, 'nc_files', String(nc.id), 'pg', nc.fileName);
  }

  /** NC-06: PGファイル読込（chardet でエンコード自動検出 → UTF-8 変換） */
  async getPgFile(id: number) {
    const nc = await this.prisma.ncProgram.findUniqueOrThrow({ where: { id }, select: { id: true, fileName: true, folderName: true } });
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(
        `PGファイルが見つかりません: ${nc.fileName}  (確認パス: ${filePath})`,
      );
    }

    const buf = fs.readFileSync(filePath);

    // エンコード検出
    const detected = chardet.detect(buf) ?? 'UTF-8';
    const d = detected.toLowerCase();
    let encoding = 'UTF-8';
    if (d.includes('shift') || d.includes('cp932') || d === 'windows-1252') {
      encoding = 'SJIS';
    } else if (d.includes('euc')) {
      encoding = 'EUC-JP';
    }

    const iconvEnc = encoding === 'SJIS' ? 'CP932' : encoding;
    const content  = iconv.decode(buf, iconvEnc);

    // 改行コード検出
    const lineEnding = content.includes('\r\n')
      ? 'CRLF'
      : content.includes('\r')
      ? 'CR'
      : 'LF';

    return { content, encoding, lineEnding, fileName: nc.fileName };
  }

  /** NC-06b: PGファイル保存（iconv-lite で元エンコードに変換して上書き） */
  async savePgFile(
    id: number,
    content: string,
    encoding = 'UTF-8',
    lineEnding = 'LF',
  ) {
    const nc = await this.prisma.ncProgram.findUniqueOrThrow({ where: { id }, select: { id: true, fileName: true, folderName: true } });
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(`PGファイルが見つかりません: ${nc.fileName}`);
    }

    // 改行コード正規化 → 指定形式に変換
    let text = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (lineEnding === 'CRLF') text = text.replace(/\n/g, '\r\n');
    else if (lineEnding === 'CR')  text = text.replace(/\n/g, '\r');

    // 元エンコードに変換して保存
    const iconvEnc = encoding === 'SJIS' ? 'CP932' : encoding;
    const encoded  = iconv.encode(text, iconvEnc);
    fs.writeFileSync(filePath, encoded);

    return { ok: true };
  }

  /** NC-07: PGファイルダウンロード（バイナリストリーム返却） */
  async downloadPgFile(id: number): Promise<{ buffer: Buffer; fileName: string }> {
    const nc = await this.prisma.ncProgram.findUniqueOrThrow({
      where: { id },
      select: { id: true, fileName: true, folderName: true },
    });
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(
        `PGファイルが見つかりません: ${nc.fileName}  (パス: ${filePath})`,
      );
    }

    const buffer = fs.readFileSync(filePath);
    return { buffer, fileName: nc.fileName };
  }


}