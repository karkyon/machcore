import {
  Injectable, NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import sharp from 'sharp';

const PROGRAM_EXTS = new Set(['.mpf', '.spf', '.nc', '.cnc', '.min', '.prg', '']);

type PgRole = 'MAIN' | 'SUB' | null;

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

  private async nextSubSortOrder(mcProgramId: number): Promise<number> {
    const maxRow = await this.prisma.$queryRaw<[{max: number|null}]>`
      SELECT MAX(sort_order) as max FROM mc_files
      WHERE mc_program_id = ${mcProgramId} AND pg_role = 'SUB' AND is_deleted = false
    `;
    return (maxRow[0]?.max ?? 0) + 1;
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
    mcProgramId: number,
    uploadedBy:  number,
    file: { filename: string; mimetype: string; data: Buffer },
    pgRoleOverride?: PgRole,
  ) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const machId   = mc.machiningId;
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

    let subDir: string;
    let storedName: string;

    if (fileTypeEnum === 'PROGRAM') {
      subDir = path.join(basePath, 'mc_files', String(machId), 'pg');
      if (pgRole === 'SUB') {
        const n = await this.nextSubSortOrder(mcProgramId);
        storedName = `${machId}-${n}${ext}`;
      } else {
        storedName = `${machId}${ext}`;
      }
    } else if (fileTypeEnum === 'DRAWING') {
      subDir = path.join(basePath, 'mc_files', String(machId), 'drawings');
      const cnt = await this.prisma.mcFile.count({ where: { mcProgramId, fileType: 'DRAWING', isDeleted: false } });
      storedName = `${machId}-${cnt + 1}${ext}`;
    } else {
      subDir = path.join(basePath, 'mc_files', String(machId), 'photos');
      const cnt = await this.prisma.mcFile.count({ where: { mcProgramId, fileType: 'PHOTO', isDeleted: false } });
      storedName = `${machId}-${cnt + 1}${ext}`;
    }

    this.ensureDir(subDir);
    const filePath = path.join(subDir, storedName);
    fs.writeFileSync(filePath, file.data);

    let thumbnailPath: string | null = null;
    if (isImage) {
      try {
        const thumbDir = path.join(subDir, 'thumbnails');
        this.ensureDir(thumbDir);
        const thumbName = `thumb_${path.basename(storedName, ext)}.jpg`;
        const thumbFull = path.join(thumbDir, thumbName);
        await sharp(file.data).resize(300, 300, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbFull);
        thumbnailPath = thumbFull;
      } catch { /* ignore */ }
    }

    const sortOrder = pgRole === 'SUB' ? await this.nextSubSortOrder(mcProgramId) : 0;

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
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    const machId = mc!.machiningId;

    if (fs.existsSync(old.filePath)) {
      const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'mc_files', String(machId), 'trash');
      this.ensureDir(trashDir);
      const ext2 = path.extname(old.storedName);
      const trashName = `${path.basename(old.storedName, ext2)}_${ts}${ext2}`;
      fs.renameSync(old.filePath, path.join(trashDir, trashName));
    }
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  { isDeleted: true, deletedAt: new Date() },
    });
    return this.upload(mcProgramId, uploadedBy, file, old.pgRole as PgRole);
  }

  async delete(mcProgramId: number, fileId: number) {
    const rec = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!rec || rec.mcProgramId !== mcProgramId) throw new NotFoundException('ファイルが存在しません');

    const basePath = await this.getBasePath();
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    const machId = mc!.machiningId;

    if (fs.existsSync(rec.filePath)) {
      const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'mc_files', String(machId), 'trash');
      this.ensureDir(trashDir);
      const ext2 = path.extname(rec.storedName);
      const trashName = `${path.basename(rec.storedName, ext2)}_${ts}${ext2}`;
      fs.renameSync(rec.filePath, path.join(trashDir, trashName));
    }
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  { isDeleted: true, deletedAt: new Date() },
    });
    return { message: '削除しました' };
  }
}