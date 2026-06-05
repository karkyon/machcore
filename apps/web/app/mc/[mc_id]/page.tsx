"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, mcFilesApi, McDetail, McTooling, McWorkOffset, McIndexProgram,
         McFile, McChangeHistory, McSetupSheetLog, McWorkRecord, McCommonSearchResult } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};

const MAIN_TABS = [
  { key: "mc",          label: "マシニングデータ" },
  { key: "tooling",     label: "ツーリング" },
  { key: "offset",      label: "ワークオフセット" },
  { key: "index",       label: "インデックスプログラム" },
  { key: "commongroup", label: "共通グループ" },
  { key: "history",     label: "履歴" },
  { key: "files",       label: "写真・図" },
];

export default function McDetailPage() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();

  const [detail,    setDetail]    = useState<McDetail | null>(null);
  const [floatOpen,  setFloatOpen]  = useState(true);
  const [floatPos,   setFloatPos]   = useState({ x: 900, y: 120 });
  const [dragging,   setDragging]   = useState(false);
  const dragStart    = useRef<{ mx: number; my: number; px: number; py: number } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mainTab,   setMainTab]   = useState("mc");
  const [histTab,   setHistTab]   = useState("change");

  // 遅延ロードデータ
  const [changes, setChanges] = useState<McChangeHistory[] | null>(null);
  const [works,   setWorks]   = useState<McWorkRecord[]   | null>(null);
  const [prints,  setPrints]  = useState<McSetupSheetLog[]| null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [previewFile, setPreviewFile] = useState<typeof d.files[0] | null>(null);
  const [drawingModal,   setDrawingModal]   = useState(false);
  const [drawingBlobUrl, setDrawingBlobUrl] = useState<string | null>(null);
  const [drawingLoading, setDrawingLoading] = useState(false);
  const [drawingZoom,    setDrawingZoom]    = useState<number | "fit">("fit");
  const [drawingPan,     setDrawingPan]     = useState({ x: 0, y: 0 });
  const drawingDrag = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);
  const [drawingAuthOpen, setDrawingAuthOpen] = useState(false);
  const [previewZoom, setPreviewZoom] = useState<"fit" | "real" | number>("fit");

  // 認証
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authOpen, setAuthOpen]       = useState(false);
  const [authType, setAuthType]       = useState("edit");
  const [pendingUsb, setPendingUsb]   = useState(false);

  // タイマー
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  // PGビューア
  const [pgContent,    setPgContent]    = useState<string | null>(null);
  const [pgOrigName,   setPgOrigName]   = useState<string>("");
  const [pgFileCount,  setPgFileCount]  = useState(0);
  const [pgViewerOpen, setPgViewerOpen] = useState(false);
  const [pgLoading,    setPgLoading]    = useState(false);
  // PGアップロード
  const [pgUploading,  setPgUploading]  = useState(false);
  // 共通グループ 供用登録モーダル
  const [cpRegOpen,       setCpRegOpen]       = useState(false);
  const [cpSearchQ,       setCpSearchQ]       = useState("");
  const [cpSearchKey,     setCpSearchKey]     = useState("drawing_no");
  const [cpSearchResults, setCpSearchResults] = useState<any[]>([]);
  const [cpSearchLoading, setCpSearchLoading] = useState(false);
  const [cpSelected,      setCpSelected]      = useState<any | null>(null);
  const [cpNote,          setCpNote]          = useState("");
  const [cpSaving,        setCpSaving]        = useState(false);
  const [cpError,         setCpError]         = useState<string | null>(null);
  const [cpUnregSaving,   setCpUnregSaving]   = useState(false);
  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    if (!mcId) return;
    mcApi.findOne(mcId).then(r => {
      const data = (r as any).data ?? r;
      console.log('[MC Float] commonGroup:', data.commonGroup?.length, data.commonGroup);
      setDetail(data);
    }).catch(e => { console.error('[MC Float] findOne error:', e); setLoadError(e.message); });
    // dummy to skip original r)).catch(e => setLoadError(e.message));
  }, [mcId]);

  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  useEffect(() => {
    if (mainTab !== "history") return;
    if (histTab === "change" && changes === null) {
      setHistLoading(true);
      mcApi.changeHistory(mcId).then(r => setChanges((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
    if (histTab === "work" && works === null) {
      setHistLoading(true);
      mcApi.workRecords(mcId).then(r => setWorks((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
    if (histTab === "print" && prints === null) {
      setHistLoading(true);
      mcApi.setupSheetLogs(mcId).then(r => setPrints((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
  }, [mainTab, histTab, mcId]);

  // USB pending -> FSA API で USB直接書き込み
  useEffect(() => {
    if (isAuthenticated && pendingUsb && token) {
      setPendingUsb(false);
      handleUsbCopy();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, pendingUsb, token]);

  const handleUsbCopy = async () => {
    if (!('showDirectoryPicker' in window)) {
      const a = document.createElement('a');
      a.href = `/api/mc/${mcId}/pg-download`;
      a.download = '';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast("PGファイルをダウンロードしました（FSA非対応）");
      return;
    }
    try {
      const res = await fetch(`/api/mc/${mcId}/pg-file-info`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) { showToast('PGファイルが見つかりません'); return; }
      const info: { files: Array<{ name: string; folderName?: string; content: string }> } = await res.json();

      let dirHandle: FileSystemDirectoryHandle;
      try {
        dirHandle = await (window as any).showDirectoryPicker({ mode: 'readwrite' });
      } catch {
        return;
      }

      if (info.files.length === 1 && !info.files[0].folderName) {
        const f = info.files[0];
        const fh = await dirHandle.getFileHandle(f.name, { create: true });
        const writable = await fh.createWritable();
        const bytes = Uint8Array.from(atob(f.content), c => c.charCodeAt(0));
        await writable.write(bytes);
        await writable.close();
        showToast(`✅ ${f.name} をコピーしました`);
      } else {
        const folderName = info.files[0]?.folderName ?? `PG_${mcId}`;
        const subDir = await dirHandle.getDirectoryHandle(folderName, { create: true });
        for (const f of info.files) {
          const fh = await subDir.getFileHandle(f.name, { create: true });
          const writable = await fh.createWritable();
          const bytes = Uint8Array.from(atob(f.content), c => c.charCodeAt(0));
          await writable.write(bytes);
          await writable.close();
        }
        showToast(`✅ フォルダ「${folderName}」に ${info.files.length}件コピーしました`);
      }
    } catch (e: any) {
      showToast(`コピー失敗: ${e?.message ?? String(e)}`);
    }
  };

  const openAuth = (type: string) => { setAuthType(type); setAuthOpen(true); };

  // PGビューアを開く（MAINプログラムをテキスト表示）
  const openPgViewer = async () => {
    if (pgContent !== null) { setPgViewerOpen(true); return; }
    setPgLoading(true);
    try {
      const r = await mcApi.getPgFile(mcId);
      const data = (r as any).data ?? r;
      setPgContent(data.content ?? "");
      setPgOrigName(data.originalName ?? "");
      setPgFileCount(data.fileCount ?? 1);
      setPgViewerOpen(true);
    } catch {
      showToast("PGファイルが見つかりません");
    } finally {
      setPgLoading(false);
    }
  };

  // PGファイルアップロード
  const handlePgUpload = async (files: FileList, isFolderUpload: boolean) => {
    if (!token) { openAuth("edit"); return; }
    if (files.length === 0) return;
    setPgUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const fd = new FormData();
        fd.append('file', files[i]);
        fd.append('is_folder_upload', String(isFolderUpload));
        await fetch(`/api/mc/${mcId}/files/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
      }
      // キャッシュクリア → 再ビューア時に再取得
      setPgContent(null);
      // 詳細再取得 (pg_updated_at / pgCreator 更新反映)
      const refreshed = await mcApi.findOne(mcId);
      setDetail((refreshed as any).data ?? refreshed);
      showToast(`PGファイルを${files.length}件アップロードしました`);
    } catch {
      showToast("アップロードに失敗しました");
    } finally {
      setPgUploading(false);
    }
  };

  const fmtDate = (s: string | null | undefined) => {
    if (!s) return "—";
    try { return new Date(s).toLocaleString("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit" }); }
    catch { return s; }
  };

  const fmtCycle = (sec: number | null) => {
    if (!sec) return "—";
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return `${h}H ${String(m).padStart(2,"0")}M ${String(s).padStart(2,"0")}S`;
  };

  const fmtElapsed = (s: number) =>
    `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !dragStart.current) return;
    setFloatPos({
      x: Math.max(0, dragStart.current.px + e.clientX - dragStart.current.mx),
      y: Math.max(0, dragStart.current.py + e.clientY - dragStart.current.my),
    });
  };
  const onMouseUp = () => { setDragging(false); dragStart.current = null; };

  if (loadError) return (
    <div className="h-screen flex items-center justify-center text-red-500">
      <div className="text-center"><p className="text-2xl mb-2">⚠️</p><p>{loadError}</p>
        <button onClick={() => router.push("/")} className="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-xs font-bold transition-colors">← ダッシュボード</button>
          <button onClick={() => router.push("/mc/search")} className="mt-4 text-teal-600 text-sm hover:underline">← 検索に戻る</button>
      </div>
    </div>
  );

  if (!detail) return (
    <div className="h-screen flex items-center justify-center text-slate-400">
      <div className="text-center"><div className="animate-spin text-3xl mb-2">⚙️</div><p>読み込み中…</p></div>
    </div>
  );

  const d = detail;

  return (
    <div className="h-screen flex flex-col bg-slate-50" onMouseMove={onMouseMove} onMouseUp={onMouseUp}>
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2 flex items-center gap-3 shrink-0">
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium text-white">MC 詳細</span>
        <span className="ml-auto flex items-center gap-3">
          <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            ダッシュボードへ
          </button>
          <button onClick={() => router.push("/mc/search")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 rounded-lg text-xs font-bold text-white transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            部品検索へ戻る
          </button>
          <button onClick={() => { if (!isAuthenticated) { setPendingUsb(true); openAuth("usb_download"); } else { handleUsbCopy(); } }}
            className="text-[11px] bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded font-bold">
            PG→USB
          </button>
        </span>
      </header>
        {/* ── フローティング工程切り替えパネル ── */}
        {d && (() => { console.log('[MC Float] render check - processes:', d.processes?.length); return null; })()}
        {d && d.processes && d.processes.length > 1 && (
          <div
            style={{ position: "fixed", left: floatPos.x, top: floatPos.y, zIndex: 100, userSelect: "none" }}
            className="shadow-2xl rounded-xl overflow-hidden border border-slate-700 w-52"
          >
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
            {floatOpen && (
              <div className="bg-white">
                {d.processes.map(g => (
                  <button
                    key={g.id}
                    onClick={() => router.push(`/mc/${g.id}`)}
                    className={`w-full text-left px-3 py-2 text-xs border-b border-slate-100 flex items-center gap-2 transition-colors ${
                      g.id === d.id
                        ? "bg-teal-50 border-l-2 border-l-teal-400"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${g.id === d.id ? "bg-teal-500 text-white" : "bg-slate-100 text-slate-600"}`}>
                      {g.legacyMcid ?? g.id}
                    </span>
                    <span className="font-mono text-slate-600 truncate flex-1">{g.machine?.machineCode ?? "—"}</span>
                    <span className={`ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      g.status === "APPROVED" ? "bg-green-100 text-green-700" :
                      g.status === "CHANGING" ? "bg-orange-100 text-orange-700" :
                      "bg-slate-100 text-slate-500"
                    }`}>
                      {g.status === "APPROVED" ? "承認済" : g.status === "CHANGING" ? "変更中" : g.status === "PENDING_APPROVAL" ? "承認待" : "新規"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

      {/* 部品ヘッダー */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        {/* 1行目: 図面番号 / 名称 / 納入先 + バッジ群 */}
        <div className="flex items-center gap-3 flex-wrap mb-1.5">
          <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
          <span className="text-slate-300 text-xl font-light">/</span>
          <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
          {d.part.mainModel && <>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="text-slate-500 text-lg font-medium leading-none">{d.part.mainModel}</span>
          </>}
          <div className="flex items-center gap-2 ml-2">
            {d.machine && (
              <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">
                {d.machine.machineCode}
              </span>
            )}
            <StatusBadge status={d.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            {isAuthenticated && operator?.role === "ADMIN" && d.status !== "APPROVED" && (
              <button
                onClick={async () => {
                  if (!token) return;
                  if (!window.confirm(`承認しますか？\nMCID: ${d.legacyMcid ?? d.id}  Ver. ${d.version}`)) return;
                  try {
                    await mcApi.approve(d.id, token);
                    const r = await mcApi.findOne(d.id);
                    setDetail((r as any).data ?? r);
                  } catch { alert("承認に失敗しました"); }
                }}
                className="text-xs font-bold px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
              >
                ✓ 承認
              </button>
            )}
          </div>
        </div>
        {/* 2行目: ID情報 */}
        <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
          {d.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {d.mcProcessNo}</span>}
          <span className="text-slate-400">|</span>
          <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? d.id}</span></span>
          <span className="text-slate-400">|</span>
          <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
          {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
        </div>
      </div>

      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* コンテンツタブ */}
      <div className="bg-[#f4f7fb] border-b border-[#d0d8e4] px-4 flex gap-1 items-end shrink-0 pt-1.5 overflow-x-auto">
        {MAIN_TABS.map(tab => (
          <button key={tab.key} onClick={() => setMainTab(tab.key)}
            className={`px-3 py-1.5 text-[11px] font-semibold whitespace-nowrap rounded-t border border-b-0 transition-colors ${
              mainTab === tab.key
                ? "border-[#1b2a41] bg-[#1b2a41] text-white"
                : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]"
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* タブコンテンツ */}
      <div className="flex-1 overflow-y-auto p-5">

        {/* ─── マシニングデータ ─── */}
        {mainTab === "mc" && (
          <div className="max-w-3xl space-y-5">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200">
                <span className="text-xs font-bold text-slate-600">基本情報</span>
              </div>
              <div className="divide-y divide-slate-100">
                {/* ── 行1: 工程No・バージョン・機械 ── */}
                <div className="grid grid-cols-3 divide-x divide-slate-100">
                  <div className="px-4 py-3 bg-slate-50">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">MC工程No</div>
                    <div className="font-mono font-bold text-teal-700 text-xl leading-none">{d.mcProcessNo ?? "—"}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">バージョン</div>
                    <div className="font-mono font-bold text-slate-800 text-base">{d.version}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">機械</div>
                    <div className="font-medium text-slate-800">{d.machine?.machineName ?? d.machine?.machineCode ?? "—"}</div>
                  </div>
                </div>
                {/* ── 行2: Oナンバ・サイクルタイム・加工個数 ── */}
                <div className="grid grid-cols-3 divide-x divide-slate-100">
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">主Oナンバ</div>
                    <div className="font-mono font-semibold text-slate-800">{d.oNumber ?? "—"}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">サイクルタイム/1P</div>
                    <div className="font-mono font-semibold text-slate-800">{fmtCycle(d.cycleTimeSec)}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">加工個数/1サイクル</div>
                    <div className="font-semibold text-slate-800">{d.machiningQty ?? 1} 個</div>
                  </div>
                </div>
                {/* ── 行3: 共通部品コード + バッジ群 ── */}
                <div className="px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
                  <div>
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">共通部品コード</div>
                    <div className="font-mono text-slate-700">{d.commonPartCode ?? "—"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2 ml-auto">
                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${(d.rc ?? 0) > 0 ? "bg-teal-50 text-teal-700 border-teal-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                      RC <span className="text-sm">{d.rc ?? 0}</span>
                    </span>
                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${d.hasIndexProgram ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                      IP {d.hasIndexProgram ? "有" : "無"}
                    </span>
                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${d.hasWorkOffset ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                      WD {d.hasWorkOffset ? "有" : "無"}
                    </span>
                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${d.files.filter(f => f.file_type === "PHOTO").length > 0 ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                      写真 {d.files.filter(f => f.file_type === "PHOTO").length}
                    </span>
                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${d.files.filter(f => f.file_type === "DRAWING").length > 0 ? "bg-purple-50 text-purple-700 border-purple-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                      図 {d.files.filter(f => f.file_type === "DRAWING").length}
                    </span>
                  </div>
                </div>
                {/* ── 行4: 作成・承認情報 ── */}
                <div className="grid grid-cols-2 divide-x divide-slate-100">
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">作成日（シート）</div>
                    <div className="font-mono text-slate-800">{d.sheetCreatedAt ? fmtDate(d.sheetCreatedAt) : "—"}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">作成者（シート）</div>
                    <div className="text-slate-800">{d.creator?.name ?? "—"}</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 divide-x divide-slate-100">
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">入力日</div>
                    <div className="font-mono text-slate-800">{fmtDate(d.registeredAt)}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">オペレーター</div>
                    <div className="text-slate-800">{d.registrar?.name ?? "—"}</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 divide-x divide-slate-100">
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">承認日</div>
                    <div className="font-mono text-slate-800">{d.approvedAt ? fmtDate(d.approvedAt) : "—"}</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">承認者</div>
                    <div className={d.approver ? "text-emerald-700 font-bold" : "text-slate-400"}>{d.approver?.name ?? "未承認"}</div>
                  </div>
                </div>
                {/* ── クランプ・備考 ── */}
                {/* ── PG作成者・Save Date ── */}
                {(d.pgCreator || d.pgUpdatedAt) && (
                  <div className="grid grid-cols-2 divide-x divide-slate-100">
                    <div className="px-4 py-3">
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">PG作成者</div>
                      <div className="text-slate-800">{d.pgCreator?.name ?? "—"}</div>
                    </div>
                    <div className="px-4 py-3">
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">Save Date</div>
                      <div className="font-mono text-slate-800">
                        {d.pgUpdatedAt ? new Date(d.pgUpdatedAt).toLocaleString("ja-JP", { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" }) : "—"}
                      </div>
                    </div>
                  </div>
                )}
                {d.clampNote && (
                  <div className="px-4 py-3">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-1">クランプ</div>
                    <div className="whitespace-pre-wrap text-slate-700 text-sm">{d.clampNote}</div>
                  </div>
                )}
                {d.note && (
                  <div className="px-4 py-3 bg-amber-50">
                    <div className="text-[10px] font-bold text-amber-600 uppercase tracking-wide mb-1">備考</div>
                    <div className="whitespace-pre-wrap text-slate-700 text-sm">{d.note}</div>
                  </div>
                )}
              </div>
            </div>

            {/* 共通加工グループ */}
            {d.commonGroup.length > 1 && (
              <div className="bg-white rounded-xl border border-pink-200 overflow-hidden">
                <div className="bg-pink-50 px-4 py-2 border-b border-pink-200">
                  <span className="text-xs font-bold text-pink-700">共通加工グループ（加工ID: {d.machiningId}）</span>
                </div>
                <div className="p-2">
                  {d.commonGroup.map(g => (
                    <div key={g.id}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                        g.id === d.id ? "bg-teal-50 border border-teal-200" : "bg-white"}`}>
                      <span className="font-mono text-teal-600 font-bold text-xs">MCID:{g.legacyMcid ?? g.id}</span>
                      {g.part.partId && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 font-mono shrink-0">部品ID:{g.part.partId}</span>}
                      <span className="font-mono text-slate-700 font-bold text-xs">{g.part.drawingNo}</span>
                      <span className="text-slate-600 text-xs">{g.part.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">加工ID:{g.machiningId}</span>
                      <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[g.status] ?? ""}`}>
                        {STATUS_LABEL[g.status] ?? g.status}
                      </span>
                      {g.id === d.id && <span className="text-[10px] text-teal-600 font-bold">← 現在</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── ツーリング ─── */}
        {mainTab === "tooling" && (
          <div className="max-w-5xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between rounded-t-xl">
                <span className="text-xs font-bold text-slate-600">ツーリングリスト ({d.tooling.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="text-xs text-teal-600 hover:text-teal-700 font-bold">✏️ 編集</button>
              </div>
              {d.tooling.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ツーリングデータがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[60vh] rounded-b-xl">
                  <table className="text-xs w-full border-collapse">
                    <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                      <tr>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 w-20 whitespace-nowrap">N</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 w-36 whitespace-nowrap">工具</th>
                        <th className="px-3 py-2 text-center font-bold border-b border-teal-100 w-12 whitespace-nowrap">T</th>
                        <th className="px-3 py-2 text-center font-bold border-b border-teal-100 w-12 whitespace-nowrap">H</th>
                        <th className="px-3 py-2 text-center font-bold border-b border-teal-100 w-12 whitespace-nowrap">D</th>
                        <th className="px-3 py-2 text-center font-bold border-b border-teal-100 w-14 whitespace-nowrap">D値</th>
                        <th className="px-3 py-2 text-center font-bold border-b border-teal-100 w-14 whitespace-nowrap">SUB</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">コメント</th>
                        <th className="px-3 py-2 text-right font-bold border-b border-teal-100 w-12 whitespace-nowrap">順番</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.tooling.map((t, i) => (
                        <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-3 py-2 font-mono font-bold text-teal-700 whitespace-nowrap">{t.toolNo ?? "—"}</td>
                          <td className="px-3 py-2">{t.toolName ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-center whitespace-nowrap">{t.tNo ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-center whitespace-nowrap">{t.lengthOffsetNo ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-center whitespace-nowrap">{t.diaOffsetNo ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-center whitespace-nowrap">{t.dValueContent ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-center whitespace-nowrap">{t.subPgNo ?? "—"}</td>
                          <td className="px-3 py-2 text-slate-500 text-[11px]">{t.note ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-right text-slate-400 whitespace-nowrap">{t.sortOrder}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── ワークオフセット ─── */}
        {mainTab === "offset" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ワークオフセット ({d.workOffsets.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.workOffsets.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ワークオフセットデータがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[55vh]">
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                    <tr>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">G</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">X</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">Y</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">Z</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">A / C</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">R / B</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">備考</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.workOffsets.map((o, i) => (
                      <tr key={o.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono font-bold text-teal-600">{o.gCode}</td>
                        {[o.xOffset, o.yOffset, o.zOffset, o.aOffset, o.rOffset].map((v, j) => (
                          <td key={j} className="px-3 py-2 text-center font-mono">{v ? Number(v).toFixed(3) : "—"}</td>
                        ))}
                        <td className="px-3 py-2 text-slate-400">{o.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[55vh]">
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                    <tr>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">STEP/N</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第0軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第1軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第2軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">備考</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.indexPrograms.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── 共通グループ ─── */}
        {mainTab === "commongroup" && (
          <div className="max-w-4xl space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-teal-700 px-4 py-3 flex items-center justify-between rounded-t-xl">
                <div className="flex items-center gap-3">
                  <span className="text-white font-bold text-sm">共通グループ</span>
                  <span className="text-teal-200 text-xs font-mono">加工ID:{d.machiningId}</span>
                  {d.commonPartCode && (
                    <span className="text-teal-100 text-[11px] font-mono bg-teal-800 px-2 py-0.5 rounded">
                      {d.commonPartCode}
                    </span>
                  )}
                  <span className="text-teal-300 text-xs">{d.commonGroup.length}件</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (!isAuthenticated) { openAuth("commonpart"); return; }
                      setCpTargetPartId(""); setCpNote(""); setCpError(null); setCpRegOpen(true);
                    }}
                    className="px-3 py-1.5 bg-white text-teal-700 text-xs font-bold rounded-lg hover:bg-teal-50">
                    ＋ 新規に共通登録
                  </button>
                  <button onClick={() => router.push("/mc/common-parts")}
                    className="px-3 py-1.5 bg-teal-600 text-white text-xs font-bold rounded-lg hover:bg-teal-500 border border-teal-500">
                    🔍 共通部品検索
                  </button>
                </div>
              </div>
              {d.commonGroup.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">共通登録はありません</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {d.commonGroup.map((g: any) => (
                    <div key={g.id}
                      className={`flex items-center gap-3 px-4 py-3 text-xs hover:bg-teal-50 transition-colors
                        ${g.id === d.id ? "bg-teal-50 border-l-4 border-teal-500" : ""}`}>
                      <span className="font-mono text-teal-600 font-bold whitespace-nowrap">MCID:{g.legacyMcid ?? g.id}</span>
                      {g.part?.partId && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 font-mono shrink-0">
                          部品ID:{g.part.partId}
                        </span>
                      )}
                      <span className="font-mono text-slate-700 font-bold whitespace-nowrap">{g.part?.drawingNo}</span>
                      <span className="text-slate-600 truncate max-w-[180px]">{g.part?.name}</span>
                      {g.part?.clientName && (
                        <span className="text-slate-400 text-[10px] shrink-0">[{g.part.clientName}]</span>
                      )}
                      <span className="text-[10px] text-slate-400 font-mono whitespace-nowrap shrink-0">加工ID:{g.machiningId}</span>
                      <span className="font-mono text-slate-500 shrink-0">{g.version ?? (g.machining?.version)}</span>
                      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[g.status] ?? ""}`}>
                        {STATUS_LABEL[g.status] ?? g.status}
                      </span>
                      {g.id === d.id && <span className="text-[10px] text-teal-600 font-bold shrink-0">← 現在</span>}
                      <div className="ml-auto flex items-center gap-2 shrink-0">
                        {g.id !== d.id && (
                          <button onClick={() => router.push(`/mc/${g.id}`)}
                            className="px-2 py-1 bg-teal-600 text-white text-[10px] font-bold rounded hover:bg-teal-700">
                            詳細
                          </button>
                        )}
                        {g.id !== d.id && d.commonGroup.length > 1 && isAuthenticated && (
                          <button
                            disabled={cpUnregSaving}
                            onClick={async () => {
                              if (!token) return;
                              if (!confirm(`MCID:${g.legacyMcid ?? g.id} (${g.part?.drawingNo}) の共通登録を解除しますか？`)) return;
                              setCpUnregSaving(true);
                              try {
                                await mcApi.unregisterCommonPart(g.id, token);
                                showToast("✅ 共通登録を解除しました");
                                const nr = await mcApi.findOne(mcId);
                                setDetail((nr as any).data ?? nr);
                              } catch (e: any) {
                                alert(e?.response?.data?.message ?? e?.message ?? "解除失敗");
                              } finally { setCpUnregSaving(false); }
                            }}
                            className="px-2 py-1 bg-red-100 text-red-600 text-[10px] font-bold rounded hover:bg-red-200 border border-red-200 disabled:opacity-50">
                            解除
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 供用登録モーダル — 旧システム準拠: 現在の部品に対して「使いたい加工」を検索・選択 */}
        {cpRegOpen && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh]">
              {/* ヘッダー */}
              <div className="bg-teal-700 px-5 py-3 rounded-t-2xl shrink-0">
                <h2 className="text-white font-bold text-sm">📋 共通登録（供用）</h2>
                <p className="text-teal-200 text-xs mt-0.5">
                  この部品（{d.part?.drawingNo} / {d.part?.name}）に対して、
                  使いたい既存の加工データを検索して選択してください
                </p>
              </div>
              {/* 供用先確認 */}
              <div className="bg-teal-50 border-b border-teal-100 px-5 py-2 shrink-0">
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-slate-500">登録先部品:</span>
                  <span className="font-mono font-bold text-violet-700">部品ID:{d.part?.partId}</span>
                  <span className="font-mono font-bold text-teal-700">{d.part?.drawingNo}</span>
                  <span className="text-slate-700">{d.part?.name}</span>
                </div>
              </div>
              {/* 加工検索 */}
              <div className="px-5 py-3 border-b border-slate-100 shrink-0">
                <p className="text-xs font-bold text-slate-500 mb-2">STEP 1: 使いたい加工データを検索</p>
                <div className="flex gap-2">
                  <select value={cpSearchKey} onChange={e => setCpSearchKey(e.target.value)}
                    className="border border-slate-300 rounded-lg px-2 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-teal-400">
                    <option value="drawing_no">図面番号</option>
                    <option value="part_name">名称</option>
                    <option value="mcid">MCID</option>
                    <option value="machining_id">加工ID</option>
                    <option value="part_id">部品ID</option>
                  </select>
                  <input value={cpSearchQ} onChange={e => setCpSearchQ(e.target.value)}
                    onKeyDown={async e => {
                      if (e.key !== "Enter") return;
                      setCpSearchLoading(true); setCpSelected(null); setCpError(null);
                      try {
                        const res = await mcApi.search(cpSearchKey, cpSearchQ.trim());
                        setCpSearchResults((res as any).data?.rows ?? []);
                      } catch { setCpSearchResults([]); }
                      finally { setCpSearchLoading(false); }
                    }}
                    className="flex-1 border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
                    placeholder="Enterで検索" />
                  <button
                    onClick={async () => {
                      setCpSearchLoading(true); setCpSelected(null); setCpError(null);
                      try {
                        const res = await mcApi.search(cpSearchKey, cpSearchQ.trim());
                        setCpSearchResults((res as any).data?.rows ?? []);
                      } catch { setCpSearchResults([]); }
                      finally { setCpSearchLoading(false); }
                    }}
                    disabled={cpSearchLoading}
                    className="px-3 py-1.5 bg-teal-600 text-white text-xs font-bold rounded-lg hover:bg-teal-700 disabled:opacity-50">
                    {cpSearchLoading ? "..." : "検索"}
                  </button>
                </div>
              </div>
              {/* 検索結果一覧 */}
              <div className="flex-1 overflow-y-auto min-h-0">
                {cpSearchResults.length === 0 && !cpSearchLoading && (
                  <div className="text-center text-slate-400 text-xs py-8">
                    検索条件を入力してEnterキーまたは検索ボタンを押してください
                  </div>
                )}
                {cpSearchResults.map((row: any) => {
                  const isSelected = cpSelected?.machining_id === row.machining_id;
                  const isSelf = row.machining_id === d.machiningId;
                  const isDup = d.commonGroup?.some((g: any) => g.machiningId === row.machining_id && g.part?.partId === d.part?.partId);
                  return (
                    <div key={row.mc_id}
                      onClick={() => { if (!isSelf && !isDup) setCpSelected(row); }}
                      className={`flex items-center gap-3 px-4 py-2.5 text-xs border-b border-slate-100 transition-colors
                        ${isSelf || isDup ? "opacity-40 cursor-not-allowed bg-slate-50" :
                          isSelected ? "bg-teal-50 border-l-4 border-teal-500 cursor-pointer" :
                          "hover:bg-teal-50 cursor-pointer"}`}>
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${isSelected ? "border-teal-500 bg-teal-500" : "border-slate-300"}`}>
                        {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                      </div>
                      <span className="font-mono font-bold text-teal-700 whitespace-nowrap">加工ID:{row.machining_id}</span>
                      <span className="font-mono text-blue-600 whitespace-nowrap">MCID:{row.legacy_mcid ?? row.mc_id}</span>
                      <span className="font-mono font-bold text-slate-700 whitespace-nowrap">{row.drawing_no}</span>
                      <span className="text-slate-600 truncate max-w-[160px]">{row.part_name}</span>
                      <span className="text-slate-400 shrink-0">{row.machine_code ?? "—"}</span>
                      <span className="font-mono text-slate-500 shrink-0">{row.version}</span>
                      {isSelf && <span className="ml-auto text-[10px] text-slate-400 shrink-0">（現在の加工）</span>}
                      {isDup && <span className="ml-auto text-[10px] text-amber-600 shrink-0">（登録済み）</span>}
                    </div>
                  );
                })}
              </div>
              {/* 選択確認 + 登録 */}
              {cpSelected && (
                <div className="border-t border-teal-200 bg-teal-50 px-5 py-3 shrink-0">
                  <p className="text-xs font-bold text-teal-700 mb-1">STEP 2: 選択した加工を確認して登録</p>
                  <div className="flex items-center gap-3 text-xs mb-2">
                    <span className="text-slate-500">使用する加工:</span>
                    <span className="font-mono font-bold text-teal-700">加工ID:{cpSelected.machining_id}</span>
                    <span className="font-mono font-bold">{cpSelected.drawing_no}</span>
                    <span className="text-slate-600">{cpSelected.part_name}</span>
                    <span className="font-mono text-slate-500">{cpSelected.version}</span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <input value={cpNote} onChange={e => setCpNote(e.target.value)}
                      className="flex-1 border border-teal-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400"
                      placeholder="備考（任意）" />
                    <button
                      disabled={cpSaving}
                      onClick={async () => {
                        if (!token || !cpSelected) return;
                        setCpSaving(true); setCpError(null);
                        try {
                          await mcApi.registerCommonPart({
                            source_machining_id: cpSelected.machining_id,
                            target_part_id: d.partId,
                            note: cpNote || undefined,
                          }, token);
                          setCpRegOpen(false);
                          showToast("✅ 共通登録しました");
                          const nr = await mcApi.findOne(mcId);
                          setDetail((nr as any).data ?? nr);
                        } catch (e: any) {
                          setCpError(e?.response?.data?.message ?? e?.message ?? "登録失敗");
                        } finally { setCpSaving(false); }
                      }}
                      className="px-4 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-700 disabled:opacity-50 whitespace-nowrap">
                      {cpSaving ? "登録中..." : "✅ 共通登録する"}
                    </button>
                  </div>
                  {cpError && <div className="mt-1 text-red-600 text-xs">{cpError}</div>}
                </div>
              )}
              {/* フッター */}
              <div className="px-5 py-2.5 border-t border-slate-200 flex justify-end shrink-0">
                <button onClick={() => { setCpRegOpen(false); setCpSearchResults([]); setCpSelected(null); setCpSearchQ(""); }}
                  className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">
                  閉じる
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}
        {mainTab === "history" && (
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-2 mb-4">
              {[["change","変更履歴"],["work","作業記録"],["print","印刷履歴"]].map(([k, l]) => (
                <button key={k} onClick={() => setHistTab(k)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    histTab === k ? "bg-teal-600 text-white border-teal-600" : "border-slate-300 text-slate-500 hover:border-teal-400"}`}>
                  {l}
                </button>
              ))}
            </div>
            {histLoading && <div className="text-center py-8 text-slate-400">読み込み中…</div>}
            {!histLoading && histTab === "change" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!changes || changes.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">変更履歴がありません</div>
                ) : changes.map((c: any, i) => (
                  <div key={c.id} className={`px-4 py-3 border-b border-slate-100 text-sm ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400 text-xs">{fmtDate(c.changedAt)}</span>
                      <span className="text-slate-500 text-xs">{c.operator?.name ?? "—"}</span>
                      <span className="text-slate-700">{c.content ?? c.changeType}</span>
                      {c.versionAfter && <span className="ml-auto font-mono text-[10px] text-slate-400">Ver.{c.ver_after}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!histLoading && histTab === "work" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!works || works.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">作業記録がありません</div>
                ) : works.map((r: McWorkRecord, i) => (
                  <div key={r.id} className={`px-4 py-3 border-b border-slate-100 text-xs ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400">{fmtDate(r.work_date)}</span>
                      <span className="font-bold text-slate-600">{r.operator_name ?? "—"}</span>
                      <span className="text-slate-500">{r.machine_code ?? ""}</span>
                      <span>段取: {r.setup_time_min != null ? `${r.setup_time_min}分` : "—"}</span>
                      <span>加工: {r.machining_time_min != null ? `${r.machining_time_min}分` : "—"}</span>
                      {r.quantity && <span>W数: {r.quantity}</span>}
                    </div>
                    {r.note && <div className="text-slate-400 mt-1">{r.note}</div>}
                  </div>
                ))}
              </div>
            )}
            {!histLoading && histTab === "print" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!prints || prints.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">印刷履歴がありません</div>
                ) : prints.map((p: McSetupSheetLog, i) => (
                  <div key={p.id} className={`px-4 py-3 border-b border-slate-100 text-xs ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      {p.sheet_type === 'NEW' ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-100 text-teal-700 border border-teal-200">新規段取</span>
                      ) : p.sheet_type === 'REPEAT' ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700 border border-blue-200">リピート</span>
                      ) : null}
                      {p.is_reference && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-200">参考</span>
                      )}
                      <span className="text-slate-400">{new Date(p.printed_at).toLocaleString("ja-JP")}</span>
                      <span className="text-slate-600">{p.operator_name ?? "—"}</span>
                      {p.version && <span className="font-mono text-slate-400">Ver.{p.version}</span>}
                      {!p.work_collected && (
                        <span className="ml-auto px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-600 border border-red-200">未回収</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── 写真・図 ─── */}
        {mainTab === "files" && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* 📋 Ridoc図面カード */}
            {d.part.drawingNo && (
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-bold text-white bg-indigo-600 px-2.5 py-0.5 rounded-full">📋 図面</span>
                  <span className="text-xs text-slate-400">{d.part.drawingNo}</span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-white rounded-xl border-2 border-indigo-300 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                    onClick={async () => {
                      if (!isAuthenticated) { setDrawingAuthOpen(true); return; }
                      setDrawingModal(true);
                      setDrawingLoading(true);
                      try {
                        const res = await fetch(`/api/mc/${mcId}/drawing-image?imgType=ORG`, {
                          headers: token ? { Authorization: `Bearer ${token}` } : {},
                        });
                        if (!res.ok) throw new Error(`HTTP ${res.status}`);
                        const blob = await res.blob();
                        setDrawingBlobUrl(prev => { if(prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
                      } catch { setDrawingBlobUrl(null); }
                      finally { setDrawingLoading(false); }
                    }}>
                    <div className="aspect-square bg-indigo-50 flex items-center justify-center overflow-hidden">
                      <img src={`/api/mc/${mcId}/drawing-image?imgType=TN`} alt={`図面 ${d.part.drawingNo}`}
                        className="w-full h-full object-contain" loading="lazy"
                        onError={e => {
                          const el=e.target as HTMLImageElement; el.style.display="none";
                          const p=el.parentElement;
                          if(p && !p.querySelector(".no-tn-msg")){
                            const m=document.createElement("span"); m.className="no-tn-msg text-[10px] text-slate-400 text-center px-2";
                            m.textContent="図面取得不可"; p.appendChild(m);
                          }
                        }} />
                    </div>
                    <div className="px-2 py-1.5 bg-indigo-50 border-t border-indigo-200">
                      <p className="text-[11px] text-indigo-800 font-bold truncate">{d.part.drawingNo}</p>
                      <p className="text-[10px] text-slate-400">クリックで拡大表示</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {d.files.filter(f => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <div className="text-4xl mb-3">📁</div>
                <p className="text-slate-400 text-sm">ファイルがありません</p>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="mt-4 text-teal-600 text-sm hover:underline">編集画面でアップロード →</button>
              </div>
            ) : (
              <div>
                {/* 📷 写真セクション */}
                {d.files.filter(f => f.file_type === "PHOTO").length > 0 && (
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-bold text-white bg-teal-600 px-2.5 py-0.5 rounded-full">📷 写真</span>
                      <span className="text-xs text-slate-400">{d.files.filter(f => f.file_type === "PHOTO").length}枚</span>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      {d.files.filter(f => f.file_type === "PHOTO").map(f => (
                        <div key={f.id} className="bg-white rounded-xl border-2 border-teal-300 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                          onClick={() => setPreviewFile(f)}>
                          <div className="aspect-square bg-teal-50 flex items-center justify-center overflow-hidden">
                            <img src={`/api/mc/${mcId}/files/${f.id}/thumb`} alt={f.original_name}
                              className="w-full h-full object-contain" loading="lazy"
                              onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                          </div>
                          <div className="px-2 py-1.5 bg-teal-50 border-t border-teal-200">
                            <p className="text-[11px] text-teal-800 font-bold truncate">{f.stored_name ?? f.original_name}</p>
                            <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* 📐 図セクション */}
                {d.files.filter(f => f.file_type === "DRAWING").length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-bold text-white bg-purple-600 px-2.5 py-0.5 rounded-full">📐 図</span>
                      <span className="text-xs text-slate-400">{d.files.filter(f => f.file_type === "DRAWING").length}枚</span>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      {d.files.filter(f => f.file_type === "DRAWING").map(f => (
                        <div key={f.id} className="bg-white rounded-xl border-2 border-purple-300 overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                          onClick={() => setPreviewFile(f)}>
                          <div className="aspect-square bg-purple-50 flex items-center justify-center overflow-hidden">
                            <img src={`/api/mc/${mcId}/files/${f.id}/thumb`} alt={f.original_name}
                              className="w-full h-full object-contain" loading="lazy"
                              onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                          </div>
                          <div className="px-2 py-1.5 bg-purple-50 border-t border-purple-200">
                            <p className="text-[11px] text-purple-800 font-bold truncate">{f.stored_name ?? f.original_name}</p>
                            <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      </div>

      {/* PGビューアモーダル */}
      {pgViewerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-xl shadow-2xl w-[90vw] max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 shrink-0">
              <div className="flex items-center gap-3">
                <span className="font-bold text-slate-800">加工プログラム</span>
                {pgOrigName && (
                  <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded">
                    {pgOrigName}
                  </span>
                )}
                {pgFileCount > 1 && (
                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                    計{pgFileCount}ファイル（MAINを表示中）
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={`/api/mc/${mcId}/pg-download`}
                  download
                  className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold rounded-lg transition-colors"
                >
                  💾 USBへ書き出し{pgFileCount > 1 ? "（ZIP）" : ""}
                </a>
                <button
                  onClick={() => setPgViewerOpen(false)}
                  className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-colors"
                >
                  閉じる
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-slate-900 rounded-b-xl">
              <pre className="font-mono text-xs text-green-300 whitespace-pre leading-relaxed select-all">
                {pgContent ?? ""}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType={authType}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}

      {/* 📋 Ridoc図面 認証モーダル */}
      {drawingAuthOpen && (
        <AuthModal isOpen={true} mcProgramId={mcId} sessionType="edit"
          onSuccess={async () => {
            setDrawingAuthOpen(false);
            setDrawingModal(true);
            setDrawingLoading(true);
            try {
              const t = localStorage.getItem("work_token") ?? "";
              const res = await fetch(`/api/mc/${mcId}/drawing-image?imgType=ORG`, {
                headers: t ? { Authorization: `Bearer ${t}` } : {},
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const blob = await res.blob();
              setDrawingBlobUrl(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
            } catch { setDrawingBlobUrl(null); }
            finally { setDrawingLoading(false); }
          }}
          onCancel={() => setDrawingAuthOpen(false)} />
      )}

      {/* 📋 Ridoc図面モーダル */}
      {drawingModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-0"
          onClick={() => { setDrawingModal(false); setDrawingZoom("fit"); setDrawingPan({x:0,y:0}); }}>
          <div className="bg-white flex flex-col w-screen h-screen" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 shrink-0 gap-2">
              <p className="text-sm font-bold text-slate-700">📋 図面 — {d.part.drawingNo}</p>
              <div className="flex items-center gap-1.5 shrink-0">
                {/* ズームコントロール */}
                <button onClick={() => { setDrawingZoom("fit"); setDrawingPan({x:0,y:0}); }}
                  className={`px-2.5 py-1 text-xs font-bold rounded border transition-colors ${drawingZoom === "fit" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
                  FIT
                </button>
                <button onClick={() => { setDrawingZoom(100); setDrawingPan({x:0,y:0}); }}
                  className={`px-2.5 py-1 text-xs font-bold rounded border transition-colors ${drawingZoom === 100 ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
                  100%
                </button>
                <button onClick={() => setDrawingZoom(z => { const cur = typeof z === "number" ? z : 100; return Math.max(10, cur - 20); })}
                  className="px-2 py-1 text-xs font-bold rounded border bg-white text-slate-600 border-slate-300 hover:bg-slate-50">－</button>
                <span className="text-xs text-slate-500 w-12 text-center font-mono">
                  {drawingZoom === "fit" ? "FIT" : `${drawingZoom}%`}
                </span>
                <button onClick={() => setDrawingZoom(z => { const cur = typeof z === "number" ? z : 100; return Math.min(800, cur + 20); })}
                  className="px-2 py-1 text-xs font-bold rounded border bg-white text-slate-600 border-slate-300 hover:bg-slate-50">＋</button>
                <div className="w-px h-5 bg-slate-200 mx-1" />
                {drawingBlobUrl && (
                  <a href={drawingBlobUrl} download={`drawing-${d.part.drawingNo}.jpg`}
                    className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                    ⬇ ダウンロード
                  </a>
                )}
                <button onClick={() => { setDrawingModal(false); setDrawingZoom("fit"); setDrawingPan({x:0,y:0}); }}
                  className="ml-1 text-slate-400 hover:text-slate-700 text-lg px-1.5">✕</button>
              </div>
            </div>
            <div
              className="flex-1 relative overflow-hidden bg-slate-900 flex items-center justify-center"
              style={{ cursor: drawingZoom !== "fit" ? (drawingDrag.current ? "grabbing" : "grab") : "default" }}
              onWheel={e => {
                if (!drawingBlobUrl) return;
                e.preventDefault();
                const delta = e.deltaY > 0 ? -20 : 20;
                setDrawingZoom(z => {
                  const cur = typeof z === "number" ? z : 100;
                  const next = Math.max(10, Math.min(800, cur + delta));
                  return next;
                });
              }}
              onMouseDown={e => {
                if (drawingZoom === "fit") return;
                drawingDrag.current = { startX: e.clientX, startY: e.clientY, panX: drawingPan.x, panY: drawingPan.y };
              }}
              onMouseMove={e => {
                if (!drawingDrag.current) return;
                setDrawingPan({
                  x: drawingDrag.current.panX + (e.clientX - drawingDrag.current.startX),
                  y: drawingDrag.current.panY + (e.clientY - drawingDrag.current.startY),
                });
              }}
              onMouseUp={() => { drawingDrag.current = null; }}
              onMouseLeave={() => { drawingDrag.current = null; }}
            >
              {drawingLoading ? (
                <div className="flex flex-col items-center gap-3 text-slate-400">
                  <div className="w-8 h-8 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
                  <span className="text-sm">図面を取得中…</span>
                </div>
              ) : drawingBlobUrl ? (
                <div
                  style={{
                    transform: drawingZoom === "fit"
                      ? `translate(${drawingPan.x}px, ${drawingPan.y}px)`
                      : `translate(${drawingPan.x}px, ${drawingPan.y}px) scale(${(drawingZoom as number) / 100})`,
                    transformOrigin: "center center",
                    transition: drawingDrag.current ? "none" : "transform 0.1s ease",
                    userSelect: "none",
                  }}
                >
                  <img
                    src={drawingBlobUrl}
                    alt={`図面 ${d.part.drawingNo}`}
                    draggable={false}
                    style={
                      drawingZoom === "fit"
                        ? { maxWidth: "95vw", maxHeight: "calc(100vh - 60px)", objectFit: "contain", display: "block" }
                        : { width: "auto", height: "auto", display: "block" }
                    }
                  />
                </div>
              ) : (
                <p className="text-slate-400 text-sm text-center px-8">
                  図面を取得できませんでした<br />
                  <span className="text-xs text-slate-500">（Ridocサーバー未応答またはRIDOC_API_URL未設定）</span>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 写真・図プレビューモーダル */}
      {previewFile && (() => {
        const imgFiles = d.files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING");
        const curIdx = imgFiles.findIndex((f: any) => f.id === previewFile.id);
        const goPrev = () => { if (curIdx > 0) { setPreviewFile(imgFiles[curIdx - 1]); setPreviewZoom("fit"); } };
        const goNext = () => { if (curIdx < imgFiles.length - 1) { setPreviewFile(imgFiles[curIdx + 1]); setPreviewZoom("fit"); } };
        return (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-0"
          onClick={() => { setPreviewFile(null); setPreviewZoom("fit"); }}>
          <div className="bg-white flex flex-col w-screen h-screen"
            onClick={e => e.stopPropagation()}>
            {/* ヘッダー */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 shrink-0 gap-2">
              <p className="text-sm font-bold text-slate-700 truncate max-w-[40%]">
                {previewFile.original_name}
                <span className="ml-2 text-xs text-slate-400 font-normal">{curIdx + 1} / {imgFiles.length}</span>
              </p>
              <div className="flex items-center gap-1.5 shrink-0">
                <button onClick={() => setPreviewZoom("fit")}
                  className={`px-2.5 py-1 text-xs font-bold rounded border transition-colors ${previewZoom === "fit" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
                  画面内
                </button>
                <button onClick={() => setPreviewZoom("real")}
                  className={`px-2.5 py-1 text-xs font-bold rounded border transition-colors ${previewZoom === "real" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
                  実寸(100%)
                </button>
                <button onClick={() => setPreviewZoom(z => {
                  const cur = typeof z === "number" ? z : z === "real" ? 100 : 100;
                  return Math.max(10, cur - 20);
                })} className="px-2 py-1 text-xs font-bold rounded border bg-white text-slate-600 border-slate-300 hover:bg-slate-50">－</button>
                <span className="text-xs text-slate-500 w-12 text-center font-mono">
                  {previewZoom === "fit" ? "FIT" : previewZoom === "real" ? "100%" : `${previewZoom}%`}
                </span>
                <button onClick={() => setPreviewZoom(z => {
                  const cur = typeof z === "number" ? z : z === "real" ? 100 : 100;
                  return Math.min(400, cur + 20);
                })} className="px-2 py-1 text-xs font-bold rounded border bg-white text-slate-600 border-slate-300 hover:bg-slate-50">＋</button>
                <div className="w-px h-5 bg-slate-200 mx-1" />
                <button onClick={() => {
                  const w = window.open("");
                  if (w) { w.document.write(`<img src="/api/mc/${mcId}/files/${previewFile.id}/serve" onload="window.print();window.close()">`); }
                }} className="px-2.5 py-1 text-xs font-bold rounded border bg-white text-slate-600 border-slate-300 hover:bg-slate-50">🖨 印刷</button>
                {isAuthenticated && (
                  <a href={`/api/mc/${mcId}/files/${previewFile.id}/serve`} download={previewFile.original_name}
                    className="px-2.5 py-1 text-xs font-bold rounded border bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100">
                    ✏️ 編集用DL
                  </a>
                )}
                <button onClick={() => { setPreviewFile(null); setPreviewZoom("fit"); }}
                  className="ml-1 text-slate-400 hover:text-slate-700 text-lg px-1.5">✕</button>
              </div>
            </div>
            {/* 画像エリア＋左右ナビ */}
            <div className="flex-1 relative overflow-hidden bg-slate-900 flex items-center justify-center">
              {/* 左矢印 */}
              {curIdx > 0 && (
                <button onClick={goPrev}
                  className="absolute left-3 z-10 w-10 h-10 rounded-full bg-black/40 hover:bg-black/70 text-white text-xl flex items-center justify-center transition-colors">
                  ‹
                </button>
              )}
              {/* 画像スクロールエリア */}
              <div className="w-full h-full overflow-auto flex items-center justify-center">
                <img
                  key={previewFile.id}
                  src={`/api/mc/${mcId}/files/${previewFile.id}/serve`}
                  alt={previewFile.original_name}
                  style={
                    previewZoom === "fit"
                      ? { maxWidth: "100%", maxHeight: "100%", objectFit: "contain", display: "block" }
                      : previewZoom === "real"
                      ? { width: "auto", height: "auto", maxWidth: "none", maxHeight: "none", display: "block" }
                      : { transform: `scale(${previewZoom / 100})`, transformOrigin: "top left", display: "block" }
                  }
                />
              </div>
              {/* 右矢印 */}
              {curIdx < imgFiles.length - 1 && (
                <button onClick={goNext}
                  className="absolute right-3 z-10 w-10 h-10 rounded-full bg-black/40 hover:bg-black/70 text-white text-xl flex items-center justify-center transition-colors">
                  ›
                </button>
              )}
            </div>
          </div>
        </div>
        );
      })()}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">
          {toast}
        </div>
      )}
    </div>
  );
}
