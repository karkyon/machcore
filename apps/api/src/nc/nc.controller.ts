import {
  Controller, Get, Post, Put, Patch, Delete, Param, Query,
  ParseIntPipe, Body, UseGuards, Req, Res, BadRequestException, UnauthorizedException,
} from "@nestjs/common";
import { Roles } from "../common/decorators/roles.decorator";
import { RolesGuard } from "../common/guards/roles.guard";
import { ProgramSessionGuard } from "../common/guards/program-session.guard";
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
import { FinalizeNcDto } from "./dto/finalize-nc.dto";
import { SaveNcToolingDto } from "./dto/save-nc-tooling.dto";
import { NcFilesService } from "./nc-files.service";
import { UploadTicketService } from "../mc/upload-ticket.service";
import { RegisterCommonNcPartDto } from "./dto/register-common-nc-part.dto";
import { ApproveNcDto } from "./dto/approve-nc.dto";

@Controller("nc")
export class NcController {
  constructor(
    private readonly nc: NcService,
    private readonly opLog: OperationLogService,
    private readonly ncFiles: NcFilesService,
    private readonly tickets: UploadTicketService,
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

  // [v087] 共通部品(MC側 common-group/common-parts と同等機能のNC版)
  // ── 共通加工グループ ────────────────────────
  @Get("common-group/:machining_id")
  commonGroupNc(@Param("machining_id", ParseIntPipe) machiningId: number) {
    return this.nc.getCommonGroup(machiningId);
  }

  // ── 共通部品検索 ─────────────────────────────
  @Get("common-parts/search")
  searchCommonPartsNc(
    @Query("drawing_no")   drawingNo?:    string,
    @Query("name")         name?:         string,
    @Query("main_model")   mainModel?:    string,
    @Query("client_id")    clientId?:     string,
    @Query("part_id")      partIdStr?:    string,
    @Query("nc_id")        ncIdQ?:        string,
    @Query("machining_id") machiningIdQ?: string,
    @Query("page")         page?:         string,
    @Query("limit")        limit?:        string,
  ) {
    return this.nc.searchCommonParts({
      drawing_no:   drawingNo   || undefined,
      name:         name        || undefined,
      main_model:   mainModel   || undefined,
      client_id:    clientId    ? parseInt(clientId)    : undefined,
      part_id_str:  partIdStr   || undefined,
      nc_id:        ncIdQ       ? parseInt(ncIdQ)        : undefined,
      machining_id: machiningIdQ? parseInt(machiningIdQ): undefined,
      page:         page        ? parseInt(page)        : 1,
      limit:        limit       ? parseInt(limit)       : 50,
    });
  }

  // ── 共通部品登録（供用） ─────────────────────
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post("common-parts/register")
  registerCommonPartNc(@Body() dto: RegisterCommonNcPartDto, @Req() req: any) {
    return this.nc.registerCommonPart({
      target_part_id:      dto.target_part_id,
      source_machining_id: dto.source_machining_id,
      note:                dto.note,
    }, req.user.id);
  }

  // ── 共通部品登録解除 ─────────────────────────
  @UseGuards(AuthGuard("jwt"), RolesGuard)
  @Roles("OPERATOR", "ADMIN")
  @Delete("common-parts/:nc_program_id")
  unregisterCommonPartNc(
    @Param("nc_program_id", ParseIntPipe) ncProgramId: number,
    @Req() req: any,
  ) {
    return this.nc.unregisterCommonPart(ncProgramId, req.user.id);
  }

  @Get("client-names")
  async clientNames() {
    const rows = await this.nc.getClientNames();
    return rows;
  }

  @Get("recent")
  recent() { return this.nc.recent(); }

  /** 同部品の工程一覧 */
  @Get("by-part/:part_db_id")
  byPart(@Param("part_db_id", ParseIntPipe) partDbId: number) {
    return this.nc.byPart(partDbId);
  }

  @Get(":nc_id/change-history")
  changeHistory(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.changeHistory(id);
  }

  @Get(":nc_id/setup-sheet-logs")
  setupSheetLogs(
    @Param("nc_id", ParseIntPipe) id: number,
    @Query("uncollected") uncollected?: string,
  ) {
    return this.nc.setupSheetLogs(id, uncollected === "1" || uncollected === "true");
  }

  /** 段取シート回収完了（work_collected=true） */
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Put(":nc_id/setup-sheet-logs/:log_id/collect")
  async collectSetupSheet(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Param("log_id", ParseIntPipe) logId: number,
  ) {
    return this.nc.collectSetupSheet(logId);
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

  // ── Ridoc図面プロキシ（TN=サムネ / ORG=原寸）MC側と同方式 ──
  @Get(":nc_id/drawing-image")
  async drawingImage(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Query("imgType") imgType: string = "TN",
    @Res() reply: FastifyReply,
  ) {
    if (imgType !== "TN" && imgType !== "ORG") {
      reply.status(400).send({ error: "imgType は TN または ORG を指定してください" });
      return;
    }
    const prog = await this.nc.findPartDrawingNo(ncId);
    if (!prog) { reply.status(404).send({ error: "NC レコードが見つかりません" }); return; }
    if (!prog.drawingNo) { reply.status(404).send({ error: "図面番号が登録されていません" }); return; }
    const ridocUrl = process.env.RIDOC_API_URL;
    if (!ridocUrl) { reply.status(503).send({ error: "RIDOC_API_URL が設定されていません" }); return; }
    const url = `${ridocUrl}/v1/DrawingImage?docId=${encodeURIComponent(prog.drawingNo)}&imgType=${imgType}`;
    try {
      const upstream = await fetch(url, { signal: AbortSignal.timeout(30_000) });
      if (!upstream.ok) { reply.status(upstream.status).send(await upstream.text()); return; }
      const contentType = upstream.headers.get("content-type") ?? "application/octet-stream";
      const buf = Buffer.from(await upstream.arrayBuffer());
      if (["image/tiff", "image/tif", "image/bmp", "application/octet-stream"].includes(contentType)) {
        const sharp = (await import("sharp")).default;
        const jpeg = await sharp(buf).jpeg({ quality: 90 }).toBuffer();
        reply.header("Content-Type", "image/jpeg");
        reply.header("Cache-Control", "public, max-age=3600");
        return reply.send(jpeg);
      }
      reply.header("Content-Type", contentType);
      reply.header("Cache-Control", "public, max-age=3600");
      return reply.send(buf);
    } catch (e) {
      reply.status(502).send({ error: "RidocImageAPI への接続に失敗しました" });
    }
  }

  // ── UploadAgent連携: ワンタイムアップロードチケット発行（MC側と同方式） ──
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/files/upload-ticket")
  async issueUploadTicket(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Body() body: { file_type?: "PHOTO" | "DRAWING"; replace_file_id?: number; is_folder_upload?: boolean },
    @Req() req: any,
  ) {
    const ticket = this.tickets.issue({
      mcId: ncId,
      machiningId: ncId,
      userId: req.user.id,
      fileType: body.file_type,
      replaceFileId: body.replace_file_id,
      isFolderUpload: body.is_folder_upload,
      system: "NC",
    });
    return { ticket: ticket.ticket, expires_in_sec: 60, nc_id: ncId, upload_path: "/api/nc/files/upload-by-ticket" };
  }

  // ── UploadAgent連携: チケット式アップロード受理（MC側と同方式） ──
  @Post("files/upload-by-ticket")
  async uploadByTicket(@Req() req: any) {
    let fileBuffer:  Buffer | null = null;
    let fileFilename = "";
    let fileMimetype = "application/octet-stream";
    let ticketId     = "";

    for await (const part of req.parts()) {
      if ("file" in part && (part as any).file) {
        const chunks: Buffer[] = [];
        for await (const chunk of (part as any).file) chunks.push(chunk as Buffer);
        fileBuffer  = Buffer.concat(chunks);
        fileFilename = (part as any).filename ?? "";
        fileMimetype = (part as any).mimetype ?? "application/octet-stream";
      } else if ((part as any).fieldname === "ticket") {
        ticketId = (part as any).value ?? "";
      }
    }

    if (!fileBuffer) throw new BadRequestException("ファイルがありません");
    if (!ticketId)   throw new BadRequestException("ticket が必要です");

    const payload = this.tickets.consume(ticketId);
    if (!payload || payload.system !== "NC") throw new UnauthorizedException("チケットが無効、または期限切れです");

    const result = await this.ncFiles.upload(
      payload.mcId, payload.userId,
      { filename: fileFilename, mimetype: fileMimetype, data: fileBuffer },
      payload.fileType as any,
    );
    return { ...result, nc_id: payload.mcId, mode: "create" };
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
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
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
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
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
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
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

  /** NC-05b: 終了確認（バージョンインクリ + 変更履歴登録） */
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/finalize")
  finalize(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: FinalizeNcDto,
    @Req() req: any,
  ) {
    return this.nc.finalize(id, dto.change_type, dto.change_detail, req.user.id);
  }

  /** NC-05c: 変更キャンセル（CHANGING → 前の状態に戻す） */
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Patch(":nc_id/revert")
  revert(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.revert(id);
  }

  /** NC-06: 承認
   * [v094] MC同様、編集セッションと切り離し承認者本人のID+パスワードをその場で検証する。 */
  @Post(":nc_id/approve")
  approve(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: ApproveNcDto,
  ) {
    return this.nc.approve(id, dto.operator_id, dto.password);
  }

  // ── ツーリング ──────────────────────────────
  @Get(":nc_id/tooling")
  getTooling(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getTooling(id);
  }

  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Put(":nc_id/tooling")
  saveTooling(
    @Param("nc_id", ParseIntPipe) id: number,
    @Body() dto: SaveNcToolingDto,
    @Req() req: any,
  ) {
    return this.nc.saveTooling(id, dto, req.user.id);
  }

  /** NC-07: 段取シートデータ取得（認証不要） */
  @Get(":nc_id/print-data")
  getPrintData(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getPrintData(id);
  }

  /** NC-08b: ダイレクト印刷（JWT必須） */
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
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
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
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
  @UseGuards(AuthGuard("jwt"), ProgramSessionGuard)
  @Get(":nc_id/pg-file")
  getPgFile(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.getPgFile(id);
  }

  /** [v066] プログラムファイル一覧(nc_filesベース) */
  @Get(":nc_id/pg-files-list")
  listPgFilesNc(@Param("nc_id", ParseIntPipe) id: number) {
    return this.nc.listPgFilesNc(id);
  }

  /** [v076] UploadAgent連携: PG→USB専用チケット発行(MC側と同方式) */
  @UseGuards(AuthGuard("jwt"), RolesGuard, ProgramSessionGuard)
  @Roles("OPERATOR", "ADMIN")
  @Post(":nc_id/pg-to-usb-ticket")
  async issuePgToUsbTicketNc(
    @Param("nc_id", ParseIntPipe) ncId: number,
    @Req() req: any,
  ) {
    const info = await this.nc.getPgFileInfoNc(ncId);
    if (!info || !info.files || info.files.length === 0) {
      throw new BadRequestException("プログラムファイルが登録されていません");
    }
    const ticket = this.tickets.issue({
      mcId: ncId,
      machiningId: ncId,
      userId: req.user.id,
      isPgToUsb: true,
      system: "NC",
    });
    return { ticket: ticket.ticket, expires_in_sec: 60, nc_id: ncId };
  }

  /** [v076] UploadAgent連携: PG→USB専用 ファイル情報取得(チケット認証・NC) */
  @Get("files/pg-info-by-ticket")
  async getPgInfoByTicketNc(@Query("ticket") ticketId: string) {
    if (!ticketId) throw new BadRequestException("ticket が必要です");
    const payload = this.tickets.peek(ticketId);
    if (!payload || !payload.isPgToUsb) {
      throw new UnauthorizedException("チケットが無効、または期限切れです");
    }
    const info = await this.nc.getPgFileInfoNc(payload.mcId);
    return { ...info, nc_id: payload.mcId };
  }

  /** [v076] UploadAgent連携: PG→USB完了通知(チケット破棄・NC) */
  @Post("files/pg-to-usb-complete")
  async completePgToUsbNc(@Body() body: { ticket: string }) {
    if (!body?.ticket) throw new BadRequestException("ticket が必要です");
    this.tickets.invalidate(body.ticket);
    return { ok: true };
  }

  /** [v066] 個別プログラムファイルの内容取得(nc_filesベース) */
  @Get(":nc_id/pg-files/:file_id/content")
  getPgFileContentByIdNc(@Param("file_id", ParseIntPipe) fileId: number) {
    return this.nc.getPgFileContentByIdNc(fileId);
  }

  /** [v066] 個別プログラムファイルへの保存(nc_filesベース) */
  @UseGuards(AuthGuard("jwt"), ProgramSessionGuard)
  @Put(":nc_id/pg-files/:file_id/content")
  savePgFileContentByIdNc(
    @Param("file_id", ParseIntPipe) fileId: number,
    @Body() body: { content: string },
  ) {
    return this.nc.savePgFileContentByIdNc(fileId, body.content);
  }

  /** NC-06b: PGファイル保存（JWT必須） */
  @UseGuards(AuthGuard("jwt"), ProgramSessionGuard)
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
  @UseGuards(AuthGuard("jwt"), ProgramSessionGuard)
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