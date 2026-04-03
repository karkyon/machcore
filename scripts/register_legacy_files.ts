import * as fs   from 'fs';
import * as path from 'path';
import { PrismaClient } from '@prisma/client';

const NC_BASE = process.env.UPLOAD_BASE_PATH ?? '/mnt/ncfiles';
const DRY_RUN = process.argv.includes('--dry-run');
const prisma  = new PrismaClient();

function scanForFiles(dir: string, prefix: string, exts: string[]): string[] {
  if (!fs.existsSync(dir)) return [];
  const results: string[] = [];
  const lp = prefix.toLowerCase();
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      results.push(...scanForFiles(path.join(dir, entry.name), prefix, exts));
    } else {
      const base = entry.name.toLowerCase();
      const ext  = path.extname(base);
      if (base.startsWith(lp) && exts.includes(ext)) {
        results.push(path.join(dir, entry.name));
      }
    }
  }
  return results.sort();
}

async function main() {
  console.log(`NC_BASE : ${NC_BASE}`);
  console.log(`DRY_RUN : ${DRY_RUN}`);

  const ncs = await prisma.ncProgram.findMany({
    select: { id: true, legacyKid: true },
    where:  { legacyKid: { not: null } },
  });
  console.log(`対象NC: ${ncs.length}件`);

  let ok = 0, skip = 0, missPhoto = 0, missDraw = 0;

  for (const nc of ncs) {
    if (!nc.legacyKid) continue;
    const prefix = `${nc.legacyKid}-`;

    const existing = await prisma.ncFile.count({ where: { ncProgramId: nc.id } });
    if (existing > 0) { skip++; continue; }

    // 写真
    const photos = scanForFiles(path.join(NC_BASE, '写真'), prefix, ['.jpg','.jpeg','.png']);
    if (photos.length === 0) missPhoto++;
    for (const f of photos) {
      console.log(`  PHOTO: ${f}`);
      if (!DRY_RUN) {
        await prisma.ncFile.create({ data: {
          ncProgramId: nc.id, fileType: 'PHOTO',
          originalName: path.basename(f), storedName: path.basename(f),
          mimeType: 'image/jpeg', filePath: f,
          fileSize: fs.statSync(f).size, uploadedBy: 1,
        }});
      }
      ok++;
    }

    // 図
    const drawings = scanForFiles(path.join(NC_BASE, '図'), prefix, ['.tif','.tiff','.png','.jpg']);
    if (drawings.length === 0) missDraw++;
    for (const f of drawings) {
      console.log(`  DRAWING: ${f}`);
      if (!DRY_RUN) {
        const ext = path.extname(f).toLowerCase();
        const mime = (ext==='.tif'||ext==='.tiff') ? 'image/tiff' : 'image/png';
        await prisma.ncFile.create({ data: {
          ncProgramId: nc.id, fileType: 'DRAWING',
          originalName: path.basename(f), storedName: path.basename(f),
          mimeType: mime, filePath: f,
          fileSize: fs.statSync(f).size, uploadedBy: 1,
        }});
      }
      ok++;
    }
  }

  if (!DRY_RUN) {
    console.log('\nphotoCount/drawingCount 更新中...');
    for (const nc of ncs) {
      const [d,p] = await Promise.all([
        prisma.ncFile.count({ where: { ncProgramId: nc.id, fileType: 'DRAWING' } }),
        prisma.ncFile.count({ where: { ncProgramId: nc.id, fileType: 'PHOTO'   } }),
      ]);
      if (d>0||p>0) await prisma.ncProgram.update({
        where: { id: nc.id }, data: { drawingCount: d, photoCount: p },
      });
    }
  }

  console.log(`\n完了: ok=${ok}  skip=${skip}  missPhoto=${missPhoto}  missDraw=${missDraw}`);
  await prisma.$disconnect();
}

main().catch(e => { console.error(e); process.exit(1); });
