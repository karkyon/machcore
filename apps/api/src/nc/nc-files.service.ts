// apps/api/src/nc/nc-files.service.ts
// MC側 McFilesService.upload と同設計のNC版。MC/NCでストレージを完全分離する。
import {
  Injectable, NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import sharp from 'sharp';

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

  async upload(
    ncProgramId: number,
    uploadedBy:  number,
    file:        { filename: string; mimetype: string; data: Buffer },
    fileTypeOverride?: 'PHOTO' | 'DRAWING',
  ) {
    const nc = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { id: true, machiningId: true },
    });
    if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);

    const basePath = await this.getBasePath();
    const ext      = path.extname(file.filename).toLowerCase();

    const isImage = ['image/jpeg', 'image/jpg', 'image/png', 'image/tiff', 'image/tif'].includes(file.mimetype)
                   || ['.jpg', '.jpeg', '.png', '.tif', '.tiff'].includes(ext);

    let fileTypeEnum: 'PHOTO' | 'DRAWING';
    if (fileTypeOverride) fileTypeEnum = fileTypeOverride;
    else fileTypeEnum = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.mimetype) ? 'PHOTO' : 'DRAWING';

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
