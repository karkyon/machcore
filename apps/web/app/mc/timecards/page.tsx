"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TODAY = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  return res.json();
};

function fmtTime(dt: any): string {
  if (!dt) return "";
  const s = typeof dt === "string" ? dt : String(dt);
  // "1970-01-01T08:00:00.000Z" 形式（PostgreSQL Time型）
  if (s.endsWith("Z") && s.includes("T")) {
    const d = new Date(s);
    return String(d.getUTCHours()).padStart(2,"0") + ":" + String(d.getUTCMinutes()).padStart(2,"0");
  }
  // "08:00:00" 形式
  if (/^\d{2}:\d{2}/.test(s)) return s.slice(0, 5);
  // "2026-05-25T08:00:00" (ローカル)
  if (s.includes("T")) return s.slice(11, 16);
  return s;
}

function calcKadouMin(start: string, end: string): number {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  if (isNaN(sh) || isNaN(eh)) return 0;
  let diff = (eh * 60 + em) - (sh * 60 + sm);
  if (diff < 0) diff += 24 * 60;
  if (sh < 13 && eh >= 13) diff -= 60;
  return Math.max(0, diff);
}

function fmtMin(min: number): string {
  if (min <= 0) return "—";
  return `${min}m`;
}

interface RowState {
  id: number;
  machineName: string;
  systemType: string;
  startTime: string;
  endTime: string;
  note: string;
  dirty: boolean;
  saving: boolean;
}

export default function TimecardPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [adminUser,  setAdminUser]  = useState<{ name: string } | null>(null);
  const [workDate,   setWorkDate]   = useState(TODAY());
  const [sysType,    setSysType]    = useState<"MC"|"NC">("MC");
  const [rows,       setRows]       = useState<RowState[]>([]);
  const [loading,    setLoading]    = useState(false);
  const [toast,      setToast]      = useState<string | null>(null);
  const [toastOk,    setToastOk]    = useState(true);

  const showToast = useCallback((msg: string, ok = true) => {
    setToast(msg); setToastOk(ok); setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token) { router.replace("/admin/login"); return; }
    if (user) { try { setAdminUser(JSON.parse(user)); } catch {} }
  }, [router]);

  const loadData = useCallback(async (date: string) => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/timecards?work_date=${date}`);
      const cards: any[] = Array.isArray(data) ? data : (data.data ?? []);
      setRows(cards.map((c: any) => ({
        id:          c.id,
        machineName: c.machine?.machineName ?? c.machine?.machineCode ?? String(c.machine_id),
        systemType:  c.machine?.systemType ?? "MC",
        startTime:   fmtTime(c.start_time),
        endTime:     fmtTime(c.end_time),
        note:        c.note ?? "",
        dirty:       false,
        saving:      false,
      })));
    } catch (e: any) {
      showToast(`データ取得失敗: ${e.message}`, false);
    } finally { setLoading(false); }
  }, [showToast]);

  useEffect(() => { loadData(workDate); }, [workDate, loadData]);

  const updateRow = (idx: number, field: "startTime" | "endTime" | "note", value: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value, dirty: true } : r));
  };

  const handleUpdate = useCallback(async (idx: number) => {
    const row = rows[idx];
    if (!row.startTime || !row.endTime) { showToast("⚠️ 開始・終了時刻を入力してください", false); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      await apiFetch(`/admin/timecards/${row.id}`, {
        method: "PUT",
        body: JSON.stringify({ start_time: row.startTime + ":00", end_time: row.endTime + ":00", note: row.note || undefined }),
      });
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.machineName} 更新しました`, true);
    } catch (e: any) {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast(`❌ 更新失敗: ${e.message}`, false);
    }
  }, [rows, showToast]);

  const handleAllUpdate = useCallback(async () => {
    const dirtyRows = filteredRows.filter(r => r.dirty && r.startTime && r.endTime);
    if (dirtyRows.length === 0) { showToast("変更なし"); return; }
    setRows(prev => prev.map(r => r.dirty ? { ...r, saving: true } : r));
    let ok = 0, ng = 0;
    const results = await Promise.allSettled(
      dirtyRows.map(row =>
        apiFetch(`/admin/timecards/${row.id}`, {
          method: "PUT",
          body: JSON.stringify({ start_time: row.startTime + ":00", end_time: row.endTime + ":00", note: row.note || undefined }),
        })
      )
    );
    results.forEach(r => { if (r.status === "fulfilled") ok++; else ng++; });
    await loadData(workDate);
    if (ng === 0) showToast(`✅ ${ok}件を保存しました`, true);
    else          showToast(`⚠️ ${ok}件成功、${ng}件失敗`, false);
  }, [rows, workDate, loadData, showToast]);

  const setAllTime = (field: "startTime" | "endTime", val: string) => {
    setRows(prev => prev.map(r => ({ ...r, [field]: val, dirty: true })));
    showToast(`全機械の${field === "startTime" ? "開始" : "終了"}を${val}にセット`);
  };

  const filteredRows = rows.filter(r => r.systemType === sysType);
  const dirtyCount = filteredRows.filter(r => r.dirty).length;

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">


      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toastOk ? "bg-green-600" : "bg-red-600"}`}>
          {toast}
        </div>
      )}


        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">機械タイムカード</h1>
            <span className="text-xs text-slate-400">稼働時間一覧（昼休み12:00-13:00跨ぎ -60分補正）</span>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
            <label className="text-sm font-bold text-slate-600">日付</label>
            <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            <button onClick={() => setWorkDate(TODAY())} className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-bold">今日</button>
            <button onClick={() => loadData(workDate)} className="text-xs px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg font-bold">↺ 再読込</button>
            <div className="flex items-center gap-1 ml-2">
              {(["MC","NC"] as const).map(t => (
                <button key={t} onClick={() => setSysType(t)}
                  className={`text-xs px-3 py-1.5 rounded-lg font-bold border transition-colors ${
                    sysType === t ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
                  }`}>{t}</button>
              ))}
            </div>
            <span className="text-xs text-slate-400">{filteredRows.length}件</span>
            <div className="ml-auto flex items-center gap-2 flex-wrap">
              <button onClick={() => setAllTime("startTime","08:00")} className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg font-bold whitespace-nowrap">全機械 08:00開始</button>
              <button onClick={() => setAllTime("endTime","17:00")} className="text-xs px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 border border-blue-200 rounded-lg font-bold whitespace-nowrap">全機械 17:00終了</button>
              <button onClick={() => setAllTime("endTime","19:00")} className="text-xs px-3 py-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 border border-purple-200 rounded-lg font-bold whitespace-nowrap">全機械 19:00終了</button>
              {dirtyCount > 0 && (
                <button onClick={handleAllUpdate} className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded-lg whitespace-nowrap">
                  💾 {dirtyCount}件を一括更新
                </button>
              )}
            </div>
          </div>

          {/* 固定ヘッダーテーブル */}
          <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
            <div className="shrink-0 border-b border-slate-200">
              <table className="w-full text-sm table-fixed">
                <colgroup>
                  <col className="w-44"/><col className="w-28"/><col className="w-28"/>
                  <col className="w-20"/><col className="w-44"/><col className="w-20"/>
                </colgroup>
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs uppercase">
                    <th className="px-4 py-3 text-left font-bold">機械名</th>
                    <th className="px-3 py-3 text-left font-bold">開始時刻</th>
                    <th className="px-3 py-3 text-left font-bold">終了時刻</th>
                    <th className="px-3 py-3 text-left font-bold">稼働時間</th>
                    <th className="px-3 py-3 text-left font-bold">備考</th>
                    <th className="px-3 py-3 text-center font-bold">更新</th>
                  </tr>
                </thead>
              </table>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="text-center py-20 text-slate-400">読み込み中…</div>
              ) : rows.length === 0 ? (
                <div className="text-center py-20 text-slate-400">
                  <p className="mb-1">データがありません</p>
                  <p className="text-xs">毎朝5:00に自動生成されます</p>
                </div>
              ) : (
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-44"/><col className="w-28"/><col className="w-28"/>
                    <col className="w-20"/><col className="w-44"/><col className="w-20"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filteredRows.map((row, idx) => {
                      const kadou = calcKadouMin(row.startTime, row.endTime);
                      return (
                        <tr key={row.id} className={`${row.dirty ? "bg-orange-50" : idx%2===0?"bg-white":"bg-slate-50/30"}`}>
                          <td className="px-4 py-2 text-slate-800 text-sm font-medium truncate">{row.machineName}</td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.startTime} onChange={e => updateRow(idx, "startTime", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-24 focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.endTime} onChange={e => updateRow(idx, "endTime", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-24 focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-2 text-xs font-bold text-slate-700">{fmtMin(kadou)}</td>
                          <td className="px-3 py-1.5">
                            <input type="text" value={row.note} onChange={e => updateRow(idx, "note", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-full focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-2 text-center">
                            {row.dirty && (
                              <button onClick={() => handleUpdate(idx)} disabled={row.saving}
                                className="text-xs px-2 py-1 bg-sky-600 hover:bg-sky-700 text-white rounded font-bold disabled:opacity-50">
                                {row.saving ? "…" : "更新"}
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
          </div>
        </main>
    </AdminLayout>
  );
}
