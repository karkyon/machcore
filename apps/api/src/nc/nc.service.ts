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

    // Google Fontsの読込を少し待つ（タイムアウトしても続行）
    await new Promise(r => setTimeout(r, 2000)); // Noto Sans JP読込待機

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
      data: { ncProgramId, operatorId },
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
  const drawingsSection = (includeDrawings && drawingBase64s.length > 0)
    ? '<section style="margin-bottom:12px;page-break-inside:avoid;"><h3 class=\"sec-title\">段取図</h3><div style="display:flex;flex-direction:column;gap:10px;">'
      + drawingBase64s.map((src: string, i: number) =>
          '<img src="' + src + '" alt="段取図' + (i + 1) + '" style="max-width:100%;height:auto;border:1px solid #e2e8f0;border-radius:4px;" />'
        ).join('')
      + '</div></section>'
    : '';
  const now             = new Date();
  const fmtNow          = `${now.getFullYear()}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  const statusLabel: Record<string, string> = {
    NEW:              '新規',
    PENDING_APPROVAL: '未承認',
    APPROVED:         '承認済',
    CHANGING:         '変更中',
  };
  const statusColor: Record<string, string> = {
    NEW:              '#1d4ed8',
    PENDING_APPROVAL: '#b45309',
    APPROVED:         '#15803d',
    CHANGING:         '#b91c1c',
  };

  const toolRows = (includeTools && data.tools.length > 0) ? `
    <section>
      <h3 class="sec-title">工具リスト</h3>
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:32px">No</th>
            <th style="width:80px">加工種別</th>
            <th>チップ型番（形状）</th>
            <th>ホルダー型番</th>
            <th style="width:52px">ノーズR</th>
            <th style="width:42px">T番号</th>
            <th>備考</th>
          </tr>
        </thead>
        <tbody>
          ${data.tools.map((t: any) => `
            <tr style="page-break-inside: avoid;">
              <td class="center mono">${t.sortOrder}</td>
              <td>${t.processType ?? ''}</td>
              <td class="mono">${t.chipModel ?? ''}</td>
              <td class="mono">${t.holderModel ?? ''}</td>
              <td class="center">${t.noseR ?? ''}</td>
              <td class="center mono">${t.tNumber ?? ''}</td>
              <td class="note">${t.note ?? ''}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </section>` : '';

  const clampSection = (includeClamp && data.clampNote) ? `
    <section>
      <h3 class="sec-title">クランプ・備考</h3>
      <div class="clamp-box">${data.clampNote.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')}</div>
    </section>` : '';

  return `<!DOCTYPE html>
    <html lang="ja">
      <head>
        <meta charset="UTF-8">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
        <style>
          *  { margin:0; padding:0; box-sizing:border-box; }
          body {
            font-family: 'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif;
            font-size: 9.5pt; color: #111; line-height: 1.4;
          }
          /* ── ページヘッダー ── */
          .ph { display:flex; justify-content:space-between; align-items:flex-end;
                border-bottom:2.5px solid #1e3a5f; padding-bottom:5px; margin-bottom:10px; }
          .ph-title { font-size:15pt; font-weight:700; color:#1e3a5f; }
          .ph-meta  { font-size:7.5pt; color:#555; text-align:right; line-height:1.6; }
          /* ── 部品バナー ── */
          .banner { background:#1e3a5f; color:#fff; padding:7px 12px;
                    border-radius:5px; margin-bottom:10px; }
          .banner-name { font-size:13pt; font-weight:700; }
          .banner-ids  { font-size:7.5pt; opacity:.85; margin-top:3px; letter-spacing:.02em; }
          .badge { display:inline-block; padding:1px 6px; border-radius:3px;
                  font-size:7pt; font-weight:700; border:1px solid currentColor; margin-left:6px; }
          /* ── グリッド ── */
          .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px; }
          .box   { border:1px solid #cbd5e1; border-radius:4px; overflow:hidden; }
          .box-h { font-size:7.5pt; font-weight:700; background:#f1f5f9;
                  padding:3px 8px; color:#475569; border-bottom:1px solid #cbd5e1; }
          .row   { display:flex; padding:3px 8px; border-bottom:1px solid #f1f5f9; }
          .row:last-child { border-bottom:none; }
          .lbl   { width:80px; color:#6b7280; font-size:8pt; flex-shrink:0; }
          .val   { font-family:monospace; font-size:9pt; }
          /* ── セクション ── */
          .sec-title { font-size:9pt; font-weight:700; color:#1e3a5f;
                      border-bottom:1.5px solid #1e3a5f; padding-bottom:3px; margin-bottom:6px; }
          section { margin-bottom:12px; }
          /* ── クランプ備考 ── */
          .clamp-box { background:#fefce8; border:1px solid #fde047; border-radius:4px;
                      padding:8px 12px; font-size:9pt; white-space:pre-wrap; line-height:1.7; }
          /* ── 工具テーブル ── */
          .tbl { width:100%; border-collapse:collapse; font-size:8.5pt; }
          .tbl th { background:#f1f5f9; font-weight:700; padding:4px 5px;
                    border:1px solid #cbd5e1; color:#334155; text-align:left; }
          .tbl td { padding:3px 5px; border:1px solid #e2e8f0; vertical-align:top; }
          .tbl tr:nth-child(even) td { background:#f8fafc; }
          .tbl tr { page-break-inside:avoid; }
          .center { text-align:center; }
          .mono   { font-family:monospace; }
          .note   { font-size:8pt; color:#555; }
          @media print {
            body { print-color-adjust:exact; -webkit-print-color-adjust:exact; }
          }
        </style>
      </head>
      <body>
        <div class="ph">
          <span class="ph-title">NC 段取シート</span>
          <div class="ph-meta">
            <div>MachCore — NC旋盤プログラム管理システム</div>
            <div>Ver. <strong>${data.version}</strong> &nbsp;|&nbsp; 出力日時: ${fmtNow}</div>
          </div>
        </div>

        <div class="banner">
          <div class="banner-name">
            ${data.part.name} — 工程 L${data.processL}
            <span class="badge" style="color:${statusColor[data.status] ?? '#555'};border-color:${statusColor[data.status] ?? '#555'};">
              ${statusLabel[data.status] ?? data.status}
            </span>
          </div>
          <div class="banner-ids">
            図面番号: ${data.part.drawingNo}
            &nbsp;|&nbsp; 部品ID: ${data.part.partId}
            &nbsp;|&nbsp; NC_id: ${data.id}
            ${data.part.clientName ? `&nbsp;|&nbsp; 納入先: ${data.part.clientName}` : ''}
            ${data.processingId   ? `&nbsp;|&nbsp; 加工ID: ${data.processingId}` : ''}
          </div>
        </div>

        <div class="grid2">
          <div class="box">
            <div class="box-h">加工情報</div>
            <div class="row"><span class="lbl">工程</span><span class="val">L${data.processL}</span></div>
            <div class="row"><span class="lbl">機械</span><span class="val">${data.machine?.machineName ?? data.machine?.machineCode ?? '—'}</span></div>
            <div class="row"><span class="lbl">加工時間</span><span class="val">${data.machiningTime != null ? `${data.machiningTime} 分` : '—'}</span></div>
            <div class="row"><span class="lbl">O番号</span><span class="val">${data.oNumber ?? '—'}</span></div>
          </div>
          <div class="box">
            <div class="box-h">ファイル情報</div>
            <div class="row"><span class="lbl">フォルダ名</span><span class="val">${data.folderName}</span></div>
            <div class="row"><span class="lbl">ファイル名</span><span class="val">${data.fileName}</span></div>
            <div class="row"><span class="lbl">登録者</span><span class="val">${data.registrar?.name ?? '—'}</span></div>
            <div class="row"><span class="lbl">承認者</span><span class="val">${data.approver?.name ?? '未承認'}</span></div>
          </div>
        </div>

        ${clampSection}
        ${drawingsSection}
        ${toolRows}
      </body>
    </html>`;
  }

  // ─────────────────────────────────────────────────────────
  // PG ファイル関連  NC-06 / NC-06b
  // ─────────────────────────────────────────────────────────

  /** ファイルパス解決（company_settings.upload_base_path / folderName / fileName） */
  private async resolvePgFilePath(
    nc: { id: number; fileName: string },
  ): Promise<string> {
    const setting = await this.prisma.companySetting.findFirst();
    const base =
      setting?.uploadBasePath ??
      '/home/karkyon/projects/machcore/uploads';
    return path.join(base, 'nc_files', String(nc.id), 'pg', nc.fileName);
  }

  /** NC-06: PGファイル読込（chardet でエンコード自動検出 → UTF-8 変換） */
  async getPgFile(id: number) {
    const nc = await this.prisma.ncProgram.findUniqueOrThrow({ where: { id }, select: { id: true, fileName: true } });
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
    const nc = await this.prisma.ncProgram.findUniqueOrThrow({ where: { id }, select: { id: true, fileName: true } });
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
      select: { id: true, fileName: true },
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