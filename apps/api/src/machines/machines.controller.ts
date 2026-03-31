import { Controller, Get } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Controller('machines')
export class MachinesController {
  constructor(private readonly prisma: PrismaService) {}

  /** MCH-01: 機械マスタ一覧 */
  @Get()
  findAll() {
    return this.prisma.machine.findMany({
      where: { isActive: true },
      select: { id: true, machineCode: true, machineName: true, sortOrder: true },
      orderBy: { sortOrder: 'asc' },
    });
  }
}
