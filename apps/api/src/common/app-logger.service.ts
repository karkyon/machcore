import { Injectable, LoggerService } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
export type LogCategory =
  | 'CRON' | 'AUTH' | 'API' | 'PDF' | 'FILE'
  | 'DB' | 'TIMECARD' | 'SYSTEM' | 'MC' | 'NC';

@Injectable()
export class AppLoggerService {
  constructor(private readonly prisma: PrismaService) {}

  /** 非同期・fire-and-forget でDBに記録 */
  log(level: LogLevel, category: LogCategory, message: string, detail?: Record<string, unknown>): void {
    const ts = new Date().toISOString();
    const prefix = `[${level}][${category}] ${ts}`;
    if (level === 'ERROR')  console.error(prefix, message, detail ?? '');
    else if (level === 'WARN') console.warn(prefix, message, detail ?? '');
    else if (level === 'DEBUG') console.debug(prefix, message, detail ?? '');
    else                        console.log(prefix, message, detail ?? '');

    this.prisma.systemLog.create({
      data: { level, category, message, detail: (detail ?? null) as any },
    }).catch(() => { /* ログ失敗は無視 */ });
  }

  info (category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log('INFO',  category, message, detail); }
  warn (category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log('WARN',  category, message, detail); }
  error(category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log('ERROR', category, message, detail); }
  debug(category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log('DEBUG', category, message, detail); }
}
