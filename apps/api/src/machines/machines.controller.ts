import { Controller, Get, Query } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Controller('machines')
export class MachinesController {
  constructor(private readonly prisma: PrismaService) {}

  /** MCH-01: 機械マスタ一覧
   *  system クエリ(NC|MC)を指定すると、そのシステム専用機械 + 共通(BOTH)機械のみに絞る。
   *  省略時は全件返す(admin系画面など既存呼び出しへの後方互換のため)。 */
  @Get()
  findAll(@Query('system') system?: 'NC' | 'MC') {
    const where: any = { isActive: true };
    if (system === 'NC' || system === 'MC') {
      where.systemType = { in: [system, 'BOTH'] };
    }
    return this.prisma.machine.findMany({
      where,
      select: { id: true, machineCode: true, machineName: true, sortOrder: true, isActive: true, pgIsFolder: true },
      orderBy: { sortOrder: 'asc' },
    });
  }
}
