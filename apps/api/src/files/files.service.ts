// apps/api/src/files/files.service.ts
import {
  Injectable, NotFoundException, BadRequestException, ForbiddenException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import sharp from 'sharp';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';

// アップロード対象MIMEタイプ
const ALLOWED_MIME: Record<string, string> = {
  'image/jpeg':     'PHOTO',
  'image/jpg':      'PHOTO',
  'image/png':      'PHOTO',
  'image/tiff':     'DRAWING',
  'image/tif':      'DRAWING',
  'application/pdf':'DRAWING',
  'text/plain':     'PROGRAM',
};

@Injectable()
export class FilesService {
  constructor(private readonly prisma: PrismaService) {}

  // ── 保存先ベースパスを取得（DB設定 or デフォルト） ──────────────
  private async getBasePath(): Promise<string> {
    const setting = await this.prisma.companySetting.findFirst();
    return setting?.uploadBasePath
      ?? '/home/karkyon/projects/machcore/uploads';
  }

  // ── ディレクトリ保証 ──────────────────────────────────────────
  private ensureDir(dirPath: string) {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
  }

  // ── FIL-01: ファイル一覧 ──────────────────────────────────────
  async listFiles(ncProgramId: number) {
    const rows = await this.prisma.ncFile.findMany({
      where:   { ncProgramId },
      orderBy: { uploadedAt: 'desc' },
      include: { uploader: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      file_type:      r.fileType,
      original_name:  r.originalName,
      stored_name:    r.storedName,
      mime_type:      r.mimeType,
      file_size:      r.fileSize,
      file_path:      r.filePath,
      thumbnail_path: r.thumbnailPath,
      uploaded_by:    r.uploader?.name ?? null,
      uploaded_at:    r.uploadedAt,
    }));
  }

  // ── FIL-02: アップロード ──────────────────────────────────────
  async uploadFile(
    ncProgramId: number,
    uploaderId: number,
    fileStream: Readable,
    originalName: string,
    mimeType: string,
  ) {
    // nc_program 存在確認
    const nc = await this.prisma.ncProgram.findUnique({ where: { id: ncProgramId } });
    if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);

    // MIMEチェック
    const fileTypeStr = ALLOWED_MIME[mimeType.toLowerCase()];
    if (!fileTypeStr) throw new BadRequestException(`未対応のファイル形式: ${mimeType}`);

    const basePath  = await this.getBasePath();
    const timestamp = Date.now();
    const ext       = path.extname(originalName).toLowerCase();
    const storedName = `${ncProgramId}_${timestamp}${ext}`;
    const subDir     = path.join(basePath, 'nc_files', String(ncProgramId), fileTypeStr.toLowerCase());
    this.ensureDir(subDir);

    let finalPath: string;
    let finalMime = mimeType;
    let thumbPath: string | null = null;

    // TIFF → PNG変換
    if (mimeType === 'image/tiff' || mimeType === 'image/tif') {
      const pngName = storedName.replace(/\.tiff?$/i, '.png');
      finalPath = path.join(subDir, pngName);
      finalMime = 'image/png';
      // ストリームをバッファ化してsharpで変換
      const chunks: Buffer[] = [];
      for await (const chunk of fileStream) chunks.push(chunk as Buffer);
      const inputBuf = Buffer.concat(chunks);
      await sharp(inputBuf).png().toFile(finalPath);
      // サムネイル生成
      const thumbDir = path.join(basePath, 'nc_files', String(ncProgramId), 'thumbnails');
      this.ensureDir(thumbDir);
      const thumbName = `thumb_${pngName}`;
      thumbPath = path.join(thumbDir, thumbName);
      await sharp(inputBuf).resize(200, 200, { fit: 'inside' }).png().toFile(thumbPath);
    } else if (mimeType.startsWith('image/')) {
      // 通常画像 → そのまま保存 + サムネイル生成
      finalPath = path.join(subDir, storedName);
      const chunks: Buffer[] = [];
      for await (const chunk of fileStream) chunks.push(chunk as Buffer);
      const inputBuf = Buffer.concat(chunks);
      fs.writeFileSync(finalPath, inputBuf);
      // サムネイル
      const thumbDir = path.join(basePath, 'nc_files', String(ncProgramId), 'thumbnails');
      this.ensureDir(thumbDir);
      const thumbName = `thumb_${storedName}`;
      thumbPath = path.join(thumbDir, thumbName);
      await sharp(inputBuf).resize(200, 200, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbPath);
    } else {
      // PDF / NCプログラム → ストリームをそのまま書き込み
      finalPath = path.join(subDir, storedName);
      await pipeline(fileStream, fs.createWriteStream(finalPath));
    }

    const fileSize = fs.statSync(finalPath).size;

    // DB登録
    const record = await this.prisma.ncFile.create({
      data: {
        ncProgramId,
        fileType:      fileTypeStr as any,
        originalName,
        storedName,
        mimeType:      finalMime,
        filePath:      finalPath,
        thumbnailPath: thumbPath,
        fileSize,
        uploadedBy:    uploaderId,
      },
    });

    // nc_programs の枚数カウント更新
    await this.updateFileCounts(ncProgramId);

    return { id: record.id, message: 'アップロード完了', stored_name: storedName };
  }

  // ── FIL-03: Base64編集済み画像保存 ────────────────────────────
  async uploadEdited(
    ncProgramId: number,
    uploaderId: number,
    base64Data: string,
    originalFileId: number,
  ) {
    const original = await this.prisma.ncFile.findUnique({ where: { id: originalFileId } });
    if (!original) throw new NotFoundException(`file_id ${originalFileId} が存在しません`);

    const basePath   = await this.getBasePath();
    const timestamp  = Date.now();
    const storedName = `edited_${ncProgramId}_${timestamp}.jpg`;
    const subDir     = path.join(basePath, 'nc_files', String(ncProgramId), 'photo');
    this.ensureDir(subDir);

    const finalPath = path.join(subDir, storedName);
    const buf = Buffer.from(base64Data.replace(/^data:image\/\w+;base64,/, ''), 'base64');
    fs.writeFileSync(finalPath, buf);

    // サムネイル
    const thumbDir  = path.join(basePath, 'nc_files', String(ncProgramId), 'thumbnails');
    this.ensureDir(thumbDir);
    const thumbPath = path.join(thumbDir, `thumb_${storedName}`);
    await sharp(buf).resize(200, 200, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbPath);

    const record = await this.prisma.ncFile.create({
      data: {
        ncProgramId,
        fileType:      'PHOTO',
        originalName:  `edited_${original.originalName}`,
        storedName,
        mimeType:      'image/jpeg',
        filePath:      finalPath,
        thumbnailPath: thumbPath,
        fileSize:      buf.length,
        uploadedBy:    uploaderId,
      },
    });

    await this.updateFileCounts(ncProgramId);
    return { id: record.id, message: '編集済み画像を保存しました' };
  }

  // ── FIL-04: ファイル削除 ──────────────────────────────────────
  async deleteFile(fileId: number, requesterId: number, requesterRole: string) {
    const file = await this.prisma.ncFile.findUnique({ where: { id: fileId } });
    if (!file) throw new NotFoundException(`file_id ${fileId} が存在しません`);

    // ADMIN or アップロード本人のみ削除可
    if (requesterRole !== 'ADMIN' && file.uploadedBy !== requesterId) {
      throw new ForbiddenException('削除権限がありません');
    }

    // 物理ファイル削除
    if (fs.existsSync(file.filePath)) fs.unlinkSync(file.filePath);
    if (file.thumbnailPath && fs.existsSync(file.thumbnailPath)) {
      fs.unlinkSync(file.thumbnailPath);
    }

    await this.prisma.ncFile.delete({ where: { id: fileId } });
    await this.updateFileCounts(file.ncProgramId);
    return { message: 'ファイルを削除しました' };
  }

  // ── FIL-00: ファイル配信（プレビュー用） ───────────────────────
  async serveFile(fileId: number) {
    const file = await this.prisma.ncFile.findUnique({ where: { id: fileId } });
    if (!file) throw new NotFoundException(`file_id ${fileId} が存在しません`);
    if (!fs.existsSync(file.filePath)) throw new NotFoundException('ファイルが見つかりません');
    return { filePath: file.filePath, mimeType: file.mimeType, fileName: file.originalName };
  }

  // ── FIL-00b: サムネイル配信 ────────────────────────────────────
  async serveThumb(fileId: number) {
    const file = await this.prisma.ncFile.findUnique({ where: { id: fileId } });
    if (!file) throw new NotFoundException(`file_id ${fileId} が存在しません`);

    // thumbnailPath があれば優先、なければオリジナルをフォールバック
    const servePath =
      file.thumbnailPath && fs.existsSync(file.thumbnailPath)
        ? file.thumbnailPath
        : file.filePath;

    if (!fs.existsSync(servePath))
      throw new NotFoundException('ファイルが見つかりません');

    const thumbMime = file.thumbnailPath ? 'image/jpeg' : file.mimeType;
    return {
      filePath: servePath,
      mimeType: thumbMime,
      fileName: path.basename(servePath),
    };
  }


  // ── FIL-EDIT: 編集済み画像保存（元ファイル保持・命名規則適用） ──
  async saveEditedFile(
    fileId: number,
    imageBuffer: Buffer,
    ncProgramId: number,
    processingId: string | undefined,
    uploaderId: number,
  ) {
    const orig = await this.prisma.ncFile.findUnique({ where: { id: fileId } });
    if (!orig) throw new NotFoundException(`file_id ${fileId} が存在しません`);

    const base    = await this.getBasePath();
    const dir     = path.join(base, 'nc_files', String(ncProgramId), 'images');
    this.ensureDir(dir);

    // 命名規則: {加工ID}-{YYYYMMDD-HHmmss}-{連番}.png
    const dateStr = new Date().toISOString()
      .replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
    const pid = processingId || String(ncProgramId);
    const existing = fs.readdirSync(dir).filter(f => f.startsWith(`${pid}-`));
    const seq = String(existing.length + 1).padStart(3, '0');
    const fileName = `${pid}-${dateStr}-${seq}.png`;
    const filePath = path.join(dir, fileName);

    fs.writeFileSync(filePath, imageBuffer);

    // PNG サムネイル生成（400px）
    const thumbName = `thumb_${fileName}`;
    const thumbPath = path.join(dir, thumbName);
    await sharp(imageBuffer).resize(400).jpeg({ quality: 80 }).toFile(thumbPath);

    // DB登録
    const record = await this.prisma.ncFile.create({
      data: {
        ncProgramId,
        uploadedBy:    uploaderId,
        fileType:      'PHOTO',
        originalName:  fileName,
        storedName:    fileName,
        mimeType:      'image/png',
        fileSize:      imageBuffer.length,
        filePath,
        thumbnailPath: thumbPath,
      },
    });

    await this.updateFileCounts(ncProgramId);
    return { id: record.id, file_name: fileName, message: '編集済み画像を保存しました' };
  }

  // ── 保存先パス更新 ────────────────────────────────────────────
  async updateStoragePath(newPath: string) {
    const trimmed = newPath.trim();
    if (!trimmed) throw new BadRequestException('パスが空です');
    const setting = await this.prisma.companySetting.upsert({
      where:  { id: 1 },
      update: { uploadBasePath: trimmed },
      create: { id: 1, companyName: '未設定', uploadBasePath: trimmed },
    });
    return { upload_base_path: setting.uploadBasePath, message: '保存先パスを更新しました' };
  }

  // ── nc_programs の drawingCount / photoCount 更新 ─────────────
  private async updateFileCounts(ncProgramId: number) {
    const [drawings, photos] = await Promise.all([
      this.prisma.ncFile.count({ where: { ncProgramId, fileType: 'DRAWING' } }),
      this.prisma.ncFile.count({ where: { ncProgramId, fileType: 'PHOTO'   } }),
    ]);
    await this.prisma.ncProgram.update({
      where: { id: ncProgramId },
      data:  { drawingCount: drawings, photoCount: photos },
    });
  }
}
