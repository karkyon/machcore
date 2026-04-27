import {
  Controller, Get, Post, Put, Delete, Param, Query,
  ParseIntPipe, Body, UseGuards, Req, Res,
} from '@nestjs/common';
import type { FastifyReply } from 'fastify';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from '../common/decorators/roles.decorator';
import { RolesGuard } from '../common/guards/roles.guard';
import { OperationLogService } from '../common/operation-log.service';
import { McService } from './mc.service';
import { McFilesService } from './mc-files.service';
import { CreateMcDto } from './dto/create-mc.dto';
import { UpdateMcDto } from './dto/update-mc.dto';
import { CreateMcWorkRecordDto } from './dto/create-mc-work-record.dto';
import { SaveToolingDto } from './dto/save-tooling.dto';
import { SaveWorkOffsetsDto } from './dto/save-work-offsets.dto';
import { SaveIndexProgramsDto } from './dto/save-index-programs.dto';
import { PrintMcDto } from './dto/print-mc.dto';

@Controller('mc')
export class McController {
  constructor(
    private readonly mc:      McService,
    private readonly mcFiles: McFilesService,
    private readonly opLog:   OperationLogService,
  ) {}

  // ── 検索・一覧 ──────────────────────────────
  @Get('search')
  search(
    @Query('key')          key:         string,
    @Query('q')            q:           string,
    @Query('limit')        limit:       string,
    @Query('offset')       offset:      string,
    @Query('client_name')  clientName:  string,
    @Query('machine_id')   machineId:   string,
    @Query('machine_code') machineCode: string,
  ) {
    return this.mc.search(key, q, parseInt(limit) || 50, parseInt(offset) || 0,
      clientName, machineId ? parseInt(machineId) : undefined, machineCode || undefined);
  }

  @Get('recent')
  recent() { return this.mc.recent(); }

  // ── 共通加工グループ ────────────────────────
  @Get('common-group/:machining_id')
  commonGroup(@Param('machining_id', ParseIntPipe) machiningId: number) {
    return this.mc.getCommonGroup(machiningId);
  }

  // ── 新規登録 ────────────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post()
  create(@Body() dto: CreateMcDto, @Req() req: any) {
    return this.mc.create(dto, req.user.id);
  }

  // ── MC詳細 ──────────────────────────────────
  @Get(':mc_id')
  findOne(@Param('mc_id', ParseIntPipe) id: number) {
    this.opLog.log({ actionType: 'MC_VIEW', mcProgramId: id });
    return this.mc.findOne(id);
  }

  // ── 更新 ────────────────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id')
  update(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: UpdateMcDto,
    @Req() req: any,
  ) {
    return this.mc.update(id, dto, req.user.id);
  }

  // ── ツーリング ──────────────────────────────
  @Get(':mc_id/tooling')
  getTooling(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getTooling(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/tooling')
  saveTooling(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: SaveToolingDto,
    @Req() req: any,
  ) {
    return this.mc.saveTooling(id, dto, req.user.id);
  }

  /** ツーリングプログラム解析（プレビュー・保存なし）*/
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/tooling/parse')
  parseTooling(@Body() body: { text: string }) {
    return this.mc.parseToolingProgram(body.text ?? '');
  }

  // ── ワークオフセット ────────────────────────
  @Get(':mc_id/work-offsets')
  getWorkOffsets(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getWorkOffsets(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/work-offsets')
  saveWorkOffsets(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: SaveWorkOffsetsDto,
    @Req() req: any,
  ) {
    return this.mc.saveWorkOffsets(id, dto, req.user.id);
  }

  // ── インデックスプログラム ──────────────────
  @Get(':mc_id/index-programs')
  getIndexPrograms(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getIndexPrograms(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/index-programs')
  saveIndexPrograms(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: SaveIndexProgramsDto,
    @Req() req: any,
  ) {
    return this.mc.saveIndexPrograms(id, dto, req.user.id);
  }

  // ── 作業記録 ────────────────────────────────
  @Get(':mc_id/work-records')
  workRecords(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.workRecords(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/work-records')
  createWorkRecord(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: CreateMcWorkRecordDto,
    @Req() req: any,
  ) {
    return this.mc.createWorkRecord(id, dto, req.user.id);
  }

  // ── 変更履歴 ────────────────────────────────
  @Get(':mc_id/change-history')
  changeHistory(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.changeHistory(id);
  }

  // ── 段取シートログ ──────────────────────────
  @Get(':mc_id/setup-sheet-logs')
  setupSheetLogs(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.setupSheetLogs(id);
  }

  // ── ファイル一覧 ────────────────────────────
  @Get(':mc_id/files')
  listFiles(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.listFiles(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/files/upload')
  async uploadFile(@Param('mc_id', ParseIntPipe) id: number, @Req() req: any) {
    const data = await req.file();
    if (!data) throw new Error('ファイルがありません');
    const buf = await data.toBuffer();
    const pgRole = (data.fields?.pg_role?.value ?? undefined) as 'MAIN' | 'SUB' | undefined;
    return this.mcFiles.upload(id, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf }, pgRole);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/files/:file_id/replace')
  async replaceFile(@Param('mc_id', ParseIntPipe) mcId: number, @Param('file_id', ParseIntPipe) fileId: number, @Req() req: any) {
    const data = await req.file();
    if (!data) throw new Error('ファイルがありません');
    const buf = await data.toBuffer();
    return this.mcFiles.replace(mcId, fileId, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Delete(':mc_id/files/:file_id')
  deleteFile(@Param('mc_id', ParseIntPipe) mcId: number, @Param('file_id', ParseIntPipe) fileId: number) {
    return this.mcFiles.delete(mcId, fileId);
  }

  // ── 段取シートPDF / 印刷 ───────────────────────
  @Get(':mc_id/print-data')
  getPrintData(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getPrintData(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/print')
  async generatePrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.mc.generateSetupSheetPdf(id, req.user.id, dto);
    this.opLog.log({
      actionType:   'MC_SETUP_PRINT',
      userId:       req.user?.sub,
      mcProgramId:  id,
      sessionId:    req.user?.session_id,
      ipAddress:    req.ip,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="mc-setup-sheet-${id}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/direct-print')
  async directPrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
  ) {
    return this.mc.directPrint(id, req.user.id, dto);
  }

  // ── 機械タイムカード ────────────────────────
  @Get('timecards')
  getTimecards(
    @Query('machine_id', ParseIntPipe) machineId: number,
    @Query('work_date') workDate: string,
  ) {
    return this.mc.getTimecards(machineId, workDate);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('timecards')
  createTimecard(@Body() body: {
    machine_id: number;
    work_date:  string;
    start_time: string;
    end_time:   string;
    note?:      string;
  }, @Req() req: any) {
    return this.mc.createTimecard(
      body.machine_id, req.user.id,
      body.work_date, body.start_time, body.end_time, body.note,
    );
  }
}
