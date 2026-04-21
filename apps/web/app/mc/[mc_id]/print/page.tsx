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
      <header className="bg-slate-800 text-white px-5 py-2 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc/search")} className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>
        <span className="text-slate-600">›</span>
        <span className="text-xs text-slate-300 truncate">{d.part.drawingNo} / 段取シート</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs border border-sky-600 hover:border-sky-400 text-sky-400 hover:text-white hover:bg-sky-700 px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>
        {isAuthenticated && operator && (
          <span className="ml-auto text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
            作業中: {operator.name} {fmtElapsed(elapsed)}
          </span>
        )}
      </header>

      <div className="bg-white border-b border-slate-200 px-5 py-2.5 shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-mono text-teal-600 font-bold">{d.part.drawingNo}</span>
          <span className={`text-[11px] px-2 py-0.5 rounded font-bold ${STATUS_COLOR[d.status] ?? ""}`}>{STATUS_LABEL[d.status] ?? d.status}</span>
          <span className="font-mono text-[11px] text-slate-400">MCID:{d.id} Ver.{d.version}</span>
        </div>
        <div className="text-sm text-slate-700 mt-0.5">{d.part.name}</div>
      </div>

      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {[
          { href: `/mc/${mcId}`,        label: "MC詳細",    active: false },
          { href: `/mc/${mcId}/edit`,   label: "変更・登録", active: false },
          { href: `/mc/${mcId}/print`,  label: "段取シート", active: true  },
          { href: `/mc/${mcId}/record`, label: "作業記録",  active: false },
        ].map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab.active ? "border-teal-400 text-teal-300" : "border-transparent text-slate-400 hover:text-white"}`}>
            {tab.label}
          </button>
        ))}
      </nav>

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
