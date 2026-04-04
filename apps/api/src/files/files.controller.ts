// apps/api/src/files/files.controller.ts
import {
  Controller, BadRequestException, Get, Post, Delete, Param, ParseIntPipe,
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

    // TIFFはブラウザ非対応 → sharp でオンザフライPNG変換
    if (mimeType === 'image/tiff' || mimeType === 'image/tif') {
      const sharp = (await import('sharp')).default;
      const pngBuf = await sharp(filePath).png().toBuffer();
      reply.header('Content-Type', 'image/png');
      reply.header('Content-Disposition', `inline; filename="${encodeURIComponent(fileName.replace(/\.tiff?$/i, '.png'))}"`);
      return reply.send(pngBuf);
    }

    reply.header('Content-Type', mimeType);
    reply.header('Content-Disposition', `inline; filename="${encodeURIComponent(fileName)}"`);
    return reply.send(fs.createReadStream(filePath));
  }

  /** FIL-00b: サムネイル配信 */
  @Get('thumb/:file_id')
  async thumb(
    @Param('file_id', ParseIntPipe) id: number,
    @Res() reply: FastifyReply,
  ) {
    const { filePath, mimeType, fileName } =
      await this.filesService.serveThumb(id);

    // TIFFはブラウザ非対応 → sharp でオンザフライPNG変換（serve と同様）
    if (mimeType === 'image/tiff' || mimeType === 'image/tif') {
      const sharp = (await import('sharp')).default;
      const pngBuf = await sharp(filePath).resize(200, 200, { fit: 'inside' }).png().toBuffer();
      reply.header('Content-Type', 'image/png');
      reply.header('Content-Disposition', `inline; filename="${encodeURIComponent(fileName.replace(/\.tiff?$/i, '.png'))}"`);
      reply.header('Cache-Control', 'public, max-age=3600');
      return reply.send(pngBuf);
    }

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
    let fileBuffer:  Buffer | null = null;
    let fileFilename = '';
    let fileMimetype = '';
    let ncProgramId  = 0;

    for await (const part of req.parts()) {
      if ('file' in part) {
        // ファイルストリームをバッファに消費してから次のパートへ
        const chunks: Buffer[] = [];
        for await (const chunk of (part as any).file) chunks.push(chunk as Buffer);
        fileBuffer   = Buffer.concat(chunks);
        fileFilename = (part as any).filename ?? '';
        fileMimetype = (part as any).mimetype ?? 'application/octet-stream';
      } else if ((part as any).fieldname === 'nc_program_id') {
        ncProgramId = parseInt((part as any).value ?? '0');
      }
    }

    if (!fileBuffer)  throw new BadRequestException('ファイルが見つかりません');
    if (!ncProgramId) throw new BadRequestException('nc_program_id が必要です');

    const { Readable } = await import('stream');
    return this.filesService.uploadFile(
      ncProgramId,
      req.user.id,
      Readable.from(fileBuffer),
      fileFilename,
      fileMimetype,
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

  /** FIL-EDIT: 編集済み画像保存（ImageEditor → multipart blob） */
  @UseGuards(AuthGuard('jwt'))
  @Post(':file_id/save-edited')
  async saveEdited(
    @Param('file_id', ParseIntPipe) fileId: number,
    @Req() req: FastifyRequest & { user: any },
  ) {
    const data = await req.file();
    if (!data) throw new BadRequestException('ファイルが見つかりません');

    const fields      = data.fields as any;
    const ncProgramId = parseInt(fields?.nc_program_id?.value ?? '0');
    const processingId: string | undefined = fields?.processing_id?.value || undefined;
    if (!ncProgramId) throw new BadRequestException('nc_program_id が必要です');

    const chunks: Buffer[] = [];
    for await (const chunk of data.file) chunks.push(chunk as Buffer);
    const imageBuffer = Buffer.concat(chunks);

    return this.filesService.saveEditedFile(
      fileId,
      imageBuffer,
      ncProgramId,
      processingId,
      req.user.id,
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
