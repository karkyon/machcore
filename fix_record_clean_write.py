#!/usr/bin/env python3
"""
fix_record_clean_write.py
添付の最新ソース（document index 5）をベースに
完全クリーンなファイルを直接書き込む。
- tcWarnMsg / setTcWarnMsg / fetchTimecardStop を完全除去
- tcModalOpen / setupKadouMin / machKadouMin state 追加
- TCボタン統合版（段取セクション内、datetimeモード）
- TimecardModal JSXマウント追加
- TimecardModal コンポーネント追加
"""
import subprocess, shutil, os, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"

if not os.path.exists(TARGET):
    print(f"ファイルが見つかりません: {TARGET}")
    sys.exit(1)

shutil.copy(TARGET, TARGET + ".bak_clean")

# ── 完全クリーン版ファイル内容 ─────────────────────────────────────
CONTENT = '''\
"use client";
import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
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

function SingleUserSelect({ users, selected, onChange, placeholder }: {
  users: UserInfo[]; selected: number | null; onChange: (id: number | null) => void; placeholder?: string;
}) {
  return (
    <select value={selected ?? ""} onChange={e => onChange(e.target.value ? parseInt(e.target.value) : null)}
      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
      <option value="">{placeholder ?? "\\u2014 \\u9078\\u629e \\u2014"}</option>
      {users.filter(u=>u.isActive!==false).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
    </select>
  );
}

function fmtDate(s: string | null) {
  if (!s) return "\\u2014";
  try { return new Date(s).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" }); } catch { return s; }
}
function fmtMin(min: number | null) {
  if (min == null || min < 0) return "\\u2014";
  const rounded = Math.round(min * 10) / 10;
  const h = Math.floor(rounded / 60);
  const m = Math.round(rounded % 60 * 10) / 10;
  return `${h}H ${m % 1 === 0 ? String(Math.round(m)).padStart(2,"0") : m}M`;
}
function fmtSec(sec: number | null) {
  if (sec == null || sec < 0) return "\\u2014";
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
    } catch { showTcToast("\\u30bf\\u30a4\\u30e0\\u30ab\\u30fc\\u30c9\\u53d6\\u5f97\\u5931\\u6557"); }
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
    if (!token) { showTcToast("\\u8a8d\\u8a3c\\u304c\\u5fc5\\u8981\\u3067\\u3059"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      if (row.id !== null) {
        await mcApi.updateTimecard(row.id, { start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
        showTcToast("\\u2705 " + row.date + " \\u66f4\\u65b0\\u3057\\u307e\\u3057\\u305f");
      } else {
        const res = await mcApi.createTimecard({ machine_id: machineId, work_date: row.date,
          start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        const newId: number = (res as any).data?.id ?? (res as any).id ?? -1;
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, id: newId, dirty: false, saving: false } : r));
        showTcToast("\\u2705 " + row.date + " \\u767b\\u9332\\u3057\\u307e\\u3057\\u305f");
      }
    } catch {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showTcToast("\\u274c \\u4fdd\\u5b58\\u5931\\u6557");
    }
  };

  const fmtK = (min: number) => Math.floor(min/60) + "H " + (min%60) + "M";
  const summaryK = (wsStr: string, weStr: string): string => {
    if (!wsStr || !weStr || rows.length === 0) return "\\u2014";
    const w = new Date(wsStr), e = new Date(weStr);
    if (isNaN(w.getTime()) || isNaN(e.getTime())) return "\\u2014";
    return fmtK(calcKadou(w, e, rows));
  };
  const dayK = (row: TcRow): string => {
    if (row.id === null && !row.dirty) return "\\u2014";
    const w = startedAt  ? new Date(startedAt)  : new Date(row.date + "T00:00:00");
    const e = finishedAt ? new Date(finishedAt) : new Date(row.date + "T23:59:59");
    const m = calcKadou(w, e, [row]);
    return m > 0 ? fmtK(m) : "0M";
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
         onClick={onClose}>
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 flex flex-col"
           style={{ maxHeight: "85vh" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-800 text-white rounded-t-2xl shrink-0">
          <div>
            <p className="text-sm font-bold">&#128197; \\u6a5f\\u68b0\\u30bf\\u30a4\\u30e0\\u30ab\\u30fc\\u30c9</p>
            <p className="text-xs text-slate-300 mt-0.5">
              {"\\u6a5f\\u68b0: "}
              <span className="font-mono font-bold text-teal-300">{machineCode}</span>
              {startedAt && (
                <span className="ml-2">
                  {startedAt.slice(0, 10)}
                  {" \\u301c "}
                  {(finishedAt || checkedAt || startedAt).slice(0, 10)}
                </span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white w-8 h-8 flex items-center justify-center text-xl">&#10005;</button>
        </div>
        <div className="flex border-b border-slate-100 bg-slate-50 shrink-0">
          {startedAt && checkedAt && (
            <div className="flex-1 px-4 py-2.5 border-r border-slate-200">
              <p className="text-[10px] text-slate-400 font-bold uppercase">\\u6bb5\\u53d6\\u7a3c\\u50cd</p>
              <p className="text-base font-mono font-bold text-blue-700">{summaryK(startedAt, checkedAt)}</p>
              <p className="text-[10px] text-slate-400">{startedAt.slice(11,16)} &#8594; {checkedAt.slice(11,16)}</p>
            </div>
          )}
          {checkedAt && finishedAt && (
            <div className="flex-1 px-4 py-2.5 border-r border-slate-200">
              <p className="text-[10px] text-slate-400 font-bold uppercase">\\u91cf\\u7523\\u7a3c\\u50cd</p>
              <p className="text-base font-mono font-bold text-green-700">{summaryK(checkedAt, finishedAt)}</p>
              <p className="text-[10px] text-slate-400">{checkedAt.slice(11,16)} &#8594; {finishedAt.slice(11,16)}</p>
            </div>
          )}
          {startedAt && finishedAt && (
            <div className="flex-1 px-4 py-2.5">
              <p className="text-[10px] text-slate-400 font-bold uppercase">\\u7dcf\\u7a3c\\u50cd</p>
              <p className="text-base font-mono font-bold text-slate-700">{summaryK(startedAt, finishedAt)}</p>
              <p className="text-[10px] text-slate-400">{startedAt.slice(11,16)} &#8594; {finishedAt.slice(11,16)}</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 px-5 py-1.5 bg-slate-50 border-b border-slate-100 text-[10px] text-slate-500 shrink-0">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-teal-50 border border-teal-300" />\\u7a3c\\u50cd\\u65e5</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-slate-100 border border-slate-300" />\\u4f11\\u65e5</span>
          <span className="ml-auto text-slate-400">\\u5909\\u66f4\\u5f8c\\u300c\\u66f4\\u65b0\\u300d\\u3067\\u53cd\\u6620</span>
        </div>
        <div className="overflow-y-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-400 text-sm">\\u8aad\\u307f\\u8fbc\\u307f\\u4e2d\\u2026</div>
          ) : rows.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-slate-400 text-sm">\\u6bb5\\u53d6\\u958b\\u59cb\\u65e5\\u6642\\u3092\\u5165\\u529b\\u3057\\u3066\\u304f\\u3060\\u3055\\u3044</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 z-10">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-bold text-slate-500 w-28">\\u65e5\\u4ed8</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">\\u958b\\u59cb</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">\\u7d42\\u4e86</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">\\u7a3c\\u50cd</th>
                  <th className="px-3 py-2 w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row, idx) => {
                  const isHoliday = row.id === null && !row.dirty;
                  const dayLabel = new Date(row.date + "T12:00:00").toLocaleDateString("ja-JP", {
                    month: "2-digit", day: "2-digit", weekday: "short",
                  });
                  const kStr = dayK(row);
                  return (
                    <tr key={row.date} className={isHoliday ? "bg-slate-50/80" : row.dirty ? "bg-amber-50" : "bg-white"}>
                      <td className="px-4 py-2.5">
                        <span className={"text-xs font-mono font-bold " + (isHoliday ? "text-slate-400" : "text-slate-700")}>{dayLabel}</span>
                        {isHoliday && <span className="ml-1.5 text-[10px] text-slate-400 italic">&#8212; \\u4f11\\u65e5 &#8212;</span>}
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.startTime}
                          onChange={(e) => updateField(idx, "startTime", e.target.value)}
                          className={"w-20 border rounded px-2 py-1 text-xs focus:ring-1 focus:ring-teal-400 focus:outline-none "
                            + (isHoliday ? "border-slate-200 text-slate-400 bg-slate-50" : "border-slate-300")} />
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.endTime}
                          onChange={(e) => updateField(idx, "endTime", e.target.value)}
                          className={"w-20 border rounded px-2 py-1 text-xs focus:ring-1 focus:ring-teal-400 focus:outline-none "
                            + (isHoliday ? "border-slate-200 text-slate-400 bg-slate-50" : "border-slate-300")} />
                      </td>
                      <td className="px-3 py-2">
                        <span className={"text-xs font-mono font-bold "
                          + (isHoliday ? "text-slate-300" : kStr !== "0M" && kStr !== "\\u2014" ? "text-teal-700" : "text-slate-400")}>
                          {kStr}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        {row.dirty && (
                          <button onClick={() => handleSave(idx)} disabled={row.saving}
                            className="text-[11px] px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold disabled:opacity-50 transition-colors whitespace-nowrap">
                            {row.saving ? "\\u2026" : row.id === null ? "\\u767b\\u9332" : "\\u66f4\\u65b0"}
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
          <p className="text-[10px] text-slate-400">&#8251; \\u7a3c\\u50cd\\u6642\\u9593 = overlap\\uff0812:00-13:00\\u662f\\u660e\\u81ea\\u52d5\\u63a7\\u9664\\uff09</p>
          <button onClick={onClose} className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-bold rounded-lg transition-colors">\\u9589\\u3058\\u308b</button>
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
      e.returnValue = "\\u4f5c\\u696d\\u304c\\u5b8c\\u4e86\\u3057\\u3066\\u3044\\u307e\\u305b\\u3093\\u3002\\u3053\\u306e\\u30da\\u30fc\\u30b8\\u3092\\u96e2\\u308c\\u307e\\u3059\\u304b\\uff1f";
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
  }, [mcId]);

  useEffect(() => {
    if (machines.length > 0 && machineId && isNaN(parseInt(machineId))) {
      const m = machines.find(m => m.machineCode === machineId);
      if (m) setMachineId(String(m.id));
      else setMachineId("");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machines]);

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
    if (r.started_at || r.finished_at) setTimeMode("datetime"); else setTimeMode("hm");
  };

  const calcTimes = useCallback(() => {
    const cycSec2 = cycleH * 3600 + cycleM * 60 + cycleS;
    const cycPcs2 = parseInt(cyclePcs)||0;
    const cyclePerPSec = cycSec2 > 0 && cycPcs2 > 0 ? cycSec2 / cycPcs2 : null;
    const qtyN = parseInt(quantity)||0;
    const setupQtyN = parseInt(setupQty)||0;
    const totalQty  = qtyN + setupQtyN;
    const machQtyBase = qtyN > 0 && qtyN !== setupQtyN ? Math.max(1, qtyN - setupQtyN) : Math.max(1, totalQty);

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
    if (sa && ca && new Date(ca) <= new Date(sa)) return "\\u6bb5\\u53d6\\u7d42\\u4e86\\u306f\\u6bb5\\u53d6\\u958b\\u59cb\\u3088\\u308a\\u5f8c\\u306e\\u65e5\\u6642\\u3092\\u5165\\u529b\\u3057\\u3066\\u304f\\u3060\\u3055\\u3044";
    if (ca && fa && new Date(fa) <= new Date(ca)) return "\\u52a0\\u5de5\\u7d42\\u4e86\\u306f\\u6bb5\\u53d6\\u7d42\\u4e86\\uff08\\u30c1\\u30a7\\u30c3\\u30afTime\\uff09\\u3088\\u308a\\u5f8c\\u306e\\u65e5\\u6642\\u3092\\u5165\\u529b\\u3057\\u3066\\u304f\\u3060\\u3055\\u3044";
    if (sa && fa && !ca && new Date(fa) <= new Date(sa)) return "\\u52a0\\u5de5\\u7d42\\u4e86\\u306f\\u6bb5\\u53d6\\u958b\\u59cb\\u3088\\u308a\\u5f8c\\u306e\\u65e5\\u6642\\u3092\\u5165\\u529b\\u3057\\u3066\\u304f\\u3060\\u3055\\u3044";
    return null;
  };

  const handleSubmit = async () => {
    if (!token) { setSaveError("\\u8a8d\\u8a3c\\u30bb\\u30c3\\u30b7\\u30e7\\u30f3\\u304c\\u5207\\u308c\\u3066\\u3044\\u307e\\u3059\\u3002\\u518d\\u8a8d\\u8a3c\\u3057\\u3066\\u304f\\u3060\\u3055\\u3044\\u3002"); setAuthOpen(true); return; }
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
      await mcApi.createWorkRecord(mcId, body, token);
      const r = await mcApi.workRecords(mcId);
      setRecords((r as any).data ?? []);
      resetForm();
      showToast("\\u2705 \\u4f5c\\u696d\\u8a18\\u9332\\u3092\\u767b\\u9332\\u3057\\u307e\\u3057\\u305f");
      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          const logId = sbSheetLogId || parseInt(sessionStorage.getItem("sb_sheet_log_id") ?? "0");
          if (logId && token) {
            try { await mcApi.collectSetupSheet(mcId, logId, token); showToast("\\u2705 \\u6bb5\\u53d6\\u30b7\\u30fc\\u30c8\\u30d0\\u30c3\\u30af\\u5b8c\\u4e86 \\u2014 \\u56de\\u53ce\\u6e08\\u307f\\u306b\\u66f4\\u65b0\\u3057\\u307e\\u3057\\u305f"); }
            catch { showToast("\\u26a0\\ufe0f \\u4f5c\\u696d\\u8a18\\u9332\\u767b\\u9332\\u6e08\\uff08\\u56de\\u53ce\\u6e08\\u307f\\u66f4\\u65b0\\u306b\\u5931\\u6557\\uff09"); }
          }
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          setTimeout(() => router.push("/"), 1500);
        }
      }
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? e?.message ?? "\\u767b\\u9332\\u306b\\u5931\\u6557\\u3057\\u307e\\u3057\\u305f";
      setSaveError(msg);
    } finally { setSaving(false); }
  };

  void searchParams;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        {!sbMode && (
          <>
            <button onClick={() => router.push(`/mc/${mcId}`)} className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
              <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg></span>MC\\u8a73\\u7d30
            </button>
            <span className="text-slate-600">|</span>
            <button onClick={() => router.push("/")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>\\u30c0\\u30c3\\u30b7\\u30e5\\u30dc\\u30fc\\u30c9\\u3078
            </button>
          </>
        )}
        {sbMode && (
          <span className="flex items-center gap-2 bg-teal-700 border border-teal-500 rounded-lg px-3 py-1">
            <span className="bg-teal-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
            <span className="text-xs font-bold text-teal-100">\\u6bb5\\u53d6\\u30b7\\u30fc\\u30c8\\u30d0\\u30c3\\u30af \\u2014 STEP2: \\u4f5c\\u696d\\u8a18\\u9332\\u5165\\u529b</span>
            <span className="text-teal-400 text-xs">\\uff08\\u767b\\u9332\\u3067\\u56de\\u53ce\\u6e08\\u307f\\u306b\\u306a\\u308a\\u307e\\u3059\\uff09</span>
          </span>
        )}
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">\\u4f5c\\u696d\\u8a18\\u9332</span>
        <span className="ml-auto">
          {isAuthenticated && operator ? (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              \\u4f5c\\u696d\\u4e2d: {operator.name} {fmtElapsed(elapsed)}
            </span>
          ) : (
            <span className="text-[11px] text-slate-400">\\u672a\\u8a8d\\u8a3c</span>
          )}
        </span>
      </header>

      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{detail.part?.drawingNo ?? "\\u2014"}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{detail.part?.name ?? "\\u2014"}</span>
            {(detail as any).part?.mainModel && <><span className="text-slate-300 text-xl font-light">/</span><span className="text-slate-500 text-lg font-medium leading-none">{(detail as any).part.mainModel}</span></>}
            <div className="flex items-center gap-2 ml-2">
              {(detail as any).machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{(detail as any).machine.machineCode}</span>}
              <StatusBadge status={detail.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {detail.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(detail as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">\\u5de5\\u7a0bNo: {(detail as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{detail.legacyMcid ?? detail.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>\\u52a0\\u5de5ID: <span className="text-slate-700">{detail.machiningId}</span></span>
            {detail.part?.partId && <><span className="text-slate-400">|</span><span>\\u90e8\\u54c1ID: <span className="text-slate-700">{detail.part.partId}</span></span></>}
          </div>
        </div>
      )}

      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>MC\\u8a73\\u7d30
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/edit`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/></svg>\\u5909\\u66f4\\u30fb\\u767b\\u9332
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>\\u6bb5\\u53d6\\u30b7\\u30fc\\u30c8
        </button>
        <button className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>\\u4f5c\\u696d\\u8a18\\u9332
        </button>
      </nav>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-52 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="px-3 py-2 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">\\u6bb5\\u53d6\\u30b7\\u30fc\\u30c8\\u4e00\\u89a7</p>
          </div>
          {setupSheets.length === 0 ? (
            <div className="px-3 py-4 text-xs text-slate-400">\\u672a\\u56de\\u53ce\\u306a\\u3057</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {setupSheets.map(s => (
                <button key={s.id} onClick={() => setSelectedSheet(s)}
                  className={`w-full text-left px-3 py-2 text-xs transition-colors ${selectedSheet?.id===s.id ? "bg-teal-50 border-l-2 border-teal-500" : "hover:bg-slate-50"}`}>
                  <div className="font-bold text-slate-700">{fmtDate(s.printed_at)}</div>
                  <div className="text-slate-400">Ver{s.version ?? "\\u2014"} {s.operator_name ?? ""}</div>
                </button>
              ))}
            </div>
          )}
          <div className="px-3 py-2 border-t border-b border-slate-100 mt-2">
            <p className="text-[10px] font-bold text-slate-400 uppercase">\\u904e\\u53bb\\u8a18\\u9332</p>
          </div>
          {records.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-400">\\u306a\\u3057</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {records.map(r => (
                <button key={r.id} onClick={() => loadRecord(r)}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-amber-50 transition-colors ${editRecordId===r.id ? "bg-amber-50 border-l-2 border-amber-400" : ""}`}>
                  <div className="font-bold text-slate-700">{fmtDate(r.work_date)}</div>
                  <div className="text-slate-400">{r.operator_name ?? "\\u2014"} / {r.machine_code ?? "\\u2014"}</div>
                  <div className="text-slate-400">{fmtMin(r.setup_time_min)} / {fmtMin(r.machining_time_min)}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {!isAuthenticated && !sbMode && (
            <div className="m-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">&#9200;</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">\\u4f5c\\u696d\\u8a18\\u9332 \\u2014 \\u4f5c\\u696d\\u958b\\u59cb\\u524d</div>
                <div className="text-xs text-teal-600 mt-0.5">\\u62c5\\u5f53\\u8005\\u8a8d\\u8a3c\\u304c\\u5fc5\\u8981\\u3067\\u3059</div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                \\u3053\\u306e\\u4f5c\\u696d\\u3092\\u958b\\u59cb\\u3059\\u308b
              </button>
            </div>
          )}

          <div className={!isAuthenticated && !sbMode ? "opacity-40 pointer-events-none select-none px-5 pb-5" : "px-5 pb-5 pt-4"}>
            {detail && (
              <div className="bg-slate-100 rounded-xl border border-slate-200 p-3 mb-4">
                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div><span className="text-slate-400 block mb-0.5">Ver</span><span className="font-bold text-slate-700">{detail.version}</span></div>
                  <div><span className="text-slate-400 block mb-0.5">\\u767b\\u9332\\u30fb\\u51fa\\u529b\\uff08\\u6bb5\\u53d6\\u30b7\\u30fc\\u30c8\\uff09</span><span className="font-bold text-slate-700">{selectedSheet ? new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP") : "\\u2014"}</span></div>
                  <div><span className="text-slate-400 block mb-0.5">\\u56de\\u53ce\\u65e5\\u6642</span><span className="font-bold text-slate-700">{fmtNow()}</span></div>
                  <div><span className="text-slate-400 block mb-0.5">\\u30aa\\u30da\\u30ec\\u30fc\\u30bf</span><span className="font-bold text-teal-700">{operator?.name ?? "\\u2014"}</span></div>
                </div>
              </div>
            )}

            <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-teal-50 border border-teal-200 text-teal-700"}`}>
              <span>{editRecordId ? "\\u270f\\ufe0f \\u7de8\\u96c6\\u30e2\\u30fc\\u30c9" : "\\uff0b \\u65b0\\u898f\\u5165\\u529b\\u30e2\\u30fc\\u30c9"}</span>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-slate-500 mr-1">\\u5165\\u529b\\u65b9\\u6cd5:</span>
                  <button onClick={() => setTimeMode("datetime")} className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="datetime" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>\\u958b\\u59cb/\\u7d42\\u4e86\\u65e5\\u6642</button>
                  <button onClick={() => setTimeMode("hm")} className={`px-2 py-0.5 rounded font-bold transition-colors ${timeMode==="hm" ? "bg-teal-600 text-white" : "bg-white text-slate-500 border border-slate-300"}`}>h/m\\u5165\\u529b</button>
                </div>
                {editRecordId && <button onClick={resetForm} className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50">\\uff0b \\u65b0\\u898f\\u306b\\u623b\\u3059</button>}
              </div>
            </div>

            <div className="space-y-4 max-w-3xl">
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u4eca\\u56de\\u4f7f\\u7528\\u6a5f\\u68b0</label>
                    <select value={machineId} onChange={e => setMachineId(e.target.value)} className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
                      <option value="">\\u2014 \\u9078\\u629e \\u2014</option>
                      {machines.filter(m => m.isActive).map(m => <option key={m.id} value={m.id}>{m.machineCode}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u30b5\\u30a4\\u30af\\u30eb\\u30bf\\u30a4\\u30e0 / 1P</label>
                    <div className="flex items-center gap-1 flex-wrap">
                      <NumInput value={cycleH} onChange={setCycleH} /><span className="text-xs text-slate-500">H</span>
                      <NumInput value={cycleM} onChange={setCycleM} min={0} max={59} /><span className="text-xs text-slate-500">M</span>
                      <NumInput value={cycleS} onChange={setCycleS} min={0} max={59} /><span className="text-xs text-slate-500">S</span>
                      <span className="text-xs text-slate-500 ml-2">\\u500b/1\\u30b5\\u30a4\\u30af\\u30eb:</span>
                      <input type="number" min="1" value={cyclePcs} onChange={e => setCyclePcs(e.target.value)} className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-blue-700 border-b border-blue-200 pb-2">&#128295; \\u6bb5\\u53d6</h3>
                {timeMode === "hm" ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u6642\\u9593</label><TimeInput h={setupH} m={setupMm} onH={setSetupH} onM={setSetupMm} /></div>
                    <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u4e2d\\u65ad\\u6642\\u9593</label><div className="flex items-center gap-1"><NumInput value={setupInterruption} onChange={setSetupInterruption} /><span className="text-xs text-slate-500">m</span></div></div>
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
                          {setupKadouMin !== null && <span className="text-xs text-blue-700 font-bold">{"\\u6bb5\\u53d6\\u7a3c\\u50cd: " + Math.floor(setupKadouMin/60) + "H " + (setupKadouMin%60) + "M"}</span>}
                          {machKadouMin  !== null && <span className="text-xs text-green-700 font-bold">{"\\u91cf\\u7523\\u7a3c\\u50cd: " + Math.floor(machKadouMin/60)  + "H " + (machKadouMin%60)  + "M"}</span>}
                          {setupKadouMin === null && machKadouMin === null && <span className="text-xs text-slate-400">\\u30bf\\u30a4\\u30e0\\u30ab\\u30fc\\u30c9\\u3092\\u78ba\\u8a8d\\u3057\\u3066\\u7a3c\\u50cd\\u6642\\u9593\\u3092\\u53c2\\u7167</span>}
                        </div>
                        <button type="button" onClick={() => setTcModalOpen(true)}
                          className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-300 hover:bg-teal-50 hover:border-teal-400 text-slate-700 hover:text-teal-700 rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                          &#128197; \\u6a5f\\u68b0\\u30bf\\u30a4\\u30e0\\u30ab\\u30fc\\u30c9\\u53c2\\u7167
                        </button>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u958b\\u59cb</label>
                        <input type="datetime-local" value={startedAt}
                          onChange={e => { setStartedAt(e.target.value); setTimeValidErr(validateDateOrder(e.target.value, checkedAt, finishedAt)); }}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u7d42\\u4e86\\uff08\\uff83\\uff7a\\uff6f\\u30afTime\\uff09</label>
                        <input type="datetime-local" value={checkedAt}
                          onChange={e => { setCheckedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, e.target.value, finishedAt)); }}
                          className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("\\u6bb5\\u53d6\\u7d42\\u4e86") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />
                      </div>
                    </div>
                    {startedAt && checkedAt && (() => {
                      const mins = Math.max(0, Math.round((new Date(checkedAt).getTime()-new Date(startedAt).getTime())/60000) - (dStopH*60+dStopM));
                      return mins > 0 ? <p className="text-xs text-blue-600 font-bold">&#8594; \\u6bb5\\u53d6\\u6642\\u9593: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                    })()}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u6642\\u306e\\u4e2d\\u65ad</label>
                        <div className="flex items-center gap-1 flex-wrap">
                          <NumInput value={dStopH} onChange={setDStopH} /><span className="text-xs text-slate-500">h</span>
                          <NumInput value={dStopM} onChange={setDStopM} min={0} max={59} /><span className="text-xs text-slate-500">m</span>
                        </div>
                      </div>
                      <div />
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-3 gap-3">
                  <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u62c5\\u5f53\\u8005\\uff08\\u8907\\u6570\\u53ef\\uff09</label><MultiUserSelect users={users} selected={setupOps} onChange={setSetupOps} placeholder="\\u62c5\\u5f53\\u8005\\u3092\\u9078\\u629e..." /></div>
                  <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u30c1\\u30a7\\u30c3\\u30af\\u62c5\\u5f53\\uff08\\uff83\\uff7a\\uff6f\\u30afMan\\uff09</label><SingleUserSelect users={users} selected={checkMan} onChange={setCheckMan} placeholder="\\u2014 \\u9078\\u629e \\u2014" /></div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u6bb5\\u53d6\\u826f\\u54c1\\u6570</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={setupQty} onChange={e => setSetupQty(e.target.value)} className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                      <span className="text-xs text-slate-500">\\u500b</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-green-50 rounded-xl border border-green-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-green-700 border-b border-green-200 pb-2">&#9881;&#65039; \\u91cf\\u7523</h3>
                {timeMode === "hm" ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u52a0\\u5de5\\u6642\\u9593</label><TimeInput h={machH} m={machMm} onH={setMachH} onM={setMachMm} /></div>
                    <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u4e2d\\u65ad\\u6642\\u9593</label><div className="flex items-center gap-1"><NumInput value={machInterruption} onChange={setMachInterruption} /><span className="text-xs text-slate-500">m</span></div></div>
                    <div />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u52a0\\u5de5\\u7d42\\u4e86</label>
                        <input type="datetime-local" value={finishedAt}
                          onChange={e => { setFinishedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, checkedAt, e.target.value)); }}
                          className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("\\u52a0\\u5de5\\u7d42\\u4e86") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />
                      </div>
                      <div />
                    </div>
                    {checkedAt && finishedAt && (() => {
                      const mins = Math.max(0, Math.round((new Date(finishedAt).getTime()-new Date(checkedAt).getTime())/60000) - (yStopH*60+yStopM));
                      return mins > 0 ? <p className="text-xs text-green-600 font-bold">&#8594; \\u52a0\\u5de5\\u6642\\u9593: {Math.floor(mins/60)}H {mins%60}M</p> : null;
                    })()}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u91cf\\u7523\\u6642\\u306e\\u4e2d\\u65ad</label>
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
                  <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u91cf\\u7523\\u4f5c\\u696d\\u8005\\uff08\\u8907\\u6570\\u53ef\\uff09</label><MultiUserSelect users={users} selected={prodOps} onChange={setProdOps} placeholder="\\u4f5c\\u696d\\u8005\\u3092\\u9078\\u629e..." /></div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u5168\\u826f\\u54c1\\u6570\\uff08\\u30ef\\u30fc\\u30af\\u6570\\uff09</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={quantity} onChange={e => setQuantity(e.target.value)} className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                      <span className="text-xs text-slate-500">\\u500b</span>
                    </div>
                  </div>
                  <div />
                </div>
              </div>

              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-purple-700 border-b border-purple-200 pb-2">&#128190; \\u30d7\\u30ed\\u30b0\\u30e9\\u30e0</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div><label className="text-xs font-bold text-slate-500 block mb-1.5">\\u30d7\\u30ed\\u30b0\\u30e9\\u30e0\\u62c5\\u5f53</label><SingleUserSelect users={users} selected={prgMan} onChange={setPrgMan} placeholder="\\u2014 \\u9078\\u629e \\u2014" /></div>
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
                      <button type="button" onClick={() => setPrgPlas("+")} className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "+" ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-300 hover:border-teal-400"}`}>&#65291;</button>
                      <button type="button" onClick={() => setPrgPlas("-")} className={`flex-1 py-2 rounded-lg text-sm font-bold border transition-colors ${prgPlas === "-" ? "bg-red-500 text-white border-red-500" : "bg-white text-slate-600 border-slate-300 hover:border-red-300"}`}>&#65293;</button>
                      <button type="button" onClick={() => setPrgPlas("")} className="px-2 py-2 rounded-lg text-xs border border-slate-200 text-slate-400 hover:bg-slate-50">\\u30af\\u30ea\\u30a2</button>
                    </div>
                  </div>
                </div>
              </div>

              {times && (
                <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                  <h3 className="text-xs font-bold text-slate-500 mb-3">\\u6642\\u9593\\u96c6\\u8a08\\uff08\\u81ea\\u52d5\\u8a08\\u7b97\\uff09</h3>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs mb-2">
                    <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u6bb5\\u53d6\\u6642\\u9593</div><div className="font-bold text-blue-700 text-sm">{fmtMin(times.setupMin)}</div></div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u52a0\\u5de5\\u6642\\u9593</div><div className="font-bold text-teal-700 text-sm">{fmtMin(times.machMin)}</div></div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u7dcf\\u6642\\u9593</div><div className="font-bold text-slate-700 text-sm">{fmtMin(times.totalMin)}</div></div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    {times.cyclePerPSec != null && <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u30b5\\u30a4\\u30af\\u30eb\\u30bf\\u30a4\\u30e0/1P</div><div className="font-bold text-purple-700 text-sm">{fmtSec(times.cyclePerPSec)}</div></div>}
                    {times.machPerPMin  != null && <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u52a0\\u5de5\\u6642\\u9593/1P</div><div className="font-bold text-teal-600 text-sm">{fmtMin(times.machPerPMin)}</div></div>}
                    {times.totalPerPMin != null && <div className="bg-white rounded-lg p-2 border border-slate-100"><div className="text-slate-400 mb-0.5">\\u7dcf\\u6642\\u9593/1P</div><div className="font-bold text-slate-600 text-sm">{fmtMin(times.totalPerPMin)}</div></div>}
                  </div>
                </div>
              )}

              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <label className="text-xs font-bold text-slate-500 block mb-1.5">\\u5099\\u8003</label>
                <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                  placeholder="\\u554f\\u984c\\u70b9\\u30fb\\u6ce8\\u610f\\u4e8b\\u9805\\u30fb\\u7279\\u8a18\\u4e8b\\u9805"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none" />
                <div className="text-right text-xs text-slate-400 mt-1">{note.length} / 1000</div>
              </div>

              {saveError && <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">{saveError}</div>}

              <div className="flex gap-3 pb-4">
                <button onClick={handleSubmit} disabled={saving || (!isAuthenticated && !sbMode)}
                  className="flex-1 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3 rounded-xl text-sm transition-colors">
                  {saving ? "\\u767b\\u9332\\u4e2d..." : editRecordId ? "\\u2713 \\u66f4\\u65b0\\uff08\\u4fdd\\u5b58\\uff09" : "\\u2713 \\u4f5c\\u696d\\u5b8c\\u4e86\\uff08\\u767b\\u9332\\uff09"}
                </button>
                <button onClick={() => { resetForm(); if (!editRecordId) { if (sbMode) router.push("/"); else { logout(); router.push(`/mc/${mcId}`); } } }}
                  className="px-5 py-3 border border-slate-300 rounded-xl text-sm text-slate-600 hover:bg-slate-100 transition-colors">
                  &#10007; \\u30ad\\u30e3\\u30f3\\u30bb\\u30eb
                </button>
              </div>
            </div>
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
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">\\u8aad\\u307f\\u8fbc\\u307f\\u4e2d\\u2026</div>}>
      <McRecordPageInner />
    </Suspense>
  );
}
'''

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print(f"書き込み完了: {len(CONTENT.splitlines())}行")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd="/home/karkyon/projects/machcore/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print(r.stdout[-5000:])
    shutil.copy(TARGET + ".bak_clean", TARGET)
    os.remove(TARGET + ".bak_clean")
    sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r = subprocess.run(["npx", "next", "build"],
    cwd="/home/karkyon/projects/machcore/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ next build エラー:")
    print(r.stdout[-5000:])
    shutil.copy(TARGET + ".bak_clean", TARGET)
    os.remove(TARGET + ".bak_clean")
    sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True, text=True)
print("✅ pm2 restart")
subprocess.run(["git", "add", "-A"], cwd="/home/karkyon/projects/machcore")
subprocess.run(["git", "commit", "-m", "feat: record page clean rewrite - TC modal, validation, HowLong kadou"],
    cwd="/home/karkyon/projects/machcore")
r = subprocess.run(["git", "push"], cwd="/home/karkyon/projects/machcore", capture_output=True, text=True)
print("✅ git push\n" + (r.stderr.strip() or r.stdout.strip()))
os.remove(TARGET + ".bak_clean")
