#!/usr/bin/env python3
"""
fix_v101c.py
============
pdf-repeat-preview エンドポイントを修正：
  ?template=repeat_header の場合 → assets/repeat_header.pdf をそのまま返す
  ?template=repeat_tooling   → assets/repeat_tooling.pdf
  ?template=repeat_wo        → assets/repeat_wo.pdf
  ?template=repeat_ip        → assets/repeat_ip.pdf
  ?template=repeat_p2        → assets/template_repeat_p2.pdf
  template 未指定             → 従来通り generateRepeatSetupSheetPdf() でフル生成

また pdf-preview (新規段取シート) も同様に：
  ?template=mc_setup_p1 → assets/template_p1.pdf を直接返す
  ?template=mc_setup_p2 → assets/template_p2.pdf を直接返す
  template 未指定        → 従来通り generateSetupSheetPdf() でフル生成
"""

import subprocess, sys

PROJECT = "/home/karkyon/projects/machcore"

def run(cmd, cwd=PROJECT, check=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"ERROR: {cmd}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}")
        sys.exit(1)
    return r.stdout, r.stderr

CTRL_PATH = f"{PROJECT}/apps/api/src/admin/admin.controller.ts"
with open(CTRL_PATH, "r") as f:
    ctrl = f.read()

# ── pdf-repeat-preview エンドポイントを全置換 ──────────────────────────────
OLD_REPEAT = '''  /** リピート段取シートPDFプレビュー生成（is_preview=true） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-repeat-preview')
  async getRepeatPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({
        where: { status: { not: 'NEW' } },
        orderBy: { id: 'desc' },
      });
      if (!first) {
        const any = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
        if (!any) throw new BadRequestException('MCプログラムが存在しません');
        mcId = any.id;
      } else {
        mcId = first.id;
      }
    }
    const pdf = await this.mcService.generateRepeatSetupSheetPdf(mcId, 1, {
      include_tooling:        true,
      include_clamp:          true,
      include_work_offsets:   true,
      include_index_programs: true,
      is_preview:             true,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="repeat-preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }'''

NEW_REPEAT = '''  /** リピート段取シートPDFプレビュー生成
   *  ?template=repeat_header  → repeat_header.pdf をそのまま返す（デザイナー用）
   *  ?template=repeat_tooling → repeat_tooling.pdf
   *  ?template=repeat_wo      → repeat_wo.pdf
   *  ?template=repeat_ip      → repeat_ip.pdf
   *  ?template=repeat_p2      → template_repeat_p2.pdf
   *  template未指定           → generateRepeatSetupSheetPdf() でフル生成
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-repeat-preview')
  async getRepeatPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = require('fs') as typeof import('fs');

    // テンプレート名 → ファイル名マップ
    const TPL_FILE_MAP: Record<string, string> = {
      'repeat_header':  'repeat_header.pdf',
      'repeat_tooling': 'repeat_tooling.pdf',
      'repeat_wo':      'repeat_wo.pdf',
      'repeat_ip':      'repeat_ip.pdf',
      'repeat_p2':      'template_repeat_p2.pdf',
    };

    // テンプレート名が指定されていてファイルが存在する → そのまま返す
    if (templateName && TPL_FILE_MAP[templateName]) {
      const filePath = `${ASSETS}/${TPL_FILE_MAP[templateName]}`;
      if (fs2.existsSync(filePath)) {
        const buf = fs2.readFileSync(filePath);
        reply.header('Content-Type',        'application/pdf');
        reply.header('Content-Disposition', `inline; filename="${TPL_FILE_MAP[templateName]}"`);
        reply.header('Content-Length',      String(buf.length));
        return reply.send(buf);
      }
      // ファイルが存在しない場合は空PDFを返す
      const { PDFDocument } = await import('pdf-lib');
      const emptyDoc = await PDFDocument.create();
      emptyDoc.addPage([595, 842]);
      const emptyBytes = await emptyDoc.save();
      reply.header('Content-Type',        'application/pdf');
      reply.header('Content-Disposition', `inline; filename="empty.pdf"`);
      reply.header('Content-Length',      String(emptyBytes.length));
      return reply.send(Buffer.from(emptyBytes));
    }

    // template未指定 → フル段取シート生成（従来動作）
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({
        where: { status: { not: 'NEW' } },
        orderBy: { id: 'desc' },
      });
      if (!first) {
        const any = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
        if (!any) throw new BadRequestException('MCプログラムが存在しません');
        mcId = any.id;
      } else {
        mcId = first.id;
      }
    }
    const pdf = await this.mcService.generateRepeatSetupSheetPdf(mcId, 1, {
      include_tooling:        true,
      include_clamp:          true,
      include_work_offsets:   true,
      include_index_programs: true,
      is_preview:             true,
    });
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="repeat-preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }'''

if OLD_REPEAT in ctrl:
    ctrl = ctrl.replace(OLD_REPEAT, NEW_REPEAT)
    print("OK: pdf-repeat-preview エンドポイント修正")
else:
    print("ERROR: pdf-repeat-preview の置換パターンが一致しません")
    # パターン確認用
    idx = ctrl.find("async getRepeatPdfPreview")
    if idx >= 0:
        print(f"  関数は行{ctrl[:idx].count(chr(10))+1}に存在。手動確認が必要")
    sys.exit(1)

# ── pdf-preview (新規段取シート) も同様にテンプレ直接返しに対応 ──────────────
OLD_PREVIEW = '''  /** PDFプレビュー生成（最初のMCプログラムを使用、is_preview=true） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-preview')
  async getPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Res() reply?: any,
  ) {
    // mc_id が指定されていない場合は最初のMCプログラムを使用
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
      if (!first) throw new BadRequestException('MCプログラムが存在しません');
      mcId = first.id;
    }
    const pdf = await this.mcService.generateSetupSheetPdf(mcId, 1, {
      include_tooling: false,
      include_clamp:   false,
      is_preview:      true,
    } as any);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }'''

NEW_PREVIEW = '''  /** PDFプレビュー生成（新規段取シート）
   *  ?template=mc_setup_p1 → template_p1.pdf をそのまま返す（デザイナー用）
   *  ?template=mc_setup_p2 → template_p2.pdf をそのまま返す
   *  template未指定         → generateSetupSheetPdf() でフル生成
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('pdf-preview')
  async getPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = require('fs') as typeof import('fs');

    const NEW_TPL_FILE_MAP: Record<string, string> = {
      'mc_setup_p1': 'template_p1.pdf',
      'mc_setup_p2': 'template_p2.pdf',
    };

    if (templateName && NEW_TPL_FILE_MAP[templateName]) {
      const filePath = `${ASSETS}/${NEW_TPL_FILE_MAP[templateName]}`;
      if (fs2.existsSync(filePath)) {
        const buf = fs2.readFileSync(filePath);
        reply.header('Content-Type',        'application/pdf');
        reply.header('Content-Disposition', `inline; filename="${NEW_TPL_FILE_MAP[templateName]}"`);
        reply.header('Content-Length',      String(buf.length));
        return reply.send(buf);
      }
    }

    // template未指定 or ファイルなし → フル生成（従来動作）
    let mcId = mcIdStr ? parseInt(mcIdStr) : 0;
    if (!mcId) {
      const first = await this.prisma.mcProgram.findFirst({ orderBy: { id: 'asc' } });
      if (!first) throw new BadRequestException('MCプログラムが存在しません');
      mcId = first.id;
    }
    const pdf = await this.mcService.generateSetupSheetPdf(mcId, 1, {
      include_tooling: false,
      include_clamp:   false,
      is_preview:      true,
    } as any);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', `inline; filename="preview-${mcId}.pdf"`);
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }'''

if OLD_PREVIEW in ctrl:
    ctrl = ctrl.replace(OLD_PREVIEW, NEW_PREVIEW)
    print("OK: pdf-preview エンドポイント修正（新規段取シートもテンプレ直接返し対応）")
else:
    print("WARN: pdf-preview の置換パターン不一致（スキップ）")

with open(CTRL_PATH, "w") as f:
    f.write(ctrl)
print("OK: admin.controller.ts 書き込み完了")

# フロント側も loadPreview で template パラメータを新規段取シートにも渡すよう修正
PAGE_PATH = f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx"
with open(PAGE_PATH, "r") as f:
    page = f.read()

OLD_LOAD_PREVIEW = '''  const loadPreview = async () => {
    setPdfLoading(true);
    try {
      const isRepeat = selTpl.startsWith("repeat_");
      let endpoint: string;
      if (isRepeat) {
        const q = new URLSearchParams({ template: selTpl });
        if (mcIdInput) q.set("mc_id", mcIdInput);
        endpoint = `/admin/pdf-repeat-preview?${q.toString()}`;
      } else {
        endpoint = `/admin/pdf-preview${mcIdInput ? `?mc_id=${mcIdInput}` : ""}`;
      }'''

NEW_LOAD_PREVIEW = '''  const loadPreview = async () => {
    setPdfLoading(true);
    try {
      const isRepeat = selTpl.startsWith("repeat_");
      let endpoint: string;
      if (isRepeat) {
        // リピート: テンプレートPDFをそのまま返す（mc_id不要、template必須）
        const q = new URLSearchParams({ template: selTpl });
        if (mcIdInput) q.set("mc_id", mcIdInput);
        endpoint = `/admin/pdf-repeat-preview?${q.toString()}`;
      } else {
        // 新規段取シート: テンプレートPDFをそのまま返す（mc_id不要、template必須）
        const q = new URLSearchParams({ template: selTpl });
        if (mcIdInput) q.set("mc_id", mcIdInput);
        endpoint = `/admin/pdf-preview?${q.toString()}`;
      }'''

if OLD_LOAD_PREVIEW in page:
    page = page.replace(OLD_LOAD_PREVIEW, NEW_LOAD_PREVIEW)
    print("OK: page.tsx loadPreview 修正（新規段取シートにも template パラメータ追加）")
else:
    print("WARN: page.tsx loadPreview パターン不一致（スキップ）")

with open(PAGE_PATH, "w") as f:
    f.write(page)
print("OK: page.tsx 書き込み完了")

# API ビルド
print("\n--- API ビルド ---")
out, err = run("pnpm --filter api build", check=False)
ts_errors = [l for l in (out+err).split("\n") if "error TS" in l]
print(f"TypeScriptエラー: {len(ts_errors)} 件")
if ts_errors:
    for e in ts_errors[:20]: print(f"  {e}")
    sys.exit(1)
if "ERR_PNPM" in err or "ERR_PNPM" in out:
    print("API ビルド失敗"); print(err[-2000:]); sys.exit(1)
print("API ビルド成功!")

# WEB ビルド
print("\n--- WEB ビルド ---")
out, err = run("pnpm --filter web build", check=False)
if "ERR_PNPM" in err or "ERR_PNPM" in out:
    print("WEB ビルド失敗"); print(out[-1000:]); print(err[-1000:]); sys.exit(1)
print("WEB ビルド成功!")

print("\n--- PM2 restart ---")
run("pm2 restart machcore-api machcore-web")
print("PM2 再起動完了")

print("\n--- git push ---")
run("git add -A")
run('git commit -m "fix(v101c): PDFエディタ プレビューをテンプレートPDF直接返しに修正"')
run("git push origin main")

print("""
fix_v101c 完了

【修正内容】
PDFエディタのプレビューは「選択中テンプレートPDFファイルをそのまま返す」方式に変更。
  repeat_header  → assets/repeat_header.pdf
  repeat_tooling → assets/repeat_tooling.pdf
  repeat_wo      → assets/repeat_wo.pdf
  repeat_ip      → assets/repeat_ip.pdf
  repeat_p2      → assets/template_repeat_p2.pdf
  mc_setup_p1    → assets/template_p1.pdf
  mc_setup_p2    → assets/template_p2.pdf

これにより各テンプレートを選択した時に
そのテンプレートのレイアウトそのものがプレビューに表示されます。
MC_ID入力は「テンプレートなし」の場合（フル段取シート確認用）にのみ使用します。
""")
