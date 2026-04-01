import {
  Controller, Get, Post, Put, Param, Query,
  ParseIntPipe, Body, UseGuards, Req,
} from "@nestjs/common";
import { AuthGuard } from "@nestjs/passport";
import { NcService } from "./nc.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";

@Controller("nc")
export class NcController {
  constructor(private readonly nc: NcService) {}

  @Get("search")
  search(
    @Query("key") key: string,
    @Query("q") q: string,
    @Query("limit") limit: string,
    @Query("offset") offset: string,
  ) {
    return this.nc.search(key, q, parseInt(limit) || 50, parseInt(offset) || 0);
  }

  @Get("recent")
  recent() { return this.nc.recent(); }

  @Get(":nc_id/change-history")
  changeHistory(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.changeHistory(id);
  }

  @Get(":nc_id/setup-sheet-logs")
  setupSheetLogs(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.setupSheetLogs(id);
  }

  @Get(":nc_id/work-records")
  workRecords(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.workRecords(id);
  }

  @Get(":nc_id")
  findOne(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.findOne(id);
  }

  /** NC-04: 新規登録 */
  @UseGuards(AuthGuard("jwt"))
  @Post()
  create(@Body() dto: CreateNcDto, @Req() req: any) {
    return this.nc.create(dto, req.user.id);
  }

  /** NC-05: 更新 */
  @UseGuards(AuthGuard("jwt"))
  @Put(":nc_id")
  update(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: UpdateNcDto,
    @Req() req: any,
  ) {
    return this.nc.update(id, dto, req.user.id);
  }
}
