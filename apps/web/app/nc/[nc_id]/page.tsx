"use client";
// SSR環境でのDOMMatrix polyfill（react-pdf用）
if (typeof window === "undefined" && typeof (global as any).DOMMatrix === "undefined") {
  (global as any).DOMMatrix = class DOMMatrix { constructor(..._: any[]) {} };
}
import React from "react";
import dynamic from "next/dynamic";
const ImageEditor = dynamic(() => import("@/components/nc/ImageEditor"), { ssr: false });
import { useDropzone } from "react-dropzone";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useRef, useCallback } from "react";
import {
  ncApi, NcDetail, NcTool, ChangeHistory, WorkRecord, SetupSheetLog,
  NcFile, filesApi, downloadApi, OperationLog, operationLogsApi,
} from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";
import { useAuth } from "@/contexts/AuthContext";
import { ProcessEntry } from "@/lib/api";
import AuthModal from "@/components/auth/AuthModal";

type MainTab = "lathe" | "history" | "files";
type HistorySubTab = "change" | "work" | "print" | "oplog";

const CHANGE_TYPE_LABELS: Record<string, string> = {
  NEW_REGISTRATION: "新規登録",
  CHANGE:           "変更",
  APPROVAL:         "承認",
  MIGRATION:        "移行",
};

export default function NcDetailPage() {
  const { nc_id } = useParams();
  const router    = useRouter();
  const ncId      = Number(nc_id);

  const [detail,      setDetail]      = useState<NcDetail | null>(null);
  const [loadError,   setLoadError]   = useState<string | null>(null);
  const [processes,   setProcesses]   = useState<ProcessEntry[]>([]);
  const [floatOpen,   setFloatOpen]   = useState(true);
  const [floatPos,    setFloatPos]    = useState({ x: 900, y: 120 });
  const [dragging,    setDragging]    = useState(false);
  const dragStart     = useRef<{ mx: number; my: number; px: number; py: number } | null>(null);

  const [mainTab,     setMainTab]     = useState<MainTab>("lathe");
  const [histTab,     setHistTab]     = useState<HistorySubTab>("change");

  const [changes,     setChanges]     = useState<ChangeHistory[] | null>(null);
  const [works,       setWorks]       = useState<WorkRecord[]    | null>(null);
  const [prints,      setPrints]      = useState<SetupSheetLog[] | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [oplogs,      setOplogs]      = useState<OperationLog[] | null>(null);

  // ── ファイルタブ用ステート ──
  const [files,        setFiles]        = useState<NcFile[] | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [previewFile,  setPreviewFile]  = useState<NcFile | null>(null);
  const [uploading,    setUploading]    = useState(false);
  const [fileError,    setFileError]    = useState<string | null>(null);
  const [pdfNumPages,  setPdfNumPages]  = useState<number>(1);
  const [pdfPage,      setPdfPage]      = useState<number>(1);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AUTH（D&Dより先に宣言必須）
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authModalOpen,   setAuthModalOpen]   = useState(false);
  const [authSessionType, setAuthSessionType] = useState("edit");

  const openAuth = useCallback((sessionType: string) => {
    setAuthSessionType(sessionType);
    setAuthModalOpen(true);
  }, []);
  const [pendingUsb, setPendingUsb] = useState(false);

  // ── ファイルアップロード（ボタン経由）──
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!token || !operator) { openAuth("edit"); return; }
    setUploading(true);
    setFileError(null);
    try {
      await filesApi.upload(ncId, file, token);
      const res = await filesApi.list(ncId);
      setFiles(res.data);
      ncApi.findOne(ncId).then(r => setDetail(r.data));
    } catch {
      setFileError("アップロードに失敗しました");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── ファイル削除 ──
  const handleDelete = async (fileId: number) => {
    if (!confirm("このファイルを削除しますか？")) return;
    if (!token) { openAuth("edit"); return; }
    try {
      await filesApi.delete(fileId, token);
      setFiles(prev => prev ? prev.filter(f => f.id !== fileId) : prev);
      if (previewFile?.id === fileId) setPreviewFile(null);
      ncApi.findOne(ncId).then(r => setDetail(r.data));
    } catch {
      setFileError("削除に失敗しました");
    }
  };

  // ── D&Dアップロード（react-dropzone）── useAuth・openAuth後に配置
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (!token || !operator) { openAuth("edit"); return; }
    setFileError(null);
    for (const file of acceptedFiles) {
      setUploading(true);
      try {
        await filesApi.upload(ncId, file, token);
      } catch {
        setFileError(`${file.name} のアップロードに失敗しました`);
      } finally {
        setUploading(false);
      }
    }
    const res = await filesApi.list(ncId);
    setFiles(res.data);
    ncApi.findOne(ncId).then(r => setDetail(r.data));
  }, [ncId, openAuth]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [], "application/pdf": [] },
    noClick: true,
    disabled: !(isAuthenticated && operator) || uploading,
  });

  // NC詳細ロード
  // USB pending: 認証成功後に自動ダウンロード
  useEffect(() => {
    if (isAuthenticated && pendingUsb && token) {
      setPendingUsb(false);
      downloadApi.pgFile(ncId, token).catch(() => alert("PGファイルのダウンロードに失敗しました"));
    }
  }, [isAuthenticated, pendingUsb, token, ncId]);

  useEffect(() => {
    if (!ncId) return;
    ncApi.findOne(ncId)
      .then(r => {
        setDetail(r.data);
        const partId = (r.data as any)?.part?.id;
        if (partId) {
          ncApi.byPart(partId).then(p => setProcesses(p.data ?? [])).catch(() => {});
        }
      })
      .catch(e => setLoadError(e.message));
  }, [ncId]);

  // 履歴タブ選択時にAPIコール（初回のみ）
  useEffect(() => {
    if (mainTab !== "history") return;
    if (histTab === "change" && changes === null) {
      setHistLoading(true);
      ncApi.changeHistory(ncId).then(r => setChanges(r.data)).finally(() => setHistLoading(false));
    }
    if (histTab === "work" && works === null) {
      setHistLoading(true);
      ncApi.workRecords(ncId).then(r => setWorks(r.data)).finally(() => setHistLoading(false));
    }
    if (histTab === "print" && prints === null) {
      setHistLoading(true);
      ncApi.setupSheetLogs(ncId).then(r => setPrints(r.data)).finally(() => setHistLoading(false));
    }
    if (histTab === "oplog" && oplogs === null) {
      setHistLoading(true);
      ncApi.operationLogs(ncId).then(r => setOplogs(r.data)).catch(() => setOplogs([])).finally(() => setHistLoading(false));
    }
  }, [mainTab, histTab, ncId, changes, works, prints, oplogs]);

  // ファイルタブ選択時にAPIコール（初回のみ）
  useEffect(() => {
    if (mainTab !== "files" || files !== null) return;
    setFilesLoading(true);
    filesApi.list(ncId)
      .then(r => setFiles(r.data))
      .catch(() => setFileError("ファイルの取得に失敗しました"))
      .finally(() => setFilesLoading(false));
  }, [mainTab, ncId, files]);

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString("ja-JP", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });

  if (loadError) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-red-500 text-sm">読み込みエラー: {loadError}</div>
    </div>
  );
  if (!detail) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-slate-400 text-sm">読み込み中...</div>
    </div>
  );

  const d = detail;

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !dragStart.current) return;
    setFloatPos({
      x: Math.max(0, dragStart.current.px + e.clientX - dragStart.current.mx),
      y: Math.max(0, dragStart.current.py + e.clientY - dragStart.current.my),
    });
  };
  const onMouseUp = () => { setDragging(false); dragStart.current = null; };

  return (
    <>
      <div className="h-screen flex flex-col bg-slate-50" onMouseMove={onMouseMove} onMouseUp={onMouseUp}>

        {/* ── ヘッダー ── */}
        <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
          <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
          <span className="text-slate-400 text-xs">|</span>
          <button onClick={() => router.push("/mc/search")} className="text-xs bg-white text-slate-800 hover:bg-slate-100 border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ MC</button>
          <span className="text-sm font-medium">NC 詳細</span>
          <span className="ml-auto">
            <button onClick={() => router.push("/nc/search")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 rounded-lg text-xs font-bold text-white transition-colors">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
              部品検索へ戻る
            </button>
          </span>


        </header>

        {/* ── フローティング工程切り替えパネル ── */}
        {processes.length > 1 && (
          <div
            style={{ position: "fixed", left: floatPos.x, top: floatPos.y, zIndex: 100, userSelect: "none" }}
            className="shadow-2xl rounded-xl overflow-hidden border border-slate-700 w-52"
          >
            {/* ヘッダー（ドラッグハンドル + OPEN/CLOSE） */}
            <div
              className="bg-slate-800 text-white px-3 py-1.5 flex items-center gap-2 cursor-move"
              onMouseDown={e => {
                setDragging(true);
                dragStart.current = { mx: e.clientX, my: e.clientY, px: floatPos.x, py: floatPos.y };
              }}
            >
              <span className="text-[10px] font-bold text-slate-300 flex-1">⚙ 工程切り替え</span>
              <button
                onMouseDown={e => e.stopPropagation()}
                onClick={() => setFloatOpen(v => !v)}
                className="text-[10px] bg-slate-700 hover:bg-slate-600 px-2 py-0.5 rounded font-bold text-slate-200"
              >
                {floatOpen ? "CLOSE" : "OPEN"}
              </button>
            </div>
            {/* 工程リスト */}
            {floatOpen && (
              <div className="bg-white">
                {processes.map(p => (
                  <button
                    key={p.nc_id}
                    onClick={() => router.push(`/nc/${p.nc_id}`)}
                    className={`w-full text-left px-3 py-2 text-xs border-b border-slate-100 flex items-center gap-2 transition-colors ${
                      p.nc_id === ncId
                        ? "bg-sky-50 border-l-2 border-l-sky-400"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${p.nc_id === ncId ? "bg-sky-500 text-white" : "bg-slate-100 text-slate-600"}`}>
                      L{p.process_l}
                    </span>
                    <span className="font-mono text-slate-600">{p.machine_code ?? "—"}</span>
                    <span className={`ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      p.status === "APPROVED" ? "bg-green-100 text-green-700" :
                      p.status === "CHANGING" ? "bg-orange-100 text-orange-700" :
                      "bg-slate-100 text-slate-500"
                    }`}>
                      {p.status === "APPROVED" ? "承認済" : p.status === "CHANGING" ? "変更中" : p.status === "PENDING_APPROVAL" ? "承認待" : "新規"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── 部品ヘッダーエリア ── */}
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-sky-600 font-bold text-lg">{d.part.drawingNo}</span>
            <ProcessBadge level={d.processL} />
            <StatusBadge status={d.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">
              Ver. {d.version}
            </span>
          </div>
          <div className="text-sm text-slate-700 font-medium mb-1">{d.part.name}</div>
          <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
            <span>NC_id: {d.id}</span>
            <span>部品ID: {d.part.partId}</span>
            {d.part.clientName && <span>納入先: {d.part.clientName}</span>}
            {d.processingId && <span>加工ID: {d.processingId}</span>}
          </div>
        </div>

        {/* ── 画面ナビゲーションタブ ── */}
        <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
          {([
            { href: `/nc/${ncId}`,        label: "NC詳細",    active: true,  svg: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> },
            { href: `/nc/${ncId}/edit`,   label: "変更・登録", active: false, svg: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> },
            { href: `/nc/${ncId}/print`,  label: "段取シート", active: false, svg: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg> },
            { href: `/nc/${ncId}/record`, label: "作業記録",  active: false, svg: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> },
          ] as { href: string; label: string; active: boolean; svg: React.ReactNode }[]).map(tab => (
            <button
              key={tab.href}
              onClick={() => router.push(tab.href)}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active
                  ? "border-sky-400 text-sky-300"
                  : "border-transparent text-slate-400 hover:text-white hover:border-slate-400"
              }`}
            >
              {tab.svg}
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>

        {/* ── メインタブバー ── */}
        <div className="bg-white border-b border-slate-200 px-5 shrink-0 flex gap-0">
          {([
            { key: "lathe",   label: "旋盤データ", svg: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg> },
            { key: "history", label: "履歴",       svg: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg> },
            { key: "files",   label: "写真・図",   svg: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg> },
          ] as { key: MainTab; label: string; svg: React.ReactNode }[]).map(t => (
            <button
              key={t.key}
              onClick={() => setMainTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                mainTab === t.key
                  ? "border-sky-500 text-sky-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.svg}
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* ── タブコンテンツ ── */}
        <div className="flex-1 overflow-y-auto">

          {/* ─ 旋盤データ（加工リスト含む） ─ */}
          {mainTab === "lathe" && (
            <div className="p-5 space-y-5 max-w-5xl">

              {/* ── 上部グリッド: 工程・機械・加工時間・フォルダ・図・写真 ── */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="grid grid-cols-6 divide-x divide-slate-100 border-b border-slate-100">
                  {[
                    { label: "工程 L", value: String(d.processL), mono: true },
                    { label: "機械",   value: d.machine?.machineCode ?? "—", mono: true },
                    { label: "加工時間", value: d.machiningTime != null ? `${d.machiningTime} 分` : "—", mono: true },
                    { label: "フォルダ", value: d.folderName ?? "—", mono: true },
                  ].map(f => (
                    <div key={f.label} className="p-3">
                      <div className="text-[10px] text-slate-400 mb-1">{f.label}</div>
                      <div className={`text-sm font-medium text-slate-800 ${f.mono ? "font-mono" : ""}`}>{f.value}</div>
                    </div>
                  ))}
                  {/* 図 */}
                  <div className="p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">図</div>
                    <button onClick={() => setMainTab("files")}
                      className="text-sm font-bold text-sky-600 hover:text-sky-700 hover:underline transition-colors">
                      {d.drawingCount} 枚
                    </button>
                  </div>
                  {/* 写真 */}
                  <div className="p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">写真</div>
                    <button onClick={() => setMainTab("files")}
                      className="text-sm font-bold text-sky-600 hover:text-sky-700 hover:underline transition-colors">
                      {d.photoCount} 枚
                    </button>
                  </div>
                </div>

                {/* ── ファイル名 / O番号（独立行） ── */}
                <div className="grid grid-cols-2 divide-x divide-slate-100 border-b border-slate-100">
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">ファイル名</div>
                    <div className="text-sm font-mono font-medium text-slate-800">{d.fileName ?? "—"}</div>
                  </div>
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">O番号</div>
                    <div className="text-sm font-mono font-medium text-slate-800">{d.oNumber ?? "—"}</div>
                  </div>
                </div>

                {/* ── NC_id / 加工ID（独立行） ── */}
                <div className="grid grid-cols-2 divide-x divide-slate-100 border-b border-slate-100">
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">NC_id</div>
                    <div className="text-sm font-mono font-medium text-slate-800">{d.id}</div>
                  </div>
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">加工ID</div>
                    <div className="text-sm font-mono font-medium text-slate-800">{d.processingId ?? "—"}</div>
                  </div>
                </div>

                {/* ── クランプ/備考 ── */}
                <div className="p-3 border-b border-slate-100">
                  <div className="text-[10px] text-slate-400 mb-1">クランプ / 備考</div>
                  <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                    {d.clampNote || "—"}
                  </pre>
                </div>

                {/* ── 登録者 / 登録日 / 承認者 ── */}
                <div className="grid grid-cols-3 divide-x divide-slate-100">
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">登録者</div>
                    <div className="text-sm text-slate-700">{d.registrar.name}</div>
                  </div>
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">登録日</div>
                    <div className="text-sm font-mono text-slate-700">{fmtDate(d.createdAt)}</div>
                  </div>
                  <div className="p-3">
                    <div className="text-[10px] text-slate-400 mb-1">承認者</div>
                    <div className="text-sm text-slate-700">{d.approver?.name ?? "未承認"}</div>
                  </div>
                </div>
              </div>

              {/* ── 写真・図への誘導バナー ── */}
              {(d.drawingCount > 0 || d.photoCount > 0) && (
                <button onClick={() => setMainTab("files")}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-sky-50 hover:bg-sky-100 border border-sky-200 rounded-xl transition-colors group text-left">
                  <div className="w-9 h-9 rounded-lg bg-sky-100 group-hover:bg-sky-200 flex items-center justify-center text-sky-600 shrink-0 transition-colors">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-sky-700">写真・図を見る</div>
                    <div className="text-xs text-sky-500 mt-0.5">
                      図 {d.drawingCount}枚 / 写真 {d.photoCount}枚 — 段取図・写真・PDFを確認できます
                    </div>
                  </div>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" strokeWidth="2" className="shrink-0"><path d="M9 18l6-6-6-6"/></svg>
                </button>
              )}

              {/* ── 加工リスト（インライン） ── */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200">
                  <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">加工リスト</span>
                  {d.tools.length > 0 && (
                    <span className="ml-2 text-xs text-slate-400">{d.tools.length}件</span>
                  )}
                </div>
                {d.tools.length === 0 ? (
                  <div className="px-4 py-6 text-center text-xs text-slate-400">工具データなし</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-200">
                          {["NO", "加工", "形状（チップ）", "ホルダー", "ノーズR", "T NO", "備考"].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-bold text-slate-500 text-[10px] uppercase tracking-wider whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {d.tools.map((t: NcTool, i: number) => (
                          <tr key={t.id} className={`border-b border-slate-100 last:border-b-0 ${i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}`}>
                            <td className="px-3 py-2.5 font-mono text-slate-500 text-center w-10">{t.sortOrder}</td>
                            <td className="px-3 py-2.5 text-slate-700">{t.processType ?? "—"}</td>
                            <td className="px-3 py-2.5 font-mono text-slate-700">{t.chipModel ?? "—"}</td>
                            <td className="px-3 py-2.5 font-mono text-slate-700">{t.holderModel ?? "—"}</td>
                            <td className="px-3 py-2.5 text-center text-slate-600">{t.noseR ?? "—"}</td>
                            <td className="px-3 py-2.5 font-mono text-slate-600 text-center">{t.tNumber ?? "—"}</td>
                            <td className="px-3 py-2.5 text-slate-500">{t.note ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

            </div>
          )}

                    {/* ─ 履歴 ─ */}
          {mainTab === "history" && (
            <div className="flex flex-col h-full">
              {/* サブタブ */}
              <div className="bg-slate-50 border-b border-slate-200 px-5 flex gap-0 shrink-0">
                {([
                  { key: "change", label: "変更履歴", svg: <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> },
                  { key: "work",   label: "作業記録", svg: <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> },
                  { key: "print",  label: "印刷履歴", svg: <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg> },
                  { key: "oplog",  label: "操作ログ", svg: <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg> },
                ] as { key: HistorySubTab; label: string; svg: React.ReactNode }[]).map(t => (
                  <button
                    key={t.key}
                    onClick={() => setHistTab(t.key)}
                    className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                      histTab === t.key
                        ? "border-sky-500 text-sky-600"
                        : "border-transparent text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {t.svg}{t.label}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                {histLoading && <div className="text-slate-400 text-sm">読み込み中...</div>}

                {/* 変更履歴 */}
                {histTab === "change" && !histLoading && (
                  changes === null ? null :
                  changes.length === 0 ? <Empty label="変更履歴なし" /> : (
                    <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                      <thead className="bg-slate-100 text-slate-600">
                        <tr>
                          {["日時", "種別", "担当者", "Ver変化", "変更内容"].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {changes.map((c, i) => (
                          <tr key={c.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(c.changed_at)}</td>
                            <td className="px-3 py-2">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                c.change_type === "APPROVE" ? "bg-green-100 text-green-700" :
                                c.change_type === "NEW"     ? "bg-blue-100 text-blue-700" :
                                c.change_type === "MIGRATE" ? "bg-slate-100 text-slate-500" :
                                "bg-amber-100 text-amber-700"
                              }`}>
                                {CHANGE_TYPE_LABELS[c.change_type] ?? c.change_type}
                              </span>
                            </td>
                            <td className="px-3 py-2">{c.operator_name ?? "—"}</td>
                            <td className="px-3 py-2 font-mono text-slate-500">
                              {c.ver_before && c.ver_after ? `${c.ver_before} → ${c.ver_after}` : "—"}
                            </td>
                            <td className="px-3 py-2 text-slate-600">{c.change_detail ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                )}

                {/* 作業記録 */}
                {histTab === "work" && !histLoading && (
                  works === null ? null :
                  works.length === 0 ? <Empty label="作業記録なし" /> : (
                    <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                      <thead className="bg-slate-100 text-slate-600">
                        <tr>
                          {["作業日", "担当者", "機械", "段取(分)", "加工(分)", "個数", "備考", ""].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {works.map((w, i) => (
                          <tr key={w.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(w.work_date)}</td>
                            <td className="px-3 py-2">{w.operator_name ?? "—"}</td>
                            <td className="px-3 py-2 font-mono">{w.machine_code ?? "—"}</td>
                            <td className="px-3 py-2 text-right">{w.setup_time     ?? "—"}</td>
                            <td className="px-3 py-2 text-right">{w.machining_time ?? "—"}</td>
                            <td className="px-3 py-2 text-right">{w.quantity ?? "—"}</td>
                            <td className="px-3 py-2 text-slate-500">{w.note ?? ""}</td>
                            <td className="px-3 py-2">
                              <button
                                onClick={() => router.push(`/nc/${ncId}/record?edit=${w.id}`)}
                                className="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-0.5 rounded transition-colors"
                              >
                                ✏️ 編集
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                )}


                {/* 操作ログ */}
                {histTab === "oplog" && !histLoading && (
                  oplogs === null ? null :
                  oplogs.length === 0 ? <Empty label="操作ログなし" /> : (
                    <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                      <thead className="bg-slate-100 text-slate-600">
                        <tr>
                          {["日時", "操作", "担当者", "詳細"].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {oplogs.map((log, i) => {
                          const labels: Record<string, { label: string; color: string }> = {
                            SESSION_START: { label: "作業開始",    color: "bg-green-100 text-green-700" },
                            SESSION_END:   { label: "作業終了",    color: "bg-slate-100 text-slate-600" },
                            USB_DOWNLOAD:  { label: "PGファイルDL", color: "bg-blue-100 text-blue-700" },
                            FILE_UPLOAD:   { label: "ファイルUP",  color: "bg-sky-100 text-sky-700" },
                            FILE_DELETE:   { label: "ファイル削除", color: "bg-red-100 text-red-600" },
                          };
                          const badge = labels[log.action_type] ?? { label: log.action_type, color: "bg-slate-100 text-slate-500" };
                          const meta  = log.metadata as Record<string, unknown> | null;
                          const detail = meta?.fileName ?? meta?.originalName ?? meta?.session_type ?? "";
                          return (
                            <tr key={log.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                              <td className="px-3 py-2 whitespace-nowrap text-slate-500">
                                {new Date(log.created_at).toLocaleString("ja-JP")}
                              </td>
                              <td className="px-3 py-2">
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${badge.color}`}>{badge.label}</span>
                              </td>
                              <td className="px-3 py-2">{log.user_name ?? "—"}</td>
                              <td className="px-3 py-2 text-slate-500 font-mono text-xs">{String(detail || "")}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )
                )}

                                {/* 印刷履歴 */}
                {histTab === "print" && !histLoading && (
                  prints === null ? null :
                  prints.length === 0 ? <Empty label="印刷履歴なし" /> : (
                    <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                      <thead className="bg-slate-100 text-slate-600">
                        <tr>
                          {["印刷日時", "印刷者", "バージョン"].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {prints.map((p, i) => (
                          <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(p.printed_at)}</td>
                            <td className="px-3 py-2">{p.printer_name ?? "—"}</td>
                            <td className="px-3 py-2 font-mono">{p.version ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                )}
              </div>
            </div>
          )}

          {/* ─ 写真・図 ─ */}
          {mainTab === "files" && (
            <div className="p-5 space-y-4">

              {/* ── D&Dゾーン ── */}
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-default ${
                  isDragActive
                    ? "border-sky-400 bg-sky-50"
                    : "border-slate-200 bg-slate-50 hover:border-slate-300"
                } ${!isAuthenticated ? "opacity-50" : ""}`}
              >
                <input {...getInputProps()} />
                <div className="text-3xl mb-2">{isDragActive ? "📂" : "🖼"}</div>
                <p className="text-sm text-slate-500">
                  {isDragActive
                    ? "ここにドロップしてアップロード"
                    : isAuthenticated
                      ? "ファイルをここにドラッグ＆ドロップ（または下のボタンから選択）"
                      : "認証後にファイルをドロップできます"}
                </p>
              </div>

              {/* ── エラー表示 ── */}
              {fileError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded-lg">
                  {fileError}
                </div>
              )}

              {/* ── アップロードボタン ── */}
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/tiff,application/pdf"
                  className="hidden"
                  onChange={handleUpload}
                />
                {(isAuthenticated && operator) ? (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white text-sm rounded-lg hover:bg-sky-700 disabled:opacity-50 transition-colors"
                  >
                    {uploading ? <span className="animate-spin">⏳</span> : <span>📎</span>}
                    {uploading ? "アップロード中…" : "ファイルを追加"}
                  </button>
                ) : (
                  <button
                    onClick={() => openAuth("edit")}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white text-sm rounded-lg hover:bg-slate-700 transition-colors"
                  >
                    🔐 認証してファイルを追加
                  </button>
                )}
                <span className="text-xs text-slate-400">
                  対応形式: JPEG / PNG / TIFF / PDF
                </span>
              </div>

              {/* ── ローディング ── */}
              {filesLoading && (
                <div className="flex items-center justify-center py-16 text-slate-400 gap-2">
                  <span className="animate-spin text-xl">⏳</span>
                  <span className="text-sm">読み込み中…</span>
                </div>
              )}

              {/* ── ファイル一覧 ── */}
              {!filesLoading && files !== null && (
                <div className="space-y-6">
                  <FileSection
                    title="📷 写真"
                    files={files.filter(f => f.file_type === "PHOTO")}
                    isAuthenticated={isAuthenticated}
                    onPreview={setPreviewFile}
                    onDelete={handleDelete}
                  />
                  <FileSection
                    title="📄 図・段取図"
                    files={files.filter(f => f.file_type === "DRAWING")}
                    isAuthenticated={isAuthenticated}
                    onPreview={setPreviewFile}
                    onDelete={handleDelete}
                  />
                  {files.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-300 gap-2">
                      <div className="text-5xl">🖼</div>
                      <p className="text-sm">ファイルがありません</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── プレビューモーダル ── */}
              {previewFile && (
                <div
                  className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
                  onClick={() => setPreviewFile(null)}
                >
                  <div
                    className="bg-white rounded-xl overflow-hidden shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col"
                    onClick={e => e.stopPropagation()}
                  >
                    {/* モーダルヘッダー */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 shrink-0">
                      <div>
                        <p className="text-sm font-bold text-slate-700 truncate max-w-[480px]">
                          {previewFile.original_name}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {fmtSize(previewFile.file_size)} ・ {fmtUploadDate(previewFile.uploaded_at)}
                          {previewFile.uploaded_by && ` ・ ${previewFile.uploaded_by}`}
                        </p>
                      </div>
                      <button
                        onClick={() => setPreviewFile(null)}
                        className="text-slate-400 hover:text-slate-700 text-xl px-2"
                      >
                        ✕
                      </button>
                    </div>

                    {/* プレビュー本体 */}
                    <div className="flex-1 overflow-auto bg-slate-900 flex items-center justify-center min-h-[300px]">
                      {previewFile.mime_type === "application/pdf" ? (
                        <div className="flex flex-col items-center gap-2 py-2">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setPdfPage(p => Math.max(1, p - 1))}
                              disabled={pdfPage <= 1}
                              className="px-3 py-1 bg-slate-700 text-white text-xs rounded disabled:opacity-40"
                            >◀</button>
                            <span className="text-white text-xs">{pdfPage} / {pdfNumPages}</span>
                            <button
                              onClick={() => setPdfPage(p => Math.min(pdfNumPages, p + 1))}
                              disabled={pdfPage >= pdfNumPages}
                              className="px-3 py-1 bg-slate-700 text-white text-xs rounded disabled:opacity-40"
                            >▶</button>
                          </div>
                          <Document
                            file={`/api/files/serve/${previewFile.id}`}
                            onLoadSuccess={({ numPages }) => { setPdfNumPages(numPages); setPdfPage(1); }}
                            className="max-h-[65vh] overflow-auto"
                          >
                            <Page pageNumber={pdfPage} width={700} />
                          </Document>
                        </div>
                      ) : (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={`/api/files/serve/${previewFile.id}`}
                          alt={previewFile.original_name}
                          className="max-w-full max-h-[70vh] object-contain"
                        />
                      )}
                    </div>

                    {/* ダウンロードリンク */}
                    <div className="px-4 py-3 border-t border-slate-200 shrink-0 flex justify-end">
                      <a
                        href={`/api/files/serve/${previewFile.id}`}
                        download={previewFile.original_name}
                        className="text-xs text-sky-600 hover:underline"
                      >
                        ⬇ ダウンロード
                      </a>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      <AuthModal
        isOpen={authModalOpen}
        sessionType={authSessionType}
        ncProgramId={ncId}
        onSuccess={() => setAuthModalOpen(false)}
        onCancel={() => setAuthModalOpen(false)}
      />
    </>
  );
}

// ── ヘルパー関数 ──────────────────────────────────────────────────

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtUploadDate(s: string): string {
  const d = new Date(s);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

// ── ヘルパーコンポーネント ────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
      <div className="px-4 py-2 bg-slate-50 border-b border-slate-100">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">{title}</span>
      </div>
      <div className="divide-y divide-slate-50">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center px-4 py-2 gap-4">
      <span className="text-xs text-slate-400 w-24 shrink-0">{label}</span>
      <span className="text-sm text-slate-700 font-mono">{value}</span>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-300 gap-2">
      <div className="text-4xl">📂</div>
      <p className="text-sm">{label}</p>
    </div>
  );
}

function FileSection({
  title,
  files,
  isAuthenticated,
  onPreview,
  onDelete,
}: {
  title: string;
  files: NcFile[];
  isAuthenticated: boolean;
  onPreview: (f: NcFile) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-bold text-slate-600">{title}</span>
        <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
          {files.length} 件
        </span>
      </div>

      {files.length === 0 ? (
        <div className="text-xs text-slate-300 py-6 text-center border border-dashed border-slate-200 rounded-xl">
          なし
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {files.map(f => (
            <div
              key={f.id}
              className="group relative bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow cursor-pointer"
            >
              <div
                className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden"
                onClick={() => onPreview(f)}
              >
                {f.mime_type === "application/pdf" ? (
                  <div className="flex flex-col items-center gap-1 text-slate-400">
                    <span className="text-3xl">📄</span>
                    <span className="text-[10px]">PDF</span>
                  </div>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`/api/files/thumb/${f.id}`}
                    alt={f.original_name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    onError={e => {
                      (e.target as HTMLImageElement).src = `/api/files/serve/${f.id}`;
                    }}
                  />
                )}
              </div>

              <div className="px-2 py-1.5">
                <p className="text-[10px] text-slate-500 truncate leading-tight">{f.original_name}</p>
                <p className="text-[9px] text-slate-300 mt-0.5">{fmtSize(f.file_size)}</p>
              </div>

              {isAuthenticated && (
                <button
                  onClick={e => { e.stopPropagation(); onDelete(f.id); }}
                  className="absolute top-1.5 right-1.5 w-5 h-5 bg-red-500/80 text-white text-[10px] rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center hover:bg-red-600"
                  title="削除"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}