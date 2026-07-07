import {
  Controller, Get, Patch, Post, Put, Delete, Param, Query,
  ParseIntPipe, Body, UseGuards, Req, Res,
} from '@nestjs/common';
import type { FastifyReply } from 'fastify';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from '../common/decorators/roles.decorator';
import { RolesGuard } from '../common/guards/roles.guard';
import { ProgramSessionGuard } from '../common/guards/program-session.guard';
import { OperationLogService } from '../common/operation-log.service';
import { McService } from './mc.service';
import { McFilesService } from './mc-files.service';
import { UploadTicketService } from './upload-ticket.service';
import { BadRequestException, UnauthorizedException } from '@nestjs/common';
import { CreateMcDto } from './dto/create-mc.dto';
import { UpdateMcDto } from './dto/update-mc.dto';
import { FinalizeMcDto } from './dto/finalize-mc.dto';
import { CreateMcWorkRecordDto } from './dto/create-mc-work-record.dto';
import { SaveToolingDto } from './dto/save-tooling.dto';
import { SaveWorkOffsetsDto } from './dto/save-work-offsets.dto';
import { SaveIndexProgramsDto } from './dto/save-index-programs.dto';
import { PrintMcDto } from './dto/print-mc.dto';
import { RegisterCommonPartDto } from './dto/register-common-part.dto';
import { ApproveMcDto } from './dto/approve-mc.dto';

@Controller('mc')
export class McController {
  constructor(
    private readonly mc:      McService,
    private readonly mcFiles: McFilesService,
    private readonly opLog:   OperationLogService,
    private readonly tickets: UploadTicketService,
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

  // [v098] 部品マスタ直接検索（新規登録用）。mc_programsとのJOINを行わないため、
  // MC情報が未登録の部品も検索対象になる。
  @Get('parts-search')
  searchParts(
    @Query('key')    key:    string,
    @Query('q')      q:      string,
    @Query('limit')  limit:  string,
    @Query('offset') offset: string,
  ) {
    return this.mc.searchParts(key, q, parseInt(limit) || 50, parseInt(offset) || 0);
  }

  @Get('recent')
  recent() { return this.mc.recent(); }

  // ── 共通加工グループ ────────────────────────
  @Get('common-group/:machining_id')
  commonGroup(@Param('machining_id', ParseIntPipe) machiningId: number) {
    return this.mc.getCommonGroup(machiningId);
  }

  // ── 共通部品検索 (F-01) ─────────────────────
  @Get('common-parts/search')
  searchCommonParts(
    @Query('drawing_no')   drawingNo?:   string,
    @Query('name')         name?:        string,
    @Query('main_model')   mainModel?:   string,
    @Query('client_id')    clientId?:    string,
    @Query('part_id')      partIdStr?:   string,
    @Query('mc_id')        mcIdQ?:       string,
    @Query('machining_id') machiningIdQ?:string,
    @Query('page')         page?:        string,
    @Query('limit')        limit?:       string,
  ) {
    return this.mc.searchCommonParts({
      drawing_no:   drawingNo   || undefined,
      name:         name        || undefined,
      main_model:   mainModel   || undefined,
      client_id:    clientId    ? parseInt(clientId)    : undefined,
      part_id_str:  partIdStr   || undefined,
      mc_id:        mcIdQ       ? parseInt(mcIdQ)       : undefined,
      machining_id: machiningIdQ? parseInt(machiningIdQ): undefined,
      page:         page        ? parseInt(page)        : 1,
      limit:        limit       ? parseInt(limit)       : 50,
    });
  }

  // ── 共通部品登録（供用）(F-03) ───────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('common-parts/register')
  registerCommonPart(@Body() dto: RegisterCommonPartDto, @Req() req: any) {
    return this.mc.registerCommonPart({
      target_part_id:      dto.target_part_id,
      source_machining_id: dto.source_machining_id,
      note:                dto.note,
    }, req.user.id);
  }

  // ── 共通部品登録解除 (F-04) ──────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Delete('common-parts/:mc_program_id')
  unregisterCommonPart(
    @Param('mc_program_id', ParseIntPipe) mcProgramId: number,
    @Req() req: any,
  ) {
    return this.mc.unregisterCommonPart(mcProgramId, req.user.id);
  }

  // ── 次の加工ID候補取得 ────────────────────────
  @Get('next-machining-id')
  async nextMachiningId() {
    return this.mc.nextMachiningId();
  }

  // ── 新規登録 ────────────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post()
  create(@Body() dto: CreateMcDto, @Req() req: any) {
    return this.mc.create(dto, req.user.id);
  }

  // ── 新規仮データプレビューPDF（DBに保存しない） ──
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('preview-new')
  async previewNew(
    @Body() dto: any,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.mc.previewNew(dto, req.user.id);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', 'inline; filename="mc-setup-preview.pdf"');
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  // ── 新規作成+段取シート印刷 (1トランザクション) ──
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('create-and-print')
  async createAndPrint(@Body() dto: any, @Req() req: any) {
    const result = await this.mc.createAndPrint(dto, req.user.id);
    return JSON.parse(result.toString());
  }


  // ── クランプマスタ (アイテムフォーム用) ─────────────
  @Get('clamp-master')
  async getClampMaster() {
    return this.mc.getClampMaster();
  }

  // ── SPシートチェック ─────────────────────────
  @Get(':mc_id/special-sheet-check')
  checkSpecialSheet(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.checkSpecialSheet(id);
  }

  // ── MC詳細 ──────────────────────────────────
  @Get(':mc_id')
  findOne(@Param('mc_id', ParseIntPipe) id: number) {
    this.opLog.log({ actionType: 'MC_VIEW', mcProgramId: id });
    return this.mc.findOne(id);
  }

  // ── 終了確認（バージョンインクリ + 変更履歴）──────
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/finalize')
  finalize(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: FinalizeMcDto,
    @Req() req: any,
  ) {
    return this.mc.finalize(id, dto.change_type, dto.change_detail, req.user.id);
  }

  // ── 変更キャンセル（CHANGING → 元のステータスに戻す）─
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Patch(':mc_id/revert')
  revert(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.revert(id);
  }

  // ── 承認 ─────────────────────────────────────
  // [v094] 承認は編集セッション(JWT)とは切り離し、承認者自身のID+パスワードを
  // その場で検証する(旧ACCESS「承認します」フォーム相当)。承認資格(canApprove)を
  // 持たないユーザは McService.approve() 内の検証で拒否される。
  @Post(':mc_id/approve')
  approve(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: ApproveMcDto,
  ) {
    return this.mc.approve(id, dto.operator_id, dto.password);
  }

  // ── 更新 ────────────────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
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

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
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

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
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

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
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

  /** 段取シートバック: legacy_mcid で未回収シート検索 */
  @Get('uncollected-by-legacy/:legacy_mcid')
  uncollectedByLegacy(@Param('legacy_mcid', ParseIntPipe) legacyMcid: number) {
    return this.mc.uncollectedByLegacy(legacyMcid);
  }

  /** 保存済み段取シートPDF取得（ログIDで原本を返す） */
  @Get('setup-sheet-logs/:log_id/pdf')
  async getSetupSheetPdf(
    @Param('log_id', ParseIntPipe) logId: number,
    @Res() reply: FastifyReply,
  ) {
    const { buffer, fileName } = await this.mc.getSetupSheetPdf(logId);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="${fileName}"`);
    reply.header('Content-Length',      String(buffer.length));
    return reply.send(buffer);
  }

  /** 段取シート回収完了（work_collected=true） */
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/setup-sheet-logs/:log_id/collect')
  async collectSetupSheet(
    @Param('mc_id',  ParseIntPipe) _mcId:  number,
    @Param('log_id', ParseIntPipe) logId: number,
  ) {
    return this.mc.collectSetupSheet(logId);
  }

  // ── PGファイル閲覧・ダウンロード ───────────────────────────────
  /** PGファイルをテキストで返す（インラインビューア用） */
  @Get(':mc_id/pg-file')
  getPgFile(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.getPgFile(id);
  }

  /** [v066] プログラムファイル一覧(複数ファイル対応の参照プレビュー/編集用) */
  @Get(':mc_id/pg-files-list')
  listPgFiles(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.listPgFiles(id);
  }

  /** [v066] 個別プログラムファイルの内容取得 */
  @Get(':mc_id/pg-files/:file_id/content')
  getPgFileContentById(@Param('file_id', ParseIntPipe) fileId: number) {
    return this.mcFiles.getPgFileContentById(fileId);
  }

  /** [v066] 個別プログラムファイルへの保存 */
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/pg-files/:file_id/content')
  savePgFileContentById(
    @Param('file_id', ParseIntPipe) fileId: number,
    @Body() body: { content: string },
    @Req() req: any,
  ) {
    return this.mcFiles.savePgFileContentById(fileId, body.content, req.user?.id ?? req.user?.sub);
  }

  /** PGファイルをテキストで保存（エディタ保存用） */
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put(':mc_id/pg-content')
  async savePgContent(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() body: { content: string; original_name?: string },
    @Req() req: any,
  ) {
    return this.mcFiles.savePgContent(id, body.content, body.original_name, req.user.id);
  }

  /** PGファイルをダウンロード（USB書き出し用）
   *  単一ファイル → octet-stream
   *  複数ファイル → zip
   */
  @Get(':mc_id/pg-file-info')
  async getPgFileInfo(
    @Param('mc_id', ParseIntPipe) id: number,
  ) {
    return this.mcFiles.getPgFileInfo(id);
  }

  @Get(':mc_id/pg-download')
  async downloadPgFile(
    @Param('mc_id', ParseIntPipe) id: number,
    @Res() reply: FastifyReply,
  ) {
    const { buffer, fileName, mimeType } = await this.mcFiles.downloadPgFile(id);
    reply.header('Content-Type',        mimeType);
    reply.header('Content-Disposition', `attachment; filename="${encodeURIComponent(fileName)}"`);
    reply.header('Content-Length',      String(buffer.length));
    return reply.send(buffer);
  }

  // ── Ridoc図面プロキシ（TN=サムネ / ORG=原寸）──────────────
  @Get(':mc_id/drawing-image')
  async drawingImage(
    @Param('mc_id', ParseIntPipe) mcId: number,
    @Query('imgType') imgType: string = 'TN',
    @Res() reply: FastifyReply,
  ) {
    if (imgType !== 'TN' && imgType !== 'ORG') {
      reply.status(400).send({ error: 'imgType は TN または ORG を指定してください' });
      return;
    }
    const prog = await this.mc.findPartDrawingNo(mcId);
    if (!prog) { reply.status(404).send({ error: 'MC レコードが見つかりません' }); return; }
    if (!prog.drawingNo) { reply.status(404).send({ error: '図面番号が登録されていません' }); return; }
    const ridocUrl = process.env.RIDOC_API_URL;
    if (!ridocUrl) { reply.status(503).send({ error: 'RIDOC_API_URL が設定されていません' }); return; }
    const url = `${ridocUrl}/v1/DrawingImage?docId=${encodeURIComponent(prog.drawingNo)}&imgType=${imgType}`;
    try {
      const upstream = await fetch(url, { signal: AbortSignal.timeout(30_000) });
      if (!upstream.ok) { reply.status(upstream.status).send(await upstream.text()); return; }
      const contentType = upstream.headers.get('content-type') ?? 'application/octet-stream';
      const buf = Buffer.from(await upstream.arrayBuffer());
      if (['image/tiff','image/tif','image/bmp','application/octet-stream'].includes(contentType)) {
        const sharp = (await import('sharp')).default;
        const jpeg = await sharp(buf).jpeg({ quality: 90 }).toBuffer();
        reply.header('Content-Type', 'image/jpeg');
        reply.header('Cache-Control', 'public, max-age=3600');
        return reply.send(jpeg);
      }
      reply.header('Content-Type', contentType);
      reply.header('Cache-Control', 'public, max-age=3600');
      return reply.send(buf);
    } catch (e) {
      reply.status(502).send({ error: 'RidocImageAPI への接続に失敗しました' });
    }
  }

  // ── ファイル一覧 ────────────────────────────
  @Get(':mc_id/files')
  listFiles(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mcFiles.listFiles(id);
  }

  // ── UploadAgent連携: PG→USB専用チケット発行 ──
  // 参照モード画面から「PG→USB」を行う際に使用。
  // Bearerトークン自体はAgentに渡さず、ワンタイムチケットのみを渡す。
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/pg-to-usb-ticket')
  async issuePgToUsbTicket(
    @Param('mc_id', ParseIntPipe) mcId: number,
    @Req() req: any,
  ) {
    const info = await this.mcFiles.getPgFileInfo(mcId);
    if (!info || !info.files || info.files.length === 0) {
      throw new BadRequestException('プログラムファイルが登録されていません');
    }
    const detail = await this.mc.findOne(mcId);
    const machiningId = (detail as any)?.machiningId;
    if (!machiningId) throw new BadRequestException('machiningId が取得できません');

    const ticket = this.tickets.issue({
      mcId,
      machiningId,
      userId: req.user.id,
      isPgToUsb: true,
    });
    return { ticket: ticket.ticket, expires_in_sec: 60, mc_id: mcId, machining_id: machiningId };
  }

  // ── UploadAgent連携: PG→USB専用 ファイル情報取得（チケット認証） ──
  // Bearerトークンではなくticketで認証する。UAがこのエンドポイントを直接呼び、
  // 転送元ファイルのBase64データを取得してUSBへコピーする。
  @Get('files/pg-info-by-ticket')
  async getPgInfoByTicket(@Query('ticket') ticketId: string) {
    if (!ticketId) throw new BadRequestException('ticket が必要です');
    const payload = this.tickets.peek(ticketId);
    if (!payload || !payload.isPgToUsb) {
      throw new UnauthorizedException('チケットが無効、または期限切れです');
    }
    const info = await this.mcFiles.getPgFileInfo(payload.mcId);
    return { ...info, mc_id: payload.mcId, machining_id: payload.machiningId };
  }

  // ── UploadAgent連携: PG→USB完了通知（チケット破棄） ──
  @Post('files/pg-to-usb-complete')
  async completePgToUsb(@Body() body: { ticket: string }) {
    if (!body?.ticket) throw new BadRequestException('ticket が必要です');
    this.tickets.invalidate(body.ticket);
    return { ok: true };
  }

  // ── UploadAgent連携: ワンタイムアップロードチケット発行 ──
  // 正規Bearer認証を経た上でのみチケットを発行。Bearerトークン自体はAgentに渡さない。
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/files/upload-ticket')
  async issueUploadTicket(
    @Param('mc_id', ParseIntPipe) mcId: number,
    @Body() body: { file_type?: 'PHOTO' | 'DRAWING' | 'PROGRAM'; replace_file_id?: number; is_folder_upload?: boolean },
    @Req() req: any,
  ) {
    const detail = await this.mc.findOne(mcId);
    const machiningId = (detail as any)?.machiningId;
    if (!machiningId) throw new BadRequestException('machiningId が取得できません');

    const ticket = this.tickets.issue({
      mcId,
      machiningId,
      userId: req.user.id,
      fileType: body.file_type,
      replaceFileId: body.replace_file_id,
      isFolderUpload: body.is_folder_upload,
    });

    // ★USB自動アップロード対応: PROGRAM(PGファイル)の場合のみ、機械マスタ＋
    //   登録済み実績値から確定した権威的なファイル名/フォルダ名をここで解決し、
    //   レスポンスに含める。UploadAgent側はこの名前でUSB取込元フォルダ内の
    //   実在確認のみを行い、OSのファイル/フォルダ選択ダイアログは表示しない。
    let expectedFileName: string | null = null;
    let expectedFolderName: string | null = null;
    let isFolderTarget = false;
    if (body.file_type === 'PROGRAM') {
      const naming = await this.mcFiles.getExpectedUploadTarget(machiningId);
      isFolderTarget = naming.isFolder;
      expectedFileName = naming.isFolder ? null : naming.fileName;
      expectedFolderName = naming.isFolder ? naming.folderName : null;
    }

    return {
      ticket: ticket.ticket, expires_in_sec: 60, mc_id: mcId, machining_id: machiningId,
      expected_file_name: expectedFileName, expected_folder_name: expectedFolderName, is_folder: isFolderTarget,
    };
  }

  // ── UploadAgent連携: チケット式アップロード受理 ──
  // 認証はBearerトークンではなくワンタイムチケットで行う。
  // req.parts() でストリーム順に走査し、ticketフィールドがfileパートの前後どちらに
  // 来てもよいようにする（multipartのフィールド順序に依存しない実装）。
  @Post('files/upload-by-ticket')
  async uploadByTicket(@Req() req: any) {
    let fileBuffer:   Buffer | null = null;
    let fileFilename  = '';
    let fileMimetype  = 'application/octet-stream';
    let ticketId      = '';
    let folderNameField = '';

    for await (const part of req.parts()) {
      if ('file' in part && (part as any).file) {
        const chunks: Buffer[] = [];
        for await (const chunk of (part as any).file) chunks.push(chunk as Buffer);
        fileBuffer  = Buffer.concat(chunks);
        fileFilename = (part as any).filename ?? '';
        fileMimetype = (part as any).mimetype ?? 'application/octet-stream';
      } else if ((part as any).fieldname === 'ticket') {
        ticketId = (part as any).value ?? '';
      } else if ((part as any).fieldname === 'folder_name') {
        folderNameField = (part as any).value ?? '';
      }
    }

    if (!fileBuffer) throw new BadRequestException('ファイルがありません');
    if (!ticketId)   throw new BadRequestException('ticket が必要です');

    const payload = this.tickets.consume(ticketId);
    if (!payload) throw new UnauthorizedException('チケットが無効、または期限切れです');

    const buf = fileBuffer;
    const isFolderUpload = payload.isFolderUpload === true;

    if (payload.replaceFileId) {
      const result = await this.mcFiles.replace(payload.mcId, payload.replaceFileId, payload.userId,
        { filename: fileFilename, mimetype: fileMimetype, data: buf });
      return { ...result, mc_id: payload.mcId, machining_id: payload.machiningId, mode: 'replace' };
    } else {
      // ★重複登録バグ修正: PROGRAM種別のアップロードでは、このチケットにおいて
      //   まだ既存ファイルのpurgeを行っていない場合のみpurgeExisting=trueを渡す。
      //   フォルダアップロード用チケットは同一チケットを使い回して複数ファイルを
      //   順次アップロードするため、1回目でpurgeした後は2回目以降purgeしない
      //   (直前にアップロードしたファイル自身を誤ってpurgeする事故を防ぐ)。
      const purgeExisting = payload.fileType === 'PROGRAM' && !payload.programPurged;

      const result: any = await this.mcFiles.upload(payload.mcId, payload.userId,
        { filename: fileFilename, mimetype: fileMimetype, data: buf },
        undefined, isFolderUpload, payload.fileType as any, folderNameField || undefined,
        purgeExisting);

      if (purgeExisting) payload.programPurged = true;

      const PROGRAM_EXTS = new Set(['.min','.spf','.mpf','.nc','.cnc','.tap','.prg','.gcode','.g','.txt']);
      const fileExt = ('.' + (fileFilename.split('.').pop()?.toLowerCase() ?? ''));
      if (PROGRAM_EXTS.has(fileExt)) {
        await this.mc.updatePgMeta(payload.mcId, payload.userId);
      }
      return { ...result, mc_id: payload.mcId, machining_id: payload.machiningId, mode: 'create' };
    }
  }

  // ── オリジナルファイル配信 ──
  @Get(':mc_id/files/:file_id/serve')
  async serveFile(
    @Param('mc_id', ParseIntPipe) _mcId: number,
    @Param('file_id', ParseIntPipe) fileId: number,
    @Res() reply: FastifyReply,
  ) {
    const { filePath, mimeType, fileName } = await this.mcFiles.serveFile(fileId);
    // TIFFはブラウザ非対応 → sharp でPNG変換
    if (mimeType === 'image/tiff' || mimeType === 'image/tif') {
      const sharp = (await import('sharp')).default;
      const pngBuf = await sharp(filePath).png().toBuffer();
      reply.header('Content-Type', 'image/png');
      reply.header('Cache-Control', 'public, max-age=3600');
      return reply.send(pngBuf);
    }
    reply.header('Content-Type', mimeType);
    reply.header('Cache-Control', 'public, max-age=3600');
    return reply.send(require('fs').createReadStream(filePath));
  }

  // ── サムネイル配信（キャッシュ付きオンデマンド）──
  @Get(':mc_id/files/:file_id/thumb')
  async serveThumb(
    @Param('mc_id', ParseIntPipe) _mcId: number,
    @Param('file_id', ParseIntPipe) fileId: number,
    @Res() reply: FastifyReply,
  ) {
    const { filePath, mimeType } = await this.mcFiles.serveThumb(fileId);
    reply.header('Content-Type', mimeType);
    reply.header('Cache-Control', 'public, max-age=86400');
    return reply.send(require('fs').createReadStream(filePath));
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/files/upload')
  async uploadFile(@Param('mc_id', ParseIntPipe) id: number, @Req() req: any) {
    const data = await req.file();
    if (!data) throw new Error('ファイルがありません');
    const buf            = await data.toBuffer();
    const isFolderUpload = (data.fields?.is_folder_upload?.value === 'true');
    const folderNameField = (data.fields?.folder_name?.value as string | undefined) ?? undefined;
    const pgCreatedBy    = data.fields?.pg_created_by?.value
                             ? parseInt(data.fields.pg_created_by.value, 10)
                             : req.user.id;
    const pgRole = (data.fields?.pg_role?.value ?? undefined) as 'MAIN' | 'SUB' | undefined;
    const fileTypeOverride = (data.fields?.file_type?.value ?? undefined) as 'PHOTO' | 'DRAWING' | undefined;
    // ★重複登録バグ修正: 直接アップロードAPIもPROGRAM再アップロード時の重複防止のため
    //   常にpurgeExisting=trueで既存の有効なPROGRAM系レコードをpurgeしてから書き込む。
    const result = await this.mcFiles.upload(id, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf }, pgRole, isFolderUpload, fileTypeOverride, folderNameField, true);
    // PROGRAMファイルの場合 pg_created_by / pg_updated_at を自動更新
    const PROGRAM_EXTS = new Set(['.min','.spf','.mpf','.nc','.cnc','.tap','.prg','.gcode','.g','.txt']);
    const fileExt = ('.' + (data.filename.split('.').pop()?.toLowerCase() ?? ''));
    if (PROGRAM_EXTS.has(fileExt)) {
      await this.mc.updatePgMeta(id, pgCreatedBy);
    }
    return result;
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/files/:file_id/replace')
  async replaceFile(@Param('mc_id', ParseIntPipe) mcId: number, @Param('file_id', ParseIntPipe) fileId: number, @Req() req: any) {
    const data = await req.file();
    if (!data) throw new Error('ファイルがありません');
    const buf = await data.toBuffer();
    return this.mcFiles.replace(mcId, fileId, req.user.id, { filename: data.filename, mimetype: data.mimetype, data: buf });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Delete(':mc_id/files/:file_id')
  deleteFile(@Param('mc_id', ParseIntPipe) mcId: number, @Param('file_id', ParseIntPipe) fileId: number) {
    return this.mcFiles.delete(mcId, fileId);
  }

  // ── リピート段取シートPDF（プレビュー）──────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/repeat-print')
  async repeatPrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    // is_preview:false → ログ記録する（ブラウザプレビューだが発行履歴は残す）
    const opts = { ...dto, is_preview: false };
    const pdf = await this.mc.generateRepeatSetupSheetPdf(id, req.user.id, opts);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="mc-repeat-sheet-${id}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  // ── リピート段取シート ダイレクト印刷 ──────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/repeat-direct-print')
  async repeatDirectPrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
  ) {
    const pdf = await this.mc.generateRepeatSetupSheetPdf(id, req.user.id, dto);
    const setting = await this.mc['prisma'].companySetting.findFirst({ select: { printerName: true, mcPrinter: true } });
    const printerName = (setting as any)?.mcPrinter || (setting as any)?.printerName;
    if (!printerName) throw new Error('MCプリンタが設定されていません');
    const tmpPath = `/tmp/machcore-mc-repeat-${id}-${Date.now()}.pdf`;
    const fs2 = await import('fs');
    fs2.writeFileSync(tmpPath, pdf);
    const { execSync: execSync2 } = await import('child_process');
    try {
      execSync2(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs2.unlinkSync(tmpPath); } catch { /**/ }
    }
    return { message: `${printerName} に送信しました` };
  }

  // ── 段取シートPDF / 印刷 ───────────────────────
  @Get(':mc_id/print-data')
  getPrintData(@Param('mc_id', ParseIntPipe) id: number) {
    return this.mc.getPrintData(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post(':mc_id/print')
  async generatePrint(
    @Param('mc_id', ParseIntPipe) id: number,
    @Body() dto: PrintMcDto,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.mc.generateSetupSheetPdf(id, req.user.id, { ...dto, is_preview: false } as any);
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

  @UseGuards(AuthGuard('jwt'), RolesGuard, ProgramSessionGuard)
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
  @Get('timecards/all')
  getTimecardsByDate(@Query('work_date') workDate: string) {
    return this.mc.getTimecardsByDate(workDate);
  }

  @Get('timecards')
  getTimecards(
    @Query('machine_id', ParseIntPipe) machineId: number,
    @Query('work_date') workDate: string,
  ) {
    return this.mc.getTimecards(machineId, workDate);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Delete('timecards/:id')
  deleteTimecard(@Param('id', ParseIntPipe) id: number) {
    return this.mc.deleteTimecard(id);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Put('timecards/:id')
  updateTimecard(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { start_time: string; end_time: string; note?: string },
  ) {
    return this.mc.updateTimecard(id, body.start_time, body.end_time, body.note);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('timecards/init')
  initTimecards(
    @Body() body: { work_date: string },
    @Req() req: any,
  ) {
    return this.mc.initTimecards(body.work_date, req.user.id);
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
