import { execSync } from "child_process";
import * as fs from 'fs';
import * as nodepath from 'path';
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


  // ── クランプマスタ管理 ──────────────────────────────

  @Get('clamp-master/:category')
  async getClampMasterCategory(@Param('category') cat: string) {
    const map: Record<string, any> = {
      vise:  () => this.prisma.clampVise.findMany({ orderBy: { sortOrder: 'asc' } }),
      chuck: () => this.prisma.clampChuck.findMany({ orderBy: { sortOrder: 'asc' } }),
      tsume: () => this.prisma.clampTsume.findMany({ orderBy: { sortOrder: 'asc' } }),
      shiki: () => this.prisma.clampShiki.findMany({ orderBy: { sortOrder: 'asc' } }),
      index: () => this.prisma.clampIndex.findMany({ orderBy: { sortOrder: 'asc' } }),
    };
    if (!map[cat]) throw new Error(`Invalid category: ${cat}`);
    return map[cat]();
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('clamp-master/:category')
  async createClampMasterItem(@Param('category') cat: string, @Body() body: any) {
    const models: Record<string, any> = {
      vise:  this.prisma.clampVise,
      chuck: this.prisma.clampChuck,
      tsume: this.prisma.clampTsume,
      shiki: this.prisma.clampShiki,
      index: this.prisma.clampIndex,
    };
    const m = models[cat];
    if (!m) throw new Error(`Invalid category: ${cat}`);
    return m.create({ data: body });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('clamp-master/:category/:id')
  async updateClampMasterItem(
    @Param('category') cat: string,
    @Param('id', ParseIntPipe) id: number,
    @Body() body: any,
  ) {
    const models: Record<string, any> = {
      vise:  this.prisma.clampVise,
      chuck: this.prisma.clampChuck,
      tsume: this.prisma.clampTsume,
      shiki: this.prisma.clampShiki,
      index: this.prisma.clampIndex,
    };
    const m = models[cat];
    if (!m) throw new Error(`Invalid category: ${cat}`);
    return m.update({ where: { id }, data: body });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('clamp-master/:category/:id')
  async deleteClampMasterItem(
    @Param('category') cat: string,
    @Param('id', ParseIntPipe) id: number,
  ) {
    const models: Record<string, any> = {
      vise:  this.prisma.clampVise,
      chuck: this.prisma.clampChuck,
      tsume: this.prisma.clampTsume,
      shiki: this.prisma.clampShiki,
      index: this.prisma.clampIndex,
    };
    const m = models[cat];
    if (!m) throw new Error(`Invalid category: ${cat}`);
    return m.delete({ where: { id } });
  }

  // ── SPシート管理 ─────────────────────────────

  /** SP-01: SPシート一覧 */
  @Get('special-sheets')
  getSpecialSheets() {
    return this.prisma.specialSheet.findMany({
      orderBy: [{ clientId: 'asc' }, { id: 'asc' }],
    });
  }

  /** SP-02: SPシート作成 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('special-sheets')
  createSpecialSheet(@Body() body: {
    client_id?: number;
    keyword?:   string;
    sheet_name: string;
    content:    string;
    version?:   number;
  }) {
    return this.prisma.specialSheet.create({
      data: {
        clientId:  body.client_id ?? null,
        keyword:   body.keyword   ?? null,
        sheetName: body.sheet_name,
        content:   body.content,
        version:   body.version ?? 0,
      },
    });
  }

  /** SP-03: SPシート更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('special-sheets/:id')
  updateSpecialSheet(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: {
      client_id?: number;
      keyword?:   string;
      sheet_name?: string;
      content?:    string;
      version?:    number;
    },
  ) {
    return this.prisma.specialSheet.update({
      where: { id },
      data: {
        clientId:  body.client_id  !== undefined ? body.client_id  : undefined,
        keyword:   body.keyword    !== undefined ? body.keyword    : undefined,
        sheetName: body.sheet_name !== undefined ? body.sheet_name : undefined,
        content:   body.content    !== undefined ? body.content    : undefined,
        version:   body.version    !== undefined ? body.version    : undefined,
      },
    });
  }

  /** SP-04: SPシート削除 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('special-sheets/:id')
  deleteSpecialSheet(@Param('id', ParseIntPipe) id: number) {
    return this.prisma.specialSheet.delete({ where: { id } });
  }

  /** SP-05: SPシート PDF アップロード */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('special-sheets/:id/upload-pdf')
  async uploadSpecialSheetPdf(
    @Param('id', ParseIntPipe) id: number,
    @Req() req: any,
  ) {
    const data = await req.file();
    if (!data) throw new BadRequestException('ファイルがありません');
    const buf = await data.toBuffer();
    const basePath = (await this.prisma.companySetting.findFirst())?.uploadBasePath
      ?? '/home/karkyon/projects/machcore/uploads';
    const dir = `${basePath}/special_sheets`;
    const fs = await import('fs');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const ext = data.filename.split('.').pop()?.toLowerCase() ?? 'pdf';
    const storedName = `sp_${id}_v${Date.now()}.${ext}`;
    const filePath = `${dir}/${storedName}`;
    fs.writeFileSync(filePath, buf);
    const relPath = `special_sheets/${storedName}`;
    await this.prisma.specialSheet.update({
      where: { id },
      data: { pdfPath: relPath },
    });
    return { message: 'アップロード完了', pdf_path: relPath };
  }

  /** SP-05c: SPシートPDF 印字版生成（MCID/部品ID/印刷日時をオーバーレイ印字） */
  @Post('special-sheets/:id/print-pdf')
  async printSpecialSheetPdf(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { mc_id?: number; part_id?: string; drawing_no?: string; part_name?: string },
    @Res() reply: any,
  ) {
    const sheet = await this.prisma.specialSheet.findUnique({ where: { id } });
    if (!sheet?.pdfPath) {
      reply.code(404).send({ message: 'PDFが登録されていません' });
      return;
    }
    const basePath = (await this.prisma.companySetting.findFirst())?.uploadBasePath
      ?? '/home/karkyon/projects/machcore/uploads';
    const filePath = `${basePath}/${sheet.pdfPath}`;
    const fsLib = await import('fs');
    if (!fsLib.existsSync(filePath)) {
      reply.code(404).send({ message: 'PDFファイルが見つかりません' });
      return;
    }

    try {
      const { PDFDocument, rgb, StandardFonts } = await import('pdf-lib');
      const existingPdfBytes = fsLib.readFileSync(filePath);
      const pdfDoc = await PDFDocument.load(existingPdfBytes);
      const font = await pdfDoc.embedFont(StandardFonts.HelveticaBold);
      const pages = pdfDoc.getPages();
      const now = new Date();
      const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
      const printedAt = `${jst.getUTCFullYear()}/${String(jst.getUTCMonth()+1).padStart(2,'0')}/${String(jst.getUTCDate()).padStart(2,'0')} ${String(jst.getUTCHours()).padStart(2,'0')}:${String(jst.getUTCMinutes()).padStart(2,'0')}`;

      const headerLine1 = [
        body.mc_id   ? `MCID: ${body.mc_id}`     : null,
        body.part_id ? `部品ID: ${body.part_id}` : null,
        body.drawing_no ? body.drawing_no         : null,
        body.part_name  ? body.part_name          : null,
      ].filter(Boolean).join('  ');
      const footerText = `印刷日時: ${printedAt}`;
      const fontSize = 9;
      const color = rgb(0.2, 0.2, 0.2);

      for (const page of pages) {
        const { height } = page.getSize();
        // ヘッダー左上 (x=20, y=height-16)
        if (headerLine1) {
          page.drawText(headerLine1, { x: 20, y: height - 16, size: fontSize, font, color });
        }
        // フッター左下 (x=20, y=8)
        page.drawText(footerText, { x: 20, y: 8, size: fontSize, font, color });
      }

      const pdfBytes = await pdfDoc.save();
      const fileName = `sp_${id}_printed.pdf`;
      reply.header('Content-Type', 'application/pdf');
      reply.header('Content-Disposition', `inline; filename="${fileName}"`);
      reply.header('Content-Length', String(pdfBytes.length));
      return reply.send(Buffer.from(pdfBytes));
    } catch (err: any) {
      reply.code(500).send({ message: 'PDF印字処理失敗: ' + err.message });
    }
  }

  /** SP-05b: SPシート PDF 配信 */
  @Get('special-sheets/:id/pdf')
  async serveSpecialSheetPdf(
    @Param('id', ParseIntPipe) id: number,
    @Res() reply: any,
  ) {
    const sheet = await this.prisma.specialSheet.findUnique({ where: { id } });
    if (!sheet?.pdfPath) {
      reply.code(404).send({ message: 'PDFが登録されていません' });
      return;
    }
    const basePath = (await this.prisma.companySetting.findFirst())?.uploadBasePath
      ?? '/home/karkyon/projects/machcore/uploads';
    const filePath = `${basePath}/${sheet.pdfPath}`;
    const fs = await import('fs');
    if (!fs.existsSync(filePath)) {
      reply.code(404).send({ message: 'PDFファイルが見つかりません' });
      return;
    }
    const fileName = sheet.pdfPath.split('/').pop() ?? 'sp.pdf';
    reply.header('Content-Type', 'application/pdf');
    reply.header('Content-Disposition', `inline; filename="${fileName}"`);
    return reply.send(fs.createReadStream(filePath));
  }

  /** SP-06: 納入先一覧（SPシート作成フォーム用） */
  @Get('clients')
  async getClients() {
    const rows = await this.prisma.part.findMany({
      where: { clientId: { not: null }, clientName: { not: null } },
      select: { clientId: true, clientName: true },
      distinct: ['clientId'],
      orderBy: { clientId: 'asc' },
    });
    return rows.map(r => ({ id: r.clientId, name: r.clientName }));
  }

  /** ADM-USR-01: ユーザ一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('users')
  getUsers() {
    return this.prisma.user.findMany({
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, canApprove: true, createdAt: true,
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
    can_approve?: boolean;
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
        canApprove:   body.can_approve ?? false,
      },
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, canApprove: true, createdAt: true,
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
      can_approve?: boolean;
    },
  ) {
    const data: any = {};
    if (body.name        !== undefined) data.name       = body.name;
    if (body.name_kana   !== undefined) data.nameKana   = body.name_kana;
    if (body.role        !== undefined) data.role       = body.role;
    if (body.is_active   !== undefined) data.isActive   = body.is_active;
    if (body.system_type !== undefined) data.systemType = body.system_type;
    if (body.can_approve !== undefined) data.canApprove = body.can_approve;
    return this.prisma.user.update({
      where:  { id },
      data,
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, systemType: true, canApprove: true, createdAt: true,
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
          ncProgram: { select: { id: true, machining: { select: { folderName: true, fileName: true } },
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
        file_name:   (r.ncProgram as any)?.machining?.fileName ?? null,
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
    pg_is_folder?: boolean;
  }) {
    return this.prisma.machine.create({
      data: {
        machineCode: body.machine_code,
        machineName: body.machine_name,
        machineType: body.machine_type,
        maker:       body.maker,
        sortOrder:   body.sort_order ?? 0,
        isActive:    true,
        pgIsFolder:  body.pg_is_folder ?? false,
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
      pg_is_folder?: boolean;
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
        ...(body.pg_is_folder != null && { pgIsFolder: body.pg_is_folder }),
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
      mc_storage_path:   s?.mcStoragePath  ?? s?.uploadBasePath ?? "/mnt/mc_files/MC/files",
      nc_storage_path:   s?.ncStoragePath  ?? "/mnt/nc_files",
      upload_base_path:  s?.uploadBasePath ?? "/mnt/mc_files",
      mc_printer:        s?.mcPrinter ?? s?.printerName ?? "",
      nc_printer:        s?.ncPrinter ?? s?.printerName ?? "",
    };
  }

  /** MC/NC個別ストレージ・プリンタ設定更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('settings/mc-nc')
  async updateMcNcSettings(@Body() body: {
    mc_storage_path?: string;
    nc_storage_path?: string;
    upload_base_path?: string;
    mc_printer?: string;
    nc_printer?: string;
  }) {
    return this.prisma.companySetting.upsert({
      where: { id: 1 },
      update: {
        ...(body.mc_storage_path !== undefined && { mcStoragePath:   body.mc_storage_path }),
        ...(body.nc_storage_path !== undefined && { ncStoragePath:   body.nc_storage_path }),
        ...(body.upload_base_path !== undefined && { uploadBasePath: body.upload_base_path }),
        ...(body.mc_printer      !== undefined && { mcPrinter:       body.mc_printer }),
        ...(body.nc_printer      !== undefined && { ncPrinter:       body.nc_printer }),
      },
      create: { id: 1, companyName: '会社名未設定',
        mcStoragePath: body.mc_storage_path, ncStoragePath: body.nc_storage_path,
        uploadBasePath: body.upload_base_path,
        mcPrinter: body.mc_printer, ncPrinter: body.nc_printer,
      },
    });
  }

  // ══ PDFフィールド定義管理 ══


  /** MC ID解決: 直接IDでヒットしない場合は legacyMcid で検索 */
  private async resolveMcId(mcIdStr?: string): Promise<number> {
    const raw = mcIdStr ? parseInt(mcIdStr) : 0;
    if (raw > 0) {
      // まず直接IDで検索
      const direct = await this.prisma.mcProgram.findUnique({ where: { id: raw } });
      if (direct) return direct.id;
      // legacyMcid でフォールバック
      const byLegacy = await this.prisma.mcProgram.findFirst({
        where: { legacyMcid: raw },
        orderBy: { id: 'desc' },
      });
      if (byLegacy) return byLegacy.id;
    }
    // mc_id 未指定 or 未ヒット → 最新の非NEWレコードを使用
    const first = await this.prisma.mcProgram.findFirst({
      where: { status: { not: 'NEW' } },
      orderBy: { id: 'desc' },
    });
    if (first) return first.id;
    const any = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
    if (!any) throw new BadRequestException('MCプログラムが存在しません');
    return any.id;
  }

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
    const mcId = await this.resolveMcId(mcIdStr);
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


  /** 新規段取シート フルプレビュー（値差し込み済み）
   *  ?mc_id=xxx  → 内部ID または legacyMcid で検索
   *  ?part_id=xx → 部品ID（part.partId 文字列）で検索
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-new-full-preview')
  async getNewFullPreview(
    @Query('mc_id')  mcIdStr?:  string,
    @Query('part_id') partIdStr?: string,
    @Res() reply?: any,
  ) {
    let mcId: number;
    if (partIdStr) {
      // 部品IDで最新のMCプログラムを検索
      const byPart = await this.prisma.mcProgram.findFirst({
        where: { part: { partId: partIdStr } },
        orderBy: { id: 'desc' },
      });
      if (!byPart) throw new BadRequestException(`部品ID "${partIdStr}" のMCプログラムが存在しません`);
      mcId = byPart.id;
    } else {
      mcId = await this.resolveMcId(mcIdStr);
    }
    const pdf = await this.mcService.generateSetupSheetPdf(mcId, 1, {
      include_tooling: true,
      include_clamp:   true,
      is_preview:      true,
    } as any);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="new-full-preview-${mcId}.pdf"`);
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
        startTime: new Date(`${dateStr}T${body.start_time}Z`),
        endTime:   new Date(`${dateStr}T${body.end_time}Z`),
        note:      body.note ?? null,
      },
    });
  }

  /** admin用: 日付別タイムカード一覧取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('timecards')
  async adminGetTimecards(@Query('work_date') workDate: string) {
    if (!workDate || !/^\d{4}-\d{2}-\d{2}$/.test(workDate)) return [];
    const cards = await this.prisma.machineTimecard.findMany({
      where: { workDate: new Date(workDate + 'T00:00:00.000Z') },
      include: { machine: { select: { machineCode: true, machineName: true, systemType: true, sortOrder: true, isActive: true } } },
      orderBy: [{ machine: { sortOrder: 'asc' } }, { id: 'asc' }],
    });
    const fmtT = (d: Date) => {
      const h = String(d.getUTCHours()).padStart(2, '0');
      const m = String(d.getUTCMinutes()).padStart(2, '0');
      return `${h}:${m}`;
    };
    return cards.map(c => ({
      id:          c.id,
      machine_id:  c.machineId,
      work_date:   workDate,
      start_time:  fmtT(c.startTime),
      end_time:    fmtT(c.endTime),
      note:        c.note ?? '',
      machine:     c.machine,
    }));
  }


  /** SYS-LOG: システムログ一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('system-logs')
  async getSystemLogs(
    @Query('level')     level?: string,
    @Query('category')  category?: string,
    @Query('date_from') dateFrom?: string,
    @Query('date_to')   dateTo?: string,
    @Query('page')      page = '1',
    @Query('limit')     limit = '100',
  ) {
    const where: any = {};
    if (level)    where.level    = level;
    if (category) where.category = category;
    if (dateFrom || dateTo) {
      where.createdAt = {};
      if (dateFrom) where.createdAt.gte = new Date(dateFrom);
      if (dateTo)   where.createdAt.lte = new Date(dateTo + 'T23:59:59Z');
    }
    const skip = (parseInt(page) - 1) * parseInt(limit);
    const take = parseInt(limit);
    const [rows, total] = await Promise.all([
      this.prisma.systemLog.findMany({ where, skip, take, orderBy: { createdAt: 'desc' } }),
      this.prisma.systemLog.count({ where }),
    ]);
    const data = rows.map(r => ({
      id:         r.id,
      level:      r.level,
      category:   r.category,
      message:    r.message,
      detail:     r.detail,
      created_at: r.createdAt.toISOString(),
    }));
    return { total, page: parseInt(page), limit: parseInt(limit), data };
  }

  /** SYS-LOG: システムログ削除（古いログ） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('system-logs/purge')
  async purgeSystemLogs(@Query('days') days = '30') {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(days));
    const result = await this.prisma.systemLog.deleteMany({ where: { createdAt: { lt: cutoff } } });
    return { deleted: result.count, message: `${parseInt(days)}日以前のログを${result.count}件削除しました` };
  }


  /** SYS-SETTING: システム設定一覧取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('system-settings')
  async getSystemSettings() {
    const rows = await this.prisma.systemSetting.findMany({ orderBy: { key: 'asc' } });
    return { data: rows };
  }

  /** SYS-SETTING: システム設定更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('system-settings')
  async updateSystemSettings(
    @Body() body: { settings: { key: string; value: string }[] },
    @Req() req: any,
  ) {
    for (const s of body.settings) {
      await this.prisma.systemSetting.upsert({
        where:  { key: s.key },
        update: { value: s.value },
        create: { key: s.key, value: s.value },
      });
    }
    // Cron 関連の設定が含まれていればリロード
    const cronKeys = ['cron_timecard_enabled', 'cron_timecard_hour', 'cron_timecard_minute'];
    if (body.settings.some(s => cronKeys.includes(s.key))) {
      await this.mcService.reloadCronTimecards();
    }
    return { message: '設定を保存しました' };
  }

  /** PM2: プロセス一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pm2/status')
  getPm2Status() {
    try {
      const out = execSync('pm2 jlist', { encoding: 'utf8', timeout: 5000 });
      const list = JSON.parse(out);
      return { data: list.map((p: any) => ({
        name:   p.name,
        pid:    p.pid,
        status: p.pm2_env?.status,
        uptime: p.pm2_env?.pm_uptime,
        cpu:    p.monit?.cpu,
        memory: p.monit?.memory,
        restarts: p.pm2_env?.restart_time,
      })) };
    } catch (e: any) {
      return { data: [], error: e.message };
    }
  }

  /** PM2: プロセス再起動 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('pm2/restart')
  async restartPm2(@Body() body: { name?: string }) {
    try {
      const target = body.name ?? 'all';
      if (target === 'all') {
        // 自プロセス(machcore-api)を含む全体restart → 自身を除いて個別restart後、自身は遅延restart
        const listOut = execSync('pm2 jlist', { encoding: 'utf8', timeout: 5000 });
        const list: any[] = JSON.parse(listOut);
        const others = list.map((p: any) => p.name).filter((n: string) => n !== 'machcore-api');
        for (const name of others) {
          try { execSync(`pm2 restart ${name}`, { encoding: 'utf8', timeout: 15000 }); } catch {}
        }
        // machcore-api自身は応答返却後に遅延restart
        setTimeout(() => {
          try { execSync('pm2 restart machcore-api', { encoding: 'utf8', timeout: 15000 }); } catch {}
        }, 1500);
        return { message: '全プロセス再起動完了（machcore-apiは1.5秒後に再起動）' };
      } else if (target === 'machcore-api') {
        // 自身のrestartは応答返却後に遅延実行
        setTimeout(() => {
          try { execSync('pm2 restart machcore-api', { encoding: 'utf8', timeout: 15000 }); } catch {}
        }, 1000);
        return { message: 'machcore-api を再起動します（1秒後）' };
      } else {
        execSync(`pm2 restart ${target}`, { encoding: 'utf8', timeout: 15000 });
        return { message: `pm2 restart ${target} 完了` };
      }
    } catch (e: any) {
      return { message: `失敗: ${e.message}` };
    }
  }

  /** PM2: pm2 save */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('pm2/save')
  savePm2() {
    try {
      execSync('pm2 save', { encoding: 'utf8', timeout: 10000 });
      return { message: 'pm2 save 完了' };
    } catch (e: any) {
      return { message: `失敗: ${e.message}` };
    }
  }


  /** CAL-01: 営業カレンダー取得（年月指定） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('calendar')
  async getCalendar(
    @Query('year')  year?: string,
    @Query('month') month?: string,
  ) {
    const y = parseInt(year ?? String(new Date().getFullYear()));
    const m = parseInt(month ?? String(new Date().getMonth() + 1));
    const from = new Date(y, m - 1, 1);
    const to   = new Date(y, m, 0);
    const rows = await this.prisma.businessCalendar.findMany({
      where: { workDate: { gte: from, lte: to } },
      orderBy: { workDate: 'asc' },
    });
    return { data: rows.map(r => ({
      id: r.id,
      work_date: r.workDate.toISOString().slice(0, 10),
      is_holiday: r.isHoliday,
      note: r.note,
    })) };
  }

  /** CAL-02: 休日登録 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('calendar')
  async setCalendar(@Body() body: { work_date: string; is_holiday: boolean; note?: string }) {
    const d = new Date(body.work_date);
    const result = await this.prisma.businessCalendar.upsert({
      where: { workDate: d },
      update: { isHoliday: body.is_holiday, note: body.note ?? null },
      create: { workDate: d, isHoliday: body.is_holiday, note: body.note ?? null },
    });
    return { id: result.id, work_date: result.workDate.toISOString().slice(0, 10), is_holiday: result.isHoliday };
  }

  /** CAL-03: 休日削除 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('calendar/:date')
  async deleteCalendar(@Param('date') date: string) {
    const d = new Date(date);
    await this.prisma.businessCalendar.deleteMany({ where: { workDate: d } });
    return { message: '削除しました' };
  }

  /** CAL-04: 年間一括登録（土日を休日として登録） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('calendar/bulk-weekend')
  async bulkWeekend(@Body() body: { year: number }) {
    const y = body.year;
    let count = 0;
    for (let m = 0; m < 12; m++) {
      const days = new Date(y, m + 1, 0).getDate();
      for (let d = 1; d <= days; d++) {
        const dt = new Date(y, m, d);
        const dow = dt.getDay();
        if (dow === 0 || dow === 6) {
          await this.prisma.businessCalendar.upsert({
            where: { workDate: dt },
            update: { isHoliday: true },
            create: { workDate: dt, isHoliday: true, note: dow === 0 ? '日曜' : '土曜' },
          });
          count++;
        }
      }
    }
    return { message: `${y}年の土日 ${count}日を休日登録しました`, count };
  }

  // ══ UploadAgent 配布管理 ══

  /** UA-01: 現在のバージョン情報取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('upload-agent/version')
  async getUploadAgentVersion() {
    const fs = await import('fs');
    const certDir = '/var/www/machcore-cert';
    const latestPath = `${certDir}/UploadAgent_Setup_latest.exe`;
    const exists = fs.existsSync(latestPath);
    const stat = exists ? fs.statSync(latestPath) : null;
    const row = await this.prisma.systemSetting.findUnique({ where: { key: 'upload_agent_version' } });
    return {
      version:      row?.value ?? '1.1.1',
      exists,
      size_bytes:   stat?.size ?? 0,
      updated_at:   stat?.mtime ?? null,
      download_url: '/api/admin/upload-agent/download',
    };
  }

  /** UA-02: exeダウンロード（HTTPS経由プロキシ） */
  @Get('upload-agent/download')
  async downloadUploadAgent(@Res() reply: FastifyReply) {
    const fs = await import('fs');
    const path = '/var/www/machcore-cert/UploadAgent_Setup_latest.exe';
    if (!fs.existsSync(path)) {
      reply.code(404).send({ message: 'ファイルが存在しません' });
      return;
    }
    const stream = fs.createReadStream(path);
    reply.header('Content-Type', 'application/octet-stream');
    reply.header('Content-Disposition', 'attachment; filename="UploadAgent_Setup_latest.exe"');
    return reply.send(stream);
  }

  /** UA-03: 新バージョンのexeをアップロードして配置 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('upload-agent/deploy')
  async deployUploadAgent(@Req() req: any, @Res() reply: FastifyReply) {
    const fs   = await import('fs');
    const path = await import('path');

    let fileBuffer: Buffer | null = null;
    let version = '1.1.1';

    for await (const part of req.parts()) {
      if ('file' in part) {
        const chunks: Buffer[] = [];
        for await (const chunk of (part as any).file) chunks.push(chunk as Buffer);
        fileBuffer = Buffer.concat(chunks);
      } else if ((part as any).fieldname === 'version') {
        version = ((part as any).value ?? '').trim() || '1.1.1';
      }
    }

    if (!fileBuffer) { reply.code(400).send({ message: 'ファイルがありません' }); return; }

    const certDir = '/var/www/machcore-cert';
    if (!fs.existsSync(certDir)) fs.mkdirSync(certDir, { recursive: true });

    const versionedPath = path.join(certDir, `UploadAgent_Setup_v${version}.exe`);
    const latestPath    = path.join(certDir, 'UploadAgent_Setup_latest.exe');
    fs.writeFileSync(versionedPath, fileBuffer);
    fs.copyFileSync(versionedPath, latestPath);

    await this.prisma.systemSetting.upsert({
      where:  { key: 'upload_agent_version' },
      update: { value: version },
      create: { key: 'upload_agent_version', value: version, description: 'UploadAgent配布バージョン' },
    });

    reply.send({ message: `v${version} を配置しました`, version, size_bytes: fileBuffer.length });
  }

  // ── ファイルブラウザ ──────────────────────────────────────────

  /** FB-01: ディレクトリツリー取得（1階層のみ・遅延ロード対応） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('files/tree')
  async getFileTree(@Query('path') queryPath: string) {
    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    // ★v028修正: NC側写真・図の実保存先は NcFilesService.upload() と同じ uploadBasePath を使う。
    //   旧実装は ncStoragePath (NC側プログラムファイル専用の別設定値) を誤って参照していたため、
    //   実際の保存先と表示参照先が一致せず「ファイルがありません」と表示される不具合があった。
    const roots = {
      photos:     nodepath.join(basePath, 'MC', 'files', 'Pictures'),
      drawings:   nodepath.join(basePath, 'MC', 'files', 'Drawings'),
      programs:   nodepath.join(basePath, 'MC', 'files', 'Programs'),
      nc_photos:   nodepath.join(basePath, 'NC', 'files', 'Pictures'),
      nc_drawings: nodepath.join(basePath, 'NC', 'files', 'Drawings'),
      nc_programs:  nodepath.join(basePath, 'NC', 'files', 'Programs'),
    };

    // 1階層のみ読む・hasChildrenチェックなし（I/O最小化）
    const readOneLevel = (dirPath: string): any => {
      if (!fs.existsSync(dirPath)) return { exists: false, path: dirPath, children: [] };
      try { if (!fs.statSync(dirPath).isDirectory()) return { exists: false, path: dirPath, children: [] }; } catch { return { exists: false, path: dirPath, children: [] }; }
      const children: any[] = [];
      try {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        for (const e of entries) {
          const fp = nodepath.join(dirPath, e.name);
          if (e.isDirectory()) {
            // hasChildrenチェックしない（readdirSync追加呼び出し禁止）
            children.push({ name: e.name, path: fp, type: 'dir', hasChildren: true });
          } else {
            let size = 0; let mtime = '';
            try { const st = fs.statSync(fp); size = st.size; mtime = st.mtime.toISOString(); } catch {}
            children.push({ name: e.name, path: fp, type: 'file', size, mtime });
          }
        }
      } catch {}
      children.sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
        return a.name.localeCompare(b.name, 'ja');
      });
      return { exists: true, path: dirPath, children };
    };

    // path指定あり → そのディレクトリの1階層を返す
    if (queryPath) return readOneLevel(queryPath);

    // path指定なし → 全ルートそれぞれの1階層を返す
    return {
      photos:     readOneLevel(roots.photos),
      drawings:   readOneLevel(roots.drawings),
      programs:   readOneLevel(roots.programs),
      nc_photos:   readOneLevel(roots.nc_photos),
      nc_drawings: readOneLevel(roots.nc_drawings),
      nc_programs: readOneLevel(roots.nc_programs),
    };
  }

  /** FB-02: ファイルプレビュー（TIFF→PNG変換・拡張子なしテキスト対応） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('files/preview')
  async previewFileBrowser(@Query('path') filePath: string, @Res() reply: FastifyReply) {
    if (!filePath || !fs.existsSync(filePath)) return reply.code(404).send({ message: 'ファイルが存在しません' });
    try { if (fs.statSync(filePath).isDirectory()) return reply.code(404).send({ message: 'ディレクトリです' }); } catch { return reply.code(404).send({ message: 'アクセス不可' }); }

    const ext = nodepath.extname(filePath).toLowerCase();
    const TEXT_EXTS = new Set(['.txt', '.nc', '.mpf', '.spf', '.cnc', '.min', '.prg', '.min']);
    const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.gif']);
    const TIFF_EXTS  = new Set(['.tif', '.tiff']);

    // 拡張子なし or テキスト系 → UTF-8テキストとして返す
    if (ext === '' || TEXT_EXTS.has(ext)) {
      try {
        const buf = fs.readFileSync(filePath);
        // バイナリ判定: NULLバイトが多ければバイナリ
        const nullCount = [...buf.slice(0, 512)].filter(b => b === 0).length;
        if (nullCount > 10) return reply.code(415).send({ message: 'バイナリファイルはプレビュー不可' });
        const text = buf.toString('utf8').slice(0, 16384);
        reply.header('Content-Type', 'text/plain; charset=utf-8');
        return reply.send(text);
      } catch { return reply.code(500).send({ message: '読み込み失敗' }); }
    }

    // TIFF → sharpでJPEGに変換してブラウザに返す
    if (TIFF_EXTS.has(ext)) {
      try {
        const sharp = (await import('sharp')).default;
        const jpegBuf = await sharp(filePath).jpeg({ quality: 85 }).toBuffer();
        reply.header('Content-Type', 'image/jpeg');
        reply.header('Content-Disposition', 'inline');
        return reply.send(jpegBuf);
      } catch (e: any) { return reply.code(500).send({ message: 'TIFF変換失敗: ' + e.message }); }
    }

    // 通常画像
    if (IMAGE_EXTS.has(ext)) {
      const mimeMap: Record<string, string> = { '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif' };
      reply.header('Content-Type', mimeMap[ext] ?? 'image/jpeg');
      reply.header('Content-Disposition', 'inline');
      return reply.send(fs.createReadStream(filePath));
    }

    // PDF
    if (ext === '.pdf') {
      reply.header('Content-Type', 'application/pdf');
      reply.header('Content-Disposition', 'inline');
      return reply.send(fs.createReadStream(filePath));
    }

    return reply.code(415).send({ message: 'プレビュー非対応の形式: ' + ext });
  }

  /** FB-03: ファイルダウンロード */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('files/download')
  async downloadFileBrowser(@Query('path') filePath: string, @Res() reply: FastifyReply) {
    if (!filePath || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      return reply.code(404).send({ message: 'ファイルが存在しません' });
    }
    const fn = nodepath.basename(filePath);
    reply.header('Content-Type', 'application/octet-stream');
    reply.header('Content-Disposition', "attachment; filename=\"" + encodeURIComponent(fn) + "\"");
    return reply.send(fs.createReadStream(filePath));
  }

  /** FB-04: ファイル/ディレクトリをゴミ箱へ移動(論理削除)。
   *  完全削除はFB-09(trash-purge)、復元はFB-08(trash-restore)で行う。 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('files/delete')
  async deleteFileBrowser(@Query('path') filePath: string) {
    if (!filePath || !fs.existsSync(filePath)) throw new BadRequestException('パスが存在しません');
    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    const trashRoot = nodepath.join(basePath, '_trash');
    if (!fs.existsSync(trashRoot)) fs.mkdirSync(trashRoot, { recursive: true });

    const st = fs.statSync(filePath);
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    const trashPath = nodepath.join(trashRoot, `${id}__${nodepath.basename(filePath)}`);
    fs.renameSync(filePath, trashPath);

    const indexPath = nodepath.join(trashRoot, '.trash-index.json');
    let index: any[] = [];
    try { if (fs.existsSync(indexPath)) index = JSON.parse(fs.readFileSync(indexPath, 'utf8')); } catch { index = []; }
    index.unshift({
      id, originalPath: filePath, trashPath, name: nodepath.basename(filePath),
      type: st.isDirectory() ? 'dir' : 'file', deletedAt: new Date().toISOString(),
    });
    fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf8');

    return { message: 'ゴミ箱へ移動しました', path: filePath, trashId: id };
  }

  /** FB-07: ゴミ箱の一覧取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('files/trash-list')
  async listTrash() {
    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    const indexPath = nodepath.join(basePath, '_trash', '.trash-index.json');
    if (!fs.existsSync(indexPath)) return { items: [] };
    let index: any[] = [];
    try { index = JSON.parse(fs.readFileSync(indexPath, 'utf8')); } catch { index = []; }
    const items = index.map((it) => ({ ...it, existsInTrash: fs.existsSync(it.trashPath) }));
    return { items };
  }

  /** FB-08: ゴミ箱から元の場所へ復元 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('files/trash-restore')
  async restoreTrash(@Body('id') id: string) {
    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    const indexPath = nodepath.join(basePath, '_trash', '.trash-index.json');
    if (!fs.existsSync(indexPath)) throw new BadRequestException('ゴミ箱が空です');
    let index: any[] = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
    const entry = index.find((it) => it.id === id);
    if (!entry) throw new BadRequestException('ゴミ箱にアイテムが見つかりません');
    if (!fs.existsSync(entry.trashPath)) throw new BadRequestException('ゴミ箱内の実体ファイルが見つかりません');
    if (fs.existsSync(entry.originalPath)) throw new BadRequestException('復元先に同名のファイル/フォルダが既に存在します');
    fs.mkdirSync(nodepath.dirname(entry.originalPath), { recursive: true });
    fs.renameSync(entry.trashPath, entry.originalPath);
    index = index.filter((it) => it.id !== id);
    fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf8');
    return { message: '復元しました', path: entry.originalPath };
  }

  /** FB-09: ゴミ箱から完全削除 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('files/trash-purge')
  async purgeTrash(@Query('id') id: string) {
    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    const indexPath = nodepath.join(basePath, '_trash', '.trash-index.json');
    if (!fs.existsSync(indexPath)) throw new BadRequestException('ゴミ箱が空です');
    let index: any[] = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
    const entry = index.find((it) => it.id === id);
    if (!entry) throw new BadRequestException('ゴミ箱にアイテムが見つかりません');
    if (fs.existsSync(entry.trashPath)) {
      const st = fs.statSync(entry.trashPath);
      if (st.isDirectory()) fs.rmSync(entry.trashPath, { recursive: true, force: true });
      else fs.unlinkSync(entry.trashPath);
    }
    index = index.filter((it) => it.id !== id);
    fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf8');
    return { message: '完全に削除しました' };
  }

  /** FB-06: ファイルブラウザの全件フラットインデックス取得。
   *  クライアント側(IndexedDB)でキャッシュして検索に使うための専用API。
   *  検索のたびにサーバーへ再帰スキャンを要求する旧方式(files/search)は、
   *  CIFSマウント上で9,500件超のディレクトリを毎回同期readdirSyncするため
   *  応答に30〜90秒以上かかる重大な性能問題があったため廃止。
   *  このAPIは「タブを開いた時」「更新ボタンを押した時」の1回だけ呼ばれる想定。
   *  非同期I/O(fs.promises)を使い、Node.jsのイベントループを長時間ブロックしないようにする。 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('files/index')
  async indexFileBrowser(@Query('tab') tab: string) {
    const fsp = (await import('fs')).promises;

    const setting = await this.prisma.companySetting.findFirst();
    const basePath = setting?.uploadBasePath ?? '/mnt/mc_files';
    // ★v028修正: files/tree と同じ理由でuploadBasePath基準に統一(詳細はfiles/tree側コメント参照)
    const roots: Record<string, string> = {
      photos:     nodepath.join(basePath, 'MC', 'files', 'Pictures'),
      drawings:   nodepath.join(basePath, 'MC', 'files', 'Drawings'),
      programs:   nodepath.join(basePath, 'MC', 'files', 'Programs'),
      nc_photos:   nodepath.join(basePath, 'NC', 'files', 'Pictures'),
      nc_drawings: nodepath.join(basePath, 'NC', 'files', 'Drawings'),
      nc_programs:  nodepath.join(basePath, 'NC', 'files', 'Programs'),
    };
    const rootPath = roots[tab];
    if (!rootPath) return { items: [], rootPath: '' };
    try { if (!(await fsp.stat(rootPath)).isDirectory()) return { items: [], rootPath }; } catch { return { items: [], rootPath }; }

    const items: Array<{ name: string; path: string; type: 'file' | 'dir'; size?: number; mtime?: string }> = [];

    // ★CIFSマウント上で7,800件超のディレクトリを無制限Promise.allで並列readdirすると、
    //   CIFS/Node.js双方に過大な同時接続負荷がかかりタイムアウトして応答が返らなくなる
    //   不具合があったため、同時実行数を制限したワーカープール方式に変更する。
    const CONCURRENCY = 32;
    const runPool = async <T, R>(inputs: T[], worker: (item: T) => Promise<R>): Promise<R[]> => {
      const results: R[] = new Array(inputs.length);
      let cursor = 0;
      const workers = Array.from({ length: Math.min(CONCURRENCY, inputs.length) }, async () => {
        while (cursor < inputs.length) {
          const idx = cursor++;
          results[idx] = await worker(inputs[idx]);
        }
      });
      await Promise.all(workers);
      return results;
    };

    // 深さ1階層ずつ、その階層の全ディレクトリのreaddirを制限付き並列実行する
    let currentLevel: string[] = [rootPath];
    while (currentLevel.length > 0) {
      const nextLevel: string[] = [];
      const levelResults = await runPool(currentLevel, async (dirPath) => {
        try {
          return { dirPath, entries: await fsp.readdir(dirPath, { withFileTypes: true }) };
        } catch {
          return { dirPath, entries: [] as any[] };
        }
      });

      // このレベルで見つかった全ファイルのstat呼び出しもまとめて制限付き並列実行する
      const fileEntries: Array<{ name: string; path: string }> = [];
      for (const { dirPath, entries } of levelResults) {
        for (const e of entries) {
          const fp = nodepath.join(dirPath, e.name);
          if (e.isDirectory()) {
            items.push({ name: e.name, path: fp, type: 'dir' });
            nextLevel.push(fp);
          } else {
            fileEntries.push({ name: e.name, path: fp });
          }
        }
      }
      const statResults = await runPool(fileEntries, async (fe) => {
        try {
          const st = await fsp.stat(fe.path);
          return { ...fe, size: st.size, mtime: st.mtime.toISOString() };
        } catch {
          return { ...fe, size: undefined as number | undefined, mtime: undefined as string | undefined };
        }
      });
      for (const r of statResults) {
        items.push({ name: r.name, path: r.path, type: 'file', size: r.size, mtime: r.mtime });
      }

      currentLevel = nextLevel;
    }

    return { items, rootPath };
  }

  /** FB-05: ファイルアップロード（登録・差し替え） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('files/upload')
  async uploadFileBrowser(@Req() req: any, @Res() reply: FastifyReply) {
    let destDir = ''; let fileName = ''; let fileBuffer: Buffer | null = null;
    for await (const part of req.parts()) {
      if ('file' in part) {
        const chunks: Buffer[] = [];
        for await (const chunk of (part as any).file) chunks.push(chunk as Buffer);
        fileBuffer = Buffer.concat(chunks);
        if (!fileName) fileName = (part as any).filename ?? 'upload';
      } else {
        const field = (part as any).fieldname; const val = (part as any).value ?? '';
        if (field === 'dest_dir') destDir = val;
        if (field === 'file_name') fileName = val;
      }
    }
    if (!fileBuffer) return reply.code(400).send({ message: 'ファイルがありません' });
    if (!destDir || !fs.existsSync(destDir)) return reply.code(400).send({ message: '保存先ディレクトリが不正です' });
    const destPath = nodepath.join(destDir, fileName);
    fs.writeFileSync(destPath, fileBuffer);
    return reply.send({ message: 'アップロード完了', path: destPath, size: fileBuffer.length });
  }


}