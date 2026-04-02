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
    if (!body.password || body.password.length < 4) {
      throw new BadRequestException('パスワードは4文字以上必要です');
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
}