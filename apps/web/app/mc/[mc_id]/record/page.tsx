"use client";
import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

// ── 共通コンポーネント ──────────────────────────────────────────
function NumInput({ value, onChange, min=0, max=999, className="" }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; className?: string;
}) {
  return (
    <input type="number" min={min} max={max} value={value}
      onChange={e => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}
      className={`border border-slate-200 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-teal-400 ${className}`}
    />
  );
}

function TimeInput({ h, m, onH, onM }: { h:number; m:number; onH:(v:number)=>void; onM:(v:number)=>void }) {
  return (
    <div className="flex items-center gap-1">
      <NumInput value={h} onChange={onH} /><span className="text-xs text-slate-500">h</span>
      <NumInput value={m} onChange={onM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
    </div>
  );
}

// 複数選択（段取担当・量産作業者）
function MultiUserSelect({ users, selected, onChange, placeholder }: {
  users: UserInfo[]; selected: number[]; onChange: (ids: number[]) => void; placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const toggle = (id: number) => onChange(selected.includes(id) ? selected.filter(x=>x!==id) : [...selected, id]);
  const names = selected.map(id => users.find(u=>u.id===id)?.name ?? "").filter(Boolean).join(" & ");
  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(v=>!v)}
        className="w-full text-left border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white hover:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-400 min-h-[38px]">
        {names || <span className="text-slate-400">{placeholder}</span>}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-52 overflow-y-auto">
          {users.filter(u=>u.isActive!==false).map(u => (
            <label key={u.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-teal-50 cursor-pointer text-sm">
              <input type="checkbox" checked={selected.includes(u.id)} onChange={() => toggle(u.id)} className="accent-teal-600" />
              {u.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// 単一選択（チェック担当・プログラム担当）
function SingleUserSelect({ users, selected, onChange, placeholder }: {
  users: UserInfo[]; selected: number | null; onChange: (id: number | null) => void; placeholder?: string;
}) {
  return (
    <select value={selected ?? ""} onChange={e => onChange(e.target.value ? parseInt(e.target.value) : null)}
      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
      <option value="">{placeholder ?? "— 選択 —"}</option>
      {users.filter(u=>u.isActive!==false).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
    </select>
  );
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" }); } catch { return s; }
}
function fmtMin(min: number | null) {
  if (min == null || min < 0) return "—";
  return `${Math.floor(min / 60)}H ${String(min % 60).padStart(2,"0")}M`;
}
function fmtSec(sec: number | null) {
  if (sec == null || sec < 0) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  if (h > 0) return `${h}H ${m}M ${s}S`;
  return `${m}M ${s}S`;
}
function fmtNow() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2,"0");
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function toLocalInput(dt: string | null): string {
  if (!dt) return "";
  try {
    const d = new Date(dt);
    const p = (n: number) => String(n).padStart(2,"0");
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
  } catch { return ""; }
}
function fmtElapsed(s: number) { return `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`; }

function McRecordPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId = parseInt(mc_id);
  const router = useRouter();
  const searchParams = useSearchParams();

  // sbMode
  const [sbMode, setSbMode] = React.useState(false);
  const [sbSheetLogId, setSbSheetLogId] = React.useState<number>(0);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const v = sessionStorage.getItem("sb_next_record");
    if (v && parseInt(v) === mcId) {
      setSbMode(true);
      const lid = sessionStorage.getItem("sb_sheet_log_id");
      if (lid) setSbSheetLogId(parseInt(lid));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const [detail, setDetail] = useState<McDetail | null>(null);
  const [setupSheets, setSetupSheets] = useState<McSetupSheetLog[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<McSetupSheetLog | null>(null);
  const [records, setRecords] = useState<McWorkRecord[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [editRecordId, setEditRecordId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // ── 入力mode ──────────────────────────────────
  const [timeMode, setTimeMode] = useState<"hm" | "datetime">("datetime");

  // ── フォーム state ────────────────────────────
  const [machineId, setMachineId] = useState<string>("");
  const [cycleH, setCycleH] = useState(0);
  const [cycleM, setCycleM] = useState(0);
  const [cycleS, setCycleS] = useState(0);
  const [cyclePcs, setCyclePcs] = useState("");

  // 段取グループ
  const [setupOps, setSetupOps] = useState<number[]>([]);
  const [startedAt, setStartedAt] = useState(""); // 段取開始
  const [checkedAt, setCheckedAt] = useState(""); // 段取終了(ﾁｪｯｸTime)
  const [checkMan, setCheckMan] = useState<number | null>(null); // ﾁｪｯｸMan
  const [dStopH, setDStopH] = useState(0);
  const [dStopM, setDStopM] = useState(0);
  const [setupQty, setSetupQty] = useState("");
  // h/m直接入力用
  const [setupH, setSetupH] = useState(0);
  const [setupMm, setSetupMm] = useState(0);
  const [setupInterruption, setSetupInterruption] = useState(0);

  // 量産グループ
  const [prodOps, setProdOps] = useState<number[]>([]);
  const [finishedAt, setFinishedAt] = useState(""); // 加工終了
  const [yStopH, setYStopH] = useState(0);
  const [yStopM, setYStopM] = useState(0);
  const [quantity, setQuantity] = useState("");
  // h/m直接入力用
  const [machH, setMachH] = useState(0);
  const [machMm, setMachMm] = useState(0);
  const [machInterruption, setMachInterruption] = useState(0);

  // プログラム
  const [prgMan, setPrgMan] = useState<number | null>(null);
  const [prgTimeH, setPrgTimeH] = useState(0);
  const [prgTimeM, setPrgTimeM] = useState(0);
  const [prgPlas, setPrgPlas] = useState("");

  const [note, setNote] = useState("");

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  useEffect(() => {
    mcApi.findOne(mcId).then(r => setDetail((r as any).data ?? (r as any))).catch(() => {});
    mcApi.setupSheetLogs(mcId).then(r => {
      const sheets = ((r as any).data ?? []).filter((s: McSetupSheetLog) => !s.work_collected);
      setSetupSheets(sheets);
      if (sheets.length > 0) setSelectedSheet(sheets[0]);
    }).catch(() => {});
    mcApi.workRecords(mcId).then(r => setRecords((r as any).data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
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

  // 機械選択時にサイクルタイム自動セット
  useEffect(() => {
    if (!detail || !machineId) return;
    const sel = machines.find(m => String(m.id) === machineId);
    if (sel && detail.machine && sel.machineCode === detail.machine.machineCode) {
      const sec = detail.cycleTimeSec ?? 0;
      if (sec) {
        setCycleH(Math.floor(sec / 3600));
        setCycleM(Math.floor((sec % 3600) / 60));
        setCycleS(sec % 60);
        setCyclePcs(String(detail.machiningQty ?? "1"));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machineId]);

  const resetForm = () => {
    setEditRecordId(null);
    setMachineId(""); setCycleH(0); setCycleM(0); setCycleS(0); setCyclePcs("");
    setSetupOps([]); setStartedAt(""); setCheckedAt(""); setCheckMan(null);
    setDStopH(0); setDStopM(0); setSetupQty("");
    setSetupH(0); setSetupMm(0); setSetupInterruption(0);
    setProdOps([]); setFinishedAt("");
    setYStopH(0); setYStopM(0); setQuantity("");
    setMachH(0); setMachMm(0); setMachInterruption(0);
    setPrgMan(null); setPrgTimeH(0); setPrgTimeM(0); setPrgPlas("");
    setNote(""); setSaveError(null);
  };

  const loadRecord = (r: McWorkRecord) => {
    setEditRecordId(r.id);
    setMachineId("");
    const cSec = r.cycle_time_sec ?? 0;
    setCycleH(Math.floor(cSec / 3600)); setCycleM(Math.floor((cSec % 3600) / 60)); setCycleS(cSec % 60);
    setCyclePcs("");
    setSetupOps((r.setup_operator_ids ?? []) as number[]);
    setStartedAt(toLocalInput(r.started_at));
    setCheckedAt(toLocalInput(r.checked_at));
    setCheckMan(null);
    const dstop = r.interrupt_setup_min ?? 0;
    setDStopH(Math.floor(dstop / 60)); setDStopM(dstop % 60);
    setSetupQty(r.setup_work_count ? String(r.setup_work_count) : "");
    setSetupH(0); setSetupMm(0); setSetupInterruption(0);
    setProdOps((r.production_operator_ids ?? []) as number[]);
    setFinishedAt(toLocalInput(r.finished_at));
    const ystop = r.interrupt_work_min ?? 0;
    setYStopH(Math.floor(ystop / 60)); setYStopM(ystop % 60);
    setQuantity(r.quantity ? String(r.quantity) : "");
    setMachH(0); setMachMm(0); setMachInterruption(0);
    setPrgMan(null);
    const pt = (r as any).prg_time_min ?? 0;
    setPrgTimeH(Math.floor(pt / 60)); setPrgTimeM(pt % 60);
    setPrgPlas((r as any).prg_plas ?? "");
    setNote(r.note ?? "");
    // 日時入力データがあればdatetime modeに切り替え
    if (r.started_at || r.finished_at) setTimeMode("datetime"); else setTimeMode("hm");
  };

  // ── VBA W_TIME準拠の時間自動計算 ──────────────────────────────
  const calcTimes = useCallback(() => {
    // 共通: サイクルタイム/1P（常に計算可能）
    const cycSec2 = cycleH * 3600 + cycleM * 60 + cycleS;
    const cycPcs2 = parseInt(cyclePcs)||0;
    const cyclePerPSec = cycSec2 > 0 && cycPcs2 > 0 ? cycSec2 / cycPcs2 : null;

    const qtyN     = parseInt(quantity)||0;
    const setupQtyN = parseInt(setupQty)||0;
    const totalQty  = qtyN + setupQtyN;
    // 加工時間/1P の分母: ワーク数 - 段取良品数 (同じ場合はワーク数)
    const machQtyBase = qtyN > 0 && qtyN !== setupQtyN ? Math.max(1, qtyN - setupQtyN) : Math.max(1, totalQty);

    if (timeMode === "hm") {
      const setupMin = setupH * 60 + setupMm;
      const machMin  = machH * 60 + machMm;
      const totalMin = setupMin + machMin;
      // h/m入力では setupMin/machMin が直接値なので必ず表示
      return {
        setupMin,
        machMin,
        totalMin,
        cyclePerPSec,
        machPerPMin:  machMin > 0 && qtyN > 0 ? Math.round(machMin / machQtyBase * 10) / 10 : null,
        totalPerPMin: totalMin > 0 && totalQty > 0 ? Math.round(totalMin / totalQty * 10) / 10 : null,
      };
    }

    // datetime mode — VBA W_TIME ロジック準拠
    // startedAt か finishedAt どちらかあれば計算を試みる
    const dStopMin = dStopH * 60 + dStopM;
    const yStopMin = yStopH * 60 + yStopM;

    let setupMin: number | null = null;
    let machMin:  number | null = null;
    let totalMin: number | null = null;

    if (startedAt && finishedAt) {
      const sv = new Date(startedAt).getTime();
      const fv = new Date(finishedAt).getTime();
      if (!isNaN(sv) && !isNaN(fv)) {
        totalMin = Math.max(0, Math.round((fv - sv) / 60000) - dStopMin - yStopMin);
      }
    }
    if (startedAt && checkedAt) {
      const sv = new Date(startedAt).getTime();
      const cv = new Date(checkedAt).getTime();
      if (!isNaN(sv) && !isNaN(cv)) {
        setupMin = Math.max(0, Math.round((cv - sv) / 60000) - dStopMin);
      }
    }
    if (checkedAt && finishedAt) {
      const cv = new Date(checkedAt).getTime();
      const fv = new Date(finishedAt).getTime();
      if (!isNaN(cv) && !isNaN(fv)) {
        machMin = Math.max(0, Math.round((fv - cv) / 60000) - yStopMin);
      }
    }
    // 何も計算できていない場合はnull返す
    if (setupMin === null && machMin === null && totalMin === null && cyclePerPSec === null) return null;

    return {
      setupMin,
      machMin,
      totalMin,
      cyclePerPSec,
      machPerPMin:  machMin != null && machMin > 0 && qtyN > 0 ? Math.round(machMin / machQtyBase * 10) / 10 : null,
      totalPerPMin: totalMin != null && totalMin > 0 && totalQty > 0 ? Math.round(totalMin / totalQty * 10) / 10 : null,
    };
  }, [timeMode, setupH, setupMm, machH, machMm, startedAt, checkedAt, finishedAt,
      dStopH, dStopM, yStopH, yStopM, quantity, setupQty, cycleH, cycleM, cycleS, cyclePcs]);

  const times = calcTimes();

  const handleSubmit = async () => {
    console.log("[STEP2] handleSubmit sbMode=", sbMode, "token=", token ? "あり" : "なし", "isAuthenticated=", isAuthenticated);
    if (!token) { setSaveError("認証セッションが切れています。再認証してください。"); setAuthOpen(true); return; }
    setSaving(true); setSaveError(null);
    try {
      const cycSec = cycleH * 3600 + cycleM * 60 + cycleS;
      const body: CreateMcWorkRecordBody = {
        setup_time_min:      times?.setupMin ?? undefined,
        machining_time_min:  times?.machMin  ?? undefined,
        cycle_time_sec:      cycSec || undefined,
        quantity:            quantity ? parseInt(quantity) : undefined,
        setup_work_count:    setupQty ? parseInt(setupQty) : undefined,
        started_at:          startedAt ? new Date(startedAt).toISOString() : undefined,
        checked_at:          checkedAt ? new Date(checkedAt).toISOString() : undefined,
        finished_at:         finishedAt ? new Date(finishedAt).toISOString() : undefined,
        interrupt_setup_min: (dStopH * 60 + dStopM) || undefined,
        interrupt_work_min:  (yStopH * 60 + yStopM) || undefined,
        setup_operator_ids:  setupOps.length ? setupOps : undefined,
        production_operator_ids: prodOps.length ? prodOps : undefined,
        prg_man:             prgMan ? (users.find(u=>u.id===prgMan)?.name ?? undefined) : undefined,
        prg_time_min:        (prgTimeH * 60 + prgTimeM) || undefined,
        prg_plas:            prgPlas || undefined,
        note:                note || undefined,
        machine_id:          machineId ? parseInt(machineId) : undefined,
      };
      await mcApi.createWorkRecord(mcId, body, token);
      const r = await mcApi.workRecords(mcId);
      setRecords((r as any).data ?? []);
      resetForm();
      showToast("✅ 作業記録を登録しました");
      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          const logId = sbSheetLogId || parseInt(sessionStorage.getItem("sb_sheet_log_id") ?? "0");
          if (logId && token) {
            try { await mcApi.collectSetupSheet(mcId, logId, token); showToast("✅ 段取シートバック完了 — 回収済みに更新しました"); }
            catch { showToast("⚠️ 作業記録登録済み（回収済み更新に失敗）"); }
          }
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          setTimeout(() => router.push("/"), 1500);
        }
      }
    } catch (e: any) {
      const msg = e?.message ?? "登録に失敗しました";
      setSaveError(msg);
      console.error("[STEP2] submit error:", e);
    } finally { setSaving(false); }
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        {!sbMode && (
          <>
            <button onClick={() => router.push(`/mc/${mcId}`)} className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
              <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg></span>MC詳細
            </button>
            <span className="text-slate-600">|</span>
            <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>ダッシュボードへ
            </button>
          </>
        )}
        {sbMode && (
          <span className="flex items-center gap-2 bg-teal-700 border border-teal-500 rounded-lg px-3 py-1">
            <span className="bg-teal-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span className="text-xs font-bold text-teal-100">段取シートバック — STEP2: 作業記録入力</span>
            <span className="text-teal-400 text-xs">（登録で回収済みになります）</span>
          </span>
        )}
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">作業記録</span>
        <span className="ml-auto">
          {isAuthenticated && operator ? (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          ) : (
            <span className="text-[11px] text-slate-400">未認証</span>
          )}
        </span>
      </header>

      {/* 部品情報バー */}
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-2 flex items-center gap-4 shrink-0 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 text-sm">{detail.part?.drawingNo ?? "—"}</span>
            <span className="text-slate-400">/</span>
            <span className="text-sm text-slate-600">{detail.part?.name ?? "—"}</span>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            <span>MCID: <span className="text-slate-700">{detail.legacyMcid ?? detail.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{detail.machiningId}</span></span>
            <span className="text-slate-400">|</span>
            <span>Ver: <span className="text-slate-700">{detail.version}</span></span>
          </div>
        </div>
      )}

      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>MC詳細
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/edit`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/></svg>変更・登録
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* メイン */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左ペイン: 段取シート一覧 */}
        <div className="w-52 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="px-3 py-2 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">段取シート一覧</p>
          </div>
          {setupSheets.length === 0 ? (
            <div className="px-3 py-4 text-xs text-slate-400">未回収なし</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {setupSheets.map(s => (
                <button key={s.id} onClick={() => setSelectedSheet(s)}
                  className={`w-full text-left px-3 py-2 text-xs transition-colors ${selectedSheet?.id===s.id ? "bg-teal-50 border-l-2 border-teal-500" : "hover:bg-slate-50"}`}>
                  <div className="font-bold text-slate-700">{fmtDate(s.printed_at)}</div>
                  <div className="text-slate-400">Ver{s.version ?? "—"} {s.operator_name ?? ""}</div>
                </button>
              ))}
            </div>
          )}
          {/* 過去記録 */}
          <div className="px-3 py-2 border-t border-b border-slate-100 mt-2">
            <p className="text-[10px] font-bold text-slate-400 uppercase">過去記録</p>
          </div>
          {records.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-400">なし</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {records.map(r => (
                <button key={r.id} onClick={() => loadRecord(r)}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-amber-50 transition-colors ${editRecordId===r.id ? "bg-amber-50 border-l-2 border-amber-400" : ""}`}>
                  <div className="font-bold text-slate-700">{fmtDate(r.work_date)}</div>
                  <div className="text-slate-400">{r.operator_name ?? "—"} / {r.machine_code ?? "—"}</div>
                  <div className="text-slate-400">{fmtMin(r.setup_time_min)} / {fmtMin(r.machining_time_min)}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 右ペイン: 入力フォーム */}
        <div className="flex-1 overflow-y-auto">
          {!isAuthenticated && !sbMode && (
            <div className="m-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-teal-600 mt-0.5">担当者認証が必要です</div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                この作業を開始する
              </button>
            </div>
          )}

          <div className={!isAuthenticated && !sbMode ? "opacity-40 pointer-events-none select-none px-5 pb-5" : "px-5 pb-5 pt-4"}>
            {/* Ver・登録日・回収日時・オペレータ（表示専用）*/}
            {detail && (
              <div className="bg-slate-100 rounded-xl border border-slate-200 p-3 mb-4">
                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block mb-0.5">Ver</span>
                    <span className="font-bold text-slate-700">{detail.version}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">登録・出力（段取シート）</span>
                    <span className="font-bold text-slate-700">{selectedSheet ? new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP") : "—"}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">回収日時</span>
                    <span className="font-bold text-slate-700">{fmtNow()}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">オペレータ</span>
                    <span className="font-bold text-teal-700">{operator?.name ?? "—"}</span>
                  </div>
                </div>
              </div>
            )}

            {/* モードバー */}
            <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${
              editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-teal-50 border border-teal-200 text-teal-700"
            }`}>
              <span>{editRecordId ? "✏️ 編集モード" : "＋ 新規入力モード"}</span>
              <div className="flex items-center gap-3">
                {/* 入力方法切り替え */}
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-slate-500 mr-1">入力方法:</span>
                  <button onClick={() => setTimeMode("datetime")}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="datetime" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>
                    開始/終了日時
                  </button>
                  <button onClick={() => setTimeMode("hm")}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="hm" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>
                    h/m入力
                  </button>
                </div>
                {editRecordId && (
                  <button onClick={resetForm} className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50">
                    ＋ 新規に戻す
                  </button>
                )}
              </div>
            </div>

            <div className="space-y-4 max-w-3xl">
              {/* 機械 + サイクルタイム */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">今回使用機械</label>
                    <select value={machineId} onChange={e => setMachineId(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
                      <option value="">— 選択 —</option>
                      {machines.filter(m => m.isActive).map(m => (
                        <option key={m.id} value={m.id}>{m.machineCode}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">サイクルタイム / 1P</label>
                    <div className="flex items-center gap-1 flex-wrap">
                      <NumInput value={cycleH} onChange={setCycleH} /><span className="text-xs text-slate-500">H</span>
                      <NumInput value={cycleM} onChange={setCycleM} min={0} max={59} /><span className="text-xs text-slate-500">M</span>
                      <NumInput value={cycleS} onChange={setCycleS} min={0} max={59} /><span className="text-xs text-slate-500">S</span>
                      <span className="text-xs text-slate-500 ml-2">個/1サイクル:</span>
                      <input type="number" min="1" value={cyclePcs} onChange={e => setCyclePcs(e.target.value)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                    </div>
                  </div>
                </div>
              </div>

              {/* 段取グループ */}
              <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-blue-700 border-b border-blue-200 pb-2">🔧 段取</h3>
                {timeMode === "hm" ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">段取時間</label>
                      <TimeInput h={setupH} m={setupMm} onH={setSetupH} onM={setSetupMm} />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">中断時間</label>
                      <div className="flex items-center gap-1">
                        <NumInput value={setupInterruption} onChange={setSetupInterruption} /><span className="text-xs text-slate-500">m</span>
                      </div>
                    </div>
                    <div />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>
                        <input type="datetime-local" value={startedAt} onChange={e => setStartedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取終了（ﾁｪｯｸTime）</label>
                        <input type="datetime-local" value={checkedAt} onChange={e => setCheckedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                      </div>
                    </div>
                    {startedAt && checkedAt && (() => {
                      const mins = Math.max(0, Math.round((new Date(checkedAt).getTime()-new Date(startedAt).getTime())/60000) - (dStopH*60+dStopM));
                      return mins > 0 ? <p className="text-xs text-blue-600 font-bold">→ 段取時間: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                    })()}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取時の中断</label>
                        <div className="flex items-center gap-1">
                          <NumInput value={dStopH} onChange={setDStopH} /><span className="text-xs text-slate-500">h</span>
                          <NumInput value={dStopM} onChange={setDStopM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                        </div>
                      </div>
                      <div />
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取担当者（複数可）</label>
                    <MultiUserSelect users={users} selected={setupOps} onChange={setSetupOps} placeholder="担当者を選択..." />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">チェック担当（ﾁｪｯｸMan）</label>
                    <SingleUserSelect users={users} selected={checkMan} onChange={setCheckMan} placeholder="— 選択 —" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取良品数</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={setupQty} onChange={e => setSetupQty(e.target.value)}
                        className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                      <span className="text-xs text-slate-500">個</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 量産グループ */}
              <div className="bg-green-50 rounded-xl border border-green-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-green-700 border-b border-green-200 pb-2">⚙️ 量産</h3>
                {timeMode === "hm" ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">加工時間</label>
                      <TimeInput h={machH} m={machMm} onH={setMachH} onM={setMachMm} />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">中断時間</label>
                      <div className="flex items-center gap-1">
                        <NumInput value={machInterruption} onChange={setMachInterruption} /><span className="text-xs text-slate-500">m</span>
                      </div>
                    </div>
                    <div />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">加工終了</label>
                        <input type="datetime-local" value={finishedAt} onChange={e => setFinishedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                      </div>
                      <div />
                    </div>
                    {checkedAt && finishedAt && (() => {
                      const mins = Math.max(0, Math.round((new Date(finishedAt).getTime()-new Date(checkedAt).getTime())/60000) - (yStopH*60+yStopM));
                      return mins > 0 ? <p className="text-xs text-green-600 font-bold">→ 加工時間: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                    })()}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">量産時の中断</label>
                        <div className="flex items-center gap-1">
                          <NumInput value={yStopH} onChange={setYStopH} /><span className="text-xs text-slate-500">h</span>
                          <NumInput value={yStopM} onChange={setYStopM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                        </div>
                      </div>
                      <div />
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">量産作業者（複数可）</label>
                    <MultiUserSelect users={users} selected={prodOps} onChange={setProdOps} placeholder="作業者を選択..." />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">全良品数（ワーク数）</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={quantity} onChange={e => setQuantity(e.target.value)}
                        className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                      <span className="text-xs text-slate-500">個</span>
                    </div>
                  </div>
                  <div />
                </div>
              </div>

              {/* プログラム */}
              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-purple-700 border-b border-purple-200 pb-2">💾 プログラム</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">プログラム担当</label>
                    <SingleUserSelect users={users} selected={prgMan} onChange={setPrgMan} placeholder="— 選択 —" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">PrgTime</label>
                    <div className="flex items-center gap-1">
                      <NumInput value={prgTimeH} onChange={setPrgTimeH} /><span className="text-xs text-slate-500">h</span>
                      <NumInput value={prgTimeM} onChange={setPrgTimeM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">PrgPlas (ePL)</label>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setPrgPlas("+")}
                        className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "+" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:border-teal-400"}`}>
                        ＋
                      </button>
                      <button type="button" onClick={() => setPrgPlas("-")}
                        className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "-" ? "bg-red-500 text-white border-red-500" : "bg-white text-slate-600 border-slate-300 hover:border-red-300"}`}>
                        ー
                      </button>
                      <button type="button" onClick={() => setPrgPlas("")}
                        className="px-2 py-2 rounded-lg text-xs border border-slate-200 text-slate-400 hover:bg-slate-50">
                        クリア
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* 時間集計（自動計算・表示のみ）*/}
              {times && (
                <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                  <h3 className="text-xs font-bold text-slate-500 mb-3">時間集計（自動計算）</h3>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs mb-2">
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-slate-400 mb-0.5">段取時間</div>
                      <div className="font-bold text-blue-700 text-sm">{fmtMin(times.setupMin)}</div>
                    </div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-slate-400 mb-0.5">加工時間</div>
                      <div className="font-bold text-teal-700 text-sm">{fmtMin(times.machMin)}</div>
                    </div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-slate-400 mb-0.5">総時間</div>
                      <div className="font-bold text-slate-700 text-sm">{fmtMin(times.totalMin)}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    {times.cyclePerPSec != null && (
                      <div className="bg-white rounded-lg p-2 border border-slate-100">
                        <div className="text-slate-400 mb-0.5">サイクルタイム/1P</div>
                        <div className="font-bold text-purple-700 text-sm">{fmtSec(times.cyclePerPSec)}</div>
                      </div>
                    )}
                    {times.machPerPMin != null && (
                      <div className="bg-white rounded-lg p-2 border border-slate-100">
                        <div className="text-slate-400 mb-0.5">加工時間/1P</div>
                        <div className="font-bold text-teal-600 text-sm">{fmtMin(times.machPerPMin)}</div>
                      </div>
                    )}
                    {times.totalPerPMin != null && (
                      <div className="bg-white rounded-lg p-2 border border-slate-100">
                        <div className="text-slate-400 mb-0.5">総時間/1P</div>
                        <div className="font-bold text-slate-600 text-sm">{fmtMin(times.totalPerPMin)}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* 備考 */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <label className="text-xs font-bold text-slate-500 block mb-1.5">備考</label>
                <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                  placeholder="問題点・注意事項・特記事項"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none" />
                <div className="text-right text-xs text-slate-400 mt-1">{note.length} / 1000</div>
              </div>

              {saveError && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">{saveError}</div>
              )}

              {/* 登録・キャンセルボタン */}
              <div className="flex gap-3 pb-4">
                <button onClick={handleSubmit} disabled={saving || (!isAuthenticated && !sbMode)}
                  className="flex-1 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm transition-colors">
                  {saving ? "登録中..." : editRecordId ? "✓ 更新（保存）" : "✓ 作業完了（登録）"}
                </button>
                <button onClick={() => {
                    resetForm();
                    if (!editRecordId) {
                      if (sbMode) { router.push("/"); }
                      else { logout(); router.push(`/mc/${mcId}`); }
                    }
                  }}
                  className="px-5 py-3 border border-slate-300 rounded-xl text-sm text-slate-600 hover:bg-slate-100 transition-colors">
                  ✗ キャンセル
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="MC_WORK_RECORD" mcProgramId={mcId}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">
          {toast}
        </div>
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
