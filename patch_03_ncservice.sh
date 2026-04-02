#!/bin/bash
# SCR-04: nc.service.ts 「図を含める」PDF埋め込み実装パッチ
# 適用先: ~/projects/machcore/apps/api/src/nc/nc.service.ts

TARGET=~/projects/machcore/apps/api/src/nc/nc.service.ts

cp "$TARGET" "${TARGET}.bak_drawings_$(date +%Y%m%d_%H%M%S)"

python3 << 'PYEOF'
import re

target = '/home/karkyon/projects/machcore/apps/api/src/nc/nc.service.ts'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. generateSetupSheetPdf で drawings をBase64に変換してから buildSetupSheetHtml に渡す ───
# 元: const html = this.buildSetupSheetHtml(data, options);
old_build_call = '''    const html = this.buildSetupSheetHtml(data, options);'''
new_build_call = '''    // 図ファイルをBase64に変換（include_drawings=true の場合）
    const drawingBase64s: string[] = [];
    if (options.include_drawings !== false && data.files && data.files.length > 0) {
      const sharp = (await import('sharp')).default;
      for (const f of data.files.slice(0, 3)) {  // 最大3枚
        try {
          const filePath = (f as any).filePath ?? (f as any).file_path;
          if (!filePath || !fs.existsSync(filePath)) continue;
          const buf = fs.readFileSync(filePath);
          const mime = (f as any).mimeType ?? (f as any).mime_type ?? '';
          let imgBuf: Buffer;
          if (mime.includes('tiff') || mime.includes('tif')) {
            imgBuf = await sharp(buf).png().toBuffer();
            drawingBase64s.push(`data:image/png;base64,${imgBuf.toString('base64')}`);
          } else if (mime.includes('pdf')) {
            // PDFは埋め込みスキップ（テキストで注記のみ）
            drawingBase64s.push(`__PDF__:${(f as any).originalName ?? 'drawing.pdf'}`);
          } else {
            drawingBase64s.push(`data:${mime};base64,${buf.toString('base64')}`);
          }
        } catch (e) {
          console.warn('Drawing embed failed:', e);
        }
      }
    }
    const html = this.buildSetupSheetHtml(data, { ...options, drawingBase64s });'''

content = content.replace(old_build_call, new_build_call, 1)

# ─── 2. buildSetupSheetHtml で drawingBase64s を処理 ───
# 既存の includeClamp の定義の後に drawingsSection を追加
old_include_clamp = '''  const includeTools    = opts.include_tools    !== false;
  const includeClamp    = opts.include_clamp    !== false;'''

new_include_clamp = '''  const includeTools    = opts.include_tools    !== false;
  const includeClamp    = opts.include_clamp    !== false;
  const includeDrawings = opts.include_drawings === true;
  const drawingBase64s: string[] = opts.drawingBase64s ?? [];

  const drawingsSection = (includeDrawings && drawingBase64s.length > 0) ? `
    <section style="margin-bottom:12px;page-break-inside:avoid;">
      <h3 class="sec-title">段取図</h3>
      <div style="display:flex;flex-direction:column;gap:10px;">
        ${drawingBase64s.map((src: string, i: number) => {
          if (src.startsWith('__PDF__:')) {
            const name = src.replace('__PDF__:', '');
            return \`<p style="font-size:9pt;color:#555;">📄 PDF図面: \${name}（PDF埋め込み非対応のため省略）</p>\`;
          }
          return \`<img src="\${src}" alt="段取図\${i + 1}" style="max-width:100%;height:auto;border:1px solid #e2e8f0;border-radius:4px;" />\`;
        }).join('')}
      </div>
    </section>
  ` : '';'''

content = content.replace(old_include_clamp, new_include_clamp, 1)

# ─── 3. HTML テンプレート内の </body> 直前に drawingsSection を挿入 ───
old_body_end = '''        ${clampSection}
        ${toolRows}
      </body>'''
new_body_end = '''        ${clampSection}
        ${drawingsSection}
        ${toolRows}
      </body>'''

content = content.replace(old_body_end, new_body_end, 1)

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ nc.service.ts パッチ適用完了")
PYEOF
