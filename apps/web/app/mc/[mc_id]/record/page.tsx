"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McWorkRecord, Machine, UserInfo } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const WORK_TYPES = ["量産", "試作", "変更", "新規登録"];

function calcTimes(startedAt: string, checkedAt: string, finishedAt: string, interruptSetup: number, interruptWork: number) {
  if (!startedAt || !finishedAt) return { setupMin: null, machMin: null };
  const start  = new Date(startedAt).getTime();
  const finish = new Date(finishedAt).getTime();
  if (isNaN(start) || isNaN(finish)) return { setupMin: null, machMin: null };
  if (checkedAt) {
    const check = new Date(checkedAt).getTime();
    if (!isNaN(check)) {
      const setupMin = Math.max(0, Math.round((check - start) / 60000) - interruptSetup);
      const machMin  = Math.max(0, Math.round((finish - check) / 60000) - interruptWork);
      return { setupMin, machMin };
    }
  }
  const total = Math.max(0, Math.round((finish - start) / 60000) - interruptSetup - interruptWork);
  return { setupMin: total, machMin: total };
}

function McRecordPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();
  const searchParams = useSearchParams();
  const editRecordId = searchParams.get("edit") ? parseInt(searchParams.get("edit")!) : null;

  const [detail,   setDetail]   = useState<McDetail | null>(null);
  const [records,  setRecords]  = useState<McWorkRecord[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [users,    setUsers]    = useState<UserInfo[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed, setElapsed]   = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // フォーム
  const [workType,       setWorkType]       = useState("量産");
  const [machineId,      setMachineId]      = useState<string>("");
  const [startedAt,      setStartedAt]      = useState("");
  const [checkedAt,      setCheckedAt]      = useState("");
  const [finishedAt,     setFinishedAt]     = useState("");
  const [interruptSetup, setInterruptSetup] = useState(0);
  const [interruptWork,  setInterruptWork]  = useState(0);
  const [quantity,       setQuantity]       = useState<string>("");
  const [setupWorkCount, setSetupWorkCount] = useState<string>("1");
  const [note,           setNote]           = useState("");
  const [saving,         setSaving]         = useState(false);
  const [saveError,      setSaveError]      = useState<string | null>(null);
  const [toast,          setToast]          = useState<string | null>(null);

  // 自動計算
  const calc = calcTimes(startedAt, checkedAt, finishedAt, interruptSetup, interruptWork);
  const cycleTimeSec = (calc.machMin != null && quantity) ?
    Math.round((calc.machMin * 60) / parseInt(quantity)) : null;

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); }, []);
  const fmtElapsed = (s: number) => `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;
  const fmtMin = (min: number | null) => min != null ? `${Math.floor(min/60)}H ${String(min%60).padStart(2,"0")}M` : "—";

  useEffect(() => {
    mcApi.findOne(mcId).then(r => setDetail((r as any).data ?? r)).catch(() => {});
    mcApi.workRecords(mcId).then(r => setRecords((r as any).data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
    // 今日の日付でデフォルト
    const now = new Date();
    const dateStr = now.toISOString().slice(0,10);
    setStartedAt(`${dateStr}T08:00`);
    setCheckedAt(`${dateStr}T09:30`);
    setFinishedAt(`${dateStr}T17:00`);
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

  const handleSubmit = async () => {
    if (!token) { setSaveError("認証が必要です"); return; }
    setSaving(true); setSaveError(null);
    try {
      await mcApi.createWorkRecord(mcId, {
        work_type:           workType,
        machine_id:          machineId ? parseInt(machineId) : undefined,
        started_at:          startedAt  || undefined,
        checked_at:          checkedAt  || undefined,
        finished_at:         finishedAt || undefined,
        interrupt_setup_min: interruptSetup || undefined,
        interrupt_work_min:  interruptWork  || undefined,
        setup_time_min:      calc.setupMin  ?? undefined,
        machining_time_min:  calc.machMin   ?? undefined,
        cycle_time_sec:      cycleTimeSec   ?? undefined,
        quantity:            quantity ? parseInt(quantity) : undefined,
        setup_work_count:    setupWorkCount ? parseInt(setupWorkCount) : undefined,
        note:                note || undefined,
      }, token);
      showToast("✅ 作業記録を登録しました");
      logout();
      const res = await mcApi.workRecords(mcId);
      setRecords((res as any).data ?? []);
      setNote(""); setQuantity("");
    } catch (e: any) {
      setSaveError(e.message ?? "登録に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const fmtDate = (s: string) => {
    try { return new Date(s).toLocaleString("ja-JP", { month: "2-digit", day: "2-digit" }); }
    catch { return s; }
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
        <span className="text-sm font-medium flex items-center gap-1.5">作業記録</span>
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
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-teal-600 font-bold text-lg">{detail.part.drawingNo}</span>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700 font-mono">
              加工ID: {detail.machiningId}
            </span>
            <StatusBadge status={detail.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {detail.version}</span>
          </div>
          <div className="text-sm text-slate-700 font-medium mb-1">{detail.part.name}</div>
          <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
            <span>MCID: {detail.id}</span>
            <span>加工ID: {detail.machiningId}</span>
            {detail.part.partId && <span>部品ID: {detail.part.partId}</span>}
            {detail.part.clientName && <span>納入先: {detail.part.clientName}</span>}
          </div>
        </div>
      )}

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
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-teal-400 text-teal-400 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          作業記録
        </button>
      </nav>

      <div className="flex flex-col flex-1 overflow-hidden">
        {/* 上: 過去記録 */}
        <div className="h-48 border-b border-slate-200 flex flex-col bg-white overflow-hidden shrink-0">
          <div className="px-4 py-2 border-b border-slate-100 bg-slate-50 flex items-center justify-between shrink-0">
            <span className="text-xs font-bold text-slate-600">過去の作業記録 ({records.length}件)</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {records.length === 0 ? (
              <div className="flex items-center justify-center h-full text-slate-400 text-sm">記録がありません</div>
            ) : records.map((r, i) => (
              <div key={r.id} className={`flex items-center gap-3 px-4 py-2 text-xs border-b border-slate-50 ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                <span className="text-slate-400 w-10">{fmtDate(r.work_date)}</span>
                <span className="font-bold text-slate-600 w-14">{r.operator_name ?? "—"}</span>
                <span className="text-slate-400 w-10">{r.machine_code ?? ""}</span>
                <span className="text-teal-600">{r.work_type ?? ""}</span>
                <span>段取: {fmtMin(r.setup_time_min)}</span>
                <span>加工: {fmtMin(r.machining_time_min)}</span>
                {r.quantity && <span>W:{r.quantity}</span>}
                {r.note && <span className="text-slate-400 truncate max-w-32">{r.note}</span>}
              </div>
            ))}
          </div>
        </div>

        {/* 下: 入力フォーム */}
        <div className="flex-1 overflow-y-auto p-4">
          {!isAuthenticated ? (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-sm w-full text-center">
                <div className="text-4xl mb-4">⏱</div>
                <h2 className="font-bold text-slate-700 mb-2">作業記録の登録</h2>
                <p className="text-slate-400 text-sm mb-6">担当者認証が必要です</p>
                <button onClick={() => setAuthOpen(true)}
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm">
                  この作業を開始する
                </button>
              </div>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto space-y-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
                <h3 className="text-sm font-bold text-slate-700">新規作業記録</h3>

                {saveError && <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">⚠️ {saveError}</div>}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">種別</label>
                    <div className="flex flex-wrap gap-1">
                      {WORK_TYPES.map(t => (
                        <button key={t} onClick={() => setWorkType(t)}
                          className={`px-3 py-1.5 text-xs rounded-lg font-medium border transition-colors ${
                            workType === t ? "bg-teal-600 text-white border-teal-600" : "border-slate-300 text-slate-600 hover:border-teal-400"}`}>
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">機械</label>
                    <select value={machineId} onChange={e => setMachineId(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {machines.filter(m => m.isActive).map(m => (
                        <option key={m.id} value={String(m.id)}>{m.machineCode}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* 時刻入力 → 自動計算 */}
                <div className="bg-teal-50 border border-teal-200 rounded-xl p-4">
                  <p className="text-xs font-bold text-teal-700 mb-3">時刻入力 → 時間自動計算</p>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <label className="text-[10px] text-teal-700 block mb-1">段取開始</label>
                      <input type="datetime-local" value={startedAt} onChange={e => setStartedAt(e.target.value)}
                        className="w-full border border-teal-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                    <div>
                      <label className="text-[10px] text-teal-700 block mb-1">チェック時刻（量産開始）</label>
                      <input type="datetime-local" value={checkedAt} onChange={e => setCheckedAt(e.target.value)}
                        className="w-full border border-teal-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                    <div>
                      <label className="text-[10px] text-teal-700 block mb-1">加工終了</label>
                      <input type="datetime-local" value={finishedAt} onChange={e => setFinishedAt(e.target.value)}
                        className="w-full border border-teal-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="text-[10px] text-teal-700 block mb-1">段取中の中断（分）</label>
                      <input type="number" min={0} value={interruptSetup} onChange={e => setInterruptSetup(Number(e.target.value))}
                        className="w-full border border-teal-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                    <div>
                      <label className="text-[10px] text-teal-700 block mb-1">加工中の中断（分）</label>
                      <input type="number" min={0} value={interruptWork} onChange={e => setInterruptWork(Number(e.target.value))}
                        className="w-full border border-teal-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                  </div>
                  {/* 計算結果 */}
                  <div className="grid grid-cols-3 gap-2 bg-white rounded-lg p-3">
                    <div className="text-center">
                      <p className="text-[10px] text-teal-600 font-bold">段取時間</p>
                      <p className="text-base font-bold text-teal-700">{fmtMin(calc.setupMin)}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-[10px] text-teal-600 font-bold">加工時間</p>
                      <p className="text-base font-bold text-teal-700">{fmtMin(calc.machMin)}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-[10px] text-teal-600 font-bold">総時間</p>
                      <p className="text-base font-bold text-teal-700">{fmtMin(calc.setupMin != null && calc.machMin != null ? calc.setupMin + calc.machMin : null)}</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">ワーク数</label>
                    <input type="number" min={0} value={quantity} onChange={e => setQuantity(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-center focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">段取_ワーク数</label>
                    <input type="number" min={0} value={setupWorkCount} onChange={e => setSetupWorkCount(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-center focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">CT/1P（自動計算）</label>
                    <div className="border border-teal-200 bg-teal-50 rounded-lg px-3 py-2 text-sm text-center text-teal-700 font-bold">
                      {cycleTimeSec ? `${Math.floor(cycleTimeSec/60)}M ${cycleTimeSec%60}S` : "—"}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">備考</label>
                  <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none" />
                </div>

                <div className="flex gap-3 justify-end">
                  <button onClick={() => { logout(); router.push(`/mc/${mcId}`); }}
                    className="px-5 py-2.5 border border-slate-300 text-slate-600 rounded-xl text-sm font-medium hover:bg-slate-50">キャンセル</button>
                  <button onClick={handleSubmit} disabled={saving}
                    className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold rounded-xl text-sm">
                    {saving ? "登録中…" : "✓ 作業完了（登録）"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} sessionType="work_record" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}

export default function McRecordPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>
      <McRecordPageInner />
    </Suspense>
  );
}
