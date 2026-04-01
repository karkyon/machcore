import { Controller, Post, Delete, Body, UseGuards, Req } from '@nestjs/common';
import { AuthService } from './auth.service';
import { AuthGuard } from '@nestjs/passport';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  /** AUTH-01: Work Session JWT 発行 */
  @Post('work-session')
  createWorkSession(@Body() body: {
    operator_id: number;
    password: string;
    session_type: string;
    nc_program_id: number;
  }) {
    return this.authService.createWorkSession(body);
  }

  /** AUTH-02: Work Session 終了 */
  @UseGuards(AuthGuard('jwt'))
  @Delete('work-session')
  endWorkSession(@Req() req: any) {
    return this.authService.endWorkSession(req.user.session_id);
  }
}
