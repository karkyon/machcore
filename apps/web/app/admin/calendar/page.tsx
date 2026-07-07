"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { nowJstDateString } from "@/lib/dateUtils";

const DOW = ["日", "月", "火", "水", "木", "金", "土"];

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

type CalEntry = { id: number; work_date: string; is_holiday: boolean; note: string | null };

export default function CalendarPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const today    = new Date();
  const [year,   setYear]   = useState(today.getFullYear());
  const [month,  setMonth]  = useState(today.getMonth() + 1);
  const [entries, setEntries] = useState<CalEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast,   setToast]   = useState<{ msg: string; ok: boolean } | null>(null);
  const [noteEdit, setNoteEdit] = useState<{ date: string; note: string } | null>(null);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch(`/admin/calendar?year=${year}&month=${month}`);
      setEntries(d.data ?? []);
    } catch (e: any) { showToast("取得失敗: " + e.message, false); }
    finally { setLoading(false); }
  }, [year, month]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  const toggle = async (dateStr: string, currentIsHoliday: boolean, note?: string) => {
    try {
      await apiFetch("/admin/calendar", {
        method: "POST",
        body: JSON.stringify({ work_date: dateStr, is_holiday: !currentIsHoliday, note: note ?? null }),
      });
      await fetchEntries();
    } catch (e: any) { showToast("更新失敗: " + e.message, false); }
  };

  const setHoliday = async (dateStr: string, isHoliday: boolean, note?: string) => {
    try {
      await apiFetch("/admin/calendar", {
        method: "POST",
        body: JSON.stringify({ work_date: dateStr, is_holiday: isHoliday, note: note ?? null }),
      });
      await fetchEntries();
      showToast(isHoliday ? "休日に設定しました" : "営業日に設定しました");
    } catch (e: any) { showToast("更新失敗: " + e.message, false); }
  };

  const bulkWeekend = async () => {
    if (!confirm(`${year}年の土日を全て休日として一括登録しますか？`)) return;
    try {
      const d = await apiFetch("/admin/calendar/bulk-weekend", { method: "POST", body: JSON.stringify({ year }) });
      showToast(d.message);
      await fetchEntries();
    } catch (e: any) { showToast("失敗: " + e.message, false); }
  };

  // カレンダーグリッド生成
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDow    = new Date(year, month - 1, 1).getDay();
  const entryMap    = Object.fromEntries(entries.map(e => [e.work_date, e]));

  const prevMonth = () => { if (month === 1) { setYear(y => y-1); setMonth(12); } else setMonth(m => m-1); };
  const nextMonth = () => { if (month === 12) { setYear(y => y+1); setMonth(1); } else setMonth(m => m+1); };

  return (
    <AdminLayout pathname={pathname}>

      {toast && <div className={"fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow text-white text-sm font-bold " + (toast.ok ? "bg-green-600" : "bg-red-600")}>{toast.msg}</div>}

        <main className="flex-1 overflow-hidden flex flex-col p-4 gap-2">
          <div className="flex flex-col gap-2 min-h-0 flex-1">
            <div className="flex items-center justify-between shrink-0">
              <h1 className="text-xl font-bold text-slate-800">営業カレンダー</h1>
              <div className="flex items-center gap-2">
                <button onClick={bulkWeekend}
                  className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-bold">
                  {year}年の土日を一括休日登録
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-2">
              <div className="flex items-center justify-between mb-1">
                <button onClick={prevMonth} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 text-slate-600 text-sm font-medium transition-colors shadow-sm"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>前月</button>
                <div className="flex items-center gap-3">
                  <select value={year} onChange={e => setYear(parseInt(e.target.value))}
                    className="text-sm border border-slate-200 rounded px-2 py-1 focus:outline-none">
                    {Array.from({length: 5}, (_, i) => today.getFullYear() - 2 + i).map(y => (
                      <option key={y} value={y}>{y}年</option>
                    ))}
                  </select>
                  <select value={month} onChange={e => setMonth(parseInt(e.target.value))}
                    className="text-sm border border-slate-200 rounded px-2 py-1 focus:outline-none">
                    {Array.from({length: 12}, (_, i) => i + 1).map(m => (
                      <option key={m} value={m}>{m}月</option>
                    ))}
                  </select>
                </div>
                <button onClick={nextMonth} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 text-slate-600 text-sm font-medium transition-colors shadow-sm">次月<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6"/></svg></button>
              </div>

              <div className="grid grid-cols-7 gap-0.5 mb-1">
                {DOW.map((d, i) => (
                  <div key={d} className={"text-center text-xs font-bold py-1 " + (i === 0 ? "text-red-500" : i === 6 ? "text-blue-500" : "text-slate-500")}>
                    {d}
                  </div>
                ))}
              </div>

              {loading ? (
                <div className="flex items-center justify-center h-48 text-slate-400">読み込み中...</div>
              ) : (
                <div className="grid grid-cols-7 gap-0.5">
                  {Array.from({length: firstDow}).map((_, i) => <div key={"empty"+i} />)}
                  {Array.from({length: daysInMonth}, (_, i) => {
                    const d = i + 1;
                    const dt = `${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
                    const dow = new Date(year, month - 1, d).getDay();
                    const entry = entryMap[dt];
                    const isHoliday = entry?.is_holiday === true; // DBに登録済みの休日のみ赤
                    const isWeekend = dow === 0 || dow === 6;
                    const isToday = dt === nowJstDateString();

                    return (
                      <button key={d} onClick={() => setHoliday(dt, !isHoliday, entry?.note ?? undefined)}
                        title={entry?.note ?? (isWeekend ? (dow===0?"日曜":"土曜") : "")}
                        className={"relative h-12 rounded flex flex-col items-center justify-center text-xs font-bold transition-colors border " +
                          (isToday ? "ring-2 ring-sky-400 " : "") +
                          (isHoliday
                            ? "bg-red-50 border-red-200 text-red-600 hover:bg-red-100"
                            : "bg-white border-slate-200 text-slate-700 hover:bg-teal-50 hover:border-teal-300")}>
                        <span>{d}</span>
                        {isHoliday && <span className="text-[9px] font-normal mt-0.5">{entry?.note ? entry.note.slice(0,4) : (isWeekend ? (dow===0?"日":"土") : "休")}</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h2 className="text-xs font-bold text-slate-600 mb-3">凡例・操作方法</h2>
              <div className="flex items-center gap-6 text-xs text-slate-500">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-red-50 border border-red-200"></div>
                  <span>休日（タイムカード自動生成スキップ）</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-white border border-slate-200"></div>
                  <span>営業日（タイムカード自動生成対象）</span>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-2">※ 日付をクリックして休日/営業日を切り替えます</p>
            </div>
          </div>
        </main>
    </AdminLayout>
  );
}
