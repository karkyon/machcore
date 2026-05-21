import { Controller, Get } from '@nestjs/common';
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
}
