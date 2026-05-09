"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useParams, useRouter } from "next/navigation";
import {
  ncApi, workRecordsApi, machinesApi, usersApi, authApi,
  NcDetail, WorkRecord, Machine, UserInfo, SetupSheetLog,
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
function RecordPageInner() {
  const params    = useParams();
  const router    = useRouter();
  const ncId      = Number(params.nc_id);
  const [searchParams] = useSearchParams ? [useSearchParams()] : [null as any];

  const [nc,       setNc]       = useState<NcDetail | null>(null);
  const [setupSheets, setSetupSheets] = useState<SetupSheetLog[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<SetupSheetLog | null>(null);
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
      const [ncRes, sheetRes, machRes, userRes] = await Promise.all([
        ncApi.findOne(ncId),
        ncApi.setupSheetLogs(ncId),
        machinesApi.list(),
        usersApi.list(),
      ]);
      setNc(ncRes.data);
      setSetupSheets((sheetRes.data as any[]).filter(s => !s.work_collected));
      setMachines(machRes.data.filter((m: Machine) => m.isActive));
      setAllUsers(userRes.data);
      setAuthUsers(userRes.data.filter((u: UserInfo) => u.isActive));
      // 機械初期値
      if (ncRes.data?.machine?.id) setMachineId(ncRes.data.machine.id);
    } catch { showToast("❌ データ取得失敗"); }
    finally { setLoading(false); }
  }, [ncId]);

  useEffect(() => { loadData(); }, [loadData]);

  // ?edit=ID がある場合、データ取得後に編集モードで開く
  useEffect(() => {
    const editId = typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("edit")
      : null;
    if (!editId || loading) return;
    const id = parseInt(editId);
    if (!id) return;
    // work_record を直接APIから取得してフォームにセット
    import("axios").then(({ default: axios }) => {
      axios.get(`/api/nc/${ncId}/work-records/${id}`).then(res => {
        const r = res.data;
        const sm = r.setup_time_min ?? 0;
        setSetupH(Math.floor(sm/60)); setSetupM(sm%60);
        const mm = r.machining_time_min ?? 0;
        setMachH(Math.floor(mm/60)); setMachM(mm%60);
        const cs = r.cycle_time_sec ?? 0;
        setCycleM(Math.floor(cs/60)); setCycleS(cs%60);
        setQuantity(r.quantity ?? "");
        setInterruption(r.interruption_time_min ?? 0);
        setWorkType(r.work_type ?? "量産");
        setNote(r.note ?? "");
        if (r.machine_id) setMachineId(r.machine_id);
        setSetupOps(Array.isArray(r.setup_operator_ids) ? r.setup_operator_ids : []);
        setProdOps(Array.isArray(r.production_operator_ids) ? r.production_operator_ids : []);
        setEditRecordId(id);
        if (!isAuthenticated) setShowAuth(true);
      }).catch(() => {});
    });
  }, [loading, ncId, isAuthenticated]);

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
        // 段取シート回収済みマーク
        if (selectedSheet) {
          const tok = workToken || localStorage.getItem("work_token") || "";
          if (tok) {
            try { await ncApi.collectSetupSheet(ncId, selectedSheet.id, tok); } catch (e) { console.error("collect error", e); }
          }
        }
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
      {/* グローバルヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push(`/nc/${ncId}`)} className="text-slate-400 hover:text-white text-xs transition-colors">← NC詳細</button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">⏱ 作業記録</span>
        <span className="ml-auto">
          {isAuthenticated ? (
            <span className="text-[11px] bg-amber-600 text-white px-3 py-1 rounded font-bold animate-pulse">
              作業中: {selOpName}　{fmtTime(elapsed)}
            </span>
          ) : (
            <span className="text-[11px] text-slate-400 bg-slate-700 px-2 py-1 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報エリア */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-sky-600 font-bold text-lg">{nc.part?.drawingNo}</span>
          <span className="text-[11px] bg-sky-100 text-sky-700 px-2 py-0.5 rounded font-mono font-bold">L{nc.processL}</span>
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
            nc.status === "APPROVED" ? "bg-green-100 text-green-700" :
            nc.status === "PENDING_APPROVAL" ? "bg-yellow-100 text-yellow-700" :
            nc.status === "CHANGING" ? "bg-orange-100 text-orange-700" :
            "bg-slate-100 text-slate-600"
          }`}>{
            nc.status === "APPROVED" ? "承認済" :
            nc.status === "PENDING_APPROVAL" ? "承認待ち" :
            nc.status === "CHANGING" ? "変更中" : "新規"
          }</span>
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {nc.version}</span>
        </div>
        <div className="text-sm text-slate-700 font-medium mb-1">{nc.part?.name}</div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>NC_id: {nc.id}</span>
          <span>部品ID: {nc.part?.partId}</span>
          {nc.part?.clientName && <span>納入先: {nc.part.clientName}</span>}
        </div>
      </div>

      {/* タブナビ */}
      <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
        <button onClick={() => router.push(`/nc/${ncId}`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          NC詳細
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/edit`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          変更・登録
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/print`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          段取シート
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/record`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-sky-400 text-sky-400 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          作業記録
        </button>
      </nav>

      <div className="flex flex-1 min-h-0">
        {/* 左ペイン: 段取シートリスト */}
        <div className="w-[380px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <div>
              <span className="text-sm font-bold text-slate-700">🗒 段取シート一覧</span>
              <span className="ml-2 text-[11px] text-slate-400">未回収: {setupSheets.length}件</span>
            </div>
            <span className="text-[10px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded">印刷日付新しい順</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {setupSheets.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2 py-12">
                <span className="text-3xl">📋</span>
                <p className="text-sm">印刷済み段取シートなし</p>
                <p className="text-xs text-slate-300">段取シート画面から印刷してください</p>
              </div>
            )}
            {setupSheets.map(s => (
              <div key={s.id}
                onClick={() => { setSelectedSheet(s); if (!isAuthenticated) setShowAuth(true); }}
                className={`px-4 py-3 border-b border-slate-100 cursor-pointer transition-colors ${
                  selectedSheet?.id === s.id
                    ? "bg-emerald-50 border-l-4 border-l-emerald-500"
                    : "hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono font-bold text-slate-600">
                    {new Date(s.printed_at).toLocaleDateString("ja-JP", {month:"2-digit",day:"2-digit"})}
                    {" "}
                    {new Date(s.printed_at).toLocaleTimeString("ja-JP", {hour:"2-digit",minute:"2-digit"})}
                  </span>
                  {s.version && (
                    <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono">
                      Ver.{s.version}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500">
                  印刷者: {(s as any).operator_name ?? "—"}
                </div>
                {selectedSheet?.id === s.id && (
                  <div className="mt-1.5 text-[11px] text-emerald-700 font-bold">▶ この段取シートで記録入力中</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 右ペイン: 入力フォーム */}
        <div className="flex-1 overflow-y-auto p-5">
          {!isAuthenticated && (
            <div className="mb-5 p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-emerald-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-emerald-600 mt-0.5">
                  {selectedSheet ? `段取シート（${new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP")}）を選択中` : "左リストから段取シートを選択してください"}
                </div>
              </div>
              <button onClick={() => setShowAuth(true)}
                className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                🔓 作業を開始する
              </button>
            </div>
          )}
          <div className={!isAuthenticated && !editRecordId ? "opacity-40 pointer-events-none select-none" : ""}>
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

export default function RecordPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>
      <RecordPageInner />
    </Suspense>
  );
}
