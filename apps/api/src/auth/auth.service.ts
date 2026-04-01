import {
  Injectable, UnauthorizedException,
  ForbiddenException, UnprocessableEntityException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';
import * as bcrypt from 'bcrypt';

const SESSION_EXPIRES_MS: Record<string, number> = {
  edit:         4 * 60 * 60 * 1000,
  setup_print:  2 * 60 * 60 * 1000,
  work_record:  2 * 60 * 60 * 1000,
  usb_download: 30 * 60 * 1000,
};

const SESSION_EXPIRES_SEC: Record<string, number> = {
  edit:         4 * 3600,
  setup_print:  2 * 3600,
  work_record:  2 * 3600,
  usb_download: 30 * 60,
};

const VALID_SESSION_TYPES = Object.keys(SESSION_EXPIRES_MS);

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwt: JwtService,
  ) {}

  async createWorkSession(body: {
    operator_id: number;
    password: string;
    session_type: string;
    nc_program_id: number;
  }) {
    if (!VALID_SESSION_TYPES.includes(body.session_type)) {
      throw new UnprocessableEntityException('session_type が不正な値です');
    }

    const user = await this.prisma.user.findFirst({
      where: { id: body.operator_id },
    });

    if (!user)          throw new UnauthorizedException('ユーザが存在しません');
    if (!user.isActive) throw new ForbiddenException('アカウントが無効です');

    const valid = await bcrypt.compare(body.password, user.passwordHash);
    if (!valid) throw new UnauthorizedException('パスワードが違います');

    const expiresMs  = SESSION_EXPIRES_MS[body.session_type];
    const expiresSec = SESSION_EXPIRES_SEC[body.session_type];
    const expiresAt  = new Date(Date.now() + expiresMs);

    const session = await this.prisma.workSession.create({
      data: {
        userId:      user.id,
        ncProgramId: body.nc_program_id,
        sessionType: body.session_type.toUpperCase() as any,
        expiresAt,
      },
    });

    const payload: Record<string, string | number> = {
      sub:          user.id,
      role:         user.role as string,
      session_type: body.session_type,
      session_id:   session.id,
    };

    const token = this.jwt.sign(payload, { expiresIn: expiresSec });

    return {
      access_token: token,
      session_type: body.session_type,
      operator:     { id: user.id, name: user.name, role: user.role },
      expires_at:   expiresAt,
    };
  }

  async endWorkSession(sessionId: string) {
    await this.prisma.workSession.updateMany({
      where: { id: sessionId },
      data:  { isActive: false, endedAt: new Date() },
    });
    return { message: 'セッションを終了しました' };
  }
}
