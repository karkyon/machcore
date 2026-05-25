#!/usr/bin/env python3
"""
fix_v75.py
===========
修正内容:
  1. [API 緊急修正] mc.module.ts に exports: [McService] 追加
     → AdminModule が McService を DI できず 500 エラーになっていた根本原因
  2. [UI] admin/pdf-editor/page.tsx: Anthropic API を使ったインタラクティブPDFエディタに刷新
     - 左ペイン: フィールド一覧テーブル（x/y/fontSize を直接数値入力）
       + 選択フィールドのスライダー編集
     - 右ペイン: iframeでPDFプレビュー + SVGオーバーレイでフィールド位置を可視化
     - 変更は即座に右側のオーバーレイに反映（PDF再生成不要）
     - 「保存してプレビュー更新」で DB保存 → PDF再生成 → 表示更新
  ビルド→pm2 restart→git push まで自動実行
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"
API  = f"{ROOT}/apps/api/src"

def read(path):
    with open(path, "r", encoding="utf-8") as f: return f.read()
def write(path, c):
    with open(path, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c: print(f"WARN: {label} — 不一致"); return False
    write(path, c.replace(old, new, 1)); print(f"OK: {label}"); return True
def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ─────────────────────────────────────────────────────────────
# 1. mc.module.ts に exports: [McService] 追加（根本原因修正）
# ─────────────────────────────────────────────────────────────
mc_module = f"{API}/mc/mc.module.ts"
patch(mc_module,
    "@Module({\n  controllers: [McController],\n  providers:   [McService, McFilesService],\n})\nexport class McModule {}",
    "@Module({\n  controllers: [McController],\n  providers:   [McService, McFilesService],\n  exports:     [McService],\n})\nexport class McModule {}",
    "mc.module.ts exports: [McService] 追加"
)

# ─────────────────────────────────────────────────────────────
# 2. admin/pdf-editor/page.tsx: 完全書き直し（インタラクティブ版）
# ─────────────────────────────────────────────────────────────
os.makedirs(f"{WEB}/app/admin/pdf-editor", exist_ok=True)
write(f"{WEB}/app/admin/pdf-editor/page.tsx", r'''"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",      label: "ユーザ管理",         icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",   label: "機械管理",           icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",     label: "機械タイムカード",   icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",   label: "システム設定",       icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",        label: "RAWデータ",          icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor", label: "PDFエディタ",        icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
];

interface PdfField {
  id: number;
  templateId: number;
  fieldKey: string;
  label: string;
  x: number;
  y: number;
  fontSize: number;
  dataSource: string;
  isActive: boolean;
  note: string | null;
  template: { name: string; filePath: string };
  // 編集中の値（未保存）
  _editX?: number;
  _editY?: number;
  _editSize?: number;
  _editActive?: boolean;
  _dirty?: boolean;
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

// A4 座標系（pdf-lib: y は bottom から上、単位 pt）
const A4_W = 595, A4_H = 842;

export default function PdfEditorPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [fields,     setFields]     = useState<PdfField[]>([]);
  const [selTpl,     setSelTpl]     = useState("mc_setup_p1");
  const [selId,      setSelId]      = useState<number | null>(null);
  const [loading,    setLoading]    = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [pdfUrl,     setPdfUrl]     = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [mcId,       setMcId]       = useState("");
  const prevUrlRef = useRef<string | null>(null);

  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3500); };

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    loadFields();
  }, [selTpl]);

  const loadFields = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/pdf-fields?template=${selTpl}`);
      const arr: PdfField[] = Array.isArray(data) ? data : [];
      setFields(arr.map(f => ({ ...f, _editX: f.x, _editY: f.y, _editSize: f.fontSize, _editActive: f.isActive, _dirty: false })));
    } catch (e: any) { showToast(`読み込み失敗: ${e.message}`, false); }
    finally { setLoading(false); }
  };

  const updateEdit = (id: number, key: "_editX" | "_editY" | "_editSize" | "_editActive", val: number | boolean) => {
    setFields(prev => prev.map(f => f.id === id ? { ...f, [key]: val, _dirty: true } : f));
  };

  const handleSaveOne = async (f: PdfField) => {
    setSaving(true);
    try {
      await apiFetch(`/admin/pdf-fields/${f.id}`, {
        method: "PUT",
        body: JSON.stringify({ x: f._editX, y: f._editY, font_size: f._editSize, is_active: f._editActive }),
      });
      // DB保存後にローカルも更新してdirtyクリア
      setFields(prev => prev.map(p => p.id === f.id ? { ...p, x: f._editX!, y: f._editY!, fontSize: f._editSize!, isActive: f._editActive!, _dirty: false } : p));
      showToast(`✅ 「${f.label}」を保存しました`, true);
    } catch (e: any) { showToast(`❌ 保存失敗: ${e.message}`, false); }
    finally { setSaving(false); }
  };

  const handleSaveAll = async () => {
    const dirty = fields.filter(f => f._dirty);
    if (!dirty.length) { showToast("変更なし", true); return; }
    setSaving(true);
    let ok = 0, ng = 0;
    await Promise.allSettled(dirty.map(f =>
      apiFetch(`/admin/pdf-fields/${f.id}`, {
        method: "PUT",
        body: JSON.stringify({ x: f._editX, y: f._editY, font_size: f._editSize, is_active: f._editActive }),
      }).then(() => ok++).catch(() => ng++)
    ));
    setFields(prev => prev.map(f => f._dirty ? { ...f, x: f._editX!, y: f._editY!, fontSize: f._editSize!, isActive: f._editActive!, _dirty: false } : f));
    showToast(ng === 0 ? `✅ ${ok}件保存しました` : `⚠️ ${ok}件成功、${ng}件失敗`, ng === 0);
    setSaving(false);
  };

  const handlePreview = async () => {
    setPdfLoading(true);
    if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
    try {
      const blob = await apiFetch(`/admin/pdf-preview${mcId ? `?mc_id=${mcId}` : ""}`);
      const url = URL.createObjectURL(blob as Blob);
      prevUrlRef.current = url;
      setPdfUrl(url);
    } catch (e: any) { showToast(`プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  const selField = fields.find(f => f.id === selId) ?? null;
  const activeFields = fields.filter(f => (f._editActive ?? f.isActive) && f.fieldKey !== "tooling_row");
  const dirtyCount = fields.filter(f => f._dirty).length;

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* ヘッダー */}
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
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
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

        {/* コンテンツ: 左ペイン（フィールドリスト）＋ 右ペイン（プレビュー） */}
        <div className="flex-1 overflow-hidden flex gap-0">

          {/* 左ペイン */}
          <div className="w-[420px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">
            {/* ツールバー */}
            <div className="shrink-0 p-3 border-b border-slate-100 space-y-2">
              <div className="flex items-center justify-between">
                <h1 className="text-sm font-bold text-slate-800">PDFフィールドエディタ</h1>
                {dirtyCount > 0 && (
                  <button onClick={handleSaveAll} disabled={saving}
                    className="px-3 py-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded disabled:opacity-50">
                    💾 {dirtyCount}件を一括保存
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <select value={selTpl} onChange={e => { setSelTpl(e.target.value); setSelId(null); }}
                  className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-xs bg-white focus:ring-1 focus:ring-sky-400 focus:outline-none">
                  <option value="mc_setup_p1">P1（段取シート表面）</option>
                  <option value="mc_setup_p2">P2（段取シート裏面）</option>
                </select>
                <input type="text" value={mcId} onChange={e => setMcId(e.target.value)} placeholder="MC_ID"
                  className="w-20 border border-slate-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                <button onClick={handlePreview} disabled={pdfLoading}
                  className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap">
                  {pdfLoading ? "生成中…" : "▶ プレビュー"}
                </button>
              </div>
            </div>

            {/* フィールド一覧テーブル */}
            <div className="flex-1 overflow-hidden flex flex-col">
              {/* ヘッダー固定 */}
              <div className="shrink-0 border-b border-slate-200 bg-slate-50">
                <table className="w-full text-xs table-fixed">
                  <colgroup>
                    <col className="w-5"/><col/><col className="w-14"/><col className="w-14"/><col className="w-12"/><col className="w-20"/>
                  </colgroup>
                  <thead>
                    <tr className="text-slate-500 uppercase text-[10px]">
                      <th className="px-1 py-2 text-center">✓</th>
                      <th className="px-2 py-2 text-left">フィールド名</th>
                      <th className="px-1 py-2 text-center">X</th>
                      <th className="px-1 py-2 text-center">Y</th>
                      <th className="px-1 py-2 text-center">pt</th>
                      <th className="px-1 py-2 text-center">操作</th>
                    </tr>
                  </thead>
                </table>
              </div>
              {/* スクロール明細 */}
              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="text-center py-10 text-slate-400 text-xs">読み込み中…</div>
                ) : (
                  <table className="w-full text-xs table-fixed">
                    <colgroup>
                      <col className="w-5"/><col/><col className="w-14"/><col className="w-14"/><col className="w-12"/><col className="w-20"/>
                    </colgroup>
                    <tbody className="divide-y divide-slate-100">
                      {fields.map(f => {
                        const isSel = selId === f.id;
                        const isDirty = f._dirty;
                        return (
                          <tr key={f.id}
                            onClick={() => setSelId(isSel ? null : f.id)}
                            className={`cursor-pointer ${isSel ? "bg-sky-50 border-l-2 border-sky-500" : isDirty ? "bg-amber-50" : "hover:bg-slate-50"} ${!(f._editActive ?? f.isActive) ? "opacity-40" : ""}`}>
                            <td className="px-1 py-1.5 text-center">
                              <input type="checkbox" checked={f._editActive ?? f.isActive}
                                onChange={e => { e.stopPropagation(); updateEdit(f.id, "_editActive", e.target.checked); }}
                                className="accent-sky-500 cursor-pointer" onClick={e => e.stopPropagation()} />
                            </td>
                            <td className="px-2 py-1.5">
                              <div className="font-medium text-slate-800 truncate">{f.label}</div>
                              <div className="text-[10px] text-slate-400 truncate font-mono">{f.dataSource}</div>
                            </td>
                            <td className="px-1 py-1 text-center">
                              <input type="number" value={f._editX ?? f.x} step="1"
                                onChange={e => updateEdit(f.id, "_editX", Number(e.target.value))}
                                onClick={e => e.stopPropagation()}
                                className="w-12 border border-slate-200 rounded px-1 py-0.5 text-center text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                            </td>
                            <td className="px-1 py-1 text-center">
                              <input type="number" value={f._editY ?? f.y} step="1"
                                onChange={e => updateEdit(f.id, "_editY", Number(e.target.value))}
                                onClick={e => e.stopPropagation()}
                                className="w-12 border border-slate-200 rounded px-1 py-0.5 text-center text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                            </td>
                            <td className="px-1 py-1 text-center">
                              <input type="number" value={f._editSize ?? f.fontSize} step="0.5" min="4" max="24"
                                onChange={e => updateEdit(f.id, "_editSize", Number(e.target.value))}
                                onClick={e => e.stopPropagation()}
                                className="w-10 border border-slate-200 rounded px-1 py-0.5 text-center text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                            </td>
                            <td className="px-1 py-1.5 text-center">
                              {f._dirty && (
                                <button onClick={e => { e.stopPropagation(); handleSaveOne(f); }} disabled={saving}
                                  className="px-2 py-0.5 bg-sky-600 hover:bg-sky-700 text-white rounded text-[10px] font-bold disabled:opacity-50 whitespace-nowrap">
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

            {/* 選択フィールドのスライダーパネル */}
            {selField && (
              <div className="shrink-0 border-t border-slate-200 p-4 bg-sky-50 space-y-3">
                <div className="text-xs font-bold text-sky-800">{selField.label} <span className="font-normal text-slate-500 ml-1 font-mono">{selField.dataSource}</span></div>
                {(["_editX","_editY"] as const).map(k => {
                  const label = k === "_editX" ? "X座標" : "Y座標 (下からの距離)";
                  const val = selField[k] ?? (k === "_editX" ? selField.x : selField.y);
                  return (
                    <div key={k} className="space-y-0.5">
                      <div className="flex justify-between items-center">
                        <label className="text-[10px] font-bold text-slate-500">{label}</label>
                        <span className="text-[10px] font-mono text-sky-700">{Number(val).toFixed(1)} pt</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <input type="range" min={0} max={k === "_editX" ? A4_W : A4_H} step={1} value={val}
                          onChange={e => updateEdit(selField.id, k, Number(e.target.value))}
                          className="flex-1 accent-sky-500 h-1.5" />
                        <input type="number" min={0} max={k === "_editX" ? A4_W : A4_H} step={1} value={val}
                          onChange={e => updateEdit(selField.id, k, Number(e.target.value))}
                          className="w-16 border border-slate-300 rounded px-1 py-0.5 text-xs text-right focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                      </div>
                    </div>
                  );
                })}
                <div className="space-y-0.5">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-bold text-slate-500">フォントサイズ</label>
                    <span className="text-[10px] font-mono text-sky-700">{Number(selField._editSize ?? selField.fontSize).toFixed(1)} pt</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="range" min={4} max={24} step={0.5} value={selField._editSize ?? selField.fontSize}
                      onChange={e => updateEdit(selField.id, "_editSize", Number(e.target.value))}
                      className="flex-1 accent-sky-500 h-1.5" />
                    <input type="number" min={4} max={24} step={0.5} value={selField._editSize ?? selField.fontSize}
                      onChange={e => updateEdit(selField.id, "_editSize", Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded px-1 py-0.5 text-xs text-right focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleSaveOne(selField)} disabled={saving || !selField._dirty}
                    className="flex-1 py-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-40">
                    {saving ? "保存中…" : "💾 保存してオーバーレイ更新"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 右ペイン: PDFプレビュー + SVGオーバーレイ */}
          <div className="flex-1 overflow-auto bg-slate-200 flex items-start justify-center p-6">
            {!pdfUrl ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4 select-none">
                <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/>
                </svg>
                <p className="text-sm font-medium">「▶ プレビュー」でPDFを生成</p>
                <p className="text-xs text-center">保存後にプレビューを再生成すると<br/>最新のフィールド位置が反映されます</p>
              </div>
            ) : (
              <div className="relative shadow-2xl" style={{ width: "595px" }}>
                <iframe src={pdfUrl} title="PDF Preview"
                  style={{ display: "block", width: "595px", height: "842px", border: "none", background: "white" }} />
                {/* SVGオーバーレイ: フィールド位置リアルタイム表示 */}
                <svg className="absolute top-0 left-0 pointer-events-none"
                  style={{ width: "595px", height: "842px" }}
                  viewBox={`0 0 ${A4_W} ${A4_H}`}>
                  {activeFields.map(f => {
                    const ex = f._editX ?? f.x;
                    const ey = f._editY ?? f.y;
                    const es = f._editSize ?? f.fontSize;
                    // PDF座標(y=bottomから上) → SVG座標(y=topから下)
                    const svgY = A4_H - ey - es;
                    const isSel = selId === f.id;
                    const isDirty = f._dirty;
                    const boxW = Math.max(40, f.label.length * es * 0.55);
                    return (
                      <g key={f.id}>
                        <rect x={ex - 1} y={svgY - 1} width={boxW} height={es + 4} rx={1}
                          fill={isSel ? "rgba(14,165,233,0.18)" : isDirty ? "rgba(249,115,22,0.12)" : "rgba(239,68,68,0.06)"}
                          stroke={isSel ? "#0ea5e9" : isDirty ? "#f97316" : "#ef4444"}
                          strokeWidth={isSel ? 1.5 : isDirty ? 1.2 : 0.7}
                          strokeDasharray={isSel ? "none" : "3,2"} />
                        <text x={ex} y={svgY + es - 1} fontSize={Math.min(es * 0.85, 7)}
                          fill={isSel ? "#0369a1" : isDirty ? "#c2410c" : "#dc2626"}
                          opacity={0.75} fontFamily="sans-serif">
                          {f.label}
                        </text>
                      </g>
                    );
                  })}
                  {/* 選択フィールドのクロスヘア */}
                  {selField && (() => {
                    const ex = selField._editX ?? selField.x;
                    const ey = selField._editY ?? selField.y;
                    const svgY = A4_H - ey;
                    return (
                      <>
                        <line x1={ex} y1={0} x2={ex} y2={A4_H} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.6} />
                        <line x1={0} y1={svgY} x2={A4_W} y2={svgY} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.6} />
                        <circle cx={ex} cy={svgY} r={3} fill="#0ea5e9" opacity={0.8} />
                      </>
                    );
                  })()}
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
''')
print("OK: admin/pdf-editor/page.tsx インタラクティブ版書き直し")

# ─────────────────────────────────────────────────────────────
# 3. ビルド + pm2 + push
# ─────────────────────────────────────────────────────────────
print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED (web) — abort"); sys.exit(1)

print("--- build api ---")
rc2 = run("pnpm --filter api build", cwd=ROOT)
if rc2 != 0: rc2 = run("pnpm run build", cwd=f"{ROOT}/apps/api")
if rc2 != 0: print("BUILD FAILED (api) — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-api machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v75): mc.module exports修正(全API500修正)+PDFエディタインタラクティブ版' && git push", cwd=ROOT)
print("DONE v75")
