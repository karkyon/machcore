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
    // MC専用パス (mcStoragePath) を優先、未設定時は uploadBasePath、それも未設定時はデフォルト
    return s?.mcStoragePath ?? s?.uploadBasePath ?? '/mnt/ncfiles/mc_files';
  }

  private ensureDir(p: string) {
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
  }

  // ── MC オリジナルファイル配信 ──
  async serveFile(fileId: number): Promise<{ filePath: string; mimeType: string; fileName: string }> {
    const file = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!file) throw new Error(`mc_file ${fileId} が存在しません`);
    if (!fs.existsSync(file.filePath)) throw new Error('ファイルが見つかりません');
    return { filePath: file.filePath, mimeType: file.mimeType, fileName: file.originalName };
  }

  // ── MC ファイルサムネイル配信（キャッシュ付きオンデマンド生成）──
  async serveThumb(fileId: number): Promise<{ filePath: string; mimeType: string }> {
    const file = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!file) throw new Error(`mc_file ${fileId} が存在しません`);

    // 既存サムネがあれば即返す
    if (file.thumbnailPath && fs.existsSync(file.thumbnailPath)) {
      return { filePath: file.thumbnailPath, mimeType: 'image/jpeg' };
    }

    // オリジナルが存在しない場合はエラー
    if (!fs.existsSync(file.filePath)) throw new Error('ファイルが見つかりません');

    // サムネ生成
    const basePath = await this.getBasePath();
    const thumbDir = path.join(basePath, 'mc_files', 'thumbnails');
    this.ensureDir(thumbDir);
    const ext      = path.extname(file.storedName || file.filePath);
    const baseName = path.basename(file.storedName || file.filePath, ext);
    const thumbName = `thumb_${baseName}.jpg`;
    const thumbFull = path.join(thumbDir, thumbName);

    await sharp(file.filePath)
      .resize(300, 300, { fit: 'inside' })
      .jpeg({ quality: 80 })
      .toFile(thumbFull);

    // DB更新
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  { thumbnailPath: thumbFull },
    });

    return { filePath: thumbFull, mimeType: 'image/jpeg' };
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
    fileTypeOverride?: 'PHOTO' | 'DRAWING',  // フロントから明示指定されたファイル種別
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
    if (isProgram)                      fileTypeEnum = 'PROGRAM';
    else if (fileTypeOverride)          fileTypeEnum = fileTypeOverride;  // フロント指定を最優先
    else if (isImage || isPdf)          fileTypeEnum = ['image/jpeg','image/jpg','image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';
    else                                fileTypeEnum = 'OTHER';

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
        // 同名のファイル（単体アップで作られた pg/{machId} ファイル）が存在したら退避
        const pgFlatFile = path.join(basePath, 'mc_files', 'pg', String(machId));
        if (fs.existsSync(pgFlatFile) && fs.statSync(pgFlatFile).isFile()) {
          const ts2 = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
          fs.renameSync(pgFlatFile, path.join(basePath, 'mc_files', 'pg', `${machId}.bak_${ts2}`));
        }
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

    // 旧ファイルを同じパスで上書き（ファイル数を増やさない）
    const filePath = old.filePath;
    this.ensureDir(path.dirname(filePath));
    fs.writeFileSync(filePath, file.data);

    // サムネイルも上書き再生成
    const isImage = /^image\//i.test(file.mimetype);
    if (isImage && old.thumbnailPath) {
      try {
        this.ensureDir(path.dirname(old.thumbnailPath));
        await sharp(file.data).resize(300, 300, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(old.thumbnailPath);
      } catch { /* ignore */ }
    }

    // DBレコードをそのまま更新（IDは変わらない・ファイルは増えない）
    await this.prisma.mcFile.update({
      where: { id: fileId },
      data:  {
        originalName: file.filename,
        mimeType:     file.mimetype,
        fileSize:     file.data.length,
        uploadedBy,
        uploadedAt:   new Date(),
      },
    });
    return { id: fileId, message: '差し替え完了', stored_name: old.storedName };
  }


  // ── PGファイルテキスト保存（エディタ保存用）─────────────────────
  async savePgContent(
    mcProgramId: number,
    content: string,
    originalName: string | undefined,
    uploadedBy: number,
  ): Promise<{ message: string }> {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const machId   = mc.machiningId;

    // 既存MAINファイルを取得
    const existing = await this.prisma.mcFile.findFirst({
      where: { mcProgramId, fileType: 'PROGRAM', pgRole: 'MAIN', isDeleted: false },
      orderBy: { uploadedAt: 'desc' },
    });

    const iconv = require('iconv-lite') as typeof import('iconv-lite');
    const buf   = iconv.encode(content, 'Shift_JIS');

    if (existing && fs.existsSync(existing.filePath)) {
      // 既存ファイルを上書き
      fs.writeFileSync(existing.filePath, buf);
      // pg_updated_at を更新 (McMachiningDetail)
      await this.prisma.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
      });
      return { message: 'PGファイルを保存しました' };
    }

    // 既存なし → 新規保存
    const name = originalName ?? `${machId}`;
    const flatDir = path.join(basePath, 'mc_files', 'pg');
    this.ensureDir(flatDir);
    const storedName = `${machId}`;
    const filePath   = path.join(flatDir, storedName);
    fs.writeFileSync(filePath, buf);

    await this.prisma.mcFile.create({
      data: {
        mcProgramId,
        fileType:    'PROGRAM',
        pgRole:      'MAIN',
        originalName: name,
        storedName,
        mimeType:    'text/plain',
        filePath,
        fileSize:    buf.length,
        uploadedBy,
        sortOrder:   0,
      },
    });
    await this.prisma.mcMachiningDetail.update({
      where: { machiningId: mc.machiningId },
      data:  { pgUpdatedAt: new Date(), pgCreatedBy: uploadedBy },
    });
    return { message: 'PGファイルを新規保存しました' };
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

  // PG→USB用: ファイル情報+Base64コンテンツを返す（FSA API向け）
  async getPgFileInfo(mcProgramId: number): Promise<{
    files: Array<{ name: string; folderName?: string; content: string }>;
  }> {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException('MCプログラムが存在しません');

    const recs = await this.prisma.mcFile.findMany({
      where:   { mcProgramId, fileType: 'PROGRAM', isDeleted: false },
      orderBy: [{ pgRole: 'asc' }, { uploadedAt: 'asc' }],
    });
    if (recs.length === 0) throw new NotFoundException('PGファイルが存在しません');

    if (recs.length === 1) {
      const rec = recs[0];
      if (!fs.existsSync(rec.filePath)) throw new NotFoundException('PGファイルが見つかりません');
      const buf = fs.readFileSync(rec.filePath);
      return { files: [{ name: rec.originalName, content: buf.toString('base64') }] };
    }

    const folderName = String(mc.machiningId);
    const files: Array<{ name: string; folderName: string; content: string }> = [];
    for (const rec of recs) {
      if (!fs.existsSync(rec.filePath)) continue;
      const buf = fs.readFileSync(rec.filePath);
      files.push({ name: rec.originalName, folderName, content: buf.toString('base64') });
    }
    return { files };
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