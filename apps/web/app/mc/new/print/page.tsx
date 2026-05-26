"use client";
import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

function McNewPrintInner() {
  const router = useRouter();
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [pending, setPending] = useState<any>(null);
  const [includeDrawings, setIncludeDrawings] = useState(false);
  const [printing, setDirectPrinting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [printError, setPrintError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = typeof window !== "undefined" ? { current: null as any } : { current: null as any };

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 4000); }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const d = sessionStorage.getItem("mc_new_pending");
      if (!d) { router.push("/mc/new"); return; }
      setPending(JSON.parse(d));
    }
  }, []);

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

  const handlePreview = async () => {
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

  const handleDirectPrint = async () => {
    if (!token || !pending) { setPrintError("認証または情報が不足しています"); return; }
    setDirectPrinting(true); setPrintError(null);
    try {
      const body = { ...pending, include_drawings: includeDrawings };
      const res = await fetch("/api/mc/create-and-print", {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.message ?? `HTTP ${res.status}`);
      if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending");
      logout();
      if (j.retried) {
        showToast(`⚠️ ${j.message}`);
      } else {
        showToast(`✅ ${j.message}`);
      }
      setTimeout(() => router.push(`/mc/${j.mc_id}`), 2000);
    } catch (e: any) {
      setPrintError(e.message ?? "印刷に失敗しました");
    } finally {
      setDirectPrinting(false);
    }
  };

  if (!pending) return <div className="h-screen flex items-center justify-center text-slate-400">読み込み中…</div>;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc/new")} disabled={isAuthenticated}
          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors ${isAuthenticated ? "border-slate-600 text-slate-500 cursor-not-allowed opacity-40" : "border-slate-500 text-slate-300 hover:bg-slate-700"}`}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          ← 登録画面に戻る
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">段取シート発行（新規）</span>
        <div className="ml-auto flex items-center gap-3">
          {isAuthenticated && operator ? (
            <span className="text-xs bg-red-600 text-white px-3 py-1 rounded-full font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          ) : (
            <button onClick={() => setAuthOpen(true)}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-lg font-bold transition-colors">
              🔒 要認証 — クリックして認証
            </button>
          )}
        </div>
      </header>

      <div className="bg-white border-b border-slate-200 px-5 py-2 flex items-center gap-4 shrink-0 flex-wrap">
        <span className="font-bold text-slate-700 text-sm">{pending.drawing_no}</span>
        <span className="text-slate-400">/</span>
        <span className="text-sm text-slate-600">{pending.part_name}</span>
        <span className="text-slate-400 text-xs ml-2">加工ID（仮）: <span className="font-mono font-bold text-teal-700">{pending.machining_id}</span></span>
        <span className="ml-1 text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">印刷確定時に加工IDが確定します</span>
      </div>

      <div className="flex-1 overflow-y-auto p-5 flex items-center justify-center">
        {printError && (
          <div className="fixed top-20 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg shadow z-50">❌ {printError}</div>
        )}

        {!isAuthenticated ? (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 max-w-md w-full text-center">
            <div className="text-5xl mb-4">🖨</div>
            <h2 className="text-slate-700 font-bold text-lg mb-2">段取シート発行（新規）</h2>
            <p className="text-slate-400 text-sm mb-6">発行には担当者認証が必要です</p>
            <div className="bg-slate-50 rounded-xl p-4 mb-6 text-sm text-left space-y-1">
              <div className="flex justify-between"><span className="text-slate-500">図番</span><span className="font-medium">{pending.drawing_no}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">部品名</span><span className="font-medium">{pending.part_name}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">加工ID（仮）</span><span className="font-mono font-bold text-teal-700">{pending.machining_id}</span></div>
            </div>
            <button onClick={() => setAuthOpen(true)}
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
                <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                  className="accent-teal-600 w-4 h-4" />
                <span className="text-slate-700">図を含める</span>
              </label>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-5 text-xs text-amber-700">
              ⚠️ 「プリンタに直接印刷」のみ加工IDが確定し、MCデータが登録されます。<br/>
              この画面を離脱した場合、MCデータは登録されません。
            </div>
            <button onClick={handlePreview} disabled={previewing || printing}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm mt-2">
              {previewing ? "PDF生成中..." : "📄 プレビュー（透かし入り・記録なし）"}
            </button>
            <button onClick={handleDirectPrint} disabled={printing || previewing}
              className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm mt-3">
              {printing ? "登録・送信中..." : "🖨 プリンタに直接印刷（加工IDを確定）"}
            </button>
            <button onClick={() => { logout(); if (typeof window !== "undefined") sessionStorage.removeItem("mc_new_pending"); router.push("/"); }}
              disabled={printing || previewing}
              className="w-full bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-600 font-bold py-3 rounded-xl text-sm transition-colors mt-3">
              ✗ キャンセル（ダッシュボードへ戻る）
            </button>
          </div>
        )}
      </div>

      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={0} mcProgramId={0} sessionType="setup_print"
          onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}

export default function McNewPrintPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>
      <McNewPrintInner />
    </Suspense>
  );
}
