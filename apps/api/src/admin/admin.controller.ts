import { execSync } from "child_process";
import {
  Controller, Get, Post, Put, Delete, Body, UseGuards,
  Param, ParseIntPipe, Query, BadRequestException,
} from '@nestjs/common';
import * as bcrypt from 'bcrypt';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from '../common/decorators/roles.decorator';
import { RolesGuard } from '../common/guards/roles.guard';
import { PrismaService } from '../prisma/prisma.service';
import { FilesService } from '../files/files.service';

const ALLOWED_TABLES = [
  'users', 'machines', 'parts', 'nc_programs',
  'work_records', 'change_history', 'operation_logs', 'setup_sheet_logs',
];

@Controller('admin')
export class AdminController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly filesService: FilesService,
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
        role: true, isActive: true, createdAt: true,
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
        role: true, isActive: true, createdAt: true,
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
    },
  ) {
    const data: any = {};
    if (body.name      !== undefined) data.name     = body.name;
    if (body.name_kana !== undefined) data.nameKana  = body.name_kana;
    if (body.role      !== undefined) data.role      = body.role;
    if (body.is_active !== undefined) data.isActive  = body.is_active;
    return this.prisma.user.update({
      where:  { id },
      data,
      select: {
        id: true, employeeCode: true, name: true, nameKana: true,
        role: true, isActive: true, createdAt: true,
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
      const out = execSync('lpstat -p 2>/dev/null', { encoding: 'utf-8', timeout: 5000 });
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
}
