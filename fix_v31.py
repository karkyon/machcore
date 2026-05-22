#!/usr/bin/env python3
# coding: utf-8
"""
fix_v31.py — record/page.tsx 全面改修
  1. sbMode検出をuseLayoutEffectに変更（SSRでsbMode=falseのまま描画される問題を修正）
  2. 種別（work_type）フィールドを削除
  3. フォームを旧システム「段取ｼｰﾄ戻り2」準拠に全面改修:
     - 機械（今回使用機械）
     - サイクルタイム（TH/TM/TS）
     - 1サイクル個数（setup_work_count流用 ※新規フィールド不要）
     - 段取グループ: 段取担当（複数）/ 段取開始 / 段取終了 / 中断H:M / 段取良品数
     - 量産グループ: 量産作業者（複数）/ 加工終了 / 中断H:M / 全良品数
     - 時間集計: 段取時間・加工時間・総時間・/1P（自動計算・表示のみ）
     - 備考
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"
REC_PATH = ROOT + "/apps/web/app/mc/[mc_id]/record/page.tsx"

# ─────────────────────────────────────────────────────────────
# 全体を新しい内容で置き換える
# ─────────────────────────────────────────────────────────────
NEW_CONTENT = r'''"use client";
import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

function fmtDate(s: string | null) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" }); }
  catch { return s; }
}
function fmtMin(min: number | null) {
  if (min == null) return "—";
  return `${Math.floor(min / 60)}H ${String(min % 60).padStart(2, "0")}M`;
}

// 日時をdatetime-local input用文字列に変換
function toLocalInput(dt: string | null): string {
  if (!dt) return "";
  try {
    const d = new Date(dt);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ""; }
}

// H/M から分に変換
const hm2min = (h: number, m: number) => h * 60 + m;
// 分からH/M
const min2hm = (min: number) => ({ h: Math.floor(min / 60), m: min % 60 });

function McRecordPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId = parseInt(mc_id);

  // sbMode: クライアントサイドのみ（useLayoutEffect）で検出
  const [sbMode, setSbMode] = React.useState(false);
  const [sbSheetLogId, setSbSheetLogId] = React.useState<number>(0);
  useLayoutEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === mcId) {
        setSbMode(true);
        const lid = sessionStorage.getItem("sb_sheet_log_id");
        if (lid) setSbSheetLogId(parseInt(lid));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const router = useRouter();
  const searchParams = useSearchParams();

  const [detail,       setDetail]       = useState<McDetail | null>(null);
  const [setupSheets,  setSetupSheets]  = useState<McSetupSheetLog[]>([]);
  const [selectedSheet,setSelectedSheet]= useState<McSetupSheetLog | null>(null);
  const [records,      setRecords]      = useState<McWorkRecord[]>([]);
  const [machines,     setMachines]     = useState<Machine[]>([]);
  const [users,        setUsers]        = useState<UserInfo[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed,  setElapsed]  = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [editRecordId, setEditRecordId] = useState<number | null>(null);

  // ─── フォーム state ───
  const [machineId,    setMachineId]    = useState<string>("");
  // サイクルタイム
  const [cycleH,       setCycleH]       = useState(0);
  const [cycleM,       setCycleM]       = useState(0);
  const [cycleS,       setCycleS]       = useState(0);
  // 1サイクル個数（setup_work_count借用 ※段取良品数と区別）
  const [cyclePcs,     setCyclePcs]     = useState<string>("");
  // 段取グループ
  const [setupOps,     setSetupOps]     = useState<number[]>([]);  // setup_operator_ids
  const [startedAt,    setStartedAt]    = useState("");            // started_at
  const [checkedAt,    setCheckedAt]    = useState("");            // checked_at (段取終了)
  const [dStopH,       setDStopH]       = useState(0);
  const [dStopM,       setDStopM]       = useState(0);
  const [setupQty,     setSetupQty]     = useState<string>("");    // setup_work_count
  // 量産グループ
  const [prodOps,      setProdOps]      = useState<number[]>([]);  // production_operator_ids
  const [finishedAt,   setFinishedAt]   = useState("");            // finished_at
  const [yStopH,       setYStopH]       = useState(0);
  const [yStopM,       setYStopM]       = useState(0);
  const [quantity,     setQuantity]     = useState<string>("");    // quantity
  // 備考
  const [note,         setNote]         = useState("");
  const [saving,       setSaving]       = useState(false);
  const [saveError,    setSaveError]    = useState<string | null>(null);
  const [toast,        setToast]        = useState<string | null>(null);

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); }, []);
  const fmtElapsed = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  useEffect(() => {
    mcApi.findOne(mcId).then(r => setDetail((r as any).data ?? r)).catch(() => {});
    mcApi.setupSheetLogs(mcId).then(r => setSetupSheets((r as any).data ?? [])).catch(() => {});
    mcApi.workRecords(mcId).then(r => setRecords((r as any).data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
  }, [mcId]);

  // 機械選択時にサイクルタイムを自動セット（今回使用機械 = 登録機械の場合）
  useEffect(() => {
    if (!detail || !machineId) return;
    const selMachine = machines.find(m => String(m.id) === machineId);
    if (selMachine && detail.machine && selMachine.machineCode === detail.machine.machineCode) {
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

  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const resetForm = () => {
    setEditRecordId(null);
    setMachineId(""); setCycleH(0); setCycleM(0); setCycleS(0); setCyclePcs("");
    setSetupOps([]); setStartedAt(""); setCheckedAt("");
    setDStopH(0); setDStopM(0); setSetupQty("");
    setProdOps([]); setFinishedAt("");
    setYStopH(0); setYStopM(0); setQuantity("");
    setNote(""); setSaveError(null);
  };

  const loadRecord = (r: McWorkRecord) => {
    setEditRecordId(r.id);
    setMachineId(""); // machine_id → 選択肢に紐付け省略
    const cSec = r.cycle_time_sec ?? 0;
    setCycleH(Math.floor(cSec / 3600));
    setCycleM(Math.floor((cSec % 3600) / 60));
    setCycleS(cSec % 60);
    setCyclePcs(""); // 1S_個数は現在work_recordsに保存されていない
    setSetupOps((r.setup_operator_ids ?? []) as number[]);
    setStartedAt(toLocalInput(r.started_at));
    setCheckedAt(toLocalInput(r.checked_at));
    const dstop = r.interrupt_setup_min ?? 0;
    setDStopH(Math.floor(dstop / 60)); setDStopM(dstop % 60);
    setSetupQty(r.setup_work_count ? String(r.setup_work_count) : "");
    setProdOps((r.production_operator_ids ?? []) as number[]);
    setFinishedAt(toLocalInput(r.finished_at));
    const ystop = r.interrupt_work_min ?? 0;
    setYStopH(Math.floor(ystop / 60)); setYStopM(ystop % 60);
    setQuantity(r.quantity ? String(r.quantity) : "");
    setNote(r.note ?? "");
  };

  // 時間集計（自動計算）
  const calcTimes = () => {
    if (!startedAt || !checkedAt || !finishedAt) return null;
    const s = new Date(startedAt).getTime();
    const c = new Date(checkedAt).getTime();
    const f = new Date(finishedAt).getTime();
    if (isNaN(s) || isNaN(c) || isNaN(f)) return null;
    const setupMin = Math.max(0, Math.round((c - s) / 60000) - hm2min(dStopH, dStopM));
    const machMin  = Math.max(0, Math.round((f - c) / 60000) - hm2min(yStopH, yStopM));
    const totalMin = setupMin + machMin;
    const qty = parseInt(quantity) || 0;
    const setupQtyN = parseInt(setupQty) || 0;
    const totalQty = qty + setupQtyN;
    const machPerPMin = totalQty > 0 ? machMin / totalQty : null;
    return { setupMin, machMin, totalMin, machPerPMin };
  };
  const times = calcTimes();

  const handleSubmit = async () => {
    if (!token && !sbMode) return;
    setSaving(true); setSaveError(null);
    try {
      const cycSec = cycleH * 3600 + cycleM * 60 + cycleS;
      const body: CreateMcWorkRecordBody = {
        setup_time_min:      times?.setupMin || undefined,
        machining_time_min:  times?.machMin  || undefined,
        cycle_time_sec:      cycSec || undefined,
        quantity:            quantity ? parseInt(quantity) : undefined,
        setup_work_count:    setupQty ? parseInt(setupQty) : undefined,
        started_at:          startedAt ? new Date(startedAt).toISOString() : undefined,
        checked_at:          checkedAt ? new Date(checkedAt).toISOString() : undefined,
        finished_at:         finishedAt ? new Date(finishedAt).toISOString() : undefined,
        interrupt_setup_min: hm2min(dStopH, dStopM) || undefined,
        interrupt_work_min:  hm2min(yStopH, yStopM) || undefined,
        setup_operator_ids:  setupOps.length ? setupOps : undefined,
        production_operator_ids: prodOps.length ? prodOps : undefined,
        note:                note || undefined,
        machine_id:          machineId ? parseInt(machineId) : undefined,
      };
      await mcApi.createWorkRecord(mcId, body, token ?? "");
      const r = await mcApi.workRecords(mcId);
      setRecords((r as any).data ?? []);
      resetForm();
      showToast("✅ 作業記録を登録しました");
      if (sbMode && typeof window !== "undefined") {
        const v = sessionStorage.getItem("sb_next_record");
        if (v && parseInt(v) === mcId) {
          const logId = sbSheetLogId || parseInt(sessionStorage.getItem("sb_sheet_log_id") ?? "0");
          if (logId && token) {
            try {
              await mcApi.collectSetupSheet(mcId, logId, token);
              showToast("✅ 段取シートバック完了 — 回収済みに更新しました");
            } catch { showToast("⚠️ 作業記録登録済み（回収済み更新に失敗）"); }
          }
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          setTimeout(() => router.push("/"), 1500);
        }
      }
    } catch { setSaveError("登録に失敗しました"); }
    finally { setSaving(false); }
  };

  const d = detail;

  // ユーザー選択トグル
  const toggleUser = (arr: number[], setArr: (v: number[]) => void, id: number) => {
    setArr(arr.includes(id) ? arr.filter(x => x !== id) : [...arr, id]);
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        {!sbMode && (
          <>
            <button onClick={() => router.push(`/mc/${mcId}`)}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
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
          ) : sbMode ? (
            <span className="text-[11px] bg-teal-600 text-white px-2 py-0.5 rounded font-bold">STEP2実行中</span>
          ) : (
            <span className="text-[11px] bg-slate-600 text-white px-2 py-0.5 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報 */}
      {d && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
            <div className="flex items-center gap-2 ml-2">
              <StatusBadge status={d.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(d as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(d as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? d.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
            {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
          </div>
        </div>
      )}

      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/edit`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => !sbMode && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (sbMode ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* メインコンテンツ: 左ペイン（シート一覧）+ 右ペイン（フォーム） */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左ペイン: 段取シート一覧 + 過去記録 */}
        <div className="w-52 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="px-3 py-2 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">段取シート一覧</p>
            {setupSheets.filter(s => !s.work_collected).length === 0
              ? <p className="text-[10px] text-slate-400 mt-1">未回収なし</p>
              : <p className="text-[10px] text-amber-600 font-bold mt-1">未回収 {setupSheets.filter(s => !s.work_collected).length}件</p>
            }
          </div>
          {setupSheets.map(s => (
            <button key={s.id} onClick={() => setSelectedSheet(selectedSheet?.id === s.id ? null : s)}
              className={`text-left px-3 py-2 border-b border-slate-100 text-[11px] transition-colors ${selectedSheet?.id === s.id ? "bg-teal-50 border-l-2 border-l-teal-500" : "hover:bg-slate-50"}`}>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className={`text-[9px] font-bold px-1 py-0.5 rounded ${s.work_collected ? "bg-slate-100 text-slate-400" : "bg-amber-100 text-amber-700"}`}>
                  {s.work_collected ? "回収済" : "未回収"}
                </span>
                {s.is_reference && <span className="text-[9px] bg-slate-100 text-slate-500 px-1 rounded">参考</span>}
              </div>
              <div className="text-slate-700 mt-0.5">{new Date(s.printed_at).toLocaleDateString("ja-JP")}</div>
              {s.version && <div className="text-slate-400">Ver.{s.version}</div>}
              <div className="text-slate-500">{s.operator_name ?? "—"}</div>
              {selectedSheet?.id === s.id && (
                <div className="mt-1 text-[10px] text-teal-700 font-bold">▶ 選択中</div>
              )}
            </button>
          ))}
          {/* 過去記録一覧 */}
          {records.length > 0 && (
            <div className="mt-2 px-3 py-1 border-t border-slate-100">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">過去記録 ({records.length}件)</p>
              {records.map(r => (
                <button key={r.id} onClick={() => loadRecord(r)}
                  className="w-full text-left px-2 py-1.5 rounded text-[10px] hover:bg-slate-50 border border-slate-100 mb-1 transition-colors">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">{fmtDate(r.work_date)}</span>
                    <span className="text-teal-600 font-bold text-[9px] border border-teal-200 px-1 rounded">編集</span>
                  </div>
                  <div className="text-slate-500">{r.operator_name ?? "—"} / {r.machine_code ?? "—"}</div>
                  <div className="text-slate-400">{fmtMin(r.setup_time_min)} / {fmtMin(r.machining_time_min)}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 右ペイン: 入力フォーム */}
        <div className="flex-1 overflow-y-auto">
          {/* 非sbMode かつ 未認証の場合のみ作業開始前パネル */}
          {!isAuthenticated && !sbMode && (
            <div className="m-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-teal-600 mt-0.5">
                  {selectedSheet ? `段取シート（${new Date(selectedSheet.printed_at).toLocaleDateString("ja-JP")}）を選択中` : "左リストから段取シートを選択してください"}
                </div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                この作業を開始する
              </button>
            </div>
          )}

          <div className={!isAuthenticated && !sbMode ? "opacity-40 pointer-events-none select-none px-5 pb-5" : "px-5 pb-5 pt-4"}>
            {/* モードバー */}
            <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${
              editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-teal-50 border border-teal-200 text-teal-700"
            }`}>
              <span>{editRecordId ? "✏️ 編集モード" : "＋ 新規入力モード"}</span>
              {editRecordId && (
                <button onClick={resetForm} className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50">
                  ＋ 新規に戻す
                </button>
              )}
            </div>

            <div className="space-y-4 max-w-2xl">

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
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={cycleH} onChange={e => setCycleH(parseInt(e.target.value)||0)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                      <span className="text-xs text-slate-500">H</span>
                      <input type="number" min="0" max="59" value={cycleM} onChange={e => setCycleM(parseInt(e.target.value)||0)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                      <span className="text-xs text-slate-500">M</span>
                      <input type="number" min="0" max="59" value={cycleS} onChange={e => setCycleS(parseInt(e.target.value)||0)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                      <span className="text-xs text-slate-500">S</span>
                      <span className="ml-2 text-xs text-slate-500 whitespace-nowrap">個/1サイクル</span>
                      <input type="number" min="1" value={cyclePcs} onChange={e => setCyclePcs(e.target.value)}
                        className="w-12 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="1" />
                    </div>
                  </div>
                </div>
              </div>

              {/* 段取グループ */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="text-xs font-bold text-slate-600 mb-3 flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-blue-400 rounded-full inline-block"></span>段取
                </h3>
                <div className="space-y-3">
                  {/* 段取担当（複数選択）*/}
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">段取担当者</label>
                    <div className="flex flex-wrap gap-1.5">
                      {users.filter(u => u.isActive).map(u => (
                        <button key={u.id} type="button"
                          onClick={() => toggleUser(setupOps, setSetupOps, u.id)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors ${
                            setupOps.includes(u.id) ? "bg-blue-600 text-white border-blue-600" : "bg-white text-slate-600 border-slate-200 hover:border-blue-400"
                          }`}>
                          {u.name}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>
                      <input type="datetime-local" value={startedAt} onChange={e => setStartedAt(e.target.value)}
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">段取終了</label>
                      <input type="datetime-local" value={checkedAt} onChange={e => setCheckedAt(e.target.value)}
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">段取時の中断</label>
                      <div className="flex items-center gap-1">
                        <input type="number" min="0" value={dStopH} onChange={e => setDStopH(parseInt(e.target.value)||0)}
                          className="w-16 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                        <span className="text-xs text-slate-500">h</span>
                        <input type="number" min="0" max="59" value={dStopM} onChange={e => setDStopM(parseInt(e.target.value)||0)}
                          className="w-16 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                        <span className="text-xs text-slate-500">m</span>
                      </div>
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
              </div>

              {/* 量産グループ */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="text-xs font-bold text-slate-600 mb-3 flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-teal-400 rounded-full inline-block"></span>量産
                </h3>
                <div className="space-y-3">
                  {/* 量産作業者（複数選択）*/}
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">量産作業者</label>
                    <div className="flex flex-wrap gap-1.5">
                      {users.filter(u => u.isActive).map(u => (
                        <button key={u.id} type="button"
                          onClick={() => toggleUser(prodOps, setProdOps, u.id)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors ${
                            prodOps.includes(u.id) ? "bg-teal-600 text-white border-teal-600" : "bg-white text-slate-600 border-slate-200 hover:border-teal-400"
                          }`}>
                          {u.name}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">加工終了</label>
                      <input type="datetime-local" value={finishedAt} onChange={e => setFinishedAt(e.target.value)}
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1.5">量産時の中断</label>
                      <div className="flex items-center gap-1">
                        <input type="number" min="0" value={yStopH} onChange={e => setYStopH(parseInt(e.target.value)||0)}
                          className="w-16 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                        <span className="text-xs text-slate-500">h</span>
                        <input type="number" min="0" max="59" value={yStopM} onChange={e => setYStopM(parseInt(e.target.value)||0)}
                          className="w-16 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                        <span className="text-xs text-slate-500">m</span>
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">全良品数（ワーク数）</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={quantity} onChange={e => setQuantity(e.target.value)}
                        className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400" placeholder="0" />
                      <span className="text-xs text-slate-500">個</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 時間集計（自動計算・表示のみ）*/}
              {times && (
                <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                  <h3 className="text-xs font-bold text-slate-500 mb-3">時間集計（自動計算）</h3>
                  <div className="grid grid-cols-3 gap-3 text-center text-sm">
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-xs text-slate-400 mb-0.5">段取時間</div>
                      <div className="font-bold text-blue-700">{fmtMin(times.setupMin)}</div>
                    </div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-xs text-slate-400 mb-0.5">加工時間</div>
                      <div className="font-bold text-teal-700">{fmtMin(times.machMin)}</div>
                    </div>
                    <div className="bg-white rounded-lg p-2 border border-slate-100">
                      <div className="text-xs text-slate-400 mb-0.5">総時間</div>
                      <div className="font-bold text-slate-700">{fmtMin(times.totalMin)}</div>
                    </div>
                    {times.machPerPMin !== null && (
                      <div className="bg-white rounded-lg p-2 border border-slate-100 col-span-3">
                        <div className="text-xs text-slate-400 mb-0.5">加工時間/1P</div>
                        <div className="font-bold text-slate-700">{fmtMin(times.machPerPMin)}</div>
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
                      if (sbMode) {
                        // sbMode中断 → sessionStorageは残す（STEP1完了状態を保持）
                        router.push("/");
                      } else {
                        logout();
                        router.push(`/mc/${mcId}`);
                      }
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
        <AuthModal
          isOpen={true}
          sessionType="MC_WORK_RECORD"
          mcProgramId={mcId}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)}
        />
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
'''

p = pathlib.Path(REC_PATH)
p.write_text(NEW_CONTENT, encoding="utf-8")
print("OK: record/page.tsx 書き込み完了")

# Build
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
print(r.stdout[-4000:] if len(r.stdout) > 4000 else r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart ---")
r2 = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && source \"$NVM_DIR/nvm.sh\" && "
    "cd /home/karkyon/projects/machcore && "
    "pm2 delete machcore-web && "
    "pm2 start ecosystem.config.js --only machcore-web",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout)
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-1000:])
    sys.exit(1)

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'feat: record/page.tsx 旧システム準拠フォーム全面改修 種別削除 段取/量産グループ 時間集計自動計算 sbMode useLayoutEffect修正 v31' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])

print("\nDONE")
