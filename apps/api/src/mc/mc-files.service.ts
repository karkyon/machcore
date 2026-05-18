// apps/api/src/mc/mc-files.service.ts
import {
  Injectable, NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import sharp from 'sharp';

const PROGRAM_EXTS = new Set(['.mpf', '.spf', '.nc', '.cnc', '.min', '.prg', '']);

type PgRole = 'MAIN' | 'SUB' | null;

// ================================================================
// ディレクトリ設計
//   PG ケース1（単一ファイル）:
//     {base}/mc_files/pg/{machining_id}        拡張子なし
//     {base}/mc_files/pg/{machining_id}.mpf    拡張子あり
//     ※ファイル名 = machining_id + オリジナル拡張子
//
//   PG ケース2（フォルダ構成・複数ファイル）:
//     {base}/mc_files/pg/{machining_id}/MAIN.mpf
//     {base}/mc_files/pg/{machining_id}/SUB1.spf
//     ※フォルダ名 = machining_id、中のファイル名はオリジナルのまま維持
//
//   写真:    {base}/mc_files/photos/{machining_id}-{n}.jpg
//   図:      {base}/mc_files/drawings/{machining_id}-{n}.*
// ================================================================

@Injectable()
export class McFilesService {
  constructor(private readonly prisma: PrismaService) {}

  private async getBasePath(): Promise<string> {
    const s = await this.prisma.companySetting.findFirst();
    return s?.uploadBasePath ?? '/home/karkyon/projects/machcore/uploads';
  }

  private ensureDir(p: string) {
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
  }

  /** フラットディレクトリ内で {prefix}-{n}.* の最大 n を返す */
  private maxSeq(dir: string, prefix: string): number {
    if (!fs.existsSync(dir)) return 0;
    let max = 0;
    for (const f of fs.readdirSync(dir)) {
      const base = path.basename(f, path.extname(f));
      if (base.startsWith(`${prefix}-`)) {
        const n = parseInt(base.slice(prefix.length + 1), 10);
        if (!isNaN(n) && n > max) max = n;
      }
    }
    return max;
  }

  private isProgramFile(originalName: string, buf: Buffer): boolean {
    const ext = path.extname(originalName).toLowerCase();
    if (PROGRAM_EXTS.has(ext)) return true;
    const head = buf.slice(0, 512).toString('utf8', 0, 512);
    return /O\d{4}|G0\s*X|G1\s*X|G54|CYCLE\d|WORKPIECE/.test(head);
  }

  private detectPgRole(originalName: string, buf: Buffer): PgRole {
    if (!this.isProgramFile(originalName, buf)) return null;
    const ext = path.extname(originalName).toLowerCase();
    if (ext === '.spf') return 'SUB';
    return 'MAIN';
  }

  async listFiles(mcProgramId: number) {
    const rows = await this.prisma.mcFile.findMany({
      where:   { mcProgramId, isDeleted: false },
      orderBy: [{ fileType: 'asc' }, { sortOrder: 'asc' }],
      include: { uploader: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      file_type:      r.fileType,
      pg_role:        r.pgRole,
      sort_order:     r.sortOrder,
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

  async upload(
    mcProgramId:    number,
    uploadedBy:     number,
    file:           { filename: string; mimetype: string; data: Buffer },
    pgRoleOverride?: PgRole,
    isFolderUpload?: boolean,  // true=ケース2（フォルダ構成）、false/undefined=ケース1（単一）
  ) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const machId   = mc.machiningId;  // 加工ID（旧システムの machining_id）
    const ext      = path.extname(file.filename).toLowerCase();

    const isProgram = this.isProgramFile(file.filename, file.data);
    const isImage   = ['image/jpeg','image/jpg','image/png','image/tiff','image/tif'].includes(file.mimetype);
    const isPdf     = file.mimetype === 'application/pdf';

    let fileTypeEnum: string;
    if (isProgram)             fileTypeEnum = 'PROGRAM';
    else if (isImage || isPdf) fileTypeEnum = ['image/jpeg','image/jpg','image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';
    else                       fileTypeEnum = 'OTHER';

    const pgRole: PgRole = pgRoleOverride !== undefined
      ? pgRoleOverride
      : (fileTypeEnum === 'PROGRAM' ? this.detectPgRole(file.filename, file.data) : null);

    // ── パス決定 ──────────────────────────────────────────────
    let flatDir: string;
    let storedName: string;
    let sortOrder = 0;

    if (fileTypeEnum === 'PROGRAM') {
      if (isFolderUpload) {
        // ケース2: フォルダ構成 → {base}/mc_files/pg/{machining_id}/{original_filename}
        flatDir    = path.join(basePath, 'mc_files', 'pg', String(machId));
        storedName = file.filename;  // オリジナルのまま維持
      } else {
        // ケース1: 単一ファイル → {base}/mc_files/pg/{machining_id}[.ext]
        flatDir    = path.join(basePath, 'mc_files', 'pg');
        storedName = `${machId}${ext}`;  // ファイル名=加工ID+拡張子
      }

      // 同名ファイルが既存の場合は .bak_{timestamp} にリネーム退避
      const dest = path.join(flatDir, storedName);
      this.ensureDir(flatDir);
      if (fs.existsSync(dest)) {
        const ts      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
        const bakExt  = path.extname(storedName);
        const bakBase = path.basename(storedName, bakExt);
        fs.renameSync(dest, path.join(flatDir, `${bakBase}.bak_${ts}${bakExt}`));
      }

    } else if (fileTypeEnum === 'DRAWING') {
      flatDir = path.join(basePath, 'mc_files', 'drawings');
      const n = this.maxSeq(flatDir, String(machId)) + 1;
      storedName = `${machId}-${n}${ext}`;

    } else if (fileTypeEnum === 'PHOTO') {
      flatDir = path.join(basePath, 'mc_files', 'photos');
      const n = this.maxSeq(flatDir, String(machId)) + 1;
      storedName = `${machId}-${n}${ext}`;

    } else {
      // OTHER
      flatDir = path.join(basePath, 'mc_files', 'others');
      storedName = `${machId}-${Date.now()}${ext}`;
    }

    this.ensureDir(flatDir);
    const filePath = path.join(flatDir, storedName);
    fs.writeFileSync(filePath, file.data);

    // サムネイル生成（写真・図のみ）
    let thumbnailPath: string | null = null;
    if (isImage && fileTypeEnum !== 'PROGRAM') {
      try {
        const thumbDir  = path.join(basePath, 'mc_files', 'thumbnails');
        this.ensureDir(thumbDir);
        const thumbName = `thumb_${path.basename(storedName, ext)}.jpg`;
        const thumbFull = path.join(thumbDir, thumbName);
        await sharp(file.data).resize(300, 300, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbFull);
        thumbnailPath = thumbFull;
      } catch { /* ignore */ }
    }

    const record = await this.prisma.mcFile.create({
      data: {
        mcProgramId,
        fileType:     fileTypeEnum as any,
        pgRole:       pgRole ?? null,
        sortOrder,
        originalName: file.filename,
        storedName,
        mimeType:     file.mimetype,
        filePath,
        thumbnailPath,
        fileSize:     file.data.length,
        uploadedBy,
      },
    });
    return { id: record.id, message: 'アップロード完了', stored_name: storedName };
  }

  async replace(
    mcProgramId: number,
    fileId:      number,
    uploadedBy:  number,
    file: { filename: string; mimetype: string; data: Buffer },
  ) {
    const old = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!old || old.mcProgramId !== mcProgramId) throw new NotFoundException('ファイルが存在しません');

    const basePath = await this.getBasePath();

    // 旧ファイルをトラッシュへ退避
    if (fs.existsSync(old.filePath)) {
      const ts      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'mc_files', 'trash');
      this.ensureDir(trashDir);
      const ext2    = path.extname(old.storedName);
      fs.renameSync(old.filePath, path.join(trashDir, `${path.basename(old.storedName, ext2)}_${ts}${ext2}`));
    }
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  { isDeleted: true, deletedAt: new Date() },
    });
    return this.upload(mcProgramId, uploadedBy, file, old.pgRole as PgRole);
  }


  // ── PGファイル読み込み（インラインビューア用）──────────────────
  // MAINプログラムを優先、なければ最新PROGRAMを返す
  async getPgFile(mcProgramId: number): Promise<{
    content: string; encoding: string; originalName: string; fileCount: number;
  }> {
    const mainRec = await this.prisma.mcFile.findFirst({
      where:   { mcProgramId, fileType: 'PROGRAM', pgRole: 'MAIN', isDeleted: false },
      orderBy: { uploadedAt: 'desc' },
    });
    const rec = mainRec ?? await this.prisma.mcFile.findFirst({
      where:   { mcProgramId, fileType: 'PROGRAM', isDeleted: false },
      orderBy: { uploadedAt: 'desc' },
    });
    if (!rec || !fs.existsSync(rec.filePath)) {
      throw new NotFoundException('PGファイルが存在しません');
    }
    const totalCount = await this.prisma.mcFile.count({
      where: { mcProgramId, fileType: 'PROGRAM', isDeleted: false },
    });
    const buf = fs.readFileSync(rec.filePath);
    let content: string;
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const iconv = require('iconv-lite') as typeof import('iconv-lite');
      content = iconv.decode(buf, 'Shift_JIS');
    } catch {
      content = buf.toString('utf8');
    }
    return { content, encoding: 'UTF-8', originalName: rec.originalName, fileCount: totalCount };
  }

  // ── PGファイルダウンロード（USB書き出し用）──────────────────────
  // ケース1（単一）: 単体ファイルをそのままDL
  // ケース2（フォルダ構成）: フォルダ内全ファイルをZIPでDL
  async downloadPgFile(mcProgramId: number): Promise<{
    buffer: Buffer; fileName: string; mimeType: string;
  }> {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException('MCプログラムが存在しません');

    const recs = await this.prisma.mcFile.findMany({
      where:   { mcProgramId, fileType: 'PROGRAM', isDeleted: false },
      orderBy: [{ pgRole: 'asc' }, { uploadedAt: 'asc' }],
    });
    if (recs.length === 0) throw new NotFoundException('PGファイルが存在しません');

    if (recs.length === 1) {
      // ケース1: 単一ファイル → そのままDL
      const rec = recs[0];
      if (!fs.existsSync(rec.filePath)) throw new NotFoundException('PGファイルが見つかりません');
      return {
        buffer:   fs.readFileSync(rec.filePath),
        fileName: rec.storedName,       // {machining_id}[.ext]
        mimeType: 'application/octet-stream',
      };
    }

    // ケース2: 複数ファイル → ZIPでDL（ZIP名={machining_id}.zip）
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const archiver = require('archiver');
    const { PassThrough } = require('stream');
    const archive  = archiver('zip', { zlib: { level: 6 } });
    const chunks: Buffer[] = [];
    const pt = new PassThrough();
    pt.on('data', (chunk: Buffer) => chunks.push(chunk));

    await new Promise<void>((resolve, reject) => {
      pt.on('end', resolve);
      pt.on('error', reject);
      archive.on('error', reject);
      archive.pipe(pt);
      for (const rec of recs) {
        if (fs.existsSync(rec.filePath)) {
          // フォルダ内のオリジナルファイル名でZIPに格納
          archive.file(rec.filePath, { name: rec.originalName });
        }
      }
      archive.finalize();
    });

    return {
      buffer:   Buffer.concat(chunks),
      fileName: `${mc.machiningId}.zip`,
      mimeType: 'application/zip',
    };
  }

  async delete(mcProgramId: number, fileId: number) {
    const rec = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!rec || rec.mcProgramId !== mcProgramId) throw new NotFoundException('ファイルが存在しません');

    const basePath = await this.getBasePath();

    if (fs.existsSync(rec.filePath)) {
      const ts      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'mc_files', 'trash');
      this.ensureDir(trashDir);
      const ext2    = path.extname(rec.storedName);
      fs.renameSync(rec.filePath, path.join(trashDir, `${path.basename(rec.storedName, ext2)}_${ts}${ext2}`));
    }
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  { isDeleted: true, deletedAt: new Date() },
    });
    return { message: '削除しました' };
  }
}