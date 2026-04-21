#!/usr/bin/env python3
"""patch_mc_print.py
mc.service.ts に generateSetupSheetPdf / directPrint / buildSetupSheetHtml を追加
mc.controller.ts に /print と /direct-print エンドポイントを追加
"""
import sys

# ─────────────────────────────────────────────────────────────
# 1. mc.service.ts — import 追加 + メソッド追加
# ─────────────────────────────────────────────────────────────
SVC = '/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts'

with open(SVC, 'r', encoding='utf-8') as f:
    svc = f.read()

# import 追加（ファイル先頭）
OLD_IMPORT = "import { Injectable, NotFoundException } from '@nestjs/common';"
NEW_IMPORT = """\
import { Injectable, NotFoundException } from '@nestjs/common';
import * as fs from 'fs';
import { execSync } from 'child_process';\
"""
if OLD_IMPORT in svc:
    svc = svc.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print('OK: mc.service.ts import 追加')
else:
    print('ERROR: import パターン不一致'); sys.exit(1)

# mc.service.ts の末尾（最後の `}` の直前）にメソッドを追加
PRINT_METHODS = '''
  // ══════════════════════════════════════════
  // 段取シートPDF生成（Puppeteer）
  // ══════════════════════════════════════════
  async generateSetupSheetPdf(
    mcId: number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
    },
  ): Promise<Buffer> {
    const data = await this.getPrintData(mcId);
    const puppeteer = (await import('puppeteer')).default;
    const browser   = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    });
    try {
      const page = await browser.newPage();

      // 図ファイルBase64変換
      const drawingBase64s: string[] = [];
      if (options.include_drawings === true && (data as any).files?.length > 0) {
        const sharpLib = (await import('sharp')).default;
        for (const f of ((data as any).files as any[]).slice(0, 3)) {
          try {
            const filePath: string = f.filePath ?? '';
            if (!filePath || !fs.existsSync(filePath)) continue;
            const buf  = fs.readFileSync(filePath);
            const mime: string = f.mimeType ?? '';
            if (mime.includes('tiff') || mime.includes('tif')) {
              const imgBuf = await sharpLib(buf).png().toBuffer();
              drawingBase64s.push('data:image/png;base64,' + imgBuf.toString('base64'));
            } else if (!mime.includes('pdf')) {
              drawingBase64s.push('data:' + mime + ';base64,' + buf.toString('base64'));
            }
          } catch { /* skip */ }
        }
      }

      const html = this.buildSetupSheetHtml(data, { ...options, drawingBase64s });
      await page.setContent(html, { waitUntil: 'domcontentloaded', timeout: 15000 });

      const pdfUint8 = await page.pdf({
        format: 'A4',
        printBackground: true,
        margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' },
        displayHeaderFooter: true,
        headerTemplate: '<span></span>',
        footerTemplate: `<div style="font-size:8px;width:100%;text-align:center;color:#888;font-family:sans-serif;">
          <span class="pageNumber"></span> / <span class="totalPages"></span></div>`,
      });

      const pdfBuffer = Buffer.from(pdfUint8);

      await this.prisma.mcSetupSheetLog.create({
        data: { mcProgramId: mcId, operatorId, version: (data as any).version ?? null },
      }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));

      return pdfBuffer;
    } finally {
      await browser.close();
    }
  }

  // ══════════════════════════════════════════
  // ダイレクト印刷
  // ══════════════════════════════════════════
  async directPrint(
    mcId: number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
    },
  ): Promise<{ message: string }> {
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true } });
    const printerName = setting?.printerName;
    if (!printerName) throw new Error('プリンタが設定されていません。管理者設定で設定してください。');

    const pdfBuffer = await this.generateSetupSheetPdf(mcId, operatorId, options);
    const tmpPath = `/tmp/machcore-mc-print-${mcId}-${Date.now()}.pdf`;
    fs.writeFileSync(tmpPath, pdfBuffer);
    try {
      execSync(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs.unlinkSync(tmpPath); } catch { /* ignore */ }
    }
    return { message: `${printerName} に送信しました` };
  }

  // ══════════════════════════════════════════
  // MC段取シートHTMLビルダー
  // ══════════════════════════════════════════
  private buildSetupSheetHtml(data: any, opts: any): string {
    const includeTooling       = opts.include_tooling        !== false;
    const includeClamp         = opts.include_clamp          !== false;
    const includeDrawings      = opts.include_drawings        === true;
    const includeWorkOffsets   = opts.include_work_offsets    === true;
    const includeIndexPrograms = opts.include_index_programs  === true;
    const drawingBase64s: string[] = opts.drawingBase64s ?? [];

    const now    = new Date();
    const fmtNow = `${now.getFullYear()}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

    const statusLabel: Record<string, string> = {
      NEW: '新規', PENDING_APPROVAL: '未承認', APPROVED: '承認済', CHANGING: '変更中',
    };
    const statusColor: Record<string, string> = {
      NEW: '#1d4ed8', PENDING_APPROVAL: '#b45309', APPROVED: '#15803d', CHANGING: '#b91c1c',
    };

    // ツーリングリスト
    const toolingRows = (includeTooling && data.tooling?.length > 0)
      ? data.tooling.map((t: any) => `
        <tr style="page-break-inside:avoid;">
          <td class="c">${t.toolNo ?? ''}</td>
          <td>${t.toolName ?? ''}</td>
          <td class="c">${t.diameter != null ? Number(t.diameter).toFixed(1) : ''}</td>
          <td class="c">${t.lengthOffsetNo ?? ''}</td>
          <td class="c">${t.diaOffsetNo ?? ''}</td>
          <td>${t.toolType ?? ''}</td>
          <td>${t.note ?? ''}</td>
        </tr>`).join('')
      : '<tr><td colspan="7" class="c" style="color:#aaa;font-size:8pt;padding:4px;">データなし</td></tr>';

    // ワークオフセット
    const offsetRows = (includeWorkOffsets && data.workOffsets?.length > 0)
      ? data.workOffsets.map((o: any) => `
        <tr>
          <td class="c mono">${o.gCode ?? ''}</td>
          <td class="c mono">${o.xOffset != null ? Number(o.xOffset).toFixed(3) : ''}</td>
          <td class="c mono">${o.yOffset != null ? Number(o.yOffset).toFixed(3) : ''}</td>
          <td class="c mono">${o.zOffset != null ? Number(o.zOffset).toFixed(3) : ''}</td>
          <td class="c mono">${o.aOffset != null ? Number(o.aOffset).toFixed(3) : ''}</td>
          <td>${o.note ?? ''}</td>
        </tr>`).join('')
      : '<tr><td colspan="6" class="c" style="color:#aaa;font-size:8pt;padding:4px;">データなし</td></tr>';

    // インデックスプログラム
    const indexRows = (includeIndexPrograms && data.indexPrograms?.length > 0)
      ? data.indexPrograms.map((p: any) => `
        <tr>
          <td class="c">${p.sortOrder ?? ''}</td>
          <td class="mono">${p.axis0 ?? ''}</td>
          <td class="mono">${p.axis1 ?? ''}</td>
          <td class="mono">${p.axis2 ?? ''}</td>
          <td>${p.note ?? ''}</td>
        </tr>`).join('')
      : '<tr><td colspan="5" class="c" style="color:#aaa;font-size:8pt;padding:4px;">データなし</td></tr>';

    // 共通加工グループ
    const commonGroupHtml = (data.commonGroup?.length > 1)
      ? `<div style="margin-top:6px;padding:4px 8px;background:#fef3c7;border:1px solid #fbbf24;border-radius:4px;font-size:8pt;">
          <strong>共通加工</strong>（加工ID: ${data.machiningId}）：
          ${data.commonGroup.map((g: any) => `MCID ${g.id} / ${g.part?.drawingNo ?? ''} ${g.part?.name ?? ''}`).join('　')}
         </div>` : '';

    const cycleDisp = (() => {
      const s = data.cycleTimeSec;
      if (s == null) return '';
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      return `${h}H ${String(m).padStart(2,'0')}M ${String(sec).padStart(2,'0')}S`;
    })();

    const drawingsHtml = (includeDrawings && drawingBase64s.length > 0)
      ? `<div style="margin-top:8px;page-break-inside:avoid;">
           <div class="sh">段取図</div>
           <div style="display:flex;flex-wrap:wrap;gap:8px;">
             ${drawingBase64s.map((src: string, i: number) =>
               `<img src="${src}" alt="段取図${i+1}" style="max-width:49%;height:auto;border:1px solid #ccc;" />`
             ).join('')}
           </div>
         </div>` : '';

    return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
  *{margin:0;padding:0;box-sizing:border-box;}
  body{font-family:'Noto Sans JP',sans-serif;font-size:9pt;color:#1e293b;}
  h1{font-size:13pt;font-weight:700;color:#0f766e;border-bottom:2px solid #0f766e;padding-bottom:4px;margin-bottom:6px;}
  .meta{display:flex;gap:16px;font-size:8pt;color:#64748b;margin-bottom:8px;}
  table{width:100%;border-collapse:collapse;margin-bottom:8px;}
  th{background:#f0fdfa;color:#0f766e;font-size:8pt;font-weight:700;padding:3px 6px;border:1px solid #99f6e4;text-align:left;}
  td{padding:3px 6px;border:1px solid #e2e8f0;vertical-align:top;}
  .sh{font-weight:700;font-size:9pt;color:#0f766e;border-left:3px solid #0f766e;padding-left:6px;margin:8px 0 4px;}
  .c{text-align:center;}
  .mono{font-family:monospace;}
  .badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:8pt;font-weight:700;}
  .info-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px;}
  .info-cell{display:flex;gap:4px;font-size:9pt;}
  .info-key{color:#64748b;min-width:80px;flex-shrink:0;}
  .info-val{font-weight:700;}
</style>
</head>
<body>
<h1>マシニング 段取シート</h1>
<div class="meta">
  <span>MCID: <strong>${data.id}</strong></span>
  <span>加工ID: <strong>${data.machiningId}</strong></span>
  <span>Ver: <strong>${data.version}</strong></span>
  <span>発行: ${fmtNow}</span>
  <span class="badge" style="background:${statusColor[data.status] ?? '#888'};color:#fff;">
    ${statusLabel[data.status] ?? data.status}
  </span>
</div>

${commonGroupHtml}

<div class="info-grid" style="margin-top:6px;">
  <div class="info-cell"><span class="info-key">部品名称</span><span class="info-val">${data.part?.name ?? ''}</span></div>
  <div class="info-cell"><span class="info-key">図面番号</span><span class="info-val">${data.part?.drawingNo ?? ''}</span></div>
  <div class="info-cell"><span class="info-key">機械</span><span class="info-val">${data.machine?.machineName ?? data.machine?.machineCode ?? ''}</span></div>
  <div class="info-cell"><span class="info-key">主Oナンバ</span><span class="info-val mono">${data.oNumber ?? ''}</span></div>
  <div class="info-cell"><span class="info-key">CT/1P</span><span class="info-val">${cycleDisp}</span></div>
  <div class="info-cell"><span class="info-key">加工個数/1S</span><span class="info-val">${data.machiningQty ?? 1}</span></div>
  ${includeClamp ? `<div class="info-cell" style="grid-column:1/-1;"><span class="info-key">クランプ</span><span class="info-val">${data.clampNote ?? ''}</span></div>` : ''}
</div>

${includeTooling ? `<div class="sh">ツーリングリスト</div>
<table>
  <thead><tr><th class="c">T番号</th><th>工具名</th><th class="c">径(mm)</th><th class="c">H補正</th><th class="c">D補正</th><th>種別</th><th>備考</th></tr></thead>
  <tbody>${toolingRows}</tbody>
</table>` : ''}

${includeWorkOffsets ? `<div class="sh" style="page-break-before:auto;">ワークオフセット</div>
<table>
  <thead><tr><th class="c">G座標</th><th class="c">X</th><th class="c">Y</th><th class="c">Z</th><th class="c">A</th><th>備考</th></tr></thead>
  <tbody>${offsetRows}</tbody>
</table>` : ''}

${includeIndexPrograms ? `<div class="sh" style="page-break-before:auto;">インデックスプログラム</div>
<table>
  <thead><tr><th class="c">No.</th><th>第0軸</th><th>第1軸</th><th>第2軸</th><th>備考</th></tr></thead>
  <tbody>${indexRows}</tbody>
</table>` : ''}

${drawingsHtml}

<div style="margin-top:10px;font-size:8pt;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:4px;">
  登録: ${data.registrar?.name ?? ''} / 承認: ${data.approver?.name ?? '未承認'}
  ${data.note ? `<br>備考: ${data.note}` : ''}
</div>
</body>
</html>`;
  }
'''

# サービス末尾の `}` の直前に挿入
if svc.rstrip().endswith('}'):
    svc = svc.rstrip()[:-1] + PRINT_METHODS + '\n}\n'
    print('OK: mc.service.ts に PDF/Print メソッド追加')
else:
    print('ERROR: mc.service.ts 末尾パターン不一致'); sys.exit(1)

with open(SVC, 'w', encoding='utf-8') as f:
    f.write(svc)

# ─────────────────────────────────────────────────────────────
# 2. mc.controller.ts — /print と /direct-print エンドポイント追加
# ─────────────────────────────────────────────────────────────
CTL = '/home/karkyon/projects/machcore/apps/api/src/mc/mc.controller.ts'

with open(CTL, 'r', encoding='utf-8') as f:
    ctl = f.read()

# import に Res / FastifyReply を追加
OLD_CTL_IMPORT = "import {\n  Controller, Get, Post, Put, Param, Query,\n  ParseIntPipe, Body, UseGuards, Req,\n} from '@nestjs/common';"
NEW_CTL_IMPORT = "import {\n  Controller, Get, Post, Put, Param, Query,\n  ParseIntPipe, Body, UseGuards, Req, Res,\n} from '@nestjs/common';\nimport type { FastifyReply } from 'fastify';"

if OLD_CTL_IMPORT in ctl:
    ctl = ctl.replace(OLD_CTL_IMPORT, NEW_CTL_IMPORT, 1)
    print('OK: mc.controller.ts import 更新')
else:
    print('ERROR: mc.controller.ts import パターン不一致'); sys.exit(1)

# import に PrintMcDto を追加（既にある場合はスキップ）
if 'PrintMcDto' not in ctl:
    ctl = ctl.replace(
        "import { SaveIndexProgramsDto } from './dto/save-index-programs.dto';",
        "import { SaveIndexProgramsDto } from './dto/save-index-programs.dto';\nimport { PrintMcDto } from './dto/print-mc.dto';"
    )
    print('OK: PrintMcDto import 追加')

# ファイル一覧エンドポイントの後にprint/direct-printを追加
OLD_LAST = '''  // ── 機械タイムカード ────────────────────────'''
NEW_LAST = '''  // ── 段取シートPDF / 印刷 ───────────────────────
  @Get(':mc_id/print-data')
  getPrintData(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getPrintData(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/print')
  async generatePrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.mc.generateSetupSheetPdf(id, req.user.id, dto);
    this.opLog.log({
      actionType:   'MC_SETUP_PRINT',
      userId:       req.user?.sub,
      mcProgramId:  id,
      sessionId:    req.user?.session_id,
      ipAddress:    req.ip,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="mc-setup-sheet-${id}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/direct-print')
  async directPrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
  ) {
    return this.mc.directPrint(id, req.user.id, dto);
  }

  // ── 機械タイムカード ────────────────────────'''

if OLD_LAST in ctl:
    ctl = ctl.replace(OLD_LAST, NEW_LAST, 1)
    print('OK: mc.controller.ts に print / direct-print 追加')
else:
    print('ERROR: mc.controller.ts 挿入位置パターン不一致'); sys.exit(1)

# getPrintData の重複を削除（既にcontrollerにある場合）
import re
ctl = re.sub(
    r"  // ── 段取シートデータ ─+\n  @Get\(':mc_id/print-data'\)\n  getPrintData.*?}\n\n",
    '',
    ctl,
    flags=re.DOTALL
)

with open(CTL, 'w', encoding='utf-8') as f:
    f.write(ctl)

print('\n✅ MC Print API パッチ完了')
