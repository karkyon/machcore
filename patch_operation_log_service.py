#!/usr/bin/env python3
"""patch_operation_log_service.py — LogCtx に MC 対応を追加"""

TARGET = '/home/karkyon/projects/machcore/apps/api/src/common/operation-log.service.ts'

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

OLD = '''export interface LogCtx {
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
}'''

NEW = '''export interface LogCtx {
  actionType:   'VIEW' | 'SEARCH' | 'EDIT_START' | 'EDIT_SAVE' | 'APPROVE'
              | 'SETUP_PRINT' | 'WORK_RECORD' | 'USB_DOWNLOAD'
              | 'FILE_UPLOAD' | 'FILE_DELETE' | 'LOGIN' | 'LOGOUT'
              | 'SESSION_START' | 'SESSION_END'
              | 'MC_VIEW' | 'MC_EDIT_START' | 'MC_EDIT_SAVE' | 'MC_APPROVE'
              | 'MC_SETUP_PRINT' | 'MC_WORK_RECORD' | 'MC_USB_DOWNLOAD';
  userId?:      number;
  ncProgramId?: number;
  mcProgramId?: number;
  sessionId?:   string;
  ipAddress?:   string;
  userAgent?:   string;
  metadata?:    Record<string, unknown>;
}'''

OLD_LOG = '''  log(ctx: LogCtx): void {
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
  }'''

NEW_LOG = '''  log(ctx: LogCtx): void {
    this.prisma.operationLog.create({
      data: {
        actionType:  ctx.actionType as any,
        userId:      ctx.userId      ?? undefined,
        ncProgramId: ctx.ncProgramId ?? undefined,
        mcProgramId: ctx.mcProgramId ?? undefined,
        sessionId:   ctx.sessionId   ?? undefined,
        ipAddress:   ctx.ipAddress   ?? undefined,
        userAgent:   ctx.userAgent   ?? undefined,
        metadata:    (ctx.metadata ?? undefined) as any,
      },
    }).catch(() => { /* ログ失敗は無視 */ });
  }'''

ok = True
if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print('OK: LogCtx MC ActionType + mcProgramId 追加')
else:
    print('ERROR: LogCtx パターン不一致')
    ok = False

if OLD_LOG in src:
    src = src.replace(OLD_LOG, NEW_LOG, 1)
    print('OK: log() メソッド mcProgramId 追加')
else:
    print('ERROR: log() パターン不一致')
    ok = False

if ok:
    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write(src)
    print('✅ 完了')
else:
    exit(1)
