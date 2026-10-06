import * as fs from 'fs';
import type { PDFDocument, PDFImage } from 'pdf-lib';

export type DrawingFileRef = { filePath: string; mimeType?: string | null; originalName?: string | null };

/**
 * 段取シートPDFの末尾に図(DRAWING)を追加する。
 * 画像は1図1ページ(A4・図の縦横比で縦/横を決めて余白20ptでFIT配置)、PDFの図は全ページをそのまま追加。
 * JPEG/PNG以外(TIFF/BMP/GIF/WebP等)やembedできない画像は sharp でPNGに変換する。
 * 読めない図はスキップしてログのみ(段取シート自体の発行は止めない)。
 */
export async function appendDrawingPages(doc: PDFDocument, files: DrawingFileRef[]): Promise<number> {
  const { PDFDocument: PDFDoc } = await import('pdf-lib');
  const sharp = (await import('sharp')).default;
  const A4W = 595.28, A4H = 841.89, M = 20;
  let added = 0;
  for (const f of files) {
    try {
      if (!f.filePath || !fs.existsSync(f.filePath)) {
        console.warn('[setupsheet] 図ファイルが見つかりません:', f.filePath);
        continue;
      }
      const buf = fs.readFileSync(f.filePath);
      const mime = (f.mimeType ?? '').toLowerCase();
      const name = (f.originalName ?? f.filePath).toLowerCase();
      if (mime.includes('pdf') || name.endsWith('.pdf')) {
        const src = await PDFDoc.load(buf, { ignoreEncryption: true });
        const pages = await doc.copyPages(src, src.getPageIndices());
        pages.forEach(p => doc.addPage(p));
        added += pages.length;
        continue;
      }
      let img: PDFImage;
      try {
        if (mime.includes('png') || name.endsWith('.png')) img = await doc.embedPng(buf);
        else if (mime.includes('jpeg') || mime.includes('jpg') || /\.jpe?g$/.test(name)) img = await doc.embedJpg(buf);
        else img = await doc.embedPng(await sharp(buf).png().toBuffer());
      } catch {
        img = await doc.embedPng(await sharp(buf).png().toBuffer());
      }
      const landscape = img.width > img.height;
      const pw = landscape ? A4H : A4W;
      const ph = landscape ? A4W : A4H;
      const s = Math.min((pw - 2 * M) / img.width, (ph - 2 * M) / img.height);
      const w = img.width * s, h = img.height * s;
      const page = doc.addPage([pw, ph]);
      page.drawImage(img, { x: (pw - w) / 2, y: (ph - h) / 2, width: w, height: h });
      added++;
    } catch (e: any) {
      console.warn('[setupsheet] 図の追加に失敗:', f.filePath, e?.message);
    }
  }
  return added;
}
