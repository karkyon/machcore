"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, McDetail, machinesApi, Machine } from "@/lib/api";
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

function McPrintPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();
  const searchParams = useSearchParams();
  const isNewEntry = searchParams.get('from') === 'new';

  const [nc, setNc]   = useState<McDetail | null>(null);
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed, setElapsed]   = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const [includeTooling,        setIncludeTooling]        = useState(true);
  const [includeClamp,          setIncludeClamp]          = useState(true);
  const [includeDrawings,       setIncludeDrawings]       = useState(false);
  const [includeWorkOffsets,    setIncludeWorkOffsets]    = useState(true);
  const [includeIndexPrograms,  setIncludeIndexPrograms]  = useState(true);
  const [isReference,           setIsReference]           = useState(false);

  // リピート確認ステップ
  const [repeatPurpose,   setRepeatPurpose]   = useState<'setup' | 'reference' | 'continuous'>('setup');
  const [repeatQty,       setRepeatQty]       = useState<number>(1);
  const [repeatMachineId, setRepeatMachineId] = useState<number | null>(null);
  const [repeatConfirmed, setRepeatConfirmed] = useState(false);
  const [machines,        setMachines]        = useState<Machine[]>([]);

  const [printing,       setPrinting]       = useState(false);
  const [directPrinting, setDirectPrinting] = useState(false);
  const [printError,     setPrintError]     = useState<string | null>(null);
  const [toast,          setToast]          = useState<string | null>(null);
  const [spSheets,    setSpSheets]    = useState<Array<{ id: number; keyword: string | null; sheet_name: string; content: string; pdf_path: string | null; version: number }>>([]);
  const [spModalOpen, setSpModalOpen] = useState(false);
  const [spSkipped,   setSpSkipped]   = useState(false);
  const [pendingPrint, setPendingPrint] = useState<"preview" | "direct" | null>(null);

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); }, []);

  useEffect(() => {
    machinesApi.list().then(r => {
      const list = Array.isArray((r as any).data) ? (r as any).data : (Array.isArray(r) ? r : []);
      setMachines(list);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    mcApi.getPrintData(mcId).then(r => setNc((r as any).data ?? r)).catch(() => {});
  }, [mcId]);

  // ── 前回印刷時の機械・ワーク数・用途をデフォルト値としてセット ──
  useEffect(() => {
    if (!machines.length) return; // machines取得後に実行
    mcApi.setupSheetLogs(mcId).then(r => {
      const logs: any[] = Array.isArray((r as any).data) ? (r as any).data : (Array.isArray(r) ? r : []);
      // 未回収 & REPEATシートのうち最新（printedAt降順先頭）を取得
      const latest = logs.find(l => !l.work_collected && l.sheet_type === 'REPEAT')
        ?? logs.find(l => !l.work_collected)
        ?? logs[0];
      if (!latest) return;
      // machine_id_log → machines配列のidと照合してデフォルトセット
      if (latest.machine_id_log && repeatMachineId === null) {
        const m = machines.find(m => m.id === latest.machine_id_log);
        if (m) setRepeatMachineId(m.id);
      }
      // ワーク数
      if (latest.quantity && latest.quantity > 0 && repeatQty === 1) {
        setRepeatQty(latest.quantity);
      }
      // 用途
      if (latest.purpose) {
        const purposeMap: Record<string, 'setup' | 'reference' | 'continuous'> = {
          setup: 'setup', reference: 'reference', continuous: 'continuous',
          段取: 'setup', 参考資料: 'reference', 連続使用: 'continuous',
        };
        const mapped = purposeMap[latest.purpose];
        if (mapped) setRepeatPurpose(mapped);
      }
    }).catch(() => {});
  }, [mcId, machines]); // machinesが取得されてから実行

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

  const isNew = nc?.status === "NEW";

  const printBody = {
    include_tooling:        includeTooling,
    include_clamp:          includeClamp,
    include_drawings:       includeDrawings,
    include_work_offsets:   includeWorkOffsets,
    include_index_programs: includeIndexPrograms,
    ...(!isNew && repeatConfirmed ? {
      purpose:    repeatPurpose,
      quantity:   repeatPurpose !== 'reference' ? repeatQty : undefined,
      machine_id: repeatPurpose !== 'reference' ? repeatMachineId ?? undefined : undefined,
    } : {}),
  };

  const validateRepeat = (): string | null => {
    if (isNew) return null;
    if (!repeatConfirmed) return '発行前の確認を完了してください';
    if (repeatPurpose !== 'reference' && (!repeatQty || repeatQty < 1)) return 'ワーク数を入力してください';
    if (repeatPurpose !== 'reference' && !repeatMachineId) return '使用機械を選択してください';
    return null;
  };

  const checkSpAndPrint = async (mode: "preview" | "direct") => {
    const vErr = validateRepeat();
    if (vErr) { setPrintError(vErr); return; }
    if (spSkipped) {
      // チェック済み → そのまま印刷
      if (mode === "preview") await handlePrint();
      else await handleDirectPrint();
      return;
    }
    try {
      // 相対パス(/api)を使用 — NEXT_PUBLIC_API_URLはlocalhost参照のため他PCで失敗する
      const res = await fetch(`/api/mc/${mcId}/special-sheet-check`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.matched && data.sheets.length > 0) {
        setSpSheets(data.sheets);
        setPendingPrint(mode);
        setSpModalOpen(true);
        return;
      }
    } catch (e) {
      console.error("[SP check]", e);
    }
    // SPシートなし → そのまま印刷
    if (mode === "preview") await handlePrint();
    else await handleDirectPrint();
  };

  const handlePrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setPrinting(true); setPrintError(null);
    try {
      const endpoint = isNew ? `/api/mc/${mcId}/print` : `/api/mc/${mcId}/repeat-print`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({...printBody, is_reference: isReference, is_preview: true}),
      });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
      showToast("📄 プレビューを開きました（DBに記録されません）");
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
      const endpoint = isNew ? `/api/mc/${mcId}/direct-print` : `/api/mc/${mcId}/repeat-direct-print`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({...printBody, is_reference: isReference}),
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

  // リピート確認ブロック（isNew=false の時のみ表示）
  const repeatConfirmBlock = (() => {
    if (isNew) return null;
    if (repeatConfirmed) return (
      <div className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm flex items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="font-bold text-emerald-700">✅ 発行前の確認完了</span>
          <span className="text-slate-600">用途: <span className="font-bold">{repeatPurpose === 'setup' ? '段取' : repeatPurpose === 'reference' ? '参考資料' : '連続使用'}</span></span>
          {repeatPurpose !== 'reference' && <span className="text-slate-600">W数: <span className="font-bold">{repeatQty}</span></span>}
          {repeatPurpose !== 'reference' && repeatMachineId && (
            <span className="text-slate-600">機械: <span className="font-bold">{machines.find(m => m.id === repeatMachineId)?.machineCode ?? '—'}</span></span>
          )}
        </div>
        <button onClick={() => setRepeatConfirmed(false)} className="text-xs text-slate-500 underline ml-4 shrink-0">変更</button>
      </div>
    );
    return (
      <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 space-y-3">
        <div className="text-sm font-bold text-amber-800">⚠️ 発行前の確認</div>
        {/* 用途 */}
        <div>
          <label className="text-xs font-bold text-slate-600 mb-1 block">用途</label>
          <div className="flex gap-3 flex-wrap">
            {([['setup','段取'],['reference','参考資料'],['continuous','連続使用']] as const).map(([val,label]) => (
              <label key={val} className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" name="repeatPurpose" value={val}
                  checked={repeatPurpose === val}
                  onChange={() => setRepeatPurpose(val)}
                  className="accent-amber-600" />
                <span className="text-sm">{label}</span>
              </label>
            ))}
          </div>
        </div>
        {/* ワーク数 */}
        {repeatPurpose !== 'reference' && (
          <div>
            <label className="text-xs font-bold text-slate-600 mb-1 block">ワーク数 <span className="text-red-500">*</span></label>
            <input type="number" min={1} value={repeatQty}
              onChange={e => setRepeatQty(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-24 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
        )}
        {/* 使用機械 */}
        {repeatPurpose !== 'reference' && (
          <div>
            <label className="text-xs font-bold text-slate-600 mb-1 block">使用機械 <span className="text-red-500">*</span></label>
            <select value={repeatMachineId ?? ''}
              onChange={e => setRepeatMachineId(e.target.value ? parseInt(e.target.value) : null)}
              className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400">
              <option value="">— 選択してください —</option>
              {machines.filter(m => m.isActive).map(m => (
                <option key={m.id} value={m.id}>{m.machineCode} {m.machineName !== m.machineCode ? `(${m.machineName})` : ''}</option>
              ))}
            </select>
          </div>
        )}
        {/* 確認ボタン */}
        <div>
          <button
            onClick={() => {
              if (repeatPurpose !== 'reference' && (!repeatQty || repeatQty < 1)) { setPrintError('ワーク数を入力してください'); return; }
              if (repeatPurpose !== 'reference' && !repeatMachineId) { setPrintError('使用機械を選択してください'); return; }
              setPrintError(null);
              setRepeatConfirmed(true);
            }}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-lg transition-colors"
          >確認完了</button>
        </div>
      </div>
    );
  })();

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button
          onClick={() => !isNewEntry && router.push(`/mc/${mcId}`)}
          disabled={isNewEntry}
          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${isNewEntry ? "bg-slate-600 border-slate-600 text-slate-400 opacity-40 cursor-not-allowed pointer-events-none" : "bg-slate-700 hover:bg-slate-600 border-slate-600 text-white"}`}
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          ダッシュボードへ
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
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
        <div className="flex items-center gap-3 flex-wrap mb-1.5">
          <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
          <span className="text-slate-300 text-xl font-light">/</span>
          <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
          {d.part.mainModel && <>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="text-slate-500 text-lg font-medium leading-none">{d.part.mainModel}</span>
          </>}
          <div className="flex items-center gap-2 ml-2">
            {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
            <StatusBadge status={d.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            {spSheets.length > 0 && (
              <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-red-600 text-white animate-pulse">
                ⚠️ SP
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
          {(d as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(d as any).mcProcessNo}</span>}
          <span className="text-slate-400">|</span>
          <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? "—"}</span></span>
          <span className="text-slate-400">|</span>
          <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
          {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
        </div>
      </div>

      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !isNewEntry && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => !isNewEntry && router.push(`/mc/${mcId}/edit`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => !isNewEntry && router.push(`/mc/${mcId}/record`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
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
              <div className="border border-slate-200 rounded-xl overflow-hidden text-sm mb-6">
                <div className="grid grid-cols-3 divide-x divide-slate-200 border-b border-slate-200">
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">MC工程No</div><div className="font-bold text-teal-700">{(d as any).mcProcessNo ?? "—"}</div></div>
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">バージョン</div><div className="font-mono font-bold">{(d as any).version ?? "—"}</div></div>
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">機械</div><div className="font-bold">{d.machine?.machineCode ?? "—"}</div></div>
                </div>
                <div className="grid grid-cols-3 divide-x divide-slate-200 border-b border-slate-200">
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">主Oナンバ</div><div className="font-mono font-bold">{(d as any).oNumber ?? "—"}</div></div>
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">サイクルタイム/1P</div><div className="font-bold text-xs">{(d as any).cycleTimeSec != null ? (() => { const ct=(d as any).cycleTimeSec; const h=Math.floor(ct/3600); const m=Math.floor((ct%3600)/60); const s=ct%60; return `${h}H ${String(m).padStart(2,"0")}M ${String(s).padStart(2,"0")}S`; })() : "—"}</div></div>
                  <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">ツーリング</div><div className="font-bold">{(d as any).rc ?? (d as any).tooling?.length ?? 0} 本</div></div>
                </div>
                <div className="p-2.5 flex items-center justify-center gap-2 flex-wrap">
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${((d as any).rc ?? 0) > 0 ? "bg-teal-50 text-teal-700 border-teal-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>RC <span>{(d as any).rc ?? 0}</span></span>
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${(d as any).hasIndexProgram ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>IP {(d as any).hasIndexProgram ? "有" : "無"}</span>
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${(d as any).hasWorkOffset ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>WD {(d as any).hasWorkOffset ? "有" : "無"}</span>
                </div>
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
              {/* リピート確認ブロック */}
              {repeatConfirmBlock}

              <div className="bg-teal-600 px-5 py-3 text-white">
                <h2 className="font-bold">段取シート発行オプション</h2>
              </div>
              <div className="p-5 pb-2 space-y-3">
                <label className="flex items-center gap-3 text-sm cursor-pointer">
                  <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                    className="accent-teal-600 w-4 h-4" />
                  <span className="text-slate-700">図を含める</span>
                </label>
                {!isNew && (
                  <>
                    {([
                      ["ツーリングリストを含める", includeTooling,       setIncludeTooling],
                      ["クランプ情報を含める",     includeClamp,         setIncludeClamp],
                      ["ワークオフセットを含める", includeWorkOffsets,   setIncludeWorkOffsets],
                      ["インデックスプログラムを含める", includeIndexPrograms, setIncludeIndexPrograms],
                    ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
                      <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                        <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                          className="accent-teal-600 w-4 h-4" />
                        <span className="text-slate-700">{label}</span>
                      </label>
                    ))}
                  </>
                )}
              </div>

              <div className="px-5 py-4 pb-6 flex flex-col gap-4 border-t border-slate-100 mt-2">
                <button onClick={() => checkSpAndPrint("preview")} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : isNew ? "📄 プレビュー（透かし入り・記録なし）" : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>
                <button onClick={() => checkSpAndPrint("direct")} disabled={directPrinting}
                  className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
                  {directPrinting ? "送信中..." : "🖨 プリンタに直接印刷"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {spModalOpen && spSheets.length > 0 && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden">
            <div className="bg-red-600 px-5 py-4 flex items-center gap-3 shrink-0">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="text-white font-bold text-base">スペシャル段取シート</p>
                <p className="text-red-100 text-xs">過去にクレーム・トラブル実績のある製品です</p>
              </div>
            </div>
            <div className="overflow-y-auto flex-1 p-5 space-y-4">
              {spSheets.map(s => (
                <div key={s.id} className="border border-red-200 rounded-xl bg-red-50 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-red-800 text-sm">{s.sheet_name}</span>
                    <span className="text-xs text-red-500 font-mono">v{s.version}</span>
                  </div>
                  {s.keyword && (
                    <div className="text-[11px] text-red-600 mb-2">
                      🔑 キーワード: <span className="font-bold font-mono">{s.keyword}</span>
                    </div>
                  )}
                  <p className="text-sm text-red-900 whitespace-pre-wrap leading-relaxed">{s.content}</p>
                  {s.pdf_path && (
                    <button
                      onClick={async () => {
                        const params = new URLSearchParams();
                        if (d?.legacyMcid) params.set('mc_id', String(d.legacyMcid));
                        if (d?.part?.partId) params.set('part_id', String(d.part.partId));
                        if (d?.part?.drawingNo) params.set('drawing_no', d.part.drawingNo);
                        if (d?.part?.name) params.set('part_name', d.part.name);
                        const res = await fetch(`/api/admin/special-sheets/${s.id}/print-pdf`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            mc_id: d?.legacyMcid ?? undefined,
                            part_id: d?.part?.partId ?? undefined,
                            drawing_no: d?.part?.drawingNo ?? undefined,
                            part_name: d?.part?.name ?? undefined,
                          }),
                        });
                        if (res.ok) {
                          const blob = await res.blob();
                          window.open(URL.createObjectURL(blob), '_blank');
                        }
                      }}
                      className="mt-3 inline-flex items-center gap-1 text-xs bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700 font-bold">
                      📄 SPシートPDF を表示（MCID/日時印字）
                    </button>
                  )}
                </div>
              ))}
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
                加工内容が異なる場合は「スキップ」を選択してください
              </div>
            </div>
            <div className="border-t border-slate-200 px-5 py-4 flex gap-3 justify-end shrink-0">
              <button
                onClick={() => {
                  setSpModalOpen(false);
                  setSpSheets([]);
                  setPendingPrint(null);
                }}
                className="px-4 py-2 border border-slate-300 text-slate-600 rounded-lg text-sm hover:bg-slate-50 font-bold">
                キャンセル（印刷しない）
              </button>
              <button
                onClick={async () => {
                  setSpModalOpen(false);
                  setSpSkipped(true);
                  const mode = pendingPrint;
                  setSpSheets([]);
                  setPendingPrint(null);
                  if (mode === "preview") await handlePrint();
                  else if (mode === "direct") await handleDirectPrint();
                }}
                className="px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-bold hover:bg-red-700">
                確認した（印刷する）
              </button>
            </div>
          </div>
        </div>
      )}

      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType="setup_print" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}

export default function McPrintPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>
      <McPrintPageInner />
    </Suspense>
  );
}
