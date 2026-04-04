import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface LogCtx {
  actionType:   'VIEW' | 'SEARCH' | 'EDIT_START' | 'EDIT_SAVE' | 'APPROVE'
              | 'SETUP_PRINT' | 'WORK_RECORD' | 'USB_DOWNLOAD'
              | 'FILE_UPLOAD' | 'FILE_DELETE' | 'LOGIN' | 'LOGOUT'
              | 'SESSION_START' | 'SESSION_END';
  userId?:      number;
  ncProgramId?: number;
  sessionId?:   string;
  ipAddress?:   string;
  userAgent?:   string;
  metadata?:    Record<string, unknown>;
}

@Injectable()
export class OperationLogService {
  constructor(private readonly prisma: PrismaService) {}

  /** fire-and-forget: ログ失敗でメイン処理をブロックしない */
  log(ctx: LogCtx): void {
    this.prisma.operationLog.create({
      data: {
        actionType:  ctx.actionType as any,
        userId:      ctx.userId      ?? undefined,
        ncProgramId: ctx.ncProgramId ?? undefined,
        sessionId:   ctx.sessionId   ?? undefined,
        ipAddress:   ctx.ipAddress   ?? undefined,
        userAgent:   ctx.userAgent   ?? undefined,
        metadata:    (ctx.metadata ?? undefined) as any,
      },
    }).catch(() => { /* ログ失敗は無視 */ });
  }
}
