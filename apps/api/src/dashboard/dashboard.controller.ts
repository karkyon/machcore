import { Body, Controller, Get, Param, ParseIntPipe, Put } from '@nestjs/common';
import { DashboardService } from './dashboard.service';

@Controller('dashboard')
export class DashboardController {
  constructor(private readonly dashboard: DashboardService) {}

  @Get('uncollected-nc')
  uncollectedNc() { return this.dashboard.uncollectedNc(); }

  @Get('uncollected-mc')
  uncollectedMc() { return this.dashboard.uncollectedMc(); }

  @Get('summary')
  summary() { return this.dashboard.summary(); }

  /** MC段取シートを行方不明として処理 */
  @Put('mc-setup-sheet-logs/:id/mark-lost')
  markMcLost(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { reason: string; detail?: string; userId?: number },
  ) {
    return this.dashboard.markMcSetupSheetLost(id, body.reason, body.detail ?? null, body.userId ?? null);
  }

  /** NC段取シートを行方不明として処理 */
  @Put('nc-setup-sheet-logs/:id/mark-lost')
  markNcLost(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { reason: string; detail?: string; userId?: number },
  ) {
    return this.dashboard.markNcSetupSheetLost(id, body.reason, body.detail ?? null, body.userId ?? null);
  }
}
