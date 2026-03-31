import { Controller, Get, Post, Delete, Param, ParseIntPipe, Query, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { PrismaService } from '../prisma/prisma.service';

@Controller('files')
export class FilesController {
  constructor(private readonly prisma: PrismaService) {}

  /** FIL-02: ファイルアップロード */
  @UseGuards(AuthGuard('jwt'))
  @Post('upload')
  upload() {
    return { message: 'TODO: FIL-02 ファイルアップロード（Multer実装予定）' };
  }

  /** FIL-03: 編集済み画像保存 */
  @UseGuards(AuthGuard('jwt'))
  @Post('upload-edited')
  uploadEdited() {
    return { message: 'TODO: FIL-03 Fabric.js編集結果保存' };
  }

  /** FIL-04: ファイル削除（ADMIN） */
  @UseGuards(AuthGuard('jwt'))
  @Delete(':file_id')
  remove(@Param('file_id', ParseIntPipe) id: number) {
    return { message: `TODO: FIL-04 ファイル削除 id=${id}` };
  }
}
