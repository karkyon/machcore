import {
  Controller, Get, Post, Put, Param, Query,
  ParseIntPipe, Body, UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { NcService } from './nc.service';

@Controller('nc')
export class NcController {
  constructor(private readonly nc: NcService) {}

  /** NC-01: 部品検索 */
  @Get('search')
  search(
    @Query('key') key: string,
    @Query('q') q: string,
    @Query('limit') limit: string,
    @Query('offset') offset: string,
  ) {
    return this.nc.search(key, q, parseInt(limit) || 50, parseInt(offset) || 0);
  }

  /** NC-02: 最近のアクセス */
  @Get('recent')
  recent() {
    return this.nc.recent();
  }

  /** NC-03: NC詳細 */
  @Get(':nc_id')
  findOne(@Param('nc_id', ParseIntPipe) id: number) {
    return this.nc.findOne(id);
  }

  /** NC-04: 新規登録 */
  @UseGuards(AuthGuard('jwt'))
  @Post()
  create(@Body() body: any) {
    // TODO: 実装
    return { message: 'TODO: NC-04 新規登録' };
  }

  /** NC-05: 更新 */
  @UseGuards(AuthGuard('jwt'))
  @Put(':nc_id')
  update(@Param('nc_id', ParseIntPipe) id: number, @Body() body: any) {
    // TODO: 実装
    return { message: `TODO: NC-05 更新 id=${id}` };
  }
}
