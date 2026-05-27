import { execSync } from "child_process";
import type { FastifyReply } from 'fastify';
import {
  Controller, Get, Post, Put, Delete, Body, UseGuards,
  Param, ParseIntPipe, Query, BadRequestException, Res, Req,
} from '@nestjs/common';
import * as bcrypt from 'bcrypt';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from '../common/decorators/roles.decorator';
import { RolesGuard } from '../common/guards/roles.guard';
import { PrismaService } from '../prisma/prisma.service';
import { FilesService } from '../files/files.service';
import { McService } from '../mc/mc.service';

const ALLOWED_TABLES = [
  'users', 'machines', 'parts', 'nc_programs',
  'work_records', 'change_history', 'operation_logs', 'setup_sheet_logs', 'machine_timecards',
];

@Controller('admin')
export class AdminController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly filesService: FilesService,
    private readonly mcService: McService,
  ) {}

  @Get('company')
  getCompany() {
    return this.prisma.companySetting.findFirst();
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('company')
  updateCompany(@Body() body: { company_name?: string; logo_path?: string }) {
    return this.prisma.companySetting.upsert({
      where:  { id: 1 },
      update: { companyName: body.company_name, logoPath: body.logo_path },
      create: { id: 1, companyName: body.company_name || '会社名未設定' },
    });
  }

  /** ADM-USR-01: ユーザ一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('users')
  getUsers() {
    return this.prisma.user.findMany({
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, createdAt: true,
      },
      orderBy: { id: 'asc' },
    });
  }

  /** ADM-USR-02: ユーザ新規作成 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('users')
  async createUser(@Body() body: {
    employee_code: string;
    name: string;
    name_kana?: string;
    password: string;
    role?: 'VIEWER' | 'OPERATOR' | 'ADMIN';
  }) {
    const hash = await bcrypt.hash(body.password, 10);
    return this.prisma.user.create({
      data: {
        employeeCode: body.employee_code,
        name:         body.name,
        nameKana:     body.name_kana,
        passwordHash: hash,
        role:         body.role ?? 'OPERATOR',
        isActive:     true,
      },
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, createdAt: true,
      },
    });
  }

  /** ADM-USR-03: ユーザ更新（PW変更は /password エンドポイントで） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('users/:id')
  async updateUser(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: {
      name?: string;
      name_kana?: string;
      role?: 'VIEWER' | 'OPERATOR' | 'ADMIN';
      is_active?: boolean;
      system_type?: 'NC' | 'MC' | 'BOTH';
    },
  ) {
    const data: any = {};
    if (body.name        !== undefined) data.name       = body.name;
    if (body.name_kana   !== undefined) data.nameKana   = body.name_kana;
    if (body.role        !== undefined) data.role       = body.role;
    if (body.is_active   !== undefined) data.isActive   = body.is_active;
    if (body.system_type !== undefined) data.systemType = body.system_type;
    return this.prisma.user.update({
      where:  { id },
      data,
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, createdAt: true,
      },
    });
  }

  /** ADM-USR-03b: パスワード変更専用 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('users/:id/password')
  async resetPassword(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { password: string },
  ) {
    if (!body.password || body.password.length < 1) {
      throw new BadRequestException('パスワードを入力してください');
    }
    const hash = await bcrypt.hash(body.password, 10);
    return this.prisma.user.update({
      where:  { id },
      data:   { passwordHash: hash },
      select: { id: true, name: true },
    });
  }

  /** ADM-USR-04: ユーザ論理削除（isActive=false） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('users/:id')
  deactivateUser(@Param('id', ParseIntPipe) id: number) {
    return this.prisma.user.update({
      where:  { id },
      data:   { isActive: false },
      select: { id: true, isActive: true },
    });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('raw/:table')
  async getRaw(
    @Param('table') table: string,
    @Query('page') page = '1',
    @Query('limit') limit = '50',
  ) {
    if (!ALLOWED_TABLES.includes(table)) {
      throw new BadRequestException(`テーブル '${table}' は許可されていません`);
    }
    const p = Math.max(1, parseInt(page));
    const l = Math.min(200, Math.max(1, parseInt(limit)));
    const offset = (p - 1) * l;
    const [rows, countRows] = await Promise.all([
      this.prisma.$queryRawUnsafe<any[]>(
        `SELECT * FROM "${table}" ORDER BY id DESC LIMIT $1 OFFSET $2`, l, offset,
      ),
      this.prisma.$queryRawUnsafe<{ count: bigint }[]>(
        `SELECT COUNT(*) AS count FROM "${table}"`,
      ),
    ]);
    const total = Number(countRows[0]?.count ?? 0);
    return { table, page: p, limit: l, total, data: rows };
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('storage')
  updateStorage(@Body() body: { upload_base_path: string }) {
    return this.filesService.updateStoragePath(body.upload_base_path);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('storage')
  getStorage() {
    return this.prisma.companySetting.findFirst({
      select: { uploadBasePath: true, companyName: true },
    });
  }


  /** ADM-LOG: 操作ログ一覧（全NC・全ユーザ・フィルタ付き） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('logs')
  async getLogs(
    @Query('action_type') actionType?: string,
    @Query('user_id')     userId?: string,
    @Query('nc_id')       ncId?: string,
    @Query('date_from')   dateFrom?: string,
    @Query('date_to')     dateTo?: string,
    @Query('page')        page = '1',
    @Query('limit')       limit = '50',
  ) {
    const where: any = {};
    if (actionType) where.actionType = actionType;
    if (userId)     where.userId     = parseInt(userId);
    if (ncId)       where.ncProgramId = parseInt(ncId);
    if (dateFrom || dateTo) {
      where.createdAt = {};
      if (dateFrom) where.createdAt.gte = new Date(dateFrom);
      if (dateTo)   where.createdAt.lte = new Date(dateTo + 'T23:59:59Z');
    }
    const skip  = (parseInt(page) - 1) * parseInt(limit);
    const take  = parseInt(limit);
    const [rows, total] = await Promise.all([
      this.prisma.operationLog.findMany({
        where, skip, take,
        orderBy: { createdAt: 'desc' },
        include: {
          user:      { select: { name: true, employeeCode: true } },
          ncProgram: { select: { id: true, folderName: true, fileName: true,
                                 part: { select: { drawingNo: true, name: true } } } },
        },
      }),
      this.prisma.operationLog.count({ where }),
    ]);
    return {
      total, page: parseInt(page), limit: parseInt(limit),
      data: rows.map(r => ({
        id:          r.id,
        action_type: r.actionType,
        user_name:   r.user?.name ?? null,
        employee_code: r.user?.employeeCode ?? null,
        nc_id:       r.ncProgramId,
        drawing_no:  (r.ncProgram as any)?.part?.drawingNo ?? null,
        part_name:   (r.ncProgram as any)?.part?.name ?? null,
        file_name:   r.ncProgram?.fileName ?? null,
        metadata:    r.metadata,
        created_at:  r.createdAt,
      })),
    };
  }

  // ══ 機械マスタ管理 ══

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('machines')
  getMachines() {
    return this.prisma.machine.findMany({
      orderBy: { sortOrder: 'asc' },
    });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('machines')
  async createMachine(@Body() body: {
    machine_code: string;
    machine_name: string;
    machine_type?: string;
    maker?: string;
    sort_order?: number;
  }) {
    return this.prisma.machine.create({
      data: {
        machineCode: body.machine_code,
        machineName: body.machine_name,
        machineType: body.machine_type,
        maker:       body.maker,
        sortOrder:   body.sort_order ?? 0,
        isActive:    true,
      },
    });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('machines/:id')
  async updateMachine(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: {
      machine_code?: string;
      machine_name?: string;
      machine_type?: string;
      maker?: string;
      sort_order?: number;
      is_active?: boolean;
    },
  ) {
    return this.prisma.machine.update({
      where: { id },
      data: {
        ...(body.machine_code != null && { machineCode: body.machine_code }),
        ...(body.machine_name != null && { machineName: body.machine_name }),
        ...(body.machine_type != null && { machineType: body.machine_type }),
        ...(body.maker        != null && { maker: body.maker }),
        ...(body.sort_order   != null && { sortOrder: body.sort_order }),
        ...(body.is_active    != null && { isActive: body.is_active }),
      },
    });
  }
  /** プリンタ一覧取得（CUPS lpstat） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('printers')
  getPrinters() {
    try {
      const out = execSync('/usr/bin/lpstat -p 2>/dev/null', { encoding: 'utf-8', timeout: 5000 });
      const printers = out.split('\n')
        .filter(l => l.startsWith('printer '))
        .map(l => { const m = l.match(/^printer (\S+)/); return m ? m[1] : null; })
        .filter(Boolean);
      return { printers };
    } catch {
      return { printers: [] };
    }
  }

  /** プリンタ設定更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('printer')
  async updatePrinter(@Body() body: { printer_name: string }) {
    await this.prisma.companySetting.upsert({
      where: { id: 1 },
      update: { printerName: body.printer_name },
      create: { id: 1, companyName: '', printerName: body.printer_name },
    });
    return { message: 'プリンタ設定を更新しました' };
  }

  /** プリンタ設定取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('printer')
  async getPrinter() {
    const s = await this.prisma.companySetting.findFirst({ select: { printerName: true } });
    return { printer_name: s?.printerName ?? null };
  }


  /** MC/NC個別ストレージ・プリンタ設定取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('settings/mc-nc')
  async getMcNcSettings() {
    const s = await this.prisma.companySetting.findFirst({
      select: { mcStoragePath: true, ncStoragePath: true, mcPrinter: true, ncPrinter: true, uploadBasePath: true, printerName: true },
    });
    return {
      mc_storage_path: s?.mcStoragePath ?? s?.uploadBasePath ?? "/mnt/ncfiles/mc",
      nc_storage_path: s?.ncStoragePath ?? s?.uploadBasePath ?? "/mnt/ncfiles",
      mc_printer:      s?.mcPrinter ?? s?.printerName ?? "",
      nc_printer:      s?.ncPrinter ?? s?.printerName ?? "",
    };
  }

  /** MC/NC個別ストレージ・プリンタ設定更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('settings/mc-nc')
  async updateMcNcSettings(@Body() body: {
    mc_storage_path?: string;
    nc_storage_path?: string;
    mc_printer?: string;
    nc_printer?: string;
  }) {
    return this.prisma.companySetting.upsert({
      where: { id: 1 },
      update: {
        ...(body.mc_storage_path !== undefined && { mcStoragePath: body.mc_storage_path }),
        ...(body.nc_storage_path !== undefined && { ncStoragePath: body.nc_storage_path }),
        ...(body.mc_printer      !== undefined && { mcPrinter:     body.mc_printer }),
        ...(body.nc_printer      !== undefined && { ncPrinter:     body.nc_printer }),
      },
      create: { id: 1, companyName: '会社名未設定',
        mcStoragePath: body.mc_storage_path, ncStoragePath: body.nc_storage_path,
        mcPrinter: body.mc_printer, ncPrinter: body.nc_printer,
      },
    });
  }

  // ══ PDFフィールド定義管理 ══

  /** PDFテンプレート一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-templates')
  async getPdfTemplates() {
    return this.prisma.pdfTemplate.findMany({
      orderBy: { id: 'asc' },
    });
  }

  /** PDFフィールド定義一覧（テンプレート名でフィルタ） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-fields')
  async getPdfFields(@Query('template') templateName?: string) {
    const where: any = {};
    if (templateName) {
      const tpl = await this.prisma.pdfTemplate.findFirst({ where: { name: templateName } });
      if (tpl) where.templateId = tpl.id;
    }
    return this.prisma.pdfFieldDefinition.findMany({
      where,
      include: { template: { select: { name: true, filePath: true } } },
      orderBy: [{ templateId: 'asc' }, { sortOrder: 'asc' }],
    });
  }

  /** PDFフィールド定義更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('pdf-fields/:id')
  async updatePdfField(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: {
      x?: number;
      y?: number;
      font_size?: number;
      is_active?: boolean;
      label?: string;
      note?: string;
    },
  ) {
    return this.prisma.pdfFieldDefinition.update({
      where: { id },
      data: {
        ...(body.x         != null && { x:        body.x }),
        ...(body.y         != null && { y:        body.y }),
        ...(body.font_size != null && { fontSize: body.font_size }),
        ...(body.is_active != null && { isActive: body.is_active }),
        ...(body.label     != null && { label:    body.label }),
        ...(body.note      != null && { note:     body.note }),
      },
    });
  }

  /** PDFプレビュー生成（新規段取シート）
   *  ?template=mc_setup_p1 → template_p1.pdf をそのまま返す（デザイナー用）
   *  ?template=mc_setup_p2 → template_p2.pdf をそのまま返す
   *  template未指定         → generateSetupSheetPdf() でフル生成
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-preview')
  async getPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = require('fs') as typeof import('fs');

    const NEW_TPL_FILE_MAP: Record<string, string> = {
      'mc_setup_p1': 'template_p1.pdf',
      'mc_setup_p2': 'template_p2.pdf',
    };

    if (templateName && NEW_TPL_FILE_MAP[templateName]) {
      const filePath = `${ASSETS}/${NEW_TPL_FILE_MAP[templateName]}`;
      if (fs2.existsSync(filePath)) {
        const buf = fs2.readFileSync(filePath);
        reply.header('Content-Type',        'application/pdf');
        reply.header('Content-Disposition', `inline; filename="${NEW_TPL_FILE_MAP[templateName]}"`);
        reply.header('Content-Length',      String(buf.length));
        return reply.send(buf);
      }
    }

    // template未指定 or ファイルなし → フル生成（従来動作）
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
      if (!first) throw new BadRequestException('MCプログラムが存在しません');
      mcId = first.id;
    }
    const pdf = await this.mcService.generateSetupSheetPdf(mcId, 1, {
      include_tooling: false,
      include_clamp:   false,
      is_preview:      true,
    } as any);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }


  /** リピート段取シートPDFプレビュー生成
   *  ?template=repeat_header  → repeat_header.pdf をそのまま返す（デザイナー用）
   *  ?template=repeat_tooling → repeat_tooling.pdf
   *  ?template=repeat_wo      → repeat_wo.pdf
   *  ?template=repeat_ip      → repeat_ip.pdf
   *  ?template=repeat_p2      → template_repeat_p2.pdf
   *  template未指定           → generateRepeatSetupSheetPdf() でフル生成
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-repeat-preview')
  async getRepeatPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = require('fs') as typeof import('fs');

    // テンプレート名 → ファイル名マップ
    const TPL_FILE_MAP: Record<string, string> = {
      'repeat_header':  'repeat_header.pdf',
      'repeat_tooling': 'repeat_tooling.pdf',
      'repeat_wo':      'repeat_wo.pdf',
      'repeat_ip':      'repeat_ip.pdf',
      'repeat_p2':      'template_repeat_p2.pdf',
    };

    // テンプレート名が指定されていてファイルが存在する → そのまま返す
    if (templateName && TPL_FILE_MAP[templateName]) {
      const filePath = `${ASSETS}/${TPL_FILE_MAP[templateName]}`;
      if (fs2.existsSync(filePath)) {
        const buf = fs2.readFileSync(filePath);
        reply.header('Content-Type',        'application/pdf');
        reply.header('Content-Disposition', `inline; filename="${TPL_FILE_MAP[templateName]}"`);
        reply.header('Content-Length',      String(buf.length));
        return reply.send(buf);
      }
      // ファイルが存在しない場合は空PDFを返す
      const { PDFDocument } = await import('pdf-lib');
      const emptyDoc = await PDFDocument.create();
      emptyDoc.addPage([595, 842]);
      const emptyBytes = await emptyDoc.save();
      reply.header('Content-Type',        'application/pdf');
      reply.header('Content-Disposition', `inline; filename="empty.pdf"`);
      reply.header('Content-Length',      String(emptyBytes.length));
      return reply.send(Buffer.from(emptyBytes));
    }

    // template未指定 → フル段取シート生成（従来動作）
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({
        where: { status: { not: 'NEW' } },
        orderBy: { id: 'desc' },
      });
      if (!first) {
        const any = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
        if (!any) throw new BadRequestException('MCプログラムが存在しません');
        mcId = any.id;
      } else {
        mcId = first.id;
      }
    }
    const pdf = await this.mcService.generateRepeatSetupSheetPdf(mcId, 1, {
      include_tooling:        true,
      include_clamp:          true,
      include_work_offsets:   true,
      include_index_programs: true,
      is_preview:             true,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="repeat-preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }



  /** リピート段取シート フルプレビュー（全ブロック結合・値差し込み済み）
   *  ?mc_id= 必須。デザインモードではなくレポートプレビュー用。
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-full-preview')
  async getFullPreview(
    @Query('mc_id') mcIdStr?: string,
    @Res() reply?: any,
  ) {
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({
        where: { status: { not: 'NEW' } },
        orderBy: { id: 'desc' },
      });
      if (!first) {
        const any = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
        if (!any) throw new BadRequestException('MCプログラムが存在しません');
        mcId = any.id;
      } else {
        mcId = first.id;
      }
    }
    const pdf = await this.mcService.generateRepeatSetupSheetPdf(mcId, 1, {
      include_tooling:        true,
      include_clamp:          true,
      include_work_offsets:   true,
      include_index_programs: true,
      is_preview:             true,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="full-preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  /** PDFテンプレートファイルアップロード（差し替え） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('pdf-templates/:id/upload')
  async uploadPdfTemplate(
    @Param('id', ParseIntPipe) id: number,
    @Req() req: any,
    @Res() reply?: any,
  ) {
    const tpl = await this.prisma.pdfTemplate.findUnique({ where: { id } });
    if (!tpl) throw new BadRequestException(`テンプレート id=${id} が見つかりません`);

    const data = await req.file();
    if (!data) throw new BadRequestException('ファイルがありません');
    if (data.mimetype !== 'application/pdf') throw new BadRequestException('PDFファイルのみアップロード可能です');

    const chunks: Buffer[] = [];
    for await (const chunk of data.file) chunks.push(chunk as Buffer);
    const buf = Buffer.concat(chunks);

    // assets/ 配下に保存（file_path は相対パス "assets/xxx.pdf"）
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = await import('fs');
    // file_path から実際の保存先ファイル名を決定
    const savedName = tpl.filePath.replace(/^assets\//, '');
    const savePath  = `${ASSETS}/${savedName}`;
    fs2.writeFileSync(savePath, buf);

    return { message: `テンプレートを更新しました: ${savedName}`, file_path: tpl.filePath, size: buf.length };
  }

  // ══ 機械タイムカード (admin用) ══

  /** admin用: 全MC機械の当日タイムカード初期生成 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('timecards/init')
  async adminInitTimecards(@Body() body: { work_date: string }) {
    const machines = await this.prisma.machine.findMany({
      where: { isActive: true, systemType: 'MC' },
      orderBy: { sortOrder: 'asc' },
    });
    // ADMINユーザID=1をoperatorIdとして使用
    const operatorId = 1;
    const workDate = body.work_date;
    let created = 0;
    for (const m of machines) {
      const exists = await this.prisma.machineTimecard.findFirst({
        where: { machineId: m.id, workDate: new Date(workDate) },
      });
      if (!exists) {
        await this.prisma.machineTimecard.create({
          data: {
            machineId:  m.id,
            operatorId,
            workDate:   new Date(workDate),
            startTime:  new Date(`${workDate}T08:00:00`),
            endTime:    new Date(`${workDate}T17:00:00`),
          },
        });
        created++;
      }
    }
    return { created, total: machines.length, message: `${created}件生成` };
  }

  /** admin用: タイムカード更新（admin JWT認証） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('timecards/:id')
  async adminUpdateTimecard(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { start_time: string; end_time: string; note?: string },
  ) {
    const tc = await this.prisma.machineTimecard.findUnique({ where: { id } });
    if (!tc) throw new BadRequestException('タイムカードが見つかりません');
    const d = tc.workDate;
    const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    return this.prisma.machineTimecard.update({
      where: { id },
      data: {
        startTime: new Date(`${dateStr}T${body.start_time}`),
        endTime:   new Date(`${dateStr}T${body.end_time}`),
        note:      body.note ?? null,
      },
    });
  }

  /** admin用: 日付別タイムカード一覧取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('timecards')
  async adminGetTimecards(@Query('work_date') workDate: string) {
    const cards = await this.prisma.machineTimecard.findMany({
      where: { workDate: new Date(workDate) },
      include: { machine: { select: { machineCode: true, machineName: true, systemType: true } } },
      orderBy: [{ machine: { sortOrder: 'asc' } }, { id: 'asc' }],
    });
    return cards;
  }

}
