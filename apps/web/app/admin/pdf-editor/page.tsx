"use client";
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

// pdf-lib座標系: Y は下からの距離（A4=595×842pt）
const A4_W = 595, A4_H = 842;
// pdf-lib Y → SVG Y (上からの距離) 変換
const toSvgY = (y: number, size: number) => A4_H - y - size;

interface PdfField {
  id: number; templateId: number; fieldKey: string; label: string;
  x: number; y: number; fontSize: number; dataSource: string;
  isActive: boolean; note: string | null;
  template: { name: string };
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
  const [fields, setFields] = useState<PdfField[]>([]);
  const [selTpl, setSelTpl] = useState("mc_setup_p1");
  const [selId,  setSelId]  = useState<number | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [toast,    setToast]    = useState<{ msg: string; ok: boolean } | null>(null);
  const [pdfBytes, setPdfBytes] = useState<ArrayBuffer | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [mcIdInput,  setMcIdInput]  = useState("");
  const [canvasSize, setCanvasSize] = useState({ w: 595, h: 842 });
  const [scale, setScale] = useState(1.0);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const dragStart = useRef<{ mx: number; my: number; ox: number; oy: number } | null>(null);

  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3500); };

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    loadFields();
  }, [selTpl]);

  // pdfjs でPDFをcanvasに描画
  useEffect(() => {
    if (!pdfBytes || !canvasRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        // pdfjs CDN
        const pdfjsLib = (window as any).pdfjsLib;
        if (!pdfjsLib) { console.warn("pdfjs not loaded"); return; }
        const pdf = await pdfjsLib.getDocument({ data: pdfBytes }).promise;
        const page = await pdf.getPage(1);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current!;
        canvas.width  = viewport.width;
        canvas.height = viewport.height;
        setCanvasSize({ w: viewport.width, h: viewport.height });
        const ctx = canvas.getContext("2d")!;
        await page.render({ canvasContext: ctx, viewport }).promise;
      } catch (e) { console.error("pdfjs render error", e); }
    })();
    return () => { cancelled = true; };
  }, [pdfBytes, scale]);

  const loadFields = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/pdf-fields?template=${selTpl}`);
      const arr: PdfField[] = Array.isArray(data) ? data : [];
      setFields(arr.map(f => ({ ...f, _ex: f.x, _ey: f.y, _es: f.fontSize, _ea: f.isActive, _dirty: false })));
    } catch (e: any) { showToast(`読み込み失敗: ${e.message}`, false); }
    finally { setLoading(false); }
  };

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

  const loadPreview = async () => {
    setPdfLoading(true);
    try {
      const blob = await apiFetch(`/admin/pdf-preview${mcIdInput ? `?mc_id=${mcIdInput}` : ""}`);
      const ab = await (blob as Blob).arrayBuffer();
      setPdfBytes(ab);
    } catch (e: any) { showToast(`プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  // ── ドラッグ&ドロップ（SVGオーバーレイ上） ──
  const svgScale = canvasSize.w / A4_W; // canvas px / pdf pt

  const handleSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>, id: number, ox: number, oy: number) => {
    e.preventDefault();
    setSelId(id);
    setDraggingId(id);
    dragStart.current = { mx: e.clientX, my: e.clientY, ox, oy };
  };

  const handleSvgMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (draggingId === null || !dragStart.current) return;
    const dx = (e.clientX - dragStart.current.mx) / svgScale;
    const dy = (e.clientY - dragStart.current.my) / svgScale;
    const newX = Math.max(0, Math.min(A4_W, dragStart.current.ox + dx));
    // SVGのY増加 = PDFのY減少（下からの距離が減る）
    const newY = Math.max(0, Math.min(A4_H, dragStart.current.oy - dy));
    setFields(prev => prev.map(f => f.id === draggingId
      ? { ...f, _ex: Math.round(newX * 10) / 10, _ey: Math.round(newY * 10) / 10, _dirty: true } : f));
  }, [draggingId, svgScale]);

  const handleSvgMouseUp = useCallback(() => {
    setDraggingId(null);
    dragStart.current = null;
  }, []);

  const selField = fields.find(f => f.id === selId) ?? null;
  const activeFields = fields.filter(f => (f._ea ?? f.isActive) && f.fieldKey !== "tooling_row");
  const dirtyCount = fields.filter(f => f._dirty).length;

  return (
    <>
      {/* pdfjs CDN読み込み */}
      <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js" />
      <script dangerouslySetInnerHTML={{ __html: `
        if(window.pdfjsLib) window.pdfjsLib.GlobalWorkerOptions.workerSrc =
          'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      `}} />

      <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
            </div>
            <span className="text-sm font-bold text-slate-800">MachCore 管理パネル</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
            <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
              className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
          </div>
        </header>

        {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-emerald-500" : "bg-red-500"}`}>{toast.msg}</div>}

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* サイドバー */}
          <aside className="w-48 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
            <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
            {SIDEBAR_ITEMS.map(item => (
              <a key={item.href} href={item.href}
                className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                  pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
                {item.label}
              </a>
            ))}
          </aside>

          {/* 左ペイン: フィールド管理（w-80に縮小） */}
          <div className="w-80 shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">
            {/* ツールバー */}
            <div className="shrink-0 p-2 border-b border-slate-100 space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <select value={selTpl} onChange={e => { setSelTpl(e.target.value); setSelId(null); }}
                  className="flex-1 border border-slate-300 rounded px-2 py-1 text-xs bg-white">
                  <option value="mc_setup_p1">P1（段取シート表面）</option>
                  <option value="mc_setup_p2">P2（段取シート裏面）</option>
                </select>
                {dirtyCount > 0 && (
                  <button onClick={saveAll} disabled={saving}
                    className="px-2 py-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap">
                    💾 {dirtyCount}件保存
                  </button>
                )}
              </div>
              <div className="flex gap-1.5">
                <input type="text" value={mcIdInput} onChange={e => setMcIdInput(e.target.value)}
                  placeholder="MC_ID（省略可）"
                  className="flex-1 border border-slate-300 rounded px-2 py-1 text-xs" />
                <button onClick={loadPreview} disabled={pdfLoading}
                  className="px-2 py-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap">
                  {pdfLoading ? "生成中…" : "▶ PDF生成"}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-400">表示倍率:</span>
                {[0.75, 1.0, 1.25, 1.5].map(s => (
                  <button key={s} onClick={() => setScale(s)}
                    className={`px-2 py-0.5 text-[10px] rounded border ${scale === s ? "bg-sky-600 text-white border-sky-600" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
                    {Math.round(s * 100)}%
                  </button>
                ))}
              </div>
            </div>

            {/* フィールドテーブル（固定ヘッダー） */}
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="shrink-0 border-b border-slate-200 bg-slate-50">
                <table className="w-full text-xs table-fixed">
                  <colgroup><col className="w-5"/><col/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                  <thead>
                    <tr className="text-slate-400 text-[10px] uppercase">
                      <th className="px-1 py-1.5 text-center">✓</th>
                      <th className="px-2 py-1.5 text-left">フィールド</th>
                      <th className="py-1.5 text-center">X</th>
                      <th className="py-1.5 text-center">Y</th>
                      <th className="py-1.5 text-center">pt</th>
                      <th className="py-1.5 text-center">保存</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                {loading ? <div className="text-center py-10 text-slate-400 text-xs">読み込み中…</div> : (
                  <table className="w-full text-xs table-fixed">
                    <colgroup><col className="w-5"/><col/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                    <tbody className="divide-y divide-slate-100">
                      {fields.map(f => {
                        const isSel = selId === f.id;
                        return (
                          <tr key={f.id} onClick={() => setSelId(isSel ? null : f.id)}
                            className={`cursor-pointer ${isSel ? "bg-sky-50 border-l-2 border-sky-500" : f._dirty ? "bg-amber-50" : "hover:bg-slate-50"} ${!(f._ea ?? f.isActive) ? "opacity-40" : ""}`}>
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
                              <input type="number" value={f._es ?? f.fontSize} step="0.5" min="4" max="24"
                                onChange={e => upd(f.id, "_es", Number(e.target.value))}
                                className="w-9 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                            </td>
                            <td className="py-1 text-center" onClick={e => e.stopPropagation()}>
                              {f._dirty && (
                                <button onClick={() => saveOne(f)} disabled={saving}
                                  className="px-1.5 py-0.5 bg-sky-600 hover:bg-sky-700 text-white rounded text-[9px] font-bold disabled:opacity-50">
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
            </div>

            {/* 選択フィールドのスライダー */}
            {selField && (
              <div className="shrink-0 border-t border-slate-200 p-3 bg-sky-50 space-y-2">
                <div className="text-xs font-bold text-sky-800 truncate">{selField.label}
                  <span className="font-normal text-slate-500 ml-1 text-[10px] font-mono">{selField.dataSource}</span>
                </div>
                {([["X座標", "_ex", 0, A4_W], ["Y座標（下から）", "_ey", 0, A4_H], ["フォントサイズ", "_es", 4, 24]] as const).map(([lbl, k, mn, mx]) => {
                  const v = (selField as any)[k] ?? (k === "_ex" ? selField.x : k === "_ey" ? selField.y : selField.fontSize);
                  return (
                    <div key={k} className="space-y-0.5">
                      <div className="flex justify-between">
                        <span className="text-[10px] font-bold text-slate-500">{lbl}</span>
                        <span className="text-[10px] font-mono text-sky-700">{Number(v).toFixed(1)}</span>
                      </div>
                      <div className="flex gap-1.5 items-center">
                        <input type="range" min={mn} max={mx} step={k === "_es" ? 0.5 : 1} value={v}
                          onChange={e => upd(selField.id, k as any, Number(e.target.value))}
                          className="flex-1 accent-sky-500 h-1.5" />
                        <input type="number" min={mn} max={mx} step={k === "_es" ? 0.5 : 1} value={v}
                          onChange={e => upd(selField.id, k as any, Number(e.target.value))}
                          className="w-14 border border-slate-300 rounded px-1 py-0.5 text-xs text-right" />
                      </div>
                    </div>
                  );
                })}
                <button onClick={() => saveOne(selField)} disabled={saving || !selField._dirty}
                  className="w-full py-1 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-40">
                  {saving ? "保存中…" : "💾 保存"}
                </button>
              </div>
            )}
          </div>

          {/* 右ペイン: PDF canvas + SVGオーバーレイ（幅最大化） */}
          <div className="flex-1 overflow-auto bg-slate-300 flex items-start justify-center p-4">
            {!pdfBytes ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-4 select-none">
                <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/>
                </svg>
                <p className="text-sm font-semibold">「▶ PDF生成」でプレビューを表示</p>
                <p className="text-xs text-center text-slate-400">生成後、フィールドをドラッグして位置調整できます<br/>保存後に再生成すると印字位置を確認できます</p>
              </div>
            ) : (
              <div className="relative shadow-2xl" style={{ width: canvasSize.w, height: canvasSize.h }}>
                {/* pdfjs canvas */}
                <canvas ref={canvasRef} className="absolute top-0 left-0 block" />
                {/* SVGオーバーレイ（D&D対応、canvasと同サイズ） */}
                <svg
                  className="absolute top-0 left-0"
                  style={{
                    width: canvasSize.w, height: canvasSize.h,
                    cursor: draggingId !== null ? "grabbing" : "default",
                    userSelect: "none",
                  }}
                  viewBox={`0 0 ${A4_W} ${A4_H}`}
                  onMouseMove={handleSvgMouseMove}
                  onMouseUp={handleSvgMouseUp}
                  onMouseLeave={handleSvgMouseUp}
                >
                  {activeFields.map(f => {
                    const ex = f._ex ?? f.x, ey = f._ey ?? f.y, es = f._es ?? f.fontSize;
                    const svgY = toSvgY(ey, es);
                    const isSel = selId === f.id;
                    const isDirty = f._dirty;
                    const boxW = Math.max(30, f.label.length * es * 0.55);
                    return (
                      <g key={f.id}
                        style={{ cursor: "grab" }}
                        onMouseDown={e => handleSvgMouseDown(e, f.id, ex, ey)}>
                        <rect x={ex - 1} y={svgY - 1} width={boxW} height={es + 4} rx={1}
                          fill={isSel ? "rgba(14,165,233,0.2)" : isDirty ? "rgba(249,115,22,0.12)" : "rgba(239,68,68,0.07)"}
                          stroke={isSel ? "#0ea5e9" : isDirty ? "#f97316" : "#ef4444"}
                          strokeWidth={isSel ? 1.5 : 0.8}
                          strokeDasharray={isSel ? "none" : "3,2"} />
                        <text x={ex} y={svgY + es - 0.5}
                          fontSize={Math.min(es * 0.9, 7)}
                          fill={isSel ? "#0369a1" : isDirty ? "#c2410c" : "#dc2626"}
                          opacity={0.8} fontFamily="sans-serif" pointerEvents="none">
                          {f.label}
                        </text>
                      </g>
                    );
                  })}
                  {/* 選択フィールドのクロスヘア */}
                  {selField && (() => {
                    const ex = selField._ex ?? selField.x;
                    const ey = selField._ey ?? selField.y;
                    const es = selField._es ?? selField.fontSize;
                    const svgY = toSvgY(ey, es);
                    return (
                      <>
                        <line x1={ex} y1={0} x2={ex} y2={A4_H} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                        <line x1={0} y1={svgY} x2={A4_W} y2={svgY} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                        <circle cx={ex} cy={svgY} r={3} fill="#0ea5e9" opacity={0.7} />
                      </>
                    );
                  })()}
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
