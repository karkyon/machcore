import { Controller, Get } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Controller('users')
export class UsersController {
  constructor(private readonly prisma: PrismaService) {}

  /** USR-01: ユーザ一覧（AUTHモーダル担当者ボタン用） */
  @Get()
  findAll() {
    return this.prisma.user.findMany({
      where: { isActive: true },
      select: { id: true, name: true, role: true, avatarPath: true, isActive: true },
      orderBy: { name: 'asc' },
    });
  }
}
