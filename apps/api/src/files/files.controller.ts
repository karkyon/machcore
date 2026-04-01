// apps/api/src/files/files.controller.ts
import {
  Controller, Get, Post, Delete, Param, ParseIntPipe,
  UseGuards, Req, Res, Body,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { FilesService } from './files.service';
import type { FastifyRequest, FastifyReply } from 'fastify';
import * as fs from 'fs';

@Controller('files')
export class FilesController {
  constructor(private readonly filesService: FilesService) {}

  /** FIL-00: ファイル配信（プレビュー） */
  @Get('serve/:file_id')
  async serve(
    @Param('file_id', ParseIntPipe) id: number,
    @Res() reply: FastifyReply,
  ) {
    const { filePath, mimeType, fileName } = await this.filesService.serveFile(id);
    reply.header('Content-Type', mimeType);
    reply.header('Content-Disposition', `inline; filename="${encodeURIComponent(fileName)}"`);
    const stream = fs.createReadStream(filePath);
    return reply.send(stream);
  }

  /** FIL-00b: サムネイル配信 */
  @Get('thumb/:file_id')
  async thumb(
    @Param('file_id', ParseIntPipe) id: number,
    @Res() reply: FastifyReply,
  ) {
    const { filePath, mimeType, fileName } =
      await this.filesService.serveThumb(id);
    reply.header('Content-Type', mimeType);
    reply.header('Content-Disposition', `inline; filename="${encodeURIComponent(fileName)}"`);
    reply.header('Cache-Control', 'public, max-age=3600');
    const stream = fs.createReadStream(filePath);
    return reply.send(stream);
  }

  /** FIL-02: ファイルアップロード（写真/図/NCプログラム） */
  @UseGuards(AuthGuard('jwt'))
  @Post('upload')
  async upload(@Req() req: FastifyRequest & { user: any }) {
    const data = await req.file();
    if (!data) throw new Error('ファイルが見つかりません');

    const ncProgramId = parseInt((data.fields as any)?.nc_program_id?.value ?? '0');
    if (!ncProgramId) throw new Error('nc_program_id が必要です');

    return this.filesService.uploadFile(
      ncProgramId,
      req.user.id,
      data.file,
      data.filename,
      data.mimetype,
    );
  }

  /** FIL-03: 編集済み画像保存（Base64） */
  @UseGuards(AuthGuard('jwt'))
  @Post('upload-edited')
  async uploadEdited(
    @Req() req: FastifyRequest & { user: any },
    @Body() body: { nc_program_id: number; base64_data: string; original_file_id: number },
  ) {
    return this.filesService.uploadEdited(
      body.nc_program_id,
      req.user.id,
      body.base64_data,
      body.original_file_id,
    );
  }

  /** FIL-04: ファイル削除 */
  @UseGuards(AuthGuard('jwt'))
  @Delete(':file_id')
  async remove(
    @Param('file_id', ParseIntPipe) id: number,
    @Req() req: FastifyRequest & { user: any },
  ) {
    return this.filesService.deleteFile(id, req.user.id, req.user.role);
  }
}
