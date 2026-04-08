"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ncApi, workRecordsApi, machinesApi, usersApi, authApi,
  NcDetail, WorkRecord, Machine, UserInfo,
  CreateWorkRecordBody, UpdateWorkRecordBody,
} from "@/lib/api";

// ─── 時間入力コンポーネント ─────────────────────────────────────
function NumInput({ value, onChange, min=0, max=999, className="" }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; className?: string;
}) {
  return (
    <input type="number" min={min} max={max} value={value}
      onChange={e => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}
      className={`border border-slate-300 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-sky-300 ${className}`}
    />
  );
}

function TimeInput({ h, m, onH, onM }: { h:number; m:number; onH:(v:number)=>void; onM:(v:number)=>void }) {
  return (
    <div className="flex items-center gap-1">
      <NumInput value={h} onChange={onH} /><span className="text-xs text-slate-400">h</span>
      <NumInput value={m} onChange={onM} min={0} max={59} /><span className="text-xs text-slate-400">m</span>
    </div>
  );
}

// ─── 複数選択コンポーネント（Select2スタイル） ─────────────────
function MultiUserSelect({ users, selected, onChange, placeholder }: {
  users: UserInfo[]; selected: number[]; onChange: (ids: number[]) => void; placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggle = (id: number) => {
    onChange(selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id]);
  };

  const selectedUsers = users.filter(u => selected.includes(u.id));

  return (
    <div ref={ref} className="relative">
      <div
        onClick={() => setOpen(o => !o)}
        className="min-h-[38px] w-full border border-slate-300 rounded px-2 py-1 cursor-pointer bg-white flex flex-wrap gap-1 items-center focus:ring-2 focus:ring-sky-300"
      >
        {selectedUsers.length === 0 && (
          <span className="text-slate-400 text-sm">{placeholder}</span>
        )}
        {selectedUsers.map(u => (
          <span key={u.id} className="bg-sky-100 text-sky-800 text-xs font-medium px-2 py-0.5 rounded-full flex items-center gap-1">
            {u.name}
            <button type="button" onClick={e => { e.stopPropagation(); toggle(u.id); }}
              className="text-sky-500 hover:text-sky-700 font-bold leading-none">&times;</button>
          </span>
        ))}
        <span className="ml-auto text-slate-400 text-xs">▼</span>
      </div>
      {open && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {users.filter(u => u.isActive).map(u => (
            <div key={u.id}
              onClick={() => toggle(u.id)}
              className={`px-3 py-2 text-sm cursor-pointer flex items-center gap-2 hover:bg-sky-50 ${selected.includes(u.id) ? "bg-sky-50 font-bold text-sky-700" : "text-slate-700"}`}
            >
              <span className={`w-4 h-4 rounded border flex items-center justify-center text-xs ${selected.includes(u.id) ? "bg-sky-500 border-sky-500 text-white" : "border-slate-300"}`}>
                {selected.includes(u.id) && "✓"}
              </span>
              {u.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── メインページ ──────────────────────────────────────────────
export default function RecordPage() {
  const params    = useParams();
  const router    = useRouter();
  const ncId      = Number(params.nc_id);

  const [nc,       setNc]       = useState<NcDetail | null>(null);
  const [records,  setRecords]  = useState<WorkRecord[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [allUsers, setAllUsers] = useState<UserInfo[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [toast,    setToast]    = useState("");
  const [saving,   setSaving]   = useState(false);

  // 認証
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [workToken,        setWorkToken]       = useState("");
  const [authUsers,        setAuthUsers]       = useState<UserInfo[]>([]);
  const [selOpId,          setSelOpId]         = useState<number | null>(null);
  const [selOpName,        setSelOpName]        = useState("");
  const [password,         setPassword]        = useState("");
  const [authError,        setAuthError]       = useState("");
  const [authLoading,      setAuthLoading]     = useState(false);
  const [showAuth,         setShowAuth]        = useState(false);

  // 編集モード
  const [editRecordId, setEditRecordId] = useState<number | null>(null);

  // フォーム
  const [workType,    setWorkType]    = useState("量産");
  const [machineId,   setMachineId]   = useState<number | null>(null);
  const [setupH,      setSetupH]      = useState(0);
  const [setupM,      setSetupM]      = useState(0);
  const [machH,       setMachH]       = useState(0);
  const [machM,       setMachM]       = useState(0);
  const [cycleM,      setCycleM]      = useState(0);
  const [cycleS,      setCycleS]      = useState(0);
  const [quantity,    setQuantity]    = useState<number|"">("");
  const [interruption,setInterruption]= useState(0);
  const [note,        setNote]        = useState("");
  // 担当者複数選択
  const [setupOps,    setSetupOps]    = useState<number[]>([]);
  const [prodOps,     setProdOps]     = useState<number[]>([]);
  const [timeMode, setTimeMode] = useState<"hm"|"datetime">("hm");
  const [setupStart,  setSetupStart]  = useState("");
  const [setupEnd,    setSetupEnd]    = useState("");
  const [prodStart,   setProdStart]   = useState("");
  const [prodEnd,     setProdEnd]     = useState("");
  const [setupInterruption, setSetupInterruption] = useState(0);

  // タイマー
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 2500); };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [ncRes, recRes, machRes, userRes] = await Promise.all([
        ncApi.findOne(ncId),
        workRecordsApi.list(ncId),
        machinesApi.list(),
        usersApi.list(),
      ]);
      setNc(ncRes.data);
      setRecords(recRes.data);
      setMachines(machRes.data.filter((m: Machine) => m.isActive));
      setAllUsers(userRes.data);
      setAuthUsers(userRes.data.filter((u: UserInfo) => u.isActive));
      // 機械初期値
      if (ncRes.data?.machine?.id) setMachineId(ncRes.data.machine.id);
    } catch { showToast("❌ データ取得失敗"); }
    finally { setLoading(false); }
  }, [ncId]);

  useEffect(() => { loadData(); }, [loadData]);

  // タイマー
  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const fmtTime = (s: number) => {
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
  };

  const fmtMin = (min: number | null) => {
    if (!min) return "—";
    return `${Math.floor(min/60)}h ${min%60}m`;
  };

  const handleAuth = async () => {
    if (!selOpId || !password) { setAuthError("担当者とパスワードを入力してください"); return; }
    setAuthLoading(true); setAuthError("");
    try {
      const res = await authApi.createWorkSession({
        operator_id: selOpId, password, session_type: "work_record", nc_program_id: ncId,
      });
      setWorkToken(res.data.access_token);
      setSelOpName(res.data.operator?.name ?? "");
      setIsAuthenticated(true);
      setShowAuth(false);
      setPassword("");
    } catch { setAuthError("認証に失敗しました。パスワードを確認してください"); }
    finally { setAuthLoading(false); }
  };

  const endSession = async () => {
    if (workToken) { try { await authApi.endWorkSession(workToken); } catch {} }
    setIsAuthenticated(false); setWorkToken(""); setSelOpId(null); setSelOpName("");
  };

  const resetForm = useCallback((ncData?: NcDetail | null) => {
    setEditRecordId(null);
    setWorkType("量産"); setNote("");
    setSetupH(0); setSetupM(0); setMachH(0); setMachM(0);
    setCycleM(0); setCycleS(0); setQuantity(""); setInterruption(0);
    setSetupOps([]); setProdOps([]);
    setTimeMode("hm");
    setSetupStart(""); setSetupEnd(""); setProdStart(""); setProdEnd("");
    setSetupInterruption(0);
    if (ncData?.machine?.id) setMachineId(ncData.machine.id);
    else setMachineId(null);
  }, []);

  const handleEdit = (r: WorkRecord) => {
    if (!isAuthenticated) { setShowAuth(true); return; }
    setEditRecordId(r.id);
    const sm = r.setup_time ?? 0;
    setSetupH(Math.floor(sm/60)); setSetupM(sm%60);
    const mm = r.machining_time ?? 0;
    setMachH(Math.floor(mm/60)); setMachM(mm%60);
    const cs = r.cycle_time_sec ?? 0;
    setCycleM(Math.floor(cs/60)); setCycleS(cs%60);
    setQuantity(r.quantity ?? "");
    setInterruption(r.interruption_time_min ?? 0);
    setWorkType(r.work_type ?? "量産");
    setNote(r.note ?? "");
    setMachineId(machines.find(m => m.machineCode === r.machine_code)?.id ?? null);
    setSetupOps((r.setup_operator_ids as any) ?? []);
    setProdOps((r.production_operator_ids as any) ?? []);
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const base = {
        setup_time_min:         timeMode==="datetime" && setupStart && setupEnd
          ? Math.max(0, Math.round((new Date(setupEnd).getTime()-new Date(setupStart).getTime())/60000) - setupInterruption)
          : (setupH*60+setupM) || undefined,
        interruption_time_min:  timeMode==="datetime" ? (setupInterruption || undefined) : (interruption || undefined),
        machining_time_min:     timeMode==="datetime" && prodStart && prodEnd
          ? Math.max(0, Math.round((new Date(prodEnd).getTime()-new Date(prodStart).getTime())/60000) - (interruption||0))
          : (machH*60+machM) || undefined,
        cycle_time_sec:         (cycleM*60+cycleS) || undefined,
        quantity:               quantity !== "" ? Number(quantity) : undefined,
        work_type:              workType,
        note:                   note || undefined,
        machine_id:             machineId ?? undefined,
        setup_operator_ids:     setupOps.length > 0 ? setupOps : undefined,
        production_operator_ids:prodOps.length  > 0 ? prodOps  : undefined,
      };
      if (editRecordId) {
        await workRecordsApi.update(ncId, editRecordId, base as UpdateWorkRecordBody, workToken);
        showToast("✅ 更新しました");
      } else {
        const res = await workRecordsApi.create(ncId, base as CreateWorkRecordBody, workToken);
        if (!res.data?.id) throw new Error();
        await endSession();
        showToast("✅ 作業記録を登録しました");
        setTimeout(() => router.push(`/nc/${ncId}`), 1200);
        return;
      }
      await loadData();
      resetForm(nc);
    } catch { showToast("❌ 保存に失敗しました"); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-400">読み込み中...</div>;
  if (!nc)     return <div className="min-h-screen flex items-center justify-center text-red-500">データが見つかりません</div>;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* ヘッダー */}
      <header className="bg-slate-900 text-white px-4 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push(`/nc/${ncId}`)} className="text-slate-400 hover:text-white text-sm">← NC詳細</button>
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span className="font-bold text-sm">作業記録</span>
        </div>
        <div className="text-xs text-slate-400">{nc.part?.drawingNo} | {nc.part?.name}</div>
        {isAuthenticated && (
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs bg-amber-500 text-white px-2.5 py-1 rounded-full font-bold animate-pulse">
              ● {selOpName} 作業中 {fmtTime(elapsed)}
            </span>
            <button onClick={() => endSession()} className="text-xs text-slate-400 hover:text-white">セッション終了</button>
          </div>
        )}
        {!isAuthenticated && (
          <button onClick={() => setShowAuth(true)} className="ml-auto text-xs bg-sky-600 hover:bg-sky-500 text-white px-3 py-1.5 rounded">
            ⏱ 作業記録を入力
          </button>
        )}
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 左ペイン: 過去記録一覧 */}
        <div className="w-[420px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-600">過去の作業記録（{records.length}件）</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {records.length === 0 && (
              <p className="text-center py-12 text-slate-400 text-sm">記録がありません</p>
            )}
            {records.map(r => (
              <div key={r.id}
                className={`px-4 py-3 border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors ${editRecordId === r.id ? "bg-sky-50 border-l-4 border-l-sky-500" : ""}`}
                onClick={() => handleEdit(r)}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-500">{r.work_date?.slice(0,10)}</span>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                    r.work_type === "量産" ? "bg-green-100 text-green-700" :
                    r.work_type === "試作" ? "bg-purple-100 text-purple-700" :
                    r.work_type === "変更" ? "bg-orange-100 text-orange-700" :
                    "bg-slate-100 text-slate-600"
                  }`}>{r.work_type ?? "量産"}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-600">
                  <span>担当: {r.operator_name ?? "—"}</span>
                  <span>機械: {r.machine_code ?? "—"}</span>
                  {r.quantity && <span>{r.quantity}個</span>}
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                  <span>段取: {fmtMin(r.setup_time)}</span>
                  <span>加工: {fmtMin(r.machining_time)}</span>
                  {r.interruption_time_min ? <span>中断: {r.interruption_time_min}m</span> : null}
                </div>
                {(r.setup_operator_ids as any)?.length > 0 && (
                  <div className="text-xs text-slate-400 mt-0.5">
                    段取担当: {((r.setup_operator_ids as any) as number[]).map(id =>
                      allUsers.find(u => u.id === id)?.name ?? `id:${id}`).join(", ")}
                  </div>
                )}
                {(r.production_operator_ids as any)?.length > 0 && (
                  <div className="text-xs text-slate-400 mt-0.5">
                    量産担当: {((r.production_operator_ids as any) as number[]).map(id =>
                      allUsers.find(u => u.id === id)?.name ?? `id:${id}`).join(", ")}
                  </div>
                )}
                {r.note && <div className="text-xs text-slate-400 mt-0.5 truncate">備考: {r.note}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* 右ペイン: 入力フォーム */}
        <div className={`flex-1 overflow-y-auto p-5 ${!isAuthenticated && !editRecordId ? "opacity-50 pointer-events-none select-none" : ""}`}>
          {/* モードバー */}
          <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${
            editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-sky-50 border border-sky-200 text-sky-700"
          }`}>
            <span>{editRecordId ? `✏️ 編集モード — 記録ID: ${editRecordId}` : "＋ 新規入力モード"}</span>
            {editRecordId && (
              <button onClick={() => resetForm(nc)} className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50">
                ＋ 新規に戻す
              </button>
            )}
          </div>

          <div className="space-y-4 max-w-2xl">
            {/* 種別 + 機械 */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-2">種別 *</label>
                <div className="flex gap-2 flex-wrap">
                  {["量産","試作"].map(t => (
                    <button key={t} type="button" onClick={() => setWorkType(t)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-colors ${workType === t ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-2">使用機械</label>
                <select value={machineId ?? ""}
                  onChange={e => setMachineId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300 bg-white">
                  <option value="">— 選択 —</option>
                  {machines.map(m => <option key={m.id} value={m.id}>{m.id} : {m.machineName}</option>)}
                </select>
              </div>
            </div>

            {/* 段取セクション */}
            <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-blue-200 pb-2">
                <span className="text-sm font-bold text-blue-700">🔧 段取</span>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500">入力方法:</span>
                  <button type="button" onClick={() => setTimeMode("hm")}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="hm" ? "bg-blue-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>
                    h/m入力
                  </button>
                  <button type="button" onClick={() => setTimeMode("datetime")}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="datetime" ? "bg-blue-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>
                    開始/終了日時
                  </button>
                </div>
              </div>
              {timeMode === "hm" ? (
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">段取時間</label>
                    <TimeInput h={setupH} m={setupM} onH={setSetupH} onM={setSetupM} />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">中断時間</label>
                    <div className="flex items-center gap-1">
                      <NumInput value={setupInterruption} onChange={setSetupInterruption} className="w-16" />
                      <span className="text-xs text-slate-400">分</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">段取担当者（複数可）</label>
                    <MultiUserSelect users={allUsers} selected={setupOps} onChange={setSetupOps} placeholder="担当者を選択..." />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">段取開始日時</label>
                      <input type="datetime-local" value={setupStart} onChange={e => setSetupStart(e.target.value)}
                        className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">段取終了日時</label>
                      <input type="datetime-local" value={setupEnd} onChange={e => { setSetupEnd(e.target.value); setProdStart(e.target.value); }}
                        className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    </div>
                  </div>
                  {setupStart && setupEnd && (() => {
                    const mins = Math.round((new Date(setupEnd).getTime() - new Date(setupStart).getTime()) / 60000);
                    return mins > 0 ? <p className="text-xs text-blue-600 font-bold">→ 段取時間: {Math.floor(mins/60)}h {mins%60}m（{mins}分）</p> : null;
                  })()}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">中断時間（分）</label>
                      <div className="flex items-center gap-1">
                        <NumInput value={setupInterruption} onChange={setSetupInterruption} className="w-16" />
                        <span className="text-xs text-slate-400">分</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">段取担当者（複数可）</label>
                      <MultiUserSelect users={allUsers} selected={setupOps} onChange={setSetupOps} placeholder="担当者を選択..." />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 量産セクション */}
            <div className="bg-green-50 rounded-xl border border-green-200 p-4 space-y-3">
              <div className="text-sm font-bold text-green-700 border-b border-green-200 pb-2">⚙️ 量産</div>
              {timeMode === "hm" ? (
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">加工時間</label>
                    <TimeInput h={machH} m={machM} onH={setMachH} onM={setMachM} />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">中断時間</label>
                    <div className="flex items-center gap-1">
                      <NumInput value={interruption} onChange={setInterruption} className="w-16" />
                      <span className="text-xs text-slate-400">分</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">量産担当者（複数可）</label>
                    <MultiUserSelect users={allUsers} selected={prodOps} onChange={setProdOps} placeholder="担当者を選択..." />
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">量産開始日時</label>
                      <input type="datetime-local" value={prodStart} onChange={e => { setProdStart(e.target.value); setSetupEnd(e.target.value); }}
                        className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">量産終了日時</label>
                      <input type="datetime-local" value={prodEnd} onChange={e => setProdEnd(e.target.value)}
                        className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    </div>
                  </div>
                  {prodStart && prodEnd && (() => {
                    const mins = Math.round((new Date(prodEnd).getTime() - new Date(prodStart).getTime()) / 60000);
                    return mins > 0 ? <p className="text-xs text-green-600 font-bold">→ 量産時間: {Math.floor(mins/60)}h {mins%60}m（{mins}分）</p> : null;
                  })()}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">中断時間（分）</label>
                      <div className="flex items-center gap-1">
                        <NumInput value={interruption} onChange={setInterruption} className="w-16" />
                        <span className="text-xs text-slate-400">分</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">量産担当者（複数可）</label>
                      <MultiUserSelect users={allUsers} selected={prodOps} onChange={setProdOps} placeholder="担当者を選択..." />
                    </div>
                  </div>
                </div>
              )}
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">加工個数</label>
                <div className="flex items-center gap-1">
                  <input type="number" min={0} value={quantity}
                    onChange={e => setQuantity(e.target.value === "" ? "" : Number(e.target.value))}
                    className="border border-slate-300 rounded px-2 py-1.5 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                  <span className="text-xs text-slate-400">個</span>
                </div>
              </div>
            </div>

            {/* 備考 */}
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <label className="text-xs font-bold text-slate-500 block mb-2">備考</label>
              <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={1000} rows={3}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300 resize-none"
                placeholder="問題点・注意事項・特記事項" />
              <div className="text-right text-xs text-slate-400 mt-1">{note.length} / 1000</div>
            </div>

            {/* ボタン */}
            <div className="flex gap-3">
              <button onClick={handleSave} disabled={saving}
                className="flex-1 py-3 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white font-bold text-sm transition-colors">
                {saving ? "保存中..." : editRecordId ? "✓ 更新（保存）" : "✓ 作業完了（登録）"}
              </button>
              <button onClick={() => { resetForm(nc); if (!editRecordId) endSession(); router.push(`/nc/${ncId}`); }}
                className="px-6 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
                ✕ キャンセル
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 認証モーダル */}
      {showAuth && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden">
            <div className="bg-slate-800 px-5 py-4">
              <h2 className="text-white font-bold">⏱ 作業記録 — 担当者認証</h2>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-2">担当者を選択</label>
                <div className="grid grid-cols-3 gap-2 max-h-40 overflow-y-auto">
                  {authUsers.map(u => (
                    <button key={u.id} type="button" onClick={() => { setSelOpId(u.id); setAuthError(""); }}
                      className={`py-2 px-1 rounded-lg text-xs font-bold border transition-colors ${selOpId === u.id ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-700 border-slate-200 hover:border-sky-400"}`}>
                      {u.name}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">パスワード</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleAuth()}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              {authError && <p className="text-red-600 text-sm bg-red-50 rounded px-3 py-2">{authError}</p>}
              <div className="flex gap-3">
                <button onClick={() => { setShowAuth(false); setPassword(""); setAuthError(""); }}
                  className="flex-1 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium">キャンセル</button>
                <button onClick={handleAuth} disabled={authLoading || !selOpId || !password}
                  className="flex-1 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold disabled:opacity-40">
                  {authLoading ? "認証中..." : "確認して開始"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">
          {toast}
        </div>
      )}
    </div>
  );
}
