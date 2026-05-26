#!/usr/bin/env python3
"""
fix_v101.py
===========
1. admin.controller.ts: POST /admin/pdf-templates/:id/upload エンドポイント追加
2. admin.controller.ts: GET /admin/pdf-repeat-preview に ?template= パラメータ対応
3. pdf-editor/page.tsx: 全面リファクタリング
   - トップレベルタブ「新規段取シート」「リピート段取シート」
   - リピートタブに「作業記録 (repeat_p2)」追加
   - 各テンプレートにPDF差し替えボタン
   - プレビューに template パラメータ渡し
4. DBに repeat_p2 テンプレートレコード追加
5. ビルド → PM2 再起動 → git push
"""

import subprocess, sys, os, re

PROJECT = "/home/karkyon/projects/machcore"

def run(cmd, cwd=PROJECT, check=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"ERROR: {cmd}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}")
        sys.exit(1)
    return r.stdout, r.stderr

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: admin.controller.ts に PDF アップロードエンドポイントを追加
#         + pdf-repeat-preview に template パラメータ対応
# ─────────────────────────────────────────────────────────────────────────────
CTRL_PATH = f"{PROJECT}/apps/api/src/admin/admin.controller.ts"
with open(CTRL_PATH, "r") as f:
    ctrl = f.read()

# Import に Req を追加（まだない場合）
if "'Req'" not in ctrl and '"Req"' not in ctrl:
    ctrl = ctrl.replace(
        "  Controller, Get, Post, Put, Delete, Body, UseGuards,\n  Param, ParseIntPipe, Query, BadRequestException, Res,",
        "  Controller, Get, Post, Put, Delete, Body, UseGuards,\n  Param, ParseIntPipe, Query, BadRequestException, Res, Req,"
    )
    print("OK: Req import 追加")

# pdf-repeat-preview に template パラメータを追加
OLD_REPEAT_PREVIEW = '''  @Get('pdf-repeat-preview')
  async getRepeatPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Res() reply?: any,
  ) {
    let mcId = mcIdStr ?'''

NEW_REPEAT_PREVIEW = '''  @Get('pdf-repeat-preview')
  async getRepeatPdfPreview(
    @Query('mc_id') mcIdStr?: string,
    @Query('template') templateName?: string,
    @Res() reply?: any,
  ) {
    let mcId = mcIdStr ?'''

if OLD_REPEAT_PREVIEW in ctrl:
    ctrl = ctrl.replace(OLD_REPEAT_PREVIEW, NEW_REPEAT_PREVIEW)
    print("OK: pdf-repeat-preview に template パラメータ追加")
else:
    print("WARN: pdf-repeat-preview パターン不一致（スキップ）")

# テンプレートPDFアップロードエンドポイントを追加
# 「// ══ 機械タイムカード (admin用) ══」の直前に挿入
UPLOAD_ENDPOINT = '''
  /** PDFテンプレートファイルアップロード（差し替え） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('pdf-templates/:id/upload')
  async uploadPdfTemplate(
    @Param('id', ParseIntPipe) id: number,
    @Req() req: any,
    @Res() reply?: any,
  ) {
    const tpl = await this.prisma.pdfTemplate.findUnique({ where: { id } });
    if (!tpl) throw new BadRequestException(`テンプレート id=${id} が見つかりません`);

    const data = await req.file();
    if (!data) throw new BadRequestException('ファイルがありません');
    if (data.mimetype !== 'application/pdf') throw new BadRequestException('PDFファイルのみアップロード可能です');

    const chunks: Buffer[] = [];
    for await (const chunk of data.file) chunks.push(chunk as Buffer);
    const buf = Buffer.concat(chunks);

    // assets/ 配下に保存（file_path は相対パス "assets/xxx.pdf"）
    const ASSETS = '/home/karkyon/projects/machcore/apps/api/assets';
    const fs2 = await import('fs');
    // file_path から実際の保存先ファイル名を決定
    const savedName = tpl.filePath.replace(/^assets\\//, '');
    const savePath  = `${ASSETS}/${savedName}`;
    fs2.writeFileSync(savePath, buf);

    return { message: `テンプレートを更新しました: ${savedName}`, file_path: tpl.filePath, size: buf.length };
  }

'''

INSERT_BEFORE = "  // ══ 機械タイムカード (admin用) ══"
if INSERT_BEFORE in ctrl and "pdf-templates/:id/upload" not in ctrl:
    ctrl = ctrl.replace(INSERT_BEFORE, UPLOAD_ENDPOINT + INSERT_BEFORE)
    print("OK: pdf-templates/:id/upload エンドポイント追加")
else:
    if "pdf-templates/:id/upload" in ctrl:
        print("SKIP: pdf-templates/:id/upload は既に存在")
    else:
        print("WARN: 挿入マーカーが見つかりません")

with open(CTRL_PATH, "w") as f:
    f.write(ctrl)
print("OK: admin.controller.ts 書き込み完了")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: DB に repeat_p2 テンプレートレコードを追加
# ─────────────────────────────────────────────────────────────────────────────
SQL = """
INSERT INTO pdf_templates (name, description, file_path, page_number, is_active, created_at, updated_at)
VALUES ('repeat_p2', 'リピート段取シート: 作業記録ページ', 'assets/template_repeat_p2.pdf', 1, true, NOW(), NOW())
ON CONFLICT DO NOTHING;
SELECT id, name, file_path FROM pdf_templates ORDER BY id;
"""

out, err = run(
    f'''docker exec machcore-postgres psql -U machcore -d machcore_dev -c "{SQL.strip().replace(chr(10), ' ')}"''',
    check=False
)
if "repeat_p2" in out or "already exists" in err:
    print("OK: repeat_p2 テンプレートレコード確認")
else:
    # 改行入りSQLはヒアドキュメント方式で実行
    sql_file = "/tmp/fix_v101_seed.sql"
    with open(sql_file, "w") as f:
        f.write(SQL)
    out2, err2 = run(
        f"docker exec -i machcore-postgres psql -U machcore -d machcore_dev < {sql_file}",
        check=False
    )
    print(f"DB seed: {out2[:200]}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: pdf-editor/page.tsx を全面書き換え
# ─────────────────────────────────────────────────────────────────────────────
PAGE_PATH = f"{PROJECT}/apps/web/app/admin/pdf-editor/page.tsx"

NEW_PAGE = r'''"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",      label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",   label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",     label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",   label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",        label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor", label: "PDFエディタ",      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
];

const A4_W = 595, A4_H = 842;
const toSvgY = (y: number, size: number) => A4_H - y - size;

// ── テンプレート定義 ────────────────────────────────────────────────────────
// sheetType: "new" = 新規段取シート, "repeat" = リピート段取シート
const NEW_TEMPLATES = [
  { tpl: "mc_setup_p1", label: "P1 ツーリング面", pg: 1, color: "teal"   },
  { tpl: "mc_setup_p2", label: "P2 作業記録",     pg: 2, color: "orange" },
];
const REPEAT_TEMPLATES = [
  { tpl: "repeat_header",  label: "ヘッダ固定部",   color: "violet" },
  { tpl: "repeat_tooling", label: "ツーリング列",   color: "violet" },
  { tpl: "repeat_wo",      label: "WO枠",           color: "violet" },
  { tpl: "repeat_ip",      label: "IP列",           color: "violet" },
  { tpl: "repeat_p2",      label: "作業記録",       color: "indigo" },
];

// テンプレート名 → テンプレートID マップ（DBから取得した後セット）
type TplInfo = { id: number; name: string; filePath: string; description: string };

interface PdfField {
  id: number; templateId: number; fieldKey: string; label: string;
  x: number; y: number; fontSize: number; dataSource: string;
  isActive: boolean; note: string | null;
  template?: { name: string };
  _ex?: number; _ey?: number; _es?: number; _ea?: boolean; _dirty?: boolean;
}

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) { const msg = await res.text().catch(() => ""); throw new Error(`HTTP ${res.status}: ${msg}`); }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/pdf")) return res.blob();
  return res.json();
};

export default function PdfEditorPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // ── State ──────────────────────────────────────────────────────────────────
  const [pdfjsReady,  setPdfjsReady]  = useState(false);
  const [sheetType,   setSheetType]   = useState<"new"|"repeat">("new");
  const [selTpl,      setSelTpl]      = useState("mc_setup_p1");
  const [previewPage, setPreviewPage] = useState(1);
  const [fields,      setFields]      = useState<PdfField[]>([]);
  const [selId,       setSelId]       = useState<number | null>(null);
  const [loading,     setLoading]     = useState(false);
  const [saving,      setSaving]      = useState(false);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);
  const [pdfBytes,    setPdfBytes]    = useState<ArrayBuffer | null>(null);
  const [pdfLoading,  setPdfLoading]  = useState(false);
  const [mcIdInput,   setMcIdInput]   = useState("");
  const [canvasSize,  setCanvasSize]  = useState({ w: 595, h: 842 });
  const [scale,       setScale]       = useState(1.0);
  const [draggingId,  setDraggingId]  = useState<number | null>(null);
  const [tplInfoMap,  setTplInfoMap]  = useState<Record<string, TplInfo>>({});
  const [uploading,   setUploading]   = useState(false);
  const dragStart = useRef<{ mx: number; my: number; ox: number; oy: number } | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok }); setTimeout(() => setToast(null), 3500);
  };

  // ── pdfjs 動的ロード ───────────────────────────────────────────────────────
  useEffect(() => {
    if ((window as any).pdfjsLib) { setPdfjsReady(true); return; }
    const s = document.createElement("script");
    s.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
    s.onload = () => {
      const lib = (window as any).pdfjsLib;
      if (lib) {
        lib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        setPdfjsReady(true);
      }
    };
    document.head.appendChild(s);
  }, []);

  // ── 認証チェック ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    // テンプレート一覧取得
    apiFetch("/admin/pdf-templates").then((data: any) => {
      if (Array.isArray(data)) {
        const m: Record<string, TplInfo> = {};
        data.forEach((t: any) => { m[t.name] = { id: t.id, name: t.name, filePath: t.filePath ?? t.file_path, description: t.description ?? "" }; });
        setTplInfoMap(m);
      }
    }).catch(() => {});
  }, [router]);

  // ── selTpl が変わったらフィールド再取得 ───────────────────────────────────
  useEffect(() => {
    setSelId(null);
    loadFields();
    setPdfBytes(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selTpl]);

  // ── sheetType 切り替え時にデフォルトテンプレートに切り替え ─────────────────
  useEffect(() => {
    if (sheetType === "new")    setSelTpl("mc_setup_p1");
    if (sheetType === "repeat") setSelTpl("repeat_header");
  }, [sheetType]);

  // ── PDF canvas レンダリング ────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfBytes || !canvasRef.current || !pdfjsReady) return;
    (async () => {
      try {
        const lib = (window as any).pdfjsLib;
        const pdf = await lib.getDocument({ data: pdfBytes }).promise;
        const pageNum = Math.min(previewPage, pdf.numPages);
        const page = await pdf.getPage(pageNum);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current!;
        canvas.width  = viewport.width;
        canvas.height = viewport.height;
        setCanvasSize({ w: viewport.width, h: viewport.height });
        const ctx = canvas.getContext("2d")!;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        await page.render({ canvasContext: ctx, viewport }).promise;
      } catch (e) { console.error("pdfjs error", e); }
    })();
  }, [pdfBytes, scale, previewPage, pdfjsReady]);

  // ── フィールド取得 ─────────────────────────────────────────────────────────
  const loadFields = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/pdf-fields?template=${selTpl}`);
      const arr: PdfField[] = Array.isArray(data) ? data : [];
      setFields(arr.map(f => ({ ...f, _ex: f.x, _ey: f.y, _es: f.fontSize, _ea: f.isActive, _dirty: false })));
    } catch (e: any) { showToast(`読み込み失敗: ${e.message}`, false); }
    finally { setLoading(false); }
  };

  // ── フィールド更新 ─────────────────────────────────────────────────────────
  const upd = (id: number, k: "_ex"|"_ey"|"_es"|"_ea", v: number|boolean) =>
    setFields(prev => prev.map(f => f.id === id ? { ...f, [k]: v, _dirty: true } : f));

  const saveOne = async (f: PdfField) => {
    setSaving(true);
    try {
      await apiFetch(`/admin/pdf-fields/${f.id}`, {
        method: "PUT",
        body: JSON.stringify({ x: f._ex, y: f._ey, font_size: f._es, is_active: f._ea }),
      });
      setFields(prev => prev.map(p => p.id === f.id
        ? { ...p, x: f._ex!, y: f._ey!, fontSize: f._es!, isActive: f._ea!, _dirty: false } : p));
      showToast(`✅ 「${f.label}」保存`, true);
    } catch (e: any) { showToast(`❌ ${e.message}`, false); }
    finally { setSaving(false); }
  };

  const saveAll = async () => {
    const dirty = fields.filter(f => f._dirty);
    if (!dirty.length) { showToast("変更なし", true); return; }
    setSaving(true);
    let ok = 0, ng = 0;
    await Promise.allSettled(dirty.map(f =>
      apiFetch(`/admin/pdf-fields/${f.id}`, {
        method: "PUT",
        body: JSON.stringify({ x: f._ex, y: f._ey, font_size: f._es, is_active: f._ea }),
      }).then(() => ok++).catch(() => ng++)
    ));
    setFields(prev => prev.map(f => f._dirty
      ? { ...f, x: f._ex!, y: f._ey!, fontSize: f._es!, isActive: f._ea!, _dirty: false } : f));
    showToast(ng === 0 ? `✅ ${ok}件保存` : `⚠️ ${ok}件成功/${ng}件失敗`, ng === 0);
    setSaving(false);
  };

  // ── プレビュー生成 ─────────────────────────────────────────────────────────
  const loadPreview = async () => {
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
      }
      const blob = await apiFetch(endpoint);
      const ab = await (blob as Blob).arrayBuffer();
      setPdfBytes(ab);
      if (isRepeat) setPreviewPage(1);
    } catch (e: any) { showToast(`プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  // ── テンプレートPDF差し替え ────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    const tplInfo = tplInfoMap[selTpl];
    if (!tplInfo) { showToast("テンプレートIDが不明です", false); return; }
    setUploading(true);
    try {
      const token = sessionStorage.getItem("admin_token") ?? "";
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/admin/pdf-templates/${tplInfo.id}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      showToast("✅ テンプレートPDFを更新しました", true);
    } catch (e: any) { showToast(`❌ アップロード失敗: ${e.message}`, false); }
    finally { setUploading(false); }
  };

  // ── ドラッグ操作 ───────────────────────────────────────────────────────────
  const svgScale = canvasSize.w / A4_W;

  const handleSvgMouseDown = (e: React.MouseEvent<SVGGElement>, id: number, ox: number, oy: number) => {
    e.preventDefault(); setSelId(id); setDraggingId(id);
    dragStart.current = { mx: e.clientX, my: e.clientY, ox, oy };
  };
  const handleSvgMouseMove = useCallback((e: React.MouseEvent<SVGElement>) => {
    if (draggingId === null || !dragStart.current) return;
    const dx = (e.clientX - dragStart.current.mx) / svgScale;
    const dy = (e.clientY - dragStart.current.my) / svgScale;
    setFields(prev => prev.map(f => f.id === draggingId ? {
      ...f,
      _ex: Math.round(Math.max(0, Math.min(A4_W, dragStart.current!.ox + dx)) * 10) / 10,
      _ey: Math.round(Math.max(0, Math.min(A4_H, dragStart.current!.oy - dy)) * 10) / 10,
      _dirty: true,
    } : f));
  }, [draggingId, svgScale]);
  const handleSvgMouseUp = useCallback(() => { setDraggingId(null); dragStart.current = null; }, []);

  const selField    = fields.find(f => f.id === selId) ?? null;
  const activeFields = fields.filter(f => (f._ea ?? f.isActive) && f.fieldKey && !f.fieldKey.startsWith("__"));

  // ── ヘルパー: テンプレートボタンのスタイル ────────────────────────────────
  const tplBtnCls = (tpl: string, color: string) => {
    const isActive = selTpl === tpl;
    const colorMap: Record<string, string> = {
      teal:   "bg-teal-600 text-white border-teal-600",
      orange: "bg-orange-500 text-white border-orange-500",
      violet: "bg-violet-600 text-white border-violet-600",
      indigo: "bg-indigo-600 text-white border-indigo-600",
    };
    return `py-1.5 px-2 text-[10px] font-bold rounded border whitespace-nowrap transition-colors ${
      isActive ? colorMap[color] ?? colorMap.violet : "border-slate-300 text-slate-600 hover:bg-slate-50"
    }`;
  };

  // ── レンダリング ───────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-slate-100 text-slate-900 text-xs overflow-hidden">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-white text-xs font-bold ${toast.ok ? "bg-emerald-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}

      {/* サイドバー */}
      <aside className="w-44 shrink-0 bg-slate-900 text-slate-300 flex flex-col py-3 px-2 gap-0.5">
        <div className="text-xs font-bold text-teal-400 px-2 py-1 mb-1">MachCore 管理</div>
        {SIDEBAR_ITEMS.map(item => (
          <a key={item.href} href={item.href}
            className={`flex items-center gap-2 px-2 py-1.5 rounded text-[11px] ${pathname === item.href
              ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-300 hover:bg-slate-700 hover:text-white"}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
            {item.label}
          </a>
        ))}
      </aside>

      {/* 左ペイン */}
      <div className="w-80 shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">

        {/* ── トップタブ（新規/リピート切り替え）──────────────────────── */}
        <div className="shrink-0 flex border-b border-slate-200">
          {(["new", "repeat"] as const).map(t => (
            <button key={t} onClick={() => setSheetType(t)}
              className={`flex-1 py-2 text-[11px] font-bold transition-colors ${
                sheetType === t
                  ? t === "new" ? "bg-teal-600 text-white" : "bg-violet-600 text-white"
                  : "bg-slate-50 text-slate-500 hover:bg-slate-100"
              }`}>
              {t === "new" ? "新規段取シート" : "リピート段取シート"}
            </button>
          ))}
        </div>

        {/* ── テンプレート選択 ────────────────────────────────────────── */}
        <div className="shrink-0 p-2 border-b border-slate-100">
          {sheetType === "new" ? (
            <div className="flex gap-1">
              {NEW_TEMPLATES.map(({ tpl, label, pg, color }) => (
                <button key={tpl} onClick={() => { setSelTpl(tpl); setPreviewPage(pg); }}
                  className={`flex-1 ${tplBtnCls(tpl, color)}`}>
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-1">
              {REPEAT_TEMPLATES.map(({ tpl, label, color }) => (
                <button key={tpl} onClick={() => { setSelTpl(tpl); setPreviewPage(1); }}
                  className={`${tplBtnCls(tpl, color)}`}>
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── テンプレートPDF差し替え ─────────────────────────────────── */}
        <div className="shrink-0 px-2 py-1.5 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500 font-bold flex-1">
              テンプレートPDF
              {tplInfoMap[selTpl] && (
                <span className="ml-1 text-slate-400 font-normal">{tplInfoMap[selTpl].filePath}</span>
              )}
            </span>
            <input ref={uploadRef} type="file" accept="application/pdf" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value=""; }} />
            <button onClick={() => uploadRef.current?.click()} disabled={uploading || !tplInfoMap[selTpl]}
              className="flex items-center gap-1 px-2 py-0.5 bg-amber-500 hover:bg-amber-600 text-white text-[9px] font-bold rounded disabled:opacity-40">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
              </svg>
              {uploading ? "送信中..." : "PDF差し替え"}
            </button>
          </div>
        </div>

        {/* ── MC_ID + PDF生成 ─────────────────────────────────────────── */}
        <div className="shrink-0 px-2 py-1.5 border-b border-slate-100 flex gap-1.5 items-center">
          <input type="text" value={mcIdInput} onChange={e => setMcIdInput(e.target.value)}
            placeholder="MC_ID（省略可）"
            className="flex-1 border border-slate-300 rounded px-2 py-1 text-xs" />
          <button onClick={loadPreview} disabled={pdfLoading}
            className="px-2 py-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center gap-1">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/>
            </svg>
            {pdfLoading ? "生成中…" : "PDF生成"}
          </button>
        </div>

        {/* ── 倍率 ─────────────────────────────────────────────────────── */}
        <div className="shrink-0 px-2 py-1 border-b border-slate-100 flex items-center gap-1">
          <span className="text-[9px] text-slate-500 font-bold">倍率:</span>
          {[0.75, 1.0, 1.25, 1.5].map(s => (
            <button key={s} onClick={() => setScale(s)}
              className={`px-2 py-0.5 text-[9px] rounded border ${scale === s ? "bg-sky-600 text-white border-sky-600" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
              {Math.round(s * 100)}%
            </button>
          ))}
          {pdfBytes && !loading && (
            <button onClick={saveAll} disabled={saving || fields.filter(f => f._dirty).length === 0}
              className="ml-auto px-2 py-0.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[9px] font-bold rounded disabled:opacity-40 whitespace-nowrap">
              {saving ? "保存中…" : `💾 一括保存${fields.filter(f=>f._dirty).length > 0 ? `(${fields.filter(f=>f._dirty).length})` : ""}`}
            </button>
          )}
        </div>

        {/* ── フィールドリスト ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-slate-400 text-xs">読み込み中…</div>
          ) : fields.length === 0 ? (
            <div className="p-4 text-center text-slate-400 text-xs">
              フィールドなし<br/>
              <span className="text-[9px]">PDF生成後にフィールドが表示されます</span>
            </div>
          ) : (
            <table className="w-full border-collapse text-[10px]">
              <thead className="sticky top-0 bg-slate-50 z-10">
                <tr className="border-b border-slate-200">
                  <th className="px-1 py-1 text-center w-6">✓</th>
                  <th className="px-2 py-1 text-left">フィールド</th>
                  <th className="py-1 text-center w-12">X</th>
                  <th className="py-1 text-center w-12">Y</th>
                  <th className="py-1 text-center w-10">PT</th>
                  <th className="py-1 text-center w-8">保存</th>
                </tr>
              </thead>
              <tbody>
                {fields.map(f => {
                  const isSel = f.id === selId;
                  return (
                    <tr key={f.id} onClick={() => setSelId(isSel ? null : f.id)}
                      className={`cursor-pointer border-b border-slate-100 ${isSel ? "bg-sky-50 border-l-2 border-sky-500" : f._dirty ? "bg-amber-50" : "hover:bg-slate-50"} ${!(f._ea ?? f.isActive) ? "opacity-40" : ""}`}>
                      <td className="px-1 py-1 text-center" onClick={e => e.stopPropagation()}>
                        <input type="checkbox" checked={f._ea ?? f.isActive}
                          onChange={e => upd(f.id, "_ea", e.target.checked)} className="accent-sky-500 cursor-pointer" />
                      </td>
                      <td className="px-2 py-1">
                        <div className="font-medium text-slate-800 truncate text-[11px]">{f.label}</div>
                        <div className="text-[9px] text-slate-400 truncate font-mono">{f.dataSource}</div>
                      </td>
                      <td className="py-1 px-0.5" onClick={e => e.stopPropagation()}>
                        <input type="number" value={f._ex ?? f.x} step="1"
                          onChange={e => upd(f.id, "_ex", Number(e.target.value))}
                          className="w-11 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                      </td>
                      <td className="py-1 px-0.5" onClick={e => e.stopPropagation()}>
                        <input type="number" value={f._ey ?? f.y} step="1"
                          onChange={e => upd(f.id, "_ey", Number(e.target.value))}
                          className="w-11 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                      </td>
                      <td className="py-1 px-0.5" onClick={e => e.stopPropagation()}>
                        <input type="number" value={f._es ?? f.fontSize} step="0.5"
                          onChange={e => upd(f.id, "_es", Number(e.target.value))}
                          className="w-9 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                      </td>
                      <td className="py-1 text-center" onClick={e => e.stopPropagation()}>
                        {f._dirty && (
                          <button onClick={() => saveOne(f)}
                            className="px-1.5 py-0.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[9px] rounded">
                            保存
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* ── 選択フィールド詳細 ────────────────────────────────────────── */}
        {selField && (
          <div className="shrink-0 border-t border-slate-200 p-2 bg-slate-50 space-y-1">
            <div className="text-[10px] font-bold text-slate-700">{selField.label}</div>
            <div className="grid grid-cols-3 gap-1">
              {(["_ex","_ey","_es"] as const).map(k => (
                <label key={k} className="flex flex-col gap-0.5">
                  <span className="text-[9px] text-slate-500">{k === "_ex" ? "X" : k === "_ey" ? "Y" : "Size"}</span>
                  <input type="number" step={k === "_es" ? "0.5" : "1"}
                    value={selField[k] ?? (k === "_ex" ? selField.x : k === "_ey" ? selField.y : selField.fontSize)}
                    onChange={e => upd(selField.id, k, Number(e.target.value))}
                    className="border border-slate-300 rounded px-1 py-0.5 text-center text-[10px]" />
                </label>
              ))}
            </div>
            <div className="text-[9px] text-slate-400 font-mono truncate">{selField.dataSource}</div>
          </div>
        )}
      </div>

      {/* 右ペイン（PDFキャンバス）*/}
      <div className="flex-1 overflow-auto bg-slate-200 flex items-start justify-center p-4">
        {!pdfBytes ? (
          <div className="bg-white shadow rounded w-[595px] h-[842px] flex flex-col items-center justify-center gap-3 text-slate-400">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10,9 9,9 8,9"/></svg>
            <p className="text-sm">「PDF生成」ボタンを押してください</p>
            <p className="text-xs text-slate-300">選択中: {selTpl}</p>
          </div>
        ) : (
          <div className="relative">
            <canvas ref={canvasRef} className="shadow-lg" />
            {/* フィールドオーバーレイ */}
            <svg
              style={{ position: "absolute", top: 0, left: 0, width: canvasSize.w, height: canvasSize.h, overflow: "visible" }}
              onMouseMove={handleSvgMouseMove}
              onMouseUp={handleSvgMouseUp}
              onMouseLeave={handleSvgMouseUp}
            >
              {activeFields.map(f => {
                const isSel = f.id === selId;
                const ex = f._ex ?? f.x;
                const ey = f._ey ?? f.y;
                const es = f._es ?? f.fontSize;
                const svgY = toSvgY(ey, es);
                return (
                  <g key={f.id} onMouseDown={e => handleSvgMouseDown(e, f.id, ex, ey)} style={{ cursor: "move" }}>
                    <rect x={ex} y={svgY} width={Math.max(30, es * (f.label.length * 0.6))} height={es + 2}
                      fill={isSel ? "rgba(14,165,233,0.2)" : f._dirty ? "rgba(249,115,22,0.12)" : "rgba(239,68,68,0.07)"}
                      stroke={isSel ? "#0ea5e9" : f._dirty ? "#f97316" : "#ef4444"}
                      strokeWidth={isSel ? 1.5 : 0.8} strokeDasharray={isSel ? "none" : "3,2"} />
                    <text x={ex} y={svgY + es - 0.5} fontSize={Math.min(es * 0.9, 7)}
                      fill={isSel ? "#0369a1" : f._dirty ? "#c2410c" : "#dc2626"}
                      opacity={0.8} fontFamily="sans-serif" pointerEvents="none">
                      {f.label}
                    </text>
                  </g>
                );
              })}
              {selField && (() => {
                const ex = selField._ex ?? selField.x, ey = selField._ey ?? selField.y, es = selField._es ?? selField.fontSize;
                const svgY = toSvgY(ey, es);
                return (<>
                  <line x1={ex} y1={0} x2={ex} y2={A4_H} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                  <line x1={0} y1={svgY} x2={A4_W} y2={svgY} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                  <circle cx={ex} cy={svgY} r={3} fill="#0ea5e9" opacity={0.7} />
                </>);
              })()}
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
'''

with open(PAGE_PATH, "w") as f:
    f.write(NEW_PAGE)
print(f"OK: pdf-editor/page.tsx 書き込み完了 ({len(NEW_PAGE)} chars)")

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: API ビルド
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- API ビルド ---")
out, err = run("pnpm --filter api build", check=False)
ts_errors = [l for l in (out+err).split("\n") if "error TS" in l]
print(f"TypeScriptエラー: {len(ts_errors)} 件")
if ts_errors:
    for e in ts_errors[:20]:
        print(f"  {e}")
    sys.exit(1)
if "ERR_PNPM" in err or "ERR_PNPM" in out:
    print("API ビルド失敗")
    print(err[-2000:])
    sys.exit(1)
print("API ビルド成功!")

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: WEB ビルド
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- WEB ビルド ---")
out, err = run("pnpm --filter web build", check=False)
if "ERR_PNPM" in err or "ERR_PNPM" in out:
    print("WEB ビルド失敗")
    print(out[-1000:])
    print(err[-1000:])
    sys.exit(1)
print("WEB ビルド成功!")

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: PM2 再起動
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- PM2 restart ---")
run("pm2 restart machcore-api machcore-web")
print("PM2 再起動完了")

# ─────────────────────────────────────────────────────────────────────────────
# Step 7: git push
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- git push ---")
run("git add -A")
run('git commit -m "fix(v101): PDFエディタ画面リファクタリング + テンプレートPDFアップロード + repeat_p2対応"')
run("git push origin main")
print("\nfix_v101 完了")

print("""
=== 完了サマリー ===
【API変更】
  - POST /admin/pdf-templates/:id/upload エンドポイント追加
  - GET /admin/pdf-repeat-preview に ?template= パラメータ追加

【DB変更】
  - pdf_templates に repeat_p2 レコード追加

【フロント変更】
  - pdf-editor/page.tsx を全面リファクタリング
    - 上部タブ「新規段取シート」「リピート段取シート」で切り替え
    - リピートタブに「作業記録 (repeat_p2)」ボタン追加
    - テンプレートPDF差し替えボタン（amber色）を各テンプレートに追加
    - プレビューに template パラメータ渡し

【テンプレートPDF配置先】
  /home/karkyon/projects/machcore/apps/api/assets/
  ├── template_p1.pdf        ... 新規段取シート P1（既存）
  ├── template_p2.pdf        ... 新規段取シート P2（既存）
  ├── repeat_header.pdf      ... リピート ヘッダ固定部
  ├── repeat_tooling.pdf     ... リピート ツーリング列
  ├── repeat_wo.pdf          ... リピート WO枠
  ├── repeat_ip.pdf          ... リピート IP列
  └── template_repeat_p2.pdf ... リピート 作業記録 ← KARKYONさんがWORD等で作成してSCP配置
""")
