"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TODAY = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};

const SIDEBAR_ITEMS = [
  { href: "/admin/users",       label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",    label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",      label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",    label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/calendar",    label: "営業カレンダー",   icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" },
  { href: "/admin/raw",         label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor",  label: "PDFエディタ",      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
  { href: "/admin/system-logs", label: "システムログ",     icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
];

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
  const h = Math.floor(min / 60), m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? m+"m" : ""}` : `${m}m`;
}

interface RowState {
  id: number;
  machineName: string;
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
    const dirtyRows = rows.filter(r => r.dirty && r.startTime && r.endTime);
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

  const dirtyCount = rows.filter(r => r.dirty).length;

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {adminUser && <span className="text-xs text-slate-500">{adminUser.name}（管理者）</span>}
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toastOk ? "bg-green-600" : "bg-red-600"}`}>
          {toast}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

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
            <span className="text-xs text-slate-400">{rows.length}件</span>
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
                    {rows.map((row, idx) => {
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
      </div>
    </div>
  );
}
