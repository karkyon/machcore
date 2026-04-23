"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, McDetail } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};

export default function McPrintPage() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();

  const [nc, setNc]   = useState<McDetail | null>(null);
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed, setElapsed]   = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const [includeTooling,        setIncludeTooling]        = useState(true);
  const [includeClamp,          setIncludeClamp]          = useState(true);
  const [includeDrawings,       setIncludeDrawings]       = useState(false);
  const [includeWorkOffsets,    setIncludeWorkOffsets]    = useState(false);
  const [includeIndexPrograms,  setIncludeIndexPrograms]  = useState(false);

  const [printing,       setPrinting]       = useState(false);
  const [directPrinting, setDirectPrinting] = useState(false);
  const [printError,     setPrintError]     = useState<string | null>(null);
  const [toast,          setToast]          = useState<string | null>(null);

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); }, []);

  useEffect(() => {
    mcApi.getPrintData(mcId).then(r => setNc((r as any).data ?? r)).catch(() => {});
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

  const fmtElapsed = (s: number) => `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;

  const printBody = {
    include_tooling:        includeTooling,
    include_clamp:          includeClamp,
    include_drawings:       includeDrawings,
    include_work_offsets:   includeWorkOffsets,
    include_index_programs: includeIndexPrograms,
  };

  const handlePrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setPrinting(true); setPrintError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiUrl}/mc/${mcId}/print`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(printBody),
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
      logout();
      showToast("✅ 段取シートを発行しました");
      setTimeout(() => router.push(`/mc/${mcId}`), 1500);
    } catch (e: any) {
      setPrintError(e.message ?? "PDF生成に失敗しました");
    } finally {
      setPrinting(false);
    }
  };

  const handleDirectPrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setDirectPrinting(true); setPrintError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiUrl}/mc/${mcId}/direct-print`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(printBody),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.message ?? `HTTP ${res.status}`);
      logout();
      showToast(`✅ ${j.message}`);
      setTimeout(() => router.push(`/mc/${mcId}`), 1500);
    } catch (e: any) {
      setPrintError(e.message ?? "印刷に失敗しました");
    } finally {
      setDirectPrinting(false);
    }
  };

  if (!nc) return <div className="h-screen flex items-center justify-center text-slate-400">読み込み中…</div>;

  const d = nc;
  const fmtCycle = (sec: number | null) => {
    if (!sec) return "—";
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return `${h}H ${String(m).padStart(2,"0")}M ${String(s).padStart(2,"0")}S`;
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button
          onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs bg-white text-slate-800 hover:bg-slate-100 border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>
        <span className="text-sm font-medium flex items-center gap-1.5">段取シート</span>
        <span className="ml-auto">
          {isAuthenticated && operator && (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          )}
          {!isAuthenticated && (
            <span className="text-[11px] bg-slate-600 text-white px-2 py-0.5 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報エリア */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-teal-600 font-bold text-lg">{d.part.drawingNo}</span>
          {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
            d.status === "APPROVED"         ? "bg-emerald-100 text-emerald-700" :
            d.status === "PENDING_APPROVAL" ? "bg-amber-100 text-amber-700" :
            d.status === "CHANGING"         ? "bg-red-100 text-red-700" :
                                              "bg-blue-100 text-blue-700"
          }`}>{
            d.status === "APPROVED" ? "承認済" : d.status === "PENDING_APPROVAL" ? "未承認" :
            d.status === "CHANGING" ? "変更中" : "新規"
          }</span>
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
        </div>
        <div className="text-sm text-slate-700 font-medium mb-1">{d.part.name}</div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>MCID: {d.id}</span>
          <span>加工ID: {d.machiningId}</span>
          {d.part.partId && <span>部品ID: {d.part.partId}</span>}
          {d.part.clientName && <span>納入先: {d.part.clientName}</span>}
        </div>
      </div>

      {/* タブナビ */}
      <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-teal-400 text-teal-400 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          作業記録
        </button>
      </nav>      </nav>

      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center gap-3 text-xs shrink-0">
          <span className="font-bold">⚡ 作業中:</span><span>{operator.name}</span>
          <span className="font-mono bg-red-700 px-2 py-0.5 rounded">{fmtElapsed(elapsed)}</span>
          <span className="text-red-300">段取シート発行</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-5">
        {printError && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">❌ {printError}</div>
        )}

        {!isAuthenticated ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-lg w-full">
              <div className="text-center mb-6">
                <div className="text-5xl mb-3">🖨</div>
                <h2 className="text-slate-700 font-bold text-lg mb-2">段取シート発行</h2>
                <p className="text-slate-400 text-sm">発行には担当者認証が必要です</p>
              </div>
              {/* プレビュー情報 */}
              <div className="bg-slate-50 rounded-xl p-4 mb-6 text-sm space-y-2">
                <div className="flex justify-between"><span className="text-slate-500">機械</span><span className="font-medium">{d.machine?.machineName ?? "—"}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">主Oナンバ</span><span className="font-mono">{d.oNumber ?? "—"}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">CT/1P</span><span>{fmtCycle(d.cycleTimeSec)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">ツーリング</span><span>{d.tooling.length}本</span></div>
              </div>
              {/* 印刷オプション */}
              <div className="space-y-2 mb-6">
                {[
                  [includeTooling,       setIncludeTooling,       "ツーリングリストを含める"],
                  [includeClamp,         setIncludeClamp,         "クランプ情報を含める"],
                  [includeDrawings,      setIncludeDrawings,      "図を含める"],
                  [includeWorkOffsets,   setIncludeWorkOffsets,   "ワークオフセットを含める"],
                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],
                ].map(([val, setter, label]: any) => (
                  <label key={label} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">{label}</span>
                  </label>
                ))}
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm">
                この作業を開始する
              </button>
            </div>
          </div>
        ) : (
          <div className="max-w-xl mx-auto">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="bg-teal-600 px-5 py-3 text-white">
                <h2 className="font-bold">段取シート発行オプション</h2>
              </div>
              <div className="p-5 space-y-3">
                {[
                  [includeTooling,       setIncludeTooling,       "ツーリングリストを含める"],
                  [includeClamp,         setIncludeClamp,         "クランプ情報を含める"],
                  [includeDrawings,      setIncludeDrawings,      "図を含める"],
                  [includeWorkOffsets,   setIncludeWorkOffsets,   "ワークオフセットを含める"],
                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],
                ].map(([val, setter, label]: any) => (
                  <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                    <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">{label}</span>
                  </label>
                ))}
              </div>
              <div className="px-5 pb-5 flex flex-col gap-3">
                <button onClick={handlePrint} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>
                <button onClick={handleDirectPrint} disabled={directPrinting}
                  className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3 rounded-xl text-sm">
                  {directPrinting ? "送信中..." : "🖨 RICOH IM C3510 に直接印刷"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} sessionType="setup_print" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}
