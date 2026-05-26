#!/usr/bin/env python3
"""
fix_v94: mc/new/print/page.tsx にプレビューボタンとキャンセルボタンを追加
APIに POST /mc/preview-new（一時MC作成→透かし入りPDF→ロールバック）を追加
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def rep(content, old, new, label):
    if old not in content:
        print(f"WARN: {label} — 不一致"); return content
    print(f"OK: {label}"); return content.replace(old, new, 1)

# ① mc.service.ts に previewNew 追加
MC_SVC = f"{ROOT}/apps/api/src/mc/mc.service.ts"
svc = read(MC_SVC)

PREVIEW_NEW_FN = '''
  // ══════════════════════════════════════════
  // 新規仮データでプレビューPDF生成（DBに保存しない）
  // ══════════════════════════════════════════
  async previewNew(dto: any, operatorId: number): Promise<Buffer> {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);
    const machine = dto.machine_id
      ? await this.prisma.machine.findUnique({ where: { id: dto.machine_id } })
      : null;

    // 一時MCレコードを作成してPDF生成し、その後削除
    const tempMc = await this.prisma.mcProgram.create({
      data: {
        partId:       dto.part_id,
        machiningId:  dto.machining_id,
        mcProcessNo:  dto.mc_process_no ?? null,
        machineId:    dto.machine_id    ?? null,
        oNumber:      dto.o_number      ?? null,
        machiningQty: dto.machining_qty ?? 1,
        note:         dto.note          ?? null,
        legacyMcid:   dto.machining_id,
        registeredBy: operatorId,
        status:       'NEW',
        version:      '0.0001',
      },
    });

    try {
      const pdfBuffer = await this.generateSetupSheetPdf(tempMc.id, operatorId, {
        include_tooling:  false,
        include_clamp:    false,
        include_drawings: dto.include_drawings ?? false,
        is_preview:       true,
      } as any);
      return pdfBuffer;
    } finally {
      // 必ずDB削除（プレビューなのでデータ残さない）
      await this.prisma.mcProgram.delete({ where: { id: tempMc.id } }).catch(() => {});
    }
  }
'''

svc = rep(svc,
    "  // ══════════════════════════════════════════\n  // MC新規作成+段取シート印刷 (1トランザクション)",
    PREVIEW_NEW_FN + "\n  // ══════════════════════════════════════════\n  // MC新規作成+段取シート印刷 (1トランザクション)",
    "mc.service.ts previewNew追加")
write(MC_SVC, svc)

# ② mc.controller.ts に POST /mc/preview-new 追加
MC_CTL = f"{ROOT}/apps/api/src/mc/mc.controller.ts"
ctl = read(MC_CTL)
ctl = rep(ctl,
    "  // ── 新規作成+段取シート印刷 (1トランザクション) ──\n  @UseGuards(AuthGuard('jwt'), RolesGuard)\n  @Roles('OPERATOR', 'ADMIN')\n  @Post('create-and-print')",
    """  // ── 新規仮データプレビューPDF（DBに保存しない） ──
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('preview-new')
  async previewNew(
    @Body() dto: any,
    @Req() req: any,
    @Res() reply: FastifyReply,
  ) {
    const pdf = await this.mc.previewNew(dto, req.user.id);
    reply.header('Content-Type',        'application/pdf');
    reply.header('Content-Disposition', 'inline; filename="mc-setup-preview.pdf"');
    reply.header('Content-Length',      String(pdf.length));
    return reply.send(pdf);
  }

  // ── 新規作成+段取シート印刷 (1トランザクション) ──
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('create-and-print')""",
    "mc.controller.ts preview-new追加")
write(MC_CTL, ctl)

# ③ mc/new/print/page.tsx にプレビューボタン+キャンセルボタン追加
NEW_PRINT = f"{ROOT}/apps/web/app/mc/new/print/page.tsx"
p = read(NEW_PRINT)

# handlePreview関数を追加
p = rep(p,
    "  const handleDirectPrint = async () => {",
    """  const handlePreview = async () => {
    if (!token || !pending) { setPrintError("認証または情報が不足しています"); return; }
    setPreviewing(true); setPrintError(null);
    try {
      const body = { ...pending, include_drawings: includeDrawings };
      const res = await fetch("/api/mc/preview-new", {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
      showToast("📄 プレビューを開きました（DBに記録されません）");
    } catch (e: any) {
      setPrintError(e.message ?? "プレビュー生成に失敗しました");
    } finally {
      setPreviewing(false);
    }
  };

  const handleDirectPrint = async () => {""",
    "mc/new/print: handlePreview追加")

# previewing stateを追加
p = rep(p,
    "  const [printing, setDirectPrinting] = useState(false);",
    "  const [printing, setDirectPrinting] = useState(false);\n  const [previewing, setPreviewing] = useState(false);",
    "mc/new/print: previewing state追加")

# キャンセルボタンとプレビューボタンをボタン部分に追加
p = rep(p,
    """            <button onClick={handleDirectPrint} disabled={printing}
              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
              {printing ? "登録・送信中..." : "🖨 プリンタに直接印刷（加工IDを確定）"}
            </button>""",
    """            <button onClick={handlePreview} disabled={previewing || printing}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm">
              {previewing ? "PDF生成中..." : "📄 プレビュー（透かし入り・記録なし）"}
            </button>
            <button onClick={handleDirectPrint} disabled={printing || previewing}
              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
              {printing ? "登録・送信中..." : "🖨 プリンタに直接印刷（加工IDを確定）"}
            </button>
            <button onClick={() => { logout(); if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending"); router.push("/"); }}
              disabled={printing || previewing}
              className="w-full bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-600 font-bold py-3 rounded-xl text-sm transition-colors">
              ✗ キャンセル（ダッシュボードへ戻る）
            </button>""",
    "mc/new/print: プレビュー+キャンセルボタン追加")

write(NEW_PRINT, p)

print("\n--- build web ---")
r = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-3000:])
if r.stderr: print("STDERR:", r.stderr[-2000:])
if r.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-2000:])
if r.stderr: print("STDERR:", r.stderr[-1500:])
if r.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v94): 新規段取シート発行画面にプレビュー+キャンセルボタン追加"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v94")
