// apps/api/src/nc/nc-files.service.ts
// MC側 McFilesService.upload と同設計のNC版。MC/NCでストレージを完全分離する。
import {
  Injectable, NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import sharp from 'sharp';
// ★NC側PROGRAM(USB自動アップロード)対応: MC側と同一の命名ロジックを再利用する。
import { calcProgramFileName, calcProgramFolderName } from '../mc/program-file-naming.util';

const PROGRAM_EXTS = new Set(['.mpf', '.spf', '.nc', '.cnc', '.min', '.prg', '']);
type PgRole = 'MAIN' | 'SUB' | null;

// ================================================================
// ディレクトリ設計（MC側 McFilesService と同パターン、MC/NC完全分離）
//   uploadBasePath = /mnt/mc_files (admin設定値、MC/NC共通のベースパス)
//   NCファイル格納先: {base}/NC/files/{Pictures,Drawings,thumbnails}
//   写真:    {base}/NC/files/Pictures/{nc_program_id}-{n}.jpg
//   図:      {base}/NC/files/Drawings/{nc_program_id}-{n}.*
//   サムネ:  {base}/NC/files/thumbnails/{photos,drawings}/thumb_{name}.jpg
// ================================================================

@Injectable()
export class NcFilesService {
  constructor(private readonly prisma: PrismaService) {}

  private async getBasePath(): Promise<string> {
    const s = await this.prisma.companySetting.findFirst();
    return s?.uploadBasePath ?? '/mnt/mc_files';
  }

  private ensureDir(p: string) {
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
  }

  private maxSeq(dir: string, prefix: string): number {
    if (!fs.existsSync(dir)) return 0;
    const re = new RegExp(`^${prefix}-(\\d+)\\.`);
    let max = 0;
    for (const name of fs.readdirSync(dir)) {
      const m = name.match(re);
      if (m) max = Math.max(max, parseInt(m[1], 10));
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

  /**
   * ★NC側PROGRAM(USB自動アップロード)対応: MC側resolveUploadNamingと同じ考え方で、
   * 機械マスタ(Machine.pgIsFolder)に基づき権威的なファイル名/フォルダ名を算出する。
   * NcMachiningDetail.folderName/fileNameはレガシーインポート由来の別概念のため
   * 一切参照せず、常にMachine.pgIsFolderからその場で計算する。
   */
  private async resolveUploadNaming(kId: number): Promise<{ isFolder: boolean; fileName: string; folderName: string | null }> {
    const detail = await this.prisma.ncMachiningDetail.findUnique({
      where:  { kId },
      select: { machineId: true },
    });
    let isFolder = false;
    if (detail?.machineId) {
      const machine = await this.prisma.machine.findUnique({ where: { id: detail.machineId }, select: { pgIsFolder: true } });
      isFolder = !!machine?.pgIsFolder;
    }
    if (isFolder) {
      return { isFolder: true, fileName: '', folderName: calcProgramFolderName(kId) };
    }
    return { isFolder: false, fileName: calcProgramFileName(kId), folderName: null };
  }

  /** UploadAgent向け: USB自動アップロードのticket発行時に期待ファイル名/フォルダ名を公開する。 */
  async getExpectedUploadTarget(kId: number): Promise<{ isFolder: boolean; fileName: string; folderName: string | null }> {
    return this.resolveUploadNaming(kId);
  }

  /**
   * ★重複登録バグ防止(MC側と同方式): PROGRAM新規アップロード前に、既存の有効な
   * PROGRAM系レコード一式(単体ファイル or フォルダごと)をtrashへ退避し、isDeleted化する。
   * 共通部品(同一K_idを複数のNcProgram行が共有)の場合、siblingの全ncProgramIdに
   * またがる有効レコードを対象にする。
   */
  private async purgeExistingProgramFiles(
    kId: number,
    programNaming: { isFolder: boolean; fileName: string; folderName: string | null },
  ): Promise<void> {
    const basePath = await this.getBasePath();
    const ts        = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
    const trashDir  = path.join(basePath, 'trash');

    if (programNaming.isFolder) {
      const folderPath = path.join(basePath, 'NC', 'files', 'Programs', String(kId), programNaming.folderName as string);
      if (fs.existsSync(folderPath)) {
        this.ensureDir(trashDir);
        let dest = path.join(trashDir, `${programNaming.folderName}_${ts}`);
        if (fs.existsSync(dest)) dest = path.join(trashDir, `${programNaming.folderName}_${ts}_${Date.now()}`);
        fs.renameSync(folderPath, dest);
      }
    } else {
      const filePath = path.join(basePath, 'NC', 'files', 'Programs', String(kId), programNaming.fileName);
      if (fs.existsSync(filePath)) {
        this.ensureDir(trashDir);
        const ext  = path.extname(programNaming.fileName);
        const base = path.basename(programNaming.fileName, ext);
        let dest = path.join(trashDir, `${base}_${ts}${ext}`);
        if (fs.existsSync(dest)) dest = path.join(trashDir, `${base}_${ts}_${Date.now()}${ext}`);
        fs.renameSync(filePath, dest);
      }
    }

    const siblings = await this.prisma.ncProgram.findMany({
      where:  { machiningId: kId },
      select: { id: true },
    });
    const siblingIds = siblings.map(s => s.id);
    if (siblingIds.length === 0) return;

    const olds = await this.prisma.ncFile.findMany({
      where:  { ncProgramId: { in: siblingIds }, fileType: 'PROGRAM' as any, isDeleted: false },
      select: { id: true },
    });
    if (olds.length > 0) {
      await this.prisma.ncFile.updateMany({
        where: { id: { in: olds.map(o => o.id) } },
        data:  { isDeleted: true, deletedAt: new Date() },
      });
    }
  }

  // ★NC側PROGRAM(USB自動アップロード)対応で isFolderUpload/folderName/purgeExisting を追加。
  //   PHOTO/DRAWINGでは引き続き無視される。fileTypeOverrideに'PROGRAM'を指定する呼び出し元は
  //   nc.controller.ts の uploadByTicket() のみ。
  async upload(
    ncProgramId: number,
    uploadedBy:  number,
    file:        { filename: string; mimetype: string; data: Buffer },
    fileTypeOverride?: 'PHOTO' | 'DRAWING' | 'PROGRAM',
    isFolderUpload?: boolean,
    folderName?: string,
    purgeExisting?: boolean,
  ) {
    const nc = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { id: true, machiningId: true },
    });
    if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const kId      = nc.machiningId;
    const ext      = path.extname(file.filename).toLowerCase();

    const isProgram = this.isProgramFile(file.filename, file.data);
    const isImage   = ['image/jpeg', 'image/jpg', 'image/png', 'image/tiff', 'image/tif'].includes(file.mimetype)
                     || ['.jpg', '.jpeg', '.png', '.tif', '.tiff'].includes(ext);

    let fileTypeEnum: 'PHOTO' | 'DRAWING' | 'PROGRAM';
    if (isProgram) fileTypeEnum = 'PROGRAM';
    else if (fileTypeOverride && fileTypeOverride !== 'PROGRAM') fileTypeEnum = fileTypeOverride;
    else fileTypeEnum = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';

    if (fileTypeEnum === 'PROGRAM') {
      const pgRole: PgRole = this.detectPgRole(file.filename, file.data);
      const programNaming = await this.resolveUploadNaming(kId);

      if (purgeExisting) {
        await this.purgeExistingProgramFiles(kId, programNaming);
      }

      let flatDir: string;
      let storedName: string;
      let folderNameToSave: string | null = null;

      if (programNaming.isFolder) {
        flatDir = path.join(basePath, 'NC', 'files', 'Programs', String(kId), programNaming.folderName as string);
        // フォルダ内の個別ファイルはメインPG/サブPGの実名のため、ファイル名は維持する
        storedName = file.filename;
        folderNameToSave = programNaming.folderName;
      } else {
        flatDir = path.join(basePath, 'NC', 'files', 'Programs', String(kId));
        // 単体ファイルは加工ID(K_id)の下4桁に強制変換する(元ファイル名・拡張子は使用しない)
        storedName = programNaming.fileName;
      }

      this.ensureDir(flatDir);
      const filePath = path.join(flatDir, storedName);
      // purgeExisting実行後は通常ここに到達しないが、念のためのフォールバック
      if (fs.existsSync(filePath)) {
        const tsFallback = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
        const trashPg = path.join(basePath, 'trash');
        this.ensureDir(trashPg);
        const bakExt  = path.extname(storedName);
        const bakBase = path.basename(storedName, bakExt);
        fs.renameSync(filePath, path.join(trashPg, `${bakBase}-${tsFallback}${bakExt}`));
      }
      fs.writeFileSync(filePath, file.data);

      // ★共通部品(同一K_idを複数のNcProgram行が共有)対応: PHASE5インポートと同じく、
      //   siblingの全ncProgramIdに同じPROGRAMファイルレコードを登録する。
      const siblings = await this.prisma.ncProgram.findMany({
        where:  { machiningId: kId },
        select: { id: true },
      });
      const targetIds = siblings.length > 0 ? siblings.map(s => s.id) : [ncProgramId];

      let firstRecordId: number | null = null;
      for (const targetId of targetIds) {
        const rec = await this.prisma.ncFile.create({
          data: {
            ncProgramId:  targetId,
            fileType:     'PROGRAM' as any,
            pgRole:       pgRole ?? null,
            originalName: file.filename,
            storedName,
            mimeType:     file.mimetype,
            filePath,
            fileSize:     file.data.length,
            uploadedBy,
            folderName:   folderNameToSave,
          },
        });
        if (firstRecordId === null) firstRecordId = rec.id;
      }

      return { id: firstRecordId, message: 'アップロード完了', stored_name: storedName };
    }

    // ── 以降は既存のPHOTO/DRAWING処理(変更なし) ──
    const subDirName = fileTypeEnum === 'PHOTO' ? 'Pictures' : 'Drawings';
    const flatDir     = path.join(basePath, 'NC', 'files', subDirName);
    const n           = this.maxSeq(flatDir, String(ncProgramId)) + 1;
    const storedName  = `${ncProgramId}-${n}${ext}`;

    this.ensureDir(flatDir);
    const filePath = path.join(flatDir, storedName);
    fs.writeFileSync(filePath, file.data);

    let thumbnailPath: string | null = null;
    if (isImage) {
      try {
        const typeSubDir = fileTypeEnum === 'PHOTO' ? 'photos' : 'drawings';
        const thumbDir  = path.join(basePath, 'NC', 'files', 'thumbnails', typeSubDir);
        this.ensureDir(thumbDir);
        const thumbName = `thumb_${path.basename(storedName, ext)}.jpg`;
        const thumbFull = path.join(thumbDir, thumbName);
        await sharp(file.data).resize(300, 300, { fit: 'inside' }).jpeg({ quality: 80 }).toFile(thumbFull);
        thumbnailPath = thumbFull;
      } catch { /* ignore */ }
    }

    const record = await this.prisma.ncFile.create({
      data: {
        ncProgramId,
        fileType:     fileTypeEnum as any,
        originalName: file.filename,
        storedName,
        mimeType:     file.mimetype,
        filePath,
        thumbnailPath,
        fileSize:     file.data.length,
        uploadedBy,
      },
    });

    await this.updateFileCounts(ncProgramId);

    return { id: record.id, message: 'アップロード完了', stored_name: storedName };
  }

  // [v085] 共通部品(同一K_idを複数のNcProgram行が共有するケース)対応の
  //   sibling ncProgramId解決ヘルパー。詳細は nc.service.ts の同名メソッド参照。
  private async resolveSiblingNcProgramIds(ncProgramId: number): Promise<number[]> {
    const prog = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { machiningId: true },
    });
    if (!prog) return [ncProgramId];
    const siblings = await this.prisma.ncProgram.findMany({
      where:  { machiningId: prog.machiningId },
      select: { id: true },
    });
    return siblings.map(s => s.id);
  }

  // [v085] 共通部品で件数が特定のncProgramIdだけに基づいて上書きされ、他の行からの
  //   アップロード分が消えたように見える不具合を修正。
  private async updateFileCounts(ncProgramId: number) {
    const prog = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { machiningId: true },
    });
    if (!prog) return;
    const ids = await this.resolveSiblingNcProgramIds(ncProgramId);
    const [photoCount, drawingCount] = await Promise.all([
      this.prisma.ncFile.count({ where: { ncProgramId: { in: ids }, fileType: 'PHOTO' } }),
      this.prisma.ncFile.count({ where: { ncProgramId: { in: ids }, fileType: 'DRAWING' } }),
    ]);
    await this.prisma.ncMachiningDetail.update({
      where: { kId: prog.machiningId },
      data:  { photoCount, drawingCount },
    });
  }
}
