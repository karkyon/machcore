"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",      label: "ユーザ管理",         icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",   label: "機械管理",           icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",     label: "機械タイムカード",   icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",   label: "システム設定",       icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",        label: "RAWデータ",          icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor", label: "PDFフィールドエディタ", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
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
}

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) { const msg = await res.text().catch(() => ""); throw new Error(`HTTP ${res.status}: ${msg}`); }
  // PDFバイナリの場合はblobを返す
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/pdf")) return res.blob();
  return res.json();
};

export default function PdfEditorPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [fields,    setFields]    = useState<PdfField[]>([]);
  const [templates, setTemplates] = useState<string[]>([]);
  const [selTpl,    setSelTpl]    = useState("mc_setup_p1");
  const [selField,  setSelField]  = useState<PdfField | null>(null);
  const [loading,   setLoading]   = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [toast,     setToast]     = useState<{ msg: string; ok: boolean } | null>(null);
  const [pdfUrl,    setPdfUrl]    = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [mcId,      setMcId]      = useState("");
  // 編集中の値（未保存）
  const [editX,     setEditX]     = useState(0);
  const [editY,     setEditY]     = useState(0);
  const [editSize,  setEditSize]  = useState(8);
  const [editActive, setEditActive] = useState(true);

  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    loadFields();
  }, [selTpl]);

  const loadFields = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/pdf-fields?template=${selTpl}`);
      const arr: PdfField[] = Array.isArray(data) ? data : [];
      setFields(arr);
      const tplNames = [...new Set(arr.map(f => f.template?.name).filter(Boolean))];
      setTemplates(tplNames.length > 0 ? tplNames : [selTpl]);
    } catch (e: any) { showToast(`読み込み失敗: ${e.message}`, false); }
    finally { setLoading(false); }
  };

  const selectField = (f: PdfField) => {
    setSelField(f);
    setEditX(f.x); setEditY(f.y); setEditSize(f.fontSize); setEditActive(f.isActive);
  };

  const handleSave = async () => {
    if (!selField) return;
    setSaving(true);
    try {
      await apiFetch(`/admin/pdf-fields/${selField.id}`, {
        method: "PUT",
        body: JSON.stringify({ x: editX, y: editY, font_size: editSize, is_active: editActive }),
      });
      // ローカルstateも更新
      setFields(prev => prev.map(f => f.id === selField.id ? { ...f, x: editX, y: editY, fontSize: editSize, isActive: editActive } : f));
      setSelField(prev => prev ? { ...prev, x: editX, y: editY, fontSize: editSize, isActive: editActive } : null);
      showToast("✅ 保存しました", true);
    } catch (e: any) { showToast(`❌ 保存失敗: ${e.message}`, false); }
    finally { setSaving(false); }
  };

  const handlePreview = async () => {
    setPdfLoading(true);
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    try {
      const blob = await apiFetch(`/admin/pdf-preview${mcId ? `?mc_id=${mcId}` : ""}`);
      const url = URL.createObjectURL(blob as Blob);
      setPdfUrl(url);
    } catch (e: any) { showToast(`プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  const NumInput = ({ label, value, onChange, min, max, step = 1 }: any) => (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-xs font-bold text-slate-500">{label}</label>
        <input type="number" value={value} onChange={e => onChange(Number(e.target.value))}
          min={min} max={max} step={step}
          className="w-20 border border-slate-300 rounded px-2 py-1 text-xs text-right focus:ring-1 focus:ring-sky-400 focus:outline-none" />
      </div>
      <input type="range" value={value} onChange={e => onChange(Number(e.target.value))}
        min={min} max={max} step={step}
        className="w-full accent-sky-500 h-1.5" />
    </div>
  );

  const visibleFields = fields.filter(f => f.isActive && f.fieldKey !== "tooling_row");
  // PDF座標系: y は bottom から上（A4 = 595×842pt）
  const A4_W = 595, A4_H = 842;

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

        {/* メイン: 左ペイン（フィールド編集）+ 右ペイン（プレビュー） */}
        <div className="flex-1 overflow-hidden flex">

          {/* 左ペイン: フィールド一覧・編集 */}
          <div className="w-80 shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">
            {/* ツールバー */}
            <div className="shrink-0 border-b border-slate-100 p-3 space-y-2">
              <h1 className="text-sm font-bold text-slate-800">PDFフィールドエディタ</h1>
              <select value={selTpl} onChange={e => { setSelTpl(e.target.value); setSelField(null); }}
                className="w-full border border-slate-300 rounded px-2 py-1.5 text-xs bg-white focus:ring-1 focus:ring-sky-400 focus:outline-none">
                <option value="mc_setup_p1">mc_setup_p1（P1）</option>
                <option value="mc_setup_p2">mc_setup_p2（P2）</option>
              </select>
              <div className="flex gap-2">
                <input type="text" value={mcId} onChange={e => setMcId(e.target.value)} placeholder="MC ID（省略可）"
                  className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                <button onClick={handlePreview} disabled={pdfLoading}
                  className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50">
                  {pdfLoading ? "生成中…" : "▶ プレビュー"}
                </button>
              </div>
            </div>

            {/* フィールドリスト */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
              {loading ? <div className="text-center py-10 text-slate-400 text-xs">読み込み中…</div> :
                fields.map(f => (
                  <button key={f.id} onClick={() => selectField(f)}
                    className={`w-full text-left px-3 py-2 hover:bg-slate-50 transition-colors ${selField?.id === f.id ? "bg-sky-50 border-l-2 border-sky-500" : ""} ${!f.isActive ? "opacity-40" : ""}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-slate-700 truncate">{f.label}</span>
                      <span className="text-[10px] text-slate-400 font-mono shrink-0">{f.fontSize}pt</span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[10px] text-slate-400 font-mono">x:{f.x.toFixed(0)} y:{f.y.toFixed(0)}</span>
                      <span className="text-[10px] text-slate-400 truncate">{f.dataSource}</span>
                    </div>
                  </button>
                ))
              }
            </div>

            {/* 編集パネル */}
            {selField && (
              <div className="shrink-0 border-t border-slate-200 p-4 bg-sky-50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-sky-800 truncate">{selField.label}</span>
                  <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                    <input type="checkbox" checked={editActive} onChange={e => setEditActive(e.target.checked)}
                      className="accent-sky-500" />
                    有効
                  </label>
                </div>
                <NumInput label="X座標 (pt)" value={editX} onChange={setEditX} min={0} max={590} step={0.5} />
                <NumInput label="Y座標 (pt, 下からの距離)" value={editY} onChange={setEditY} min={0} max={840} step={0.5} />
                <NumInput label="フォントサイズ (pt)" value={editSize} onChange={setEditSize} min={4} max={24} step={0.5} />
                <div className="text-[10px] text-slate-500">
                  <span className="font-mono">dataSource: {selField.dataSource}</span>
                </div>
                <button onClick={handleSave} disabled={saving}
                  className="w-full py-2 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-50">
                  {saving ? "保存中…" : "💾 このフィールドを保存"}
                </button>
              </div>
            )}
          </div>

          {/* 右ペイン: PDFプレビュー + オーバーレイ */}
          <div className="flex-1 overflow-auto bg-slate-100 flex items-start justify-center p-6">
            {!pdfUrl ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/>
                </svg>
                <p className="text-sm font-medium">左の「▶ プレビュー」ボタンでPDFを生成します</p>
                <p className="text-xs">MCIDを指定するか、省略すると最初のMCプログラムを使用します</p>
              </div>
            ) : (
              <div className="relative shadow-xl">
                {/* PDFをiframeで表示 */}
                <iframe
                  src={pdfUrl}
                  className="block"
                  style={{ width: "595px", height: "842px", border: "none" }}
                  title="PDF Preview"
                />
                {/* フィールド位置オーバーレイ（SVG） */}
                <svg
                  className="absolute top-0 left-0 pointer-events-none"
                  style={{ width: "595px", height: "842px" }}
                  viewBox={`0 0 ${A4_W} ${A4_H}`}
                >
                  {visibleFields.map(f => {
                    // PDF座標: y は下から上 → SVG座標: y は上から下
                    const svgY = A4_H - f.y - f.fontSize;
                    const isSelected = selField?.id === f.id;
                    return (
                      <g key={f.id}>
                        <rect
                          x={f.x - 1} y={svgY - 1}
                          width={Math.max(60, f.label.length * f.fontSize * 0.6)}
                          height={f.fontSize + 4}
                          fill={isSelected ? "rgba(14,165,233,0.15)" : "rgba(239,68,68,0.06)"}
                          stroke={isSelected ? "#0ea5e9" : "#ef4444"}
                          strokeWidth={isSelected ? 1.5 : 0.5}
                          strokeDasharray={isSelected ? "none" : "3,2"}
                          rx={1}
                        />
                        <text
                          x={f.x}
                          y={svgY + f.fontSize - 1}
                          fontSize={Math.min(f.fontSize, 7)}
                          fill={isSelected ? "#0369a1" : "#dc2626"}
                          opacity={0.7}
                          fontFamily="sans-serif"
                        >
                          {f.label}
                        </text>
                      </g>
                    );
                  })}
                  {/* 選択フィールドのクロスヘア */}
                  {selField && (() => {
                    const svgY = A4_H - selField.y;
                    return (
                      <g>
                        <line x1={selField.x} y1={0} x2={selField.x} y2={A4_H} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                        <line x1={0} y1={svgY} x2={A4_W} y2={svgY} stroke="#0ea5e9" strokeWidth={0.5} strokeDasharray="4,3" opacity={0.5} />
                      </g>
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
