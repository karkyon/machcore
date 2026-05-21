import { Controller, Get } from '@nestjs/common';
import { DashboardService } from './dashboard.service';

@Controller('dashboard')
export class DashboardController {
  constructor(private readonly dashboard: DashboardService) {}

  /** DASH-01: 未回収段取シート一覧 */
  @Get('uncollected-sheets')
  uncollectedSheets() {
    return this.dashboard.uncollectedSheets();
  }

  /** DASH-02: サマリーカード */
  @Get('summary')
  summary() {
    return this.dashboard.summary();
  }
}
