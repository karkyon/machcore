import { Controller, Get, Query } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Controller('users')
export class UsersController {
  constructor(private readonly prisma: PrismaService) {}

  /** USR-01: ユーザ一覧（AUTHモーダル担当者ボタン用）
   *  system クエリ(NC|MC)を指定すると、そのシステム専用ユーザ + 共通(BOTH)ユーザのみに絞る。
   *  approver=true を指定すると、承認資格(canApprove=true)を持つユーザのみに絞る
   *  ([v094] 承認モーダルの担当者選択で使用。承認資格の無いユーザは選択肢に出さない)。
   *  省略時は全件返す(admin系画面など既存呼び出しへの後方互換のため)。 */
  @Get()
  findAll(
    @Query('system') system?: 'NC' | 'MC',
    @Query('approver') approver?: string,
    @Query('includeInactive') includeInactive?: string,
  ) {
    // [バグ修正] 作業記録画面で過去選択された無効ユーザの名前を正しく表示するため、
    // includeInactive=true の場合のみ無効ユーザも含めて返す(既定は従来通り有効のみ)。
    const where: any = includeInactive === 'true' ? {} : { isActive: true };
    if (system === 'NC' || system === 'MC') {
      where.systemType = { in: [system, 'BOTH'] };
    }
    if (approver === 'true') {
      where.canApprove = true;
    }
    return this.prisma.user.findMany({
      where,
      select: { id: true, name: true, role: true, avatarPath: true, isActive: true, canApprove: true },
      orderBy: { name: 'asc' },
    });
  }
}
