import {
  Controller, Get, Post, Put, Param, Query,
  ParseIntPipe, Body, UseGuards, Req, Res,
} from "@nestjs/common";
import { PrintNcDto } from "./dto/print-nc.dto";
import { SavePgFileDto } from "./dto/save-pg-file.dto";
import type { FastifyReply } from "fastify";
import { AuthGuard } from "@nestjs/passport";
import { NcService } from "./nc.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";
import { CreateWorkRecordDto } from "./dto/create-work-record.dto";

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

  /** FIL-01: ファイル一覧 */
  @Get(":nc_id/files")
  listFiles(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.listFiles(id);
  }

  /** WR-02: 作業記録 新規登録 */
  @UseGuards(AuthGuard("jwt"))
  @Post(":nc_id/work-records")
  createWorkRecord(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: CreateWorkRecordDto,
    @Req() req: any,
  ) {
    return this.nc.createWorkRecord(id, dto, req.user.id);
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

  /** NC-07: 段取シートデータ取得（認証不要） */
  @Get(":nc_id/print-data")
  getPrintData(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getPrintData(id);
  }

  /** NC-08: 段取シートPDF生成（JWT必須） */
  @UseGuards(AuthGuard("jwt"))
  @Post(":nc_id/print")
  async generatePrint(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: PrintNcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.nc.generateSetupSheetPdf(id, req.user.id, dto);
    reply.header("Content-Type",        "application/pdf");
    reply.header("Content-Disposition", `inline; filename="setup-sheet-${id}.pdf"`);
    reply.header("Content-Length",      String(pdf.length));
    return reply.send(pdf);
  }

  /** NC-06: PGファイル読込（JWT必須） */
  @UseGuards(AuthGuard("jwt"))
  @Get(":nc_id/pg-file")
  getPgFile(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getPgFile(id);
  }

  /** NC-06b: PGファイル保存（JWT必須） */
  @UseGuards(AuthGuard("jwt"))
  @Put(":nc_id/pg-file")
  savePgFile(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: SavePgFileDto,
  ) {
    return this.nc.savePgFile(id, dto.content, dto.encoding, dto.lineEnding);
  }

}