#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess, shutil, os, sys, base64

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"
REPO   = "/home/karkyon/projects/machcore"

shutil.copy(TARGET, TARGET + ".bak_rewrite")

# ── TSファイル内容（日本語はすべてUTF-8文字で直書き、エスケープなし）──
CONTENT = '''"use client";
import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

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
  const names = selected.map(id => users.find(u=>u.id===id)?.name ?? "?");
  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(o=>!o)}
        className="w-full text-left border border-slate-200 rounded-lg px-3 py-1.5 text-xs min-h-[32px] focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white">
        {names.length ? names.join(", ") : <span className="text-slate-400">{placeholder ?? "選択..."}</span>}
      </button>
      {open && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
          {users.filter(u=>u.isActive!==false).map(u => (
            <button key={u.id} type="button" onClick={() => toggle(u.id)}
              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-teal-50 ${selected.includes(u.id) ? "bg-teal-100 font-bold text-teal-700" : ""}`}>
              {selected.includes(u.id) ? "✓ " : ""}{u.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SingleUserSelect({ users, selected, onChange, placeholder }: {
  users: UserInfo[]; selected: number | null; onChange: (id: number | null) => void; placeholder?: string;
}) {
  return (
    <select value={selected ?? ""} onChange={e => onChange(e.target.value ? parseInt(e.target.value) : null)}
      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-teal-400">
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
  const rounded = Math.round(min * 10) / 10;
  const h = Math.floor(rounded / 60);
  const m = Math.round(rounded % 60 * 10) / 10;
  return `${h}H ${m % 1 === 0 ? String(Math.round(m)).padStart(2,"0") : m}M`;
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

// ─────────────────────────────────────────────────────────────────────
// 機械タイムカード参照モーダル
// ─────────────────────────────────────────────────────────────────────
interface TcRow {
  id: number | null;
  date: string;
  startTime: string;
  endTime: string;
  dirty: boolean;
  saving: boolean;
}
interface TimecardModalProps {
  open: boolean;
  onClose: () => void;
  machineCode: string;
  machineId: number;
  startedAt: string;
  checkedAt: string;
  finishedAt: string;
  token: string | null;
  onKadouChange: (setupKadouMin: number | null, machKadouMin: number | null) => void;
}
function TimecardModal({
  open, onClose, machineCode, machineId,
  startedAt, checkedAt, finishedAt, token, onKadouChange,
}: TimecardModalProps) {
  const [rows, setRows] = React.useState<TcRow[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [tcToast, setTcToast] = React.useState<string | null>(null);
  const showTcToast = (msg: string) => { setTcToast(msg); setTimeout(() => setTcToast(null), 3000); };

  const dateRange = React.useMemo((): string[] => {
    const ws = startedAt ? startedAt.slice(0, 10) : null;
    const we = finishedAt ? finishedAt.slice(0, 10)
             : checkedAt  ? checkedAt.slice(0, 10) : null;
    if (!ws) return [];
    const dates: string[] = [];
    const cur = new Date(ws + "T12:00:00");
    const end = new Date((we ?? ws) + "T12:00:00");
    while (cur <= end) {
      dates.push(cur.toISOString().slice(0, 10));
      cur.setDate(cur.getDate() + 1);
    }
    return dates;
  }, [startedAt, checkedAt, finishedAt]);

  const loadCards = React.useCallback(async () => {
    if (!open || dateRange.length === 0) return;
    setLoading(true);
    try {
      const newRows: TcRow[] = [];
      for (const dt of dateRange) {
        const res = await mcApi.timecardsByDate(dt);
        const all: any[] = (res as any).data ?? [];
        const card = all.find((c: any) => c.machine?.machineCode === machineCode);
        if (card) {
          const fmtT = (s: string) => s && s.length >= 16 ? s.slice(11, 16) : "08:00";
          newRows.push({ id: card.id, date: dt,
            startTime: fmtT(card.start_time ?? ""),
            endTime:   fmtT(card.end_time   ?? ""),
            dirty: false, saving: false });
        } else {
          newRows.push({ id: null, date: dt, startTime: "08:00", endTime: "17:00", dirty: false, saving: false });
        }
      }
      setRows(newRows);
    } catch { showTcToast("タイムカード取得失敗"); }
    finally  { setLoading(false); }
  }, [open, dateRange, machineCode]);

  React.useEffect(() => { loadCards(); }, [loadCards]);

  const calcKadou = React.useCallback((wsD: Date, weD: Date, tcRows: TcRow[]): number => {
    let total = 0;
    for (const row of tcRows) {
      if (row.id === null && !row.dirty) continue;
      const tcS = new Date(row.date + "T" + row.startTime + ":00");
      const tcE = new Date(row.date + "T" + row.endTime   + ":00");
      const ovS = tcS > wsD ? tcS : wsD;
      const ovE = tcE < weD ? tcE : weD;
      let diff = Math.round((ovE.getTime() - ovS.getTime()) / 60000);
      if (diff <= 0) continue;
      const sh = ovS.getHours() + ovS.getMinutes() / 60;
      const eh = ovE.getHours() + ovE.getMinutes() / 60;
      if (sh < 12 && eh > 13) diff -= 60;
      if (diff > 0) total += diff;
    }
    return total;
  }, []);

  React.useEffect(() => {
    if (rows.length === 0) return;
    const ws = startedAt  ? new Date(startedAt)  : null;
    const ck = checkedAt  ? new Date(checkedAt)  : null;
    const we = finishedAt ? new Date(finishedAt) : null;
    onKadouChange(
      ws && ck ? calcKadou(ws, ck, rows) : null,
      ck && we ? calcKadou(ck, we, rows) : null,
    );
  }, [rows, startedAt, checkedAt, finishedAt, calcKadou, onKadouChange]);

  const updateField = (idx: number, field: "startTime" | "endTime", val: string) =>
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val, dirty: true } : r));

  const handleSave = async (idx: number) => {
    const row = rows[idx];
    if (!token) { showTcToast("認証が必要です"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      if (row.id !== null) {
        await mcApi.updateTimecard(row.id, { start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
        showTcToast("✅ " + row.date + " 更新しました");
      } else {
        const res = await mcApi.createTimecard({ machine_id: machineId, work_date: row.date,
          start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        const newId: number = (res as any).data?.id ?? (res as any).id ?? -1;
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, id: newId, dirty: false, saving: false } : r));
        showTcToast("✅ " + row.date + " 登録しました");
      }
    } catch {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showTcToast("❌ 保存失敗");
    }
  };

  const fmtK = (min: number) => Math.floor(min/60) + "H " + (min%60) + "M";
  const summaryK = (wsStr: string, weStr: string): string => {
    if (!wsStr || !weStr || rows.length === 0) return "—";
    const w = new Date(wsStr), e = new Date(weStr);
    if (isNaN(w.getTime()) || isNaN(e.getTime())) return "—";
    return fmtK(calcKadou(w, e, rows));
  };
  const dayK = (row: TcRow): string => {
    if (row.id === null && !row.dirty) return "—";
    const w = startedAt  ? new Date(startedAt)  : new Date(row.date + "T00:00:00");
    const e = finishedAt ? new Date(finishedAt) : new Date(row.date + "T23:59:59");
    const m = calcKadou(w, e, [row]);
    return m > 0 ? fmtK(m) : "—";
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-slate-800">&#128197; 機械タイムカード参照 — {machineCode}</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">タイムカードを確認・編集できます。更新すると稼働時間に即反映されます。</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg font-bold px-2">&#10005;</button>
        </div>
        <div className="grid grid-cols-3 gap-3 px-5 py-3 bg-slate-50 border-b border-slate-100 shrink-0 text-xs font-bold">
          <div className="text-center">
            <p className="text-slate-400 mb-0.5">段取稼働</p>
            <p className="text-blue-700 text-sm">{summaryK(startedAt, checkedAt || finishedAt)}</p>
          </div>
          <div className="text-center">
            <p className="text-slate-400 mb-0.5">量産稼働</p>
            <p className="text-green-700 text-sm">{checkedAt ? summaryK(checkedAt, finishedAt) : "—"}</p>
          </div>
          <div className="text-center">
            <p className="text-slate-400 mb-0.5">総稼働</p>
            <p className="text-teal-700 text-sm">{summaryK(startedAt, finishedAt || checkedAt)}</p>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 text-sm">読み込み中...</div>
          ) : (
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="pb-2 text-left font-bold text-slate-500 w-24">日付</th>
                  <th className="pb-2 text-left font-bold text-slate-500 w-20">開始</th>
                  <th className="pb-2 text-left font-bold text-slate-500 w-20">終了</th>
                  <th className="pb-2 text-center font-bold text-slate-500 w-20">稼働時間</th>
                  <th className="pb-2 text-center font-bold text-slate-500 w-14">操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const isHoliday = row.id === null && !row.dirty;
                  const kStr = dayK(row);
                  return (
                    <tr key={row.date} className={`border-b border-slate-100 ${isHoliday ? "bg-slate-50/60" : ""}`}>
                      <td className="py-2 font-mono text-slate-700">{row.date.slice(5)}</td>
                      <td className="py-2">
                        {isHoliday ? <span className="text-slate-400 text-[11px]">― 休日 ―</span>
                          : <input type="time" value={row.startTime} onChange={e => updateField(idx,"startTime",e.target.value)}
                              className="border border-slate-200 rounded px-1.5 py-0.5 text-xs w-18 focus:outline-none focus:ring-1 focus:ring-teal-400" />}
                      </td>
                      <td className="py-2">
                        {!isHoliday && <input type="time" value={row.endTime} onChange={e => updateField(idx,"endTime",e.target.value)}
                          className="border border-slate-200 rounded px-1.5 py-0.5 text-xs w-18 focus:outline-none focus:ring-1 focus:ring-teal-400" />}
                      </td>
                      <td className="py-2 text-center">
                        <span className={"font-bold " + (kStr !== "—" ? "text-teal-700" : "text-slate-400")}>
                          {kStr}
                        </span>
                      </td>
                      <td className="py-2 text-center">
                        {row.dirty && (
                          <button onClick={() => handleSave(idx)} disabled={row.saving}
                            className="text-[11px] px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold disabled:opacity-50 transition-colors whitespace-nowrap">
                            {row.saving ? "…" : row.id === null ? "登録" : "更新"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 shrink-0">
          <p className="text-[10px] text-slate-400">※ 稼働時間 = overlap（12:00-13:00は自動控除）</p>
          <button onClick={onClose} className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-bold rounded-lg transition-colors">閉じる</button>
        </div>
        {tcToast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs px-4 py-2 rounded-full shadow-lg whitespace-nowrap">{tcToast}</div>
        )}
      </div>
    </div>
  );
}

function McRecordPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId = parseInt(mc_id);
  const router = useRouter();
  const searchParams = useSearchParams();

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
  React.useEffect(() => {
    if (!sbMode && !isAuthenticated) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "作業が完了していません。このページを離れますか？";
      return e.returnValue;
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sbMode, isAuthenticated]);

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
  const [timeValidErr, setTimeValidErr] = useState<string | null>(null);
  const [tcModalOpen, setTcModalOpen] = useState(false);
  const [setupKadouMin, setSetupKadouMin] = useState<number | null>(null);
  const [machKadouMin,  setMachKadouMin]  = useState<number | null>(null);

  const [timeMode, setTimeMode] = useState<"hm" | "datetime">("datetime");
  const [machineId, setMachineId] = useState<string>("");
  const [cycleH, setCycleH] = useState(0);
  const [cycleM, setCycleM] = useState(0);
  const [cycleS, setCycleS] = useState(0);
  const [cyclePcs, setCyclePcs] = useState("");
  const [setupOps, setSetupOps] = useState<number[]>([]);
  const [startedAt, setStartedAt] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [checkMan, setCheckMan] = useState<number | null>(null);
  const [dStopH, setDStopH] = useState(0);
  const [dStopM, setDStopM] = useState(0);
  const [setupQty, setSetupQty] = useState("");
  const [setupH, setSetupH] = useState(0);
  const [setupMm, setSetupMm] = useState(0);
  const [setupInterruption, setSetupInterruption] = useState(0);
  const [prodOps, setProdOps] = useState<number[]>([]);
  const [finishedAt, setFinishedAt] = useState("");
  const [yStopH, setYStopH] = useState(0);
  const [yStopM, setYStopM] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [machH, setMachH] = useState(0);
  const [machMm, setMachMm] = useState(0);
  const [machInterruption, setMachInterruption] = useState(0);
  const [prgMan, setPrgMan] = useState<number | null>(null);
  const [prgTimeH, setPrgTimeH] = useState(0);
  const [prgTimeM, setPrgTimeM] = useState(0);
  const [prgPlas, setPrgPlas] = useState("");
  const [note, setNote] = useState("");

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  useEffect(() => {
    mcApi.findOne(mcId).then(r => {
      const d = (r as any).data ?? (r as any);
      setDetail(d);
      if (d?.machine?.machineCode) setMachineId(d.machine.machineCode);
      if (d?.cycleTimeSec != null && d.cycleTimeSec > 0) {
        setCycleH(Math.floor(d.cycleTimeSec / 3600));
        setCycleM(Math.floor((d.cycleTimeSec % 3600) / 60));
        setCycleS(d.cycleTimeSec % 60);
      }
      if (d?.machiningQty != null && d.machiningQty > 0) setCyclePcs(String(d.machiningQty));
    }).catch(() => {});
    mcApi.setupSheetLogs(mcId).then(r => {
      const sheets = ((r as any).data ?? []).filter((s: McSetupSheetLog) => !s.work_collected);
      setSetupSheets(sheets);
      if (sheets.length > 0) setSelectedSheet(sheets[0]);
    }).catch(() => {});
    mcApi.workRecords(mcId).then(r => setRecords((r as any).data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mcId]);

  useEffect(() => {
    const qp = searchParams.get("edit");
    if (!qp) return;
    const id = parseInt(qp);
    mcApi.workRecords(mcId).then(r => {
      const recs = (r as any).data ?? [];
      const rec = recs.find((x: McWorkRecord) => x.id === id);
      if (!rec) return;
      setEditRecordId(id);
      setMachineId(rec.machine_code ?? "");
      setStartedAt(toLocalInput(rec.started_at));
      setCheckedAt(toLocalInput(rec.checked_at));
      setFinishedAt(toLocalInput(rec.finished_at));
      setSetupOps((rec.setup_operator_ids ?? []).map(Number));
      setProdOps((rec.production_operator_ids ?? []).map(Number));
      setDStopH(Math.floor((rec.interrupt_setup_min ?? 0) / 60));
      setDStopM((rec.interrupt_setup_min ?? 0) % 60);
      setYStopH(Math.floor((rec.interrupt_work_min ?? 0) / 60));
      setYStopM((rec.interrupt_work_min ?? 0) % 60);
      setSetupQty(String(rec.setup_work_count ?? ""));
      setQuantity(String(rec.quantity ?? ""));
      setCycleH(Math.floor((rec.cycle_time_sec ?? 0) / 3600));
      setCycleM(Math.floor(((rec.cycle_time_sec ?? 0) % 3600) / 60));
      setCycleS((rec.cycle_time_sec ?? 0) % 60);
      setPrgMan(rec.prg_man_id ?? null);
      setPrgTimeH(Math.floor((rec.prg_time_min ?? 0) / 60));
      setPrgTimeM((rec.prg_time_min ?? 0) % 60);
      setPrgPlas(rec.prg_plas ?? "");
      setNote(rec.note ?? "");
      setTimeMode("datetime");
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!sbMode && isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s+1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [sbMode, isAuthenticated]);

  const resetForm = () => {
    setEditRecordId(null);
    setStartedAt(""); setCheckedAt(""); setFinishedAt("");
    setSetupOps([]); setProdOps([]);
    setDStopH(0); setDStopM(0); setYStopH(0); setYStopM(0);
    setSetupQty(""); setQuantity("");
    setSetupH(0); setSetupMm(0); setMachH(0); setMachMm(0);
    setSetupInterruption(0); setMachInterruption(0);
    setCycleH(0); setCycleM(0); setCycleS(0); setCyclePcs("");
    setPrgMan(null); setPrgTimeH(0); setPrgTimeM(0); setPrgPlas("");
    setNote(""); setTimeValidErr(null);
    setSetupKadouMin(null); setMachKadouMin(null);
    if (detail?.machine?.machineCode) setMachineId(detail.machine.machineCode);
  };

  const calcTimes = useCallback(() => {
    const qtyN = quantity ? parseInt(quantity) : 0;
    const setupQtyN = setupQty ? parseInt(setupQty) : 0;
    const totalQty = qtyN;
    const cycSec = cycleH * 3600 + cycleM * 60 + cycleS;
    const cycPcsN = cyclePcs ? parseInt(cyclePcs) : 0;
    const cyclePerPSec = cycSec > 0 && cycPcsN > 0 ? cycSec / cycPcsN : cycSec > 0 ? cycSec : null;
    const machQtyBase = qtyN > setupQtyN ? Math.max(1, qtyN - setupQtyN) : Math.max(1, totalQty);

    if (timeMode === "hm") {
      const setupMin = setupH * 60 + setupMm;
      const machMin  = machH * 60 + machMm;
      const totalMin = setupMin + machMin;
      return { setupMin, machMin, totalMin, cyclePerPSec,
        machPerPMin:  machMin > 0 && qtyN > 0 ? Math.round(machMin / machQtyBase * 10) / 10 : null,
        totalPerPMin: totalMin > 0 && totalQty > 0 ? Math.round(totalMin / totalQty * 10) / 10 : null };
    }

    const dStopMin = dStopH * 60 + dStopM;
    const yStopMin = yStopH * 60 + yStopM;
    let setupMin: number | null = null;
    let machMin:  number | null = null;
    let totalMin: number | null = null;
    if (startedAt && finishedAt) {
      const sv = new Date(startedAt).getTime(), fv = new Date(finishedAt).getTime();
      if (!isNaN(sv) && !isNaN(fv)) totalMin = Math.max(0, Math.round((fv - sv) / 60000) - dStopMin - yStopMin);
    }
    if (startedAt && checkedAt) {
      const sv = new Date(startedAt).getTime(), cv = new Date(checkedAt).getTime();
      if (!isNaN(sv) && !isNaN(cv)) setupMin = Math.max(0, Math.round((cv - sv) / 60000) - dStopMin);
    }
    if (checkedAt && finishedAt) {
      const cv = new Date(checkedAt).getTime(), fv = new Date(finishedAt).getTime();
      if (!isNaN(cv) && !isNaN(fv)) machMin = Math.max(0, Math.round((fv - cv) / 60000) - yStopMin);
    }
    if (setupMin === null && machMin === null && totalMin === null && cyclePerPSec === null) return null;
    return { setupMin, machMin, totalMin, cyclePerPSec,
      machPerPMin:  machMin != null && machMin > 0 && qtyN > 0 ? Math.round(machMin / machQtyBase * 10) / 10 : null,
      totalPerPMin: totalMin != null && totalMin > 0 && totalQty > 0 ? Math.round(totalMin / totalQty * 10) / 10 : null };
  }, [timeMode, setupH, setupMm, machH, machMm, startedAt, checkedAt, finishedAt,
      dStopH, dStopM, yStopH, yStopM, quantity, setupQty, cycleH, cycleM, cycleS, cyclePcs]);

  const times = calcTimes();

  const validateDateOrder = (sa: string, ca: string, fa: string): string | null => {
    if (sa && ca && new Date(ca) <= new Date(sa)) return "段取終了は段取開始より後の日時を入力してください";
    if (ca && fa && new Date(fa) <= new Date(ca)) return "加工終了は段取終了（チェックTime）より後の日時を入力してください";
    if (sa && fa && !ca && new Date(fa) <= new Date(sa)) return "加工終了は段取開始より後の日時を入力してください";
    return null;
  };

  const handleSubmit = async () => {
    if (!token) { setSaveError("認証セッションが切れています。再認証してください。"); setAuthOpen(true); return; }
    if (timeMode === "datetime") {
      const vErr = validateDateOrder(startedAt, checkedAt, finishedAt);
      if (vErr) { setTimeValidErr(vErr); return; }
    }
    setTimeValidErr(null);
    setSaving(true); setSaveError(null);
    try {
      const cycSec = cycleH * 3600 + cycleM * 60 + cycleS;
      const body: CreateMcWorkRecordBody = {
        setup_time_min:      (times?.setupMin != null && !isNaN(times.setupMin)) ? times.setupMin : undefined,
        machining_time_min:  (times?.machMin  != null && !isNaN(times.machMin))  ? times.machMin  : undefined,
        cycle_time_sec:      cycSec || undefined,
        quantity:            (quantity && !isNaN(parseInt(quantity))) ? parseInt(quantity) : undefined,
        setup_work_count:    (setupQty && !isNaN(parseInt(setupQty))) ? parseInt(setupQty) : undefined,
        started_at:          startedAt ? new Date(startedAt).toISOString() : undefined,
        checked_at:          checkedAt ? new Date(checkedAt).toISOString() : undefined,
        finished_at:         finishedAt ? new Date(finishedAt).toISOString() : undefined,
        interrupt_setup_min: (dStopH * 60 + dStopM) > 0 ? (dStopH * 60 + dStopM) : undefined,
        interrupt_work_min:  (yStopH * 60 + yStopM) > 0 ? (yStopH * 60 + yStopM) : undefined,
        setup_operator_ids:  setupOps.length ? setupOps : undefined,
        production_operator_ids: prodOps.length ? prodOps : undefined,
        prg_man:             prgMan ? (users.find(u=>u.id===prgMan)?.name ?? undefined) : undefined,
        prg_time_min:        (prgTimeH * 60 + prgTimeM) > 0 ? (prgTimeH * 60 + prgTimeM) : undefined,
        prg_plas:            prgPlas || undefined,
        note:                note || undefined,
        machine_id:          (machineId && !isNaN(parseInt(machineId))) ? parseInt(machineId) : undefined,
      };
      if (editRecordId) {
        await mcApi.updateWorkRecord(mcId, editRecordId, body, token);
      } else {
        await mcApi.createWorkRecord(mcId, body, token);
      }
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
            catch { showToast("⚠️ 作業記録登録済（回収済み更新に失敗）"); }
          }
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          setTimeout(() => router.push("/"), 1500);
        }
      }
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? e?.message ?? "登録に失敗しました";
      setSaveError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-slate-800 text-white px-4 py-2.5 flex items-center gap-3 sticky top-0 z-30 shadow">
        <button onClick={() => router.push(`/mc/${mcId}`)} className="text-slate-400 hover:text-white text-sm">&#8592;</button>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] text-slate-400 leading-none mb-0.5">MC{mcId}</p>
          <p className="font-bold text-sm truncate">{detail?.partName ?? "..."}</p>
        </div>
        <div className="text-right">
          {isAuthenticated ? (
            <div className="text-xs text-teal-300">
              <span className="font-bold">{operator?.name}</span>
              <span className="ml-2 font-mono text-slate-400">{fmtElapsed(elapsed)}</span>
            </div>
          ) : (
            <button onClick={() => setAuthOpen(true)} className="text-xs text-amber-400 hover:text-amber-300">認証して開始</button>
          )}
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-4 space-y-4">

        {sbMode && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="text-amber-600 text-lg">&#128203;</span>
            <div className="flex-1 text-xs">
              <span className="font-bold text-amber-800">段取シートバックモード</span>
              <span className="text-amber-600 ml-2">作業完了後、段取シートを回収済みに更新します</span>
            </div>
          </div>
        )}

        {detail && (
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-bold text-slate-700">{detail.partId}</span>
                  <span className="font-bold text-slate-800">{detail.partName}</span>
                  <StatusBadge status={detail.status} />
                </div>
                <div className="flex gap-4 mt-1 text-xs text-slate-500 flex-wrap">
                  <span>MCID: {mcId}</span>
                  {detail.machine?.machineCode && <span>機械: {detail.machine.machineCode}</span>}
                </div>
              </div>
              {setupSheets.length > 0 && (
                <div className="shrink-0">
                  <p className="text-[10px] text-slate-400 mb-1">段取シート</p>
                  <div className="flex gap-1 flex-wrap">
                    {setupSheets.map(s => (
                      <button key={s.id}
                        onClick={() => setSelectedSheet(selectedSheet?.id===s.id ? null : s)}
                        className={`text-[11px] px-2 py-1 rounded-lg border font-bold transition-colors ${selectedSheet?.id===s.id ? "bg-teal-50 border-teal-400 text-teal-700" : "border-slate-200 text-slate-500 hover:border-teal-300"}`}>
                        {fmtDate(s.printed_at)} Ver{s.version}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {selectedSheet && (
              <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-4 gap-3 text-xs">
                <div><span className="text-slate-400 block mb-0.5">印刷日時</span><span className="font-bold text-slate-700">{selectedSheet.printed_at ? new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP") : "—"}</span></div>
                <div><span className="text-slate-400 block mb-0.5">回収日時</span><span className="font-bold text-slate-700">{fmtNow()}</span></div>
                <div><span className="text-slate-400 block mb-0.5">オペレータ</span><span className="font-bold text-teal-700">{operator?.name ?? "—"}</span></div>
              </div>
            )}
          </div>
        )}

        <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-teal-50 border border-teal-200 text-teal-700"}`}>
          <span>{editRecordId ? "✏️ 編集モード" : "+ 新規入力モード"}</span>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 text-xs">
              <span className="text-slate-500 mr-1">入力方法:</span>
              <button onClick={() => setTimeMode("datetime")} className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="datetime" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>開始/終了日時</button>
              <button onClick={() => setTimeMode("hm")} className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="hm" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>h/m入力</button>
            </div>
          </div>
        </div>

        <div className="space-y-4">

          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-500 border-b border-slate-100 pb-2">&#9881; 機械</h3>
            <select value={machineId} onChange={e => setMachineId(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
              <option value="">— 機械を選択 —</option>
              {machines.map(m => <option key={m.id} value={m.machineCode}>{m.machineCode} — {m.machineName}</option>)}
            </select>
          </div>

          <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 space-y-3">
            <h3 className="text-xs font-bold text-blue-700 border-b border-blue-200 pb-2">&#9201; 段取</h3>
            {timeMode === "hm" ? (
              <div className="grid grid-cols-3 gap-4">
                <div><label className="text-xs font-bold text-slate-500 block mb-1.5">段取時間</label><TimeInput h={setupH} m={setupMm} onH={setSetupH} onM={setSetupMm} /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1.5">中断時間</label><div className="flex items-center gap-1"><NumInput value={setupInterruption} onChange={setSetupInterruption} /><span className="text-xs text-slate-500">m</span></div></div>
                <div />
              </div>
            ) : (
              <div className="space-y-3">
                {timeValidErr && (
                  <div className="flex items-center gap-2 bg-red-50 border border-red-300 rounded-lg px-3 py-2 text-xs text-red-700 font-bold">
                    <span>&#9940;</span><span>{timeValidErr}</span>
                  </div>
                )}
                {detail?.machine && startedAt && (
                  <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5">
                    <div className="flex-1 min-w-0 flex items-center gap-3 flex-wrap">
                      {setupKadouMin !== null && <span className="text-xs text-blue-700 font-bold">{"段取稼働: " + Math.floor(setupKadouMin/60) + "H " + (setupKadouMin%60) + "M"}</span>}
                      {machKadouMin  !== null && <span className="text-xs text-green-700 font-bold">{"量産稼働: " + Math.floor(machKadouMin/60)  + "H " + (machKadouMin%60)  + "M"}</span>}
                      {setupKadouMin === null && machKadouMin === null && <span className="text-xs text-slate-400">タイムカードを確認して稼働時間を参照</span>}
                    </div>
                    <button type="button" onClick={() => setTcModalOpen(true)}
                      className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-300 hover:bg-teal-50 hover:border-teal-400 text-slate-700 hover:text-teal-700 rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                      &#128197; 機械タイムカード参照
                    </button>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>
                    <input type="datetime-local" value={startedAt}
                      onChange={e => { setStartedAt(e.target.value); setTimeValidErr(validateDateOrder(e.target.value, checkedAt, finishedAt)); }}
                      className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr ? "border-red-400 bg-red-50" : "border-slate-200"}`} />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取終了（CheckTime）</label>
                    <input type="datetime-local" value={checkedAt}
                      onChange={e => { setCheckedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, e.target.value, finishedAt)); }}
                      className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("段取終了") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />
                  </div>
                </div>
                {startedAt && checkedAt && (() => {
                  const mins = Math.max(0, Math.round((new Date(checkedAt).getTime()-new Date(startedAt).getTime())/60000) - (dStopH*60+dStopM));
                  return mins > 0 ? <p className="text-xs text-blue-600 font-bold">&#8594; 段取時間: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                })()}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取時の中断</label>
                    <div className="flex items-center gap-1 flex-wrap">
                      <NumInput value={dStopH} onChange={setDStopH} /><span className="text-xs text-slate-500">h</span>
                      <NumInput value={dStopM} onChange={setDStopM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">チェック担当</label>
                    <SingleUserSelect users={users} selected={checkMan} onChange={setCheckMan} placeholder="— 選択 —" />
                  </div>
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs font-bold text-slate-500 block mb-1.5">段取作業者（複数可）</label><MultiUserSelect users={users} selected={setupOps} onChange={setSetupOps} placeholder="作業者を選択..." /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1.5">段取ワーク数</label><div className="flex items-center gap-1"><input type="number" min="0" value={setupQty} onChange={e => setSetupQty(e.target.value)} className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" /><span className="text-xs text-slate-500">個</span></div></div>
            </div>
          </div>

          <div className="bg-green-50 rounded-xl border border-green-200 p-4 space-y-3">
            <h3 className="text-xs font-bold text-green-700 border-b border-green-200 pb-2">&#9881; 量産</h3>
            {timeMode === "hm" ? (
              <div className="grid grid-cols-3 gap-4">
                <div><label className="text-xs font-bold text-slate-500 block mb-1.5">加工時間</label><TimeInput h={machH} m={machMm} onH={setMachH} onM={setMachMm} /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1.5">中断時間</label><div className="flex items-center gap-1"><NumInput value={machInterruption} onChange={setMachInterruption} /><span className="text-xs text-slate-500">m</span></div></div>
                <div />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">加工終了</label>
                    <input type="datetime-local" value={finishedAt}
                      onChange={e => { setFinishedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, checkedAt, e.target.value)); }}
                      className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("加工終了") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />
                  </div>
                  <div />
                </div>
                {checkedAt && finishedAt && (() => {
                  const mins = Math.max(0, Math.round((new Date(finishedAt).getTime()-new Date(checkedAt).getTime())/60000) - (yStopH*60+yStopM));
                  return mins > 0 ? <p className="text-xs text-green-600 font-bold">&#8594; 加工時間: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                })()}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">量産時の中断</label>
                    <div className="flex items-center gap-1 flex-wrap">
                      <NumInput value={yStopH} onChange={setYStopH} /><span className="text-xs text-slate-500">h</span>
                      <NumInput value={yStopM} onChange={setYStopM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                    </div>
                  </div>
                  <div />
                </div>
              </div>
            )}
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs font-bold text-slate-500 block mb-1.5">量産作業者（複数可）</label><MultiUserSelect users={users} selected={prodOps} onChange={setProdOps} placeholder="作業者を選択..." /></div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1.5">全良品数（ワーク数）</label>
                <div className="flex items-center gap-1">
                  <input type="number" min="0" value={quantity} onChange={e => setQuantity(e.target.value)} className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                  <span className="text-xs text-slate-500">個</span>
                </div>
              </div>
              <div />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-500 border-b border-slate-100 pb-2">&#9201; サイクルタイム</h3>
            <div className="flex items-center gap-2 flex-wrap">
              <NumInput value={cycleH} onChange={setCycleH} /><span className="text-xs text-slate-500">h</span>
              <NumInput value={cycleM} onChange={setCycleM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
              <NumInput value={cycleS} onChange={setCycleS} min={0} max={59} /><span className="text-xs text-slate-500">s</span>
              <span className="text-xs text-slate-400 ml-2">/ </span>
              <input type="number" min="1" value={cyclePcs} onChange={e => setCyclePcs(e.target.value)}
                className="w-16 border border-slate-200 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="1" />
              <span className="text-xs text-slate-500">個</span>
            </div>
          </div>

          {times && (
            <div className="bg-slate-800 rounded-xl p-4 text-white">
              <p className="text-[10px] text-slate-400 mb-2 uppercase tracking-wider">集計</p>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div><p className="text-[10px] text-slate-400">段取時間</p><p className="font-bold text-blue-300">{fmtMin(times.setupMin ?? null)}</p></div>
                <div><p className="text-[10px] text-slate-400">加工時間</p><p className="font-bold text-green-300">{fmtMin(times.machMin ?? null)}</p></div>
                <div><p className="text-[10px] text-slate-400">合計</p><p className="font-bold text-teal-300">{fmtMin(times.totalMin ?? null)}</p></div>
              </div>
              {times.cyclePerPSec != null && (
                <div className="mt-2 pt-2 border-t border-slate-700 grid grid-cols-3 gap-3 text-center text-[10px] text-slate-400">
                  <div>CT/個: <span className="text-white font-bold">{fmtSec(times.cyclePerPSec)}</span></div>
                  {times.machPerPMin != null && <div>加工/個: <span className="text-white font-bold">{times.machPerPMin}m</span></div>}
                  {times.totalPerPMin != null && <div>総/個: <span className="text-white font-bold">{times.totalPerPMin}m</span></div>}
                </div>
              )}
            </div>
          )}

          <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">
            <h3 className="text-xs font-bold text-purple-700 border-b border-purple-200 pb-2">&#128190; プログラム</h3>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs font-bold text-slate-500 block mb-1.5">プログラム担当</label><SingleUserSelect users={users} selected={prgMan} onChange={setPrgMan} placeholder="— 選択 —" /></div>
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
                  <button type="button" onClick={() => setPrgPlas("+")} className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "+" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:border-teal-400"}`}>+</button>
                  <button type="button" onClick={() => setPrgPlas("-")} className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "-" ? "bg-red-500 text-white border-red-500" : "bg-white text-slate-600 border-slate-300 hover:border-red-400"}`}>-</button>
                </div>
              </div>
            </div>
          </div>

          {records.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-xs font-bold text-slate-500 border-b border-slate-100 pb-2 mb-3">過去記録</h3>
              <div className="space-y-1">
                {records.map(r => (
                  <button key={r.id} onClick={() => {
                    setEditRecordId(r.id);
                    setMachineId(r.machine_code ?? "");
                    setStartedAt(toLocalInput(r.started_at));
                    setCheckedAt(toLocalInput(r.checked_at));
                    setFinishedAt(toLocalInput(r.finished_at));
                    setTimeMode("datetime");
                  }}
                    className={`w-full text-left px-3 py-2 text-xs rounded-lg hover:bg-amber-50 transition-colors ${editRecordId===r.id ? "bg-amber-50 border border-amber-400" : "border border-transparent"}`}>
                    <span className="font-bold text-slate-700">{fmtDate(r.work_date)}</span>
                    <span className="text-slate-400 ml-2">{r.machine_code ?? "—"}</span>
                    <span className="text-slate-400 ml-2">{fmtMin(r.setup_time_min)} / {fmtMin(r.machining_time_min)}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <label className="text-xs font-bold text-slate-500 block mb-1.5">備考</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
              placeholder="問題点・注意事項・特記事項"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none" />
            <div className="text-right text-xs text-slate-400 mt-1">{note.length} / 1000</div>
          </div>

          {saveError && <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">{saveError}</div>}

          <div className="flex gap-3 pb-4">
            <button onClick={handleSubmit} disabled={saving || (!isAuthenticated && !sbMode)}
              className="flex-1 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm transition-colors">
              {saving ? "登録中..." : editRecordId ? "✓ 更新（保存）" : "✓ 作業完了（登録）"}
            </button>
            <button onClick={() => { resetForm(); if (!editRecordId) { if (sbMode) router.push("/"); else { logout(); router.push(`/mc/${mcId}`); } } }}
              className="px-5 py-3 border border-slate-300 rounded-xl text-sm text-slate-600 hover:bg-slate-100 transition-colors">
              ✗ キャンセル
            </button>
          </div>
        </div>
      </div>

      {tcModalOpen && detail?.machine && (
        <TimecardModal
          open={tcModalOpen}
          onClose={() => setTcModalOpen(false)}
          machineCode={detail.machine.machineCode}
          machineId={parseInt(machineId) || 0}
          startedAt={startedAt}
          checkedAt={checkedAt}
          finishedAt={finishedAt}
          token={token}
          onKadouChange={(s, m) => { setSetupKadouMin(s); setMachKadouMin(m); }}
        />
      )}

      {authOpen && (
        <AuthModal isOpen={true} sessionType="work_record" mcProgramId={mcId}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">{toast}</div>
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
'''

# UTF-8バイト列として書き込む（エスケープ一切なし）
raw = CONTENT.encode("utf-8")
print(f"書き込み内容: {len(raw)} bytes, {len(CONTENT.splitlines())}行")

# 確認: \\u パターン（ダブルバックスラッシュ）が入っていないことを確認
bad_count = raw.count(b'\\\\u')
print(f"問題パターン \\\\\\\\u チェック: {bad_count}箇所 (0であること)")
if bad_count > 0:
    print("❌ 問題パターンが残っています。終了します。")
    sys.exit(1)

with open(TARGET, "wb") as f:
    f.write(raw)
print("✅ ファイル書き込み完了")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=f"{REPO}/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print((r.stdout + r.stderr)[-4000:])
    shutil.copy(TARGET + ".bak_rewrite", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r = subprocess.run(["npx", "next", "build"],
    cwd=f"{REPO}/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ next build エラー:")
    print((r.stdout + r.stderr)[-2000:])
    shutil.copy(TARGET + ".bak_rewrite", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True, text=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "fix: record page - full rewrite with proper UTF-8 Japanese text (no unicode escapes)"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r2.stderr.strip() or r2.stdout.strip()))

os.remove(TARGET + ".bak_rewrite")
print("✅ 完了")
