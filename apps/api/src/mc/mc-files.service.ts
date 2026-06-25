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
//   uploadBasePath = /mnt/mc_files (admin設定値)
//   MCファイル格納先: {base}/MC/files/{Programs,Pictures,Drawings,thumbnails,others}
//
//   PG 単体ファイルアップロード:
//     {base}/MC/files/Programs/{machining_id}/{filename}
//   PG フォルダアップロード:
//     {base}/MC/files/Programs/{machining_id}/{元フォルダ名}/{filename}
//   写真:    {base}/MC/files/Pictures/{machining_id}-{n}.jpg
//   図:      {base}/MC/files/Drawings/{machining_id}-{n}.*
//   サムネ:  {base}/MC/files/thumbnails/thumb_{name}.jpg
// ================================================================

@Injectable()
export class McFilesService {
  constructor(private readonly prisma: PrismaService) {}

  private async getBasePath(): Promise<string> {
    const s = await this.prisma.companySetting.findFirst();
    // uploadBasePath (/mnt/mc_files) をベースパスとして使用。
    // 実ファイル: {base}/MC/files/{Programs,Pictures,Drawings,thumbnails,others}
    // 段取シートPDF保存には mcStoragePath を直接使用する（generateSetupSheetPdf参照）。
    return s?.uploadBasePath ?? '/mnt/mc_files';
  }

  private ensureDir(p: string) {
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
  }

  /**
   * ファイルパス解決：DBに保存されたパスが存在しない場合、
   * 複数の代替パスを順番に試して実在するパスを返す。
   * SMBマウント失敗時や段取シート修正後のパス変化に対応。
   */
  private resolveFilePath(filePath: string): string | null {
    if (fs.existsSync(filePath)) return filePath;
    const localBase = '/home/karkyon/projects/machcore/uploads';
    // 候補1: /mnt/mc_files/mc_files/xxx → uploads/mc_files/xxx
    const c1 = filePath.replace(/^\/mnt\/mc_files\/mc_files\//, localBase + '/mc_files/');
    if (c1 !== filePath && fs.existsSync(c1)) return c1;
    // 候補2: /mnt/mc_files/xxx → /mnt/mc_files/MC/files/xxx (パス修正後の旧パス救済)
    const c2 = filePath.replace(/^\/mnt\/mc_files\/(?!MC\/)/, '/mnt/mc_files/MC/files/');
    if (c2 !== filePath && fs.existsSync(c2)) return c2;
    // 候補3: /mnt/ncfiles/mc_files/xxx → uploads/mc_files/xxx
    const c3 = filePath.replace(/^\/mnt\/ncfiles\/mc_files\//, localBase + '/mc_files/');
    if (c3 !== filePath && fs.existsSync(c3)) return c3;
    // 候補4: /mnt/ncfiles/xxx → uploads/mc_files/xxx (フラット)
    const c4 = filePath.replace(/^\/mnt\/ncfiles\//, localBase + '/mc_files/');
    if (c4 !== filePath && fs.existsSync(c4)) return c4;
    // 候補5: ファイル名だけでローカル探索
    const basename = path.basename(filePath);
    for (const sub of ['Pictures', 'Drawings', 'Programs']) {
      const c5 = path.join(localBase, 'MC', 'files', sub, basename);
      if (fs.existsSync(c5)) return c5;
    }
    // 候補6: /mnt/ncfiles/mc_files/xxx → /mnt/mc_files/xxx (SMBマウント先)
    const c6 = filePath.replace(/^\/mnt\/ncfiles\/mc_files\//, '/mnt/mc_files/');
    if (c6 !== filePath && fs.existsSync(c6)) return c6;
    // 候補7: /mnt/ncfiles/xxx → /mnt/mc_files/xxx
    const c7 = filePath.replace(/^\/mnt\/ncfiles\//, '/mnt/mc_files/');
    if (c7 !== filePath && fs.existsSync(c7)) return c7;
    // 候補8: ファイル名だけで /mnt/mc_files/{drawings,photos,pg} を探索
    for (const sub of ['Drawings', 'Pictures', 'Programs']) {
      const c8 = `/mnt/mc_files/MC/files/${sub}/${basename}`;
      if (fs.existsSync(c8)) return c8;
    }
    return null;
  }

  // ── MC オリジナルファイル配信 ──
  async serveFile(fileId: number): Promise<{ filePath: string; mimeType: string; fileName: string }> {
    const file = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!file) throw new Error(`mc_file ${fileId} が存在しません`);
    const resolved = this.resolveFilePath(file.filePath);
    if (!resolved) throw new Error('ファイルが見つかりません: ' + file.filePath);
    return { filePath: resolved, mimeType: file.mimeType, fileName: file.originalName };
  }

  // ── MC ファイルサムネイル配信（キャッシュ付きオンデマンド生成）──
  async serveThumb(fileId: number): Promise<{ filePath: string; mimeType: string }> {
    const file = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!file) throw new Error(`mc_file ${fileId} が存在しません`);

    // 既存サムネがあれば即返す
    if (file.thumbnailPath && fs.existsSync(file.thumbnailPath)) {
      return { filePath: file.thumbnailPath, mimeType: 'image/jpeg' };
    }

    // オリジナルが存在しない場合: 代替パスを探す
    const resolved = this.resolveFilePath(file.filePath);
    if (!resolved) throw new Error(`ファイルが見つかりません: ${file.filePath}`);
    let srcPath = resolved;

    // サムネ生成
    try {
      // thumbDir: SMBマウント先を優先、マウント失敗時はローカルフォールバック
      const smbThumbDir = '/mnt/mc_files/MC/files/thumbnails';
      const localThumbDir = '/home/karkyon/projects/machcore/uploads/mc_files/thumbnails';
      let thumbDir: string;
      try {
        this.ensureDir(smbThumbDir);
        require('fs').accessSync(smbThumbDir, require('fs').constants.W_OK);
        thumbDir = smbThumbDir;
      } catch {
        this.ensureDir(localThumbDir);
        thumbDir = localThumbDir;
      }
      this.ensureDir(thumbDir);
      const ext      = path.extname(file.storedName || file.filePath);
      const baseName = path.basename(file.storedName || file.filePath, ext);
      // PHOTOとDRAWINGでサブディレクトリを分けて名前衝突を防ぐ
      const typeSubDir = file.fileType === 'PHOTO' ? 'photos' : 'drawings';
      const typeThumbDir = path.join(thumbDir, typeSubDir);
      if (!require('fs').existsSync(typeThumbDir)) require('fs').mkdirSync(typeThumbDir, { recursive: true });
      const thumbName = `thumb_${baseName}.jpg`;
      const thumbFull = path.join(typeThumbDir, thumbName);

      await sharp(srcPath)
        .resize(300, 300, { fit: 'inside' })
        .jpeg({ quality: 80 })
        .toFile(thumbFull);

      // DB更新
      await this.prisma.mcFile.update({
        where: { id: fileId },
        data:  { thumbnailPath: thumbFull },
      });

      return { filePath: thumbFull, mimeType: 'image/jpeg' };
    } catch (_thumbErr: any) {
      // サムネ生成失敗時: オリジナルをそのまま返す
      console.warn('[serveThumb] サムネ生成失敗:', _thumbErr?.message, '→ オリジナル返却');
      return { filePath: srcPath, mimeType: file.mimeType };
    }
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
    isFolderUpload?: boolean,
    fileTypeOverride?: 'PHOTO' | 'DRAWING',
    folderName?:     string,
  ) {
    const mc = await this.prisma.mcProgram.findUnique({ where: { id: mcProgramId } });
    if (!mc) throw new NotFoundException(`MC_id ${mcProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const machId   = mc.machiningId;
    const ext      = path.extname(file.filename).toLowerCase();

    const isProgram = this.isProgramFile(file.filename, file.data);
    const isImage   = ['image/jpeg','image/jpg','image/png','image/tiff','image/tif'].includes(file.mimetype)
                     || ['.jpg','.jpeg','.png','.tif','.tiff'].includes(ext);
    const isPdf     = file.mimetype === 'application/pdf' || ext === '.pdf';

    let fileTypeEnum: string;
    if (isProgram)                      fileTypeEnum = 'PROGRAM';
    else if (fileTypeOverride)          fileTypeEnum = fileTypeOverride;
    else if (isImage || isPdf)          fileTypeEnum = ['image/jpeg','image/jpg','image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';
    else                                fileTypeEnum = 'OTHER';

    const pgRole: PgRole = pgRoleOverride !== undefined
      ? pgRoleOverride
      : (fileTypeEnum === 'PROGRAM' ? this.detectPgRole(file.filename, file.data) : null);

    let flatDir: string;
    let storedName: string;
    let sortOrder = 0;
    const debugPathDecision: any = { fileTypeEnum, isFolderUpload, folderName, machId };

    if (fileTypeEnum === 'PROGRAM') {
      const useFolderSubdir = isFolderUpload && !!folderName;
      debugPathDecision.useFolderSubdir = useFolderSubdir;
      flatDir    = useFolderSubdir
        ? path.join(basePath, 'MC', 'files', 'Programs', String(machId), folderName as string)
        : path.join(basePath, 'MC', 'files', 'Programs', String(machId));
      storedName = file.filename;

      const dest = path.join(flatDir, storedName);
      this.ensureDir(flatDir);
      if (fs.existsSync(dest)) {
        const ts      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
        const bakExt  = path.extname(storedName);
        const bakBase = path.basename(storedName, bakExt);
        const trashPg = path.join(basePath, 'trash');
        this.ensureDir(trashPg);
        fs.renameSync(dest, path.join(trashPg, `${bakBase}-${ts}${bakExt}`));
      }

    } else if (fileTypeEnum === 'DRAWING') {
      flatDir = path.join(basePath, 'MC', 'files', 'Drawings');
      const n = this.maxSeq(flatDir, String(machId)) + 1;
      storedName = `${machId}-${n}${ext}`;

    } else if (fileTypeEnum === 'PHOTO') {
      flatDir = path.join(basePath, 'MC', 'files', 'Pictures');
      const n = this.maxSeq(flatDir, String(machId)) + 1;
      storedName = `${machId}-${n}${ext}`;

    } else {
      flatDir = path.join(basePath, 'MC', 'files', 'others');
      storedName = `${machId}-${Date.now()}${ext}`;
    }

    this.ensureDir(flatDir);
    const filePath = path.join(flatDir, storedName);
    fs.writeFileSync(filePath, file.data);
    const fileActuallyExists = fs.existsSync(filePath);

    let thumbnailPath: string | null = null;
    if (isImage && fileTypeEnum !== 'PROGRAM') {
      try {
        const typeSubDir = fileTypeEnum === 'PHOTO' ? 'photos' : 'drawings';
        const thumbDir  = path.join(basePath, 'MC', 'files', 'thumbnails', typeSubDir);
        this.ensureDir(thumbDir);
        const thumbName = `thumb_${path.basename(storedName, ext)}.jpg`;
        const thumbFull = path.join(thumbDir, thumbName);
        await sharp(file.data).resize(300, 300, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbFull);
        thumbnailPath = thumbFull;
      } catch { /* ignore */ }
    }

    const folderNameToSave = (fileTypeEnum === 'PROGRAM' && isFolderUpload && folderName) ? folderName : null;

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
        folderName:   folderNameToSave,
      },
    });

    return {
      id: record.id, message: 'アップロード完了', stored_name: storedName,
      debug: {
        ...debugPathDecision,
        fileActuallyExists,
        folderNameToSave,
        dbRecordFolderName: record.folderName,
        dbRecordFilePath: record.filePath,
      },
    };
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

    // 旧ファイルを trash/ へタイムスタンプ付きで退避してから上書き
    const filePath  = old.filePath;
    this.ensureDir(path.dirname(filePath));
    if (fs.existsSync(filePath)) {
      const tsR      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashR   = path.join(basePath, 'trash');
      this.ensureDir(trashR);
      const rExt     = path.extname(old.storedName);
      const rBase    = path.basename(old.storedName, rExt);
      fs.renameSync(filePath, path.join(trashR, `${rBase}-${tsR}${rExt}`));
    }
    fs.writeFileSync(filePath, file.data);

    // サムネイルも上書き再生成
    // ★修正: UploadAgent経由のアップロードはmimetypeが常にapplication/octet-streamになるため、拡張子もフォールバックで判定する
    const replaceExt = path.extname(file.filename).toLowerCase();
    const isImage = /^image\//i.test(file.mimetype) || ['.jpg','.jpeg','.png','.tif','.tiff'].includes(replaceExt);
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
    // Programs/{machId}/{name} に保存（単体アップロードと同じ構造）
    const flatDir  = path.join(basePath, 'MC', 'files', 'Programs', String(machId));
    this.ensureDir(flatDir);
    const storedName = name;
    const filePath   = path.join(flatDir, storedName);
    if (fs.existsSync(filePath)) {
      const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const bakExt = path.extname(storedName); const bakBase = path.basename(storedName, bakExt);
      const trashDir = path.join(basePath, 'trash'); this.ensureDir(trashDir);
      fs.renameSync(filePath, path.join(trashDir, `${bakBase}-${ts}${bakExt}`));
    }
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
    content: string; encoding: string; originalName: string; fileCount: number; filePath?: string;
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

    // ★仕様: サーバ上の実際のフォルダ構成(folder_nameカラムの有無)で
    //   USB書き出し時の階層を決める。「件数=1なら単体扱い」という旧ロジックは、
    //   フォルダアップロードでも偶然1ファイルしかないケースで階層情報を失うため廃止。
    //   各レコードが個別にfolder_nameを持っているかどうかだけで判定する。
    const files: Array<{ name: string; folderName?: string; content: string }> = [];
    for (const rec of recs) {
      if (!fs.existsSync(rec.filePath)) continue;
      const buf = fs.readFileSync(rec.filePath);
      if (rec.folderName) {
        // フォルダアップロードされたファイル: 元のフォルダ名をそのまま使う
        files.push({ name: rec.originalName, folderName: rec.folderName, content: buf.toString('base64') });
      } else {
        // 単体ファイル: フォルダ階層なし（folderNameキー自体を付けない）
        files.push({ name: rec.originalName, content: buf.toString('base64') });
      }
    }
    if (files.length === 0) throw new NotFoundException('PGファイルが見つかりません');
    return { files };
  }

  async delete(mcProgramId: number, fileId: number) {
    const rec = await this.prisma.mcFile.findUnique({ where: { id: fileId } });
    if (!rec || rec.mcProgramId !== mcProgramId) throw new NotFoundException('ファイルが存在しません');

    const basePath = await this.getBasePath();

    if (fs.existsSync(rec.filePath)) {
      const ts      = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'trash');
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