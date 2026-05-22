import { Injectable, NestMiddleware, Logger } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';

@Injectable()
export class LoggerMiddleware implements NestMiddleware {
  private readonly logger = new Logger('HTTP');

  use(req: Request, res: Response, next: NextFunction) {
    const { method, originalUrl } = req;
    const start = Date.now();
    const body = req.body;

    res.on('finish', () => {
      const { statusCode } = res;
      const ms = Date.now() - start;
      const bodyStr = body && Object.keys(body).length > 0
        ? JSON.stringify(body).slice(0, 500)
        : '';
      const level = statusCode >= 400 ? 'error' : 'log';
      this.logger[level](
        `${method} ${originalUrl} ${statusCode} ${ms}ms ${bodyStr}`
      );
    });
    next();
  }
}
