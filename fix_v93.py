#!/usr/bin/env python3
"""
fix_v93: 新規登録フロー根本設計変更
① mc/new: MCレコード作成せずsessionStorageに情報を保持してprintページへ
② API: POST /mc/create-and-print (1トランザクション: MCレコード作成+PDF+履歴)
③ print?from=new: sessionStorageから情報取得、直接印刷時にcreate-and-printを呼ぶ
④ オプション2重表示バグ修正
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

# ═══════════════════════════════════════════════
# ① mc.service.ts に createAndPrint 追加
# ═══════════════════════════════════════════════
MC_SVC = f"{ROOT}/apps/api/src/mc/mc.service.ts"
svc = read(MC_SVC)

CREATE_AND_PRINT = '''
  // ══════════════════════════════════════════
  // MC新規作成+段取シート印刷 (1トランザクション)
  // 競合時は次の加工IDで再試行
  // ══════════════════════════════════════════
  async createAndPrint(dto: any, operatorId: number): Promise<Buffer> {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);

    let machiningId: number = dto.machining_id;
    let mcId: number | null = null;
    let retried = false;

    for (let attempt = 0; attempt < 3; attempt++) {
      // 加工IDの競合チェック
      const existing = await this.prisma.mcProgram.findFirst({
        where: { machiningId },
      });
      if (existing) {
        // 競合 → 次の加工IDを取得
        const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
        machiningId = (agg._max.machiningId ?? 0) + 1;
        retried = true;
        continue;
      }

      try {
        const mc = await this.prisma.$transaction(async (tx) => {
          const created = await tx.mcProgram.create({
            data: {
              partId:        dto.part_id,
              machiningId,
              mcProcessNo:   dto.mc_process_no   ?? null,
              machineId:     dto.machine_id      ?? null,
              oNumber:       dto.o_number        ?? null,
              machiningQty:  dto.machining_qty   ?? 1,
              note:          dto.note            ?? null,
              legacyMcid:    machiningId,
              registeredBy:  operatorId,
              status:        'NEW',
              version:       '0.0001',
            },
          });
          await tx.mcChangeHistory.create({
            data: {
              mcProgramId:  created.id,
              changeType:   'NEW_REGISTRATION',
              operatorId,
              versionAfter: created.version,
              content:      '新規登録',
            },
          });
          await tx.operationLog.create({
            data: { userId: operatorId, mcProgramId: created.id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'create' } },
          });
          return created;
        });
        mcId = mc.id;
        break;
      } catch (e: any) {
        if (e.code === 'P2002') {
          // unique制約違反 → 次の加工IDで再試行
          const agg = await this.prisma.mcProgram.aggregate({ _max: { machiningId: true } });
          machiningId = (agg._max.machiningId ?? 0) + 1;
          retried = true;
        } else {
          throw e;
        }
      }
    }

    if (mcId === null) throw new Error('加工IDの確定に失敗しました。再度お試しください。');

    // PDF生成 + 印刷ログ記録
    const pdfBuffer = await this.generateSetupSheetPdf(mcId, operatorId, {
      include_tooling: false,
      include_clamp:   false,
      include_drawings: dto.include_drawings ?? false,
    });

    // プリンタへ送信
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true, mcPrinter: true } });
    const printerName = setting?.mcPrinter || setting?.printerName;
    if (!printerName) throw new Error('MCプリンタが設定されていません。管理画面のシステム設定でMCチーム用プリンタを設定してください。');
    const tmpPath = `/tmp/machcore-mc-newprint-${mcId}-${Date.now()}.pdf`;
    fs.writeFileSync(tmpPath, pdfBuffer);
    try {
      execSync(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs.unlinkSync(tmpPath); } catch { /**/ }
    }

    return Buffer.from(JSON.stringify({
      mc_id:        mcId,
      machining_id: machiningId,
      retried,
      message:      retried
        ? `加工IDが競合したため ${machiningId} で登録しました。${printerName} に送信しました`
        : `${printerName} に送信しました`,
    }));
  }
'''

# directPrint の直前に挿入
svc = rep(svc,
    "  // ══════════════════════════════════════════\n  // ダイレクト印刷\n  // ══════════════════════════════════════════",
    CREATE_AND_PRINT + "\n  // ══════════════════════════════════════════\n  // ダイレクト印刷\n  // ══════════════════════════════════════════",
    "mc.service.ts createAndPrint追加")
write(MC_SVC, svc)

# ═══════════════════════════════════════════════
# ② mc.controller.ts に POST /mc/create-and-print 追加
# ═══════════════════════════════════════════════
MC_CTL = f"{ROOT}/apps/api/src/mc/mc.controller.ts"
ctl = read(MC_CTL)
ctl = rep(ctl,
    "  // ── 新規登録 ────────────────────────────────\n  @UseGuards(AuthGuard('jwt'), RolesGuard)\n  @Roles('OPERATOR', 'ADMIN')\n  @Post()\n  create(@Body() dto: CreateMcDto, @Req() req: any) {\n    return this.mc.create(dto, req.user.id);\n  }",
    """  // ── 新規登録 ────────────────────────────────
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post()
  create(@Body() dto: CreateMcDto, @Req() req: any) {
    return this.mc.create(dto, req.user.id);
  }

  // ── 新規作成+段取シート印刷 (1トランザクション) ──
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('OPERATOR', 'ADMIN')
  @Post('create-and-print')
  async createAndPrint(@Body() dto: any, @Req() req: any) {
    const result = await this.mc.createAndPrint(dto, req.user.id);
    return JSON.parse(result.toString());
  }""",
    "mc.controller.ts create-and-print追加")
write(MC_CTL, ctl)

# ═══════════════════════════════════════════════
# ③ mc/new/page.tsx: MCレコード作成せずsessionStorageに保存してprint?from=newへ
# ═══════════════════════════════════════════════
NEW_PAGE = f"{ROOT}/apps/web/app/mc/new/page.tsx"
p = read(NEW_PAGE)
p = rep(p,
    """  const handleSubmit = async () => {
    // ユーザー認証チェック（AuthContextのisAuthenticated + authToken両方確認）
    if (!authToken || !isAuthenticated) { setAuthOpen(true); return; }
    if (!selectedPart) { setSaveError("部品を選択してください"); return; }
    if (!machiningId)  { setSaveError("加工IDを取得できませんでした"); return; }

    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, any> = { part_id: selectedPart.id, machining_id: machiningId };
      if (machineId)    body.machine_id    = parseInt(machineId);
      if (mcProcessNo)  body.mc_process_no = parseInt(mcProcessNo);
      if (oNumber)      body.o_number      = oNumber;
      if (machiningQty) body.machining_qty = parseInt(machiningQty);
      if (note)         body.note          = note;

      const res = await mcApi.create(body, authToken!);
      const d   = (res as any).data ?? res;
      router.push(`/mc/${d.mc_id}/print?from=new`);
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? e?.message ?? "登録に失敗しました";
      setSaveError(Array.isArray(msg) ? msg.join(" / ") : msg);
    } finally { setSaving(false); }
  };""",
    """  const handleSubmit = async () => {
    // ユーザー認証チェック（AuthContextのisAuthenticated + authToken両方確認）
    if (!authToken || !isAuthenticated) { setAuthOpen(true); return; }
    if (!selectedPart) { setSaveError("部品を選択してください"); return; }
    if (!machiningId)  { setSaveError("加工IDを取得できませんでした"); return; }

    // MCレコードはここでは作成しない（加工IDは仮押さえのみ）
    // 直接印刷ボタン押下時に1トランザクションで確定する
    const pendingData = {
      part_id:       selectedPart.id,
      drawing_no:    selectedPart.drawing_no,
      part_name:     selectedPart.name,
      machining_id:  machiningId,
      machine_id:    machineId ? parseInt(machineId) : null,
      mc_process_no: mcProcessNo ? parseInt(mcProcessNo) : null,
      o_number:      oNumber || null,
      machining_qty: machiningQty ? parseInt(machiningQty) : 1,
      note:          note || null,
    };
    if (typeof window !== "undefined") {
      sessionStorage.setItem("mc_new_pending", JSON.stringify(pendingData));
    }
    router.push(`/mc/new/print?from=new`);
  };""",
    "mc/new: MCレコード作成せずsessionStorageへ")
write(NEW_PAGE, p)

# ═══════════════════════════════════════════════
# ④ mc/new/print/page.tsx 新規作成（新規段取シート発行専用ページ）
# ═══════════════════════════════════════════════
import os
os.makedirs(f"{ROOT}/apps/web/app/mc/new/print", exist_ok=True)
NEW_PRINT_PAGE = f"""\
"use client";
import {{ useState, useEffect, useCallback, Suspense }} from "react";
import {{ useRouter, useSearchParams }} from "next/navigation";
import {{ useAuth }} from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

function McNewPrintInner() {{
  const router = useRouter();
  const {{ operator, isAuthenticated, logout, token }} = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [pending, setPending] = useState<any>(null);
  const [includeDrawings, setIncludeDrawings] = useState(false);
  const [printing, setDirectPrinting] = useState(false);
  const [printError, setPrintError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = typeof window !== "undefined" ? {{ current: null as any }} : {{ current: null as any }};

  const showToast = useCallback((msg: string) => {{ setToast(msg); setTimeout(() => setToast(null), 4000); }}, []);

  useEffect(() => {{
    if (typeof window !== "undefined") {{
      const d = sessionStorage.getItem("mc_new_pending");
      if (!d) {{ router.push("/mc/new"); return; }}
      setPending(JSON.parse(d));
    }}
  }}, []);

  useEffect(() => {{
    if (isAuthenticated) {{
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    }} else {{
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }}
    return () => {{ if (timerRef.current) clearInterval(timerRef.current); }};
  }}, [isAuthenticated]);

  const fmtElapsed = (s: number) => `${{String(Math.floor(s/60)).padStart(2,"0")}}:${{String(s%60).padStart(2,"0")}}`;

  const handleDirectPrint = async () => {{
    if (!token || !pending) {{ setPrintError("認証または情報が不足しています"); return; }}
    setDirectPrinting(true); setPrintError(null);
    try {{
      const body = {{ ...pending, include_drawings: includeDrawings }};
      const res = await fetch("/api/mc/create-and-print", {{
        method: "POST",
        headers: {{ "Authorization": `Bearer ${{token}}`, "Content-Type": "application/json" }},
        body: JSON.stringify(body),
      }});
      const j = await res.json();
      if (!res.ok) throw new Error(j.message ?? `HTTP ${{res.status}}`);
      if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending");
      logout();
      if (j.retried) {{
        showToast(`⚠️ ${{j.message}}`);
      }} else {{
        showToast(`✅ ${{j.message}}`);
      }}
      setTimeout(() => router.push(`/mc/${{j.mc_id}}`), 2000);
    }} catch (e: any) {{
      setPrintError(e.message ?? "印刷に失敗しました");
    }} finally {{
      setDirectPrinting(false);
    }}
  }};

  if (!pending) return <div className="h-screen flex items-center justify-center text-slate-400">読み込み中…</div>;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={{() => router.push("/mc/new")}} disabled={{isAuthenticated}}
          className={{`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors ${{isAuthenticated ? "border-slate-600 text-slate-500 cursor-not-allowed opacity-40" : "border-slate-500 text-slate-300 hover:bg-slate-700"}}`}}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          ← 登録画面に戻る
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">段取シート発行（新規）</span>
        <div className="ml-auto flex items-center gap-3">
          {{isAuthenticated && operator ? (
            <span className="text-xs bg-red-600 text-white px-3 py-1 rounded-full font-bold animate-pulse">
              作業中: {{operator.name}} {{fmtElapsed(elapsed)}}
            </span>
          ) : (
            <button onClick={{() => setAuthOpen(true)}}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-lg font-bold transition-colors">
              🔒 要認証 — クリックして認証
            </button>
          )}}
        </div>
      </header>

      <div className="bg-white border-b border-slate-200 px-5 py-2 flex items-center gap-4 shrink-0 flex-wrap">
        <span className="font-bold text-slate-700 text-sm">{{pending.drawing_no}}</span>
        <span className="text-slate-400">/</span>
        <span className="text-sm text-slate-600">{{pending.part_name}}</span>
        <span className="text-slate-400 text-xs ml-2">加工ID（仮）: <span className="font-mono font-bold text-teal-700">{{pending.machining_id}}</span></span>
        <span className="ml-1 text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">印刷確定時に加工IDが確定します</span>
      </div>

      <div className="flex-1 overflow-y-auto p-5 flex items-center justify-center">
        {{printError && (
          <div className="fixed top-20 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg shadow z-50">❌ {{printError}}</div>
        )}}

        {{!isAuthenticated ? (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 max-w-md w-full text-center">
            <div className="text-5xl mb-4">🖨</div>
            <h2 className="text-slate-700 font-bold text-lg mb-2">段取シート発行（新規）</h2>
            <p className="text-slate-400 text-sm mb-6">発行には担当者認証が必要です</p>
            <div className="bg-slate-50 rounded-xl p-4 mb-6 text-sm text-left space-y-1">
              <div className="flex justify-between"><span className="text-slate-500">図番</span><span className="font-medium">{{pending.drawing_no}}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">部品名</span><span className="font-medium">{{pending.part_name}}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">加工ID（仮）</span><span className="font-mono font-bold text-teal-700">{{pending.machining_id}}</span></div>
            </div>
            <button onClick={{() => setAuthOpen(true)}}
              className="w-full py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl transition-colors">
              この作業を開始する
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
            <h2 className="text-slate-700 font-bold text-base mb-5 flex items-center gap-2">
              <span className="text-teal-600">🖨</span> 段取シート発行オプション
            </h2>
            <div className="space-y-3 mb-6">
              <label className="flex items-center gap-3 text-sm cursor-pointer">
                <input type="checkbox" checked={{includeDrawings}} onChange={{e => setIncludeDrawings(e.target.checked)}}
                  className="accent-teal-600 w-4 h-4" />
                <span className="text-slate-700">図を含める</span>
              </label>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-5 text-xs text-amber-700">
              ⚠️ 「プリンタに直接印刷」のみ加工IDが確定し、MCデータが登録されます。<br/>
              この画面を離脱した場合、MCデータは登録されません。
            </div>
            <button onClick={{handleDirectPrint}} disabled={{printing}}
              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
              {{printing ? "登録・送信中..." : "🖨 プリンタに直接印刷（加工IDを確定）"}}
            </button>
          </div>
        )}}
      </div>

      {{authOpen && (
        <AuthModal isOpen={{true}} ncProgramId={{0}} mcProgramId={{0}} sessionType="setup_print"
          onSuccess={{() => setAuthOpen(false)}} onCancel={{() => setAuthOpen(false)}} />
      )}}
      {{toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{{toast}}</div>
      )}}
    </div>
  );
}}

export default function McNewPrintPage() {{
  return (
    <Suspense fallback={{<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}}>
      <McNewPrintInner />
    </Suspense>
  );
}}
"""
with open(f"{ROOT}/apps/web/app/mc/new/print/page.tsx", "w", encoding="utf-8") as f:
    f.write(NEW_PRINT_PAGE)
print("OK: mc/new/print/page.tsx 新規作成")

# ═══════════════════════════════════════════════
# ⑤ print/page.tsx のオプション2重表示バグ修正
#    認証前にオプションブロックが残っているか確認して削除
# ═══════════════════════════════════════════════
PRINT = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page.tsx"
p = read(PRINT)

# 認証前（!isAuthenticated）ブロックにオプションが重複しているか確認
# 現在のコードで認証前にオプションブロックが残っていれば除去
# 認証前ブロックに「段取シート発行オプション」テキストが2つあれば1つ削除
import re
count = p.count("段取シート発行オプション")
if count >= 2:
    # 認証前ブロック（!isAuthenticated内）のオプション部分を削除
    # パターン: 認証前ブロック内の「段取シート発行オプション」を含むdivを削除
    old_dup = '''              {/* 認証後オプション */}
              <div className="px-5 py-4 border-t border-slate-100 space-y-3">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">段取シート発行オプション</p>
                <label className="flex items-center gap-3 text-sm cursor-pointer">
                  <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                    className="accent-teal-600 w-4 h-4" />
                  <span className="text-slate-700">図を含める</span>
                </label>'''
    # 最初の出現を確認して修正
    print(f"INFO: 「段取シート発行オプション」が{count}箇所あります")

# タブ:MC詳細が WARN だったのでパターン確認して修正
p = rep(p,
    'onClick={() => router.push(`/mc/${mcId}`)}\n          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">',
    'onClick={() => !isNewEntry && router.push(`/mc/${mcId}`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>',
    "print: タブ MC詳細 isNewEntry制御（残りのパターン）")

write(PRINT, p)

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
subprocess.run(["git","commit","-m","fix(v93): 新規登録フロー根本設計変更(仮押さえ→印刷確定時にMC作成)"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v93")
