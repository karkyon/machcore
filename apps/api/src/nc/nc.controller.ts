import {
  Controller, Get, Post, Put, Delete, Param, Query,
  ParseIntPipe, Body, UseGuards, Req, Res,
} from "@nestjs/common";
import { Roles } from "../common/decorators/roles.decorator";
import { RolesGuard } from "../common/guards/roles.guard";
import { UpdateWorkRecordDto } from "./dto/update-work-record.dto";
import { PrintNcDto } from "./dto/print-nc.dto";
import { SavePgFileDto } from "./dto/save-pg-file.dto";
import type { FastifyReply } from "fastify";
import { AuthGuard } from "@nestjs/passport";
import { NcService } from "./nc.service";
import { OperationLogService } from "../common/operation-log.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";
import { CreateWorkRecordDto } from "./dto/create-work-record.dto";

@Controller("nc")
export class NcController {
  constructor(
    private readonly nc: NcService,
    private readonly opLog: OperationLogService,
  ) {}

  @Get("search")
  search(
    @Query("key") key: string,
    @Query("q") q: string,
    @Query("limit") limit: string,
    @Query("offset") offset: string,
    @Query("client_name") clientName: string,
    @Query("machine_id") machineId: string,
  ) {
    return this.nc.search(key, q, parseInt(limit) || 50, parseInt(offset) || 0, clientName, machineId ? parseInt(machineId) : undefined);
  }

  @Get("client-names")
  async clientNames() {
    const rows = await this.nc.getClientNames();
    return rows;
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

  /** 操作ログ一覧 */
  @Get(":nc_id/operation-logs")
  operationLogs(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.operationLogs(id);
  }

  /** FIL-01: ファイル一覧 */
  @Get(":nc_id/files")
  listFiles(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.listFiles(id);
  }


  /** WR-単件: 作業記録1件取得（編集モード用） */
  @Get(":nc_id/work-records/:record_id")
  findWorkRecord(
    @Param("nc_id",     ParseIntPipe) ncId:     number,
    @Param("record_id", ParseIntPipe) recordId: number,
  ) {
    return this.nc.findWorkRecord(ncId, recordId);
  }

  /** WR-02: 作業記録 新規登録 */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/work-records")
  createWorkRecord(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: CreateWorkRecordDto,
    @Req() req: any,
  ) {
    return this.nc.createWorkRecord(id, dto, req.user.id);
  }

    /** WR-03: 作業記録 更新 */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Put(":nc_id/work-records/:record_id")
  updateWorkRecord(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Param("record_id", ParseIntPipe) recordId: number,
    @Body() dto: UpdateWorkRecordDto,
    @Req() req: any,
  ) {
    return this.nc.updateWorkRecord(ncId, recordId, dto, req.user.id);
  }

  /** WR-04: 作業記録 削除 */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Delete(":nc_id/work-records/:record_id")
  deleteWorkRecord(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Param("record_id", ParseIntPipe) recordId: number,
    @Req() req: any,
  ) {
    return this.nc.deleteWorkRecord(ncId, recordId, req.user.id);
  }

  @Get(":nc_id")
  findOne(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.findOne(id);
  }

  /** NC-04: 新規登録 */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post()
  create(@Body() dto: CreateNcDto, @Req() req: any) {
    return this.nc.create(dto, req.user.id);
  }

  /** NC-05: 更新 */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Put(":nc_id")
  update(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: UpdateNcDto,
    @Req() req: any,
  ) {
    this.opLog.log({
      actionType:  'EDIT_SAVE',
      userId:      req.user?.sub,
      ncProgramId: id,
      sessionId:   req.user?.session_id,
      ipAddress:   req.ip,
      metadata:    { target: 'nc_data' },
    });
    return this.nc.update(id, dto, req.user.id);
  }

  /** NC-07: 段取シートデータ取得（認証不要） */
  @Get(":nc_id/print-data")
  getPrintData(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getPrintData(id);
  }

  /** NC-08b: ダイレクト印刷（JWT必須） */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/direct-print")
  async directPrint(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: PrintNcDto,
    @Req() req: any,
  ) {
    return this.nc.directPrint(id, req.user.id, dto);
  }

  /** NC-08: 段取シートPDF生成（JWT必須） */
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/print")
  async generatePrint(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: PrintNcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.nc.generateSetupSheetPdf(id, req.user.id, dto);
    this.opLog.log({
      actionType:  'SETUP_PRINT',
      userId:      req.user?.sub,
      ncProgramId: id,
      sessionId:   req.user?.session_id,
      ipAddress:   req.ip,
    });
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
  async savePgFile(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: SavePgFileDto,
    @Req() req: any,
  ) {
    const result = await this.nc.savePgFile(id, dto.content, dto.encoding, dto.lineEnding);
    this.opLog.log({
      actionType:  'EDIT_SAVE',
      userId:      req.user?.sub,
      ncProgramId: id,
      sessionId:   req.user?.session_id,
      ipAddress:   req.ip,
      metadata:    { target: 'pg_file', encoding: dto.encoding },
    });
    return result;
  }

  /** NC-07: PGファイルダウンロード（JWT必須） */
  @UseGuards(AuthGuard("jwt"))
  @Get(":nc_id/download")
  async downloadPgFile(
    @Param("nc_id", ParseIntPipe) id: number,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const { buffer, fileName } = await this.nc.downloadPgFile(id);
    this.opLog.log({
      actionType:  'USB_DOWNLOAD',
      userId:      req.user?.sub,
      ncProgramId: id,
      sessionId:   req.user?.session_id,
      ipAddress:   req.ip,
      metadata:    { fileName },
    });
    reply.header("Content-Type",        "application/octet-stream");
    reply.header("Content-Disposition", `attachment; filename="${encodeURIComponent(fileName)}"`);
    reply.header("Content-Length",      String(buffer.length));
    return reply.send(buffer);
  }


}