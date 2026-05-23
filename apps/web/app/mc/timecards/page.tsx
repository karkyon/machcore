"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TODAY = () => new Date().toISOString().slice(0, 10);

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];

// admin token使用のfetch（CORSなし、axiosインターセプター不使用）
const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

function fmtTime(dt: any): string {
  if (!dt) return "";
  const s = typeof dt === "string" ? dt : String(dt);
  if (s.includes("T") && s.endsWith("Z")) {
    const d = new Date(s);
    return String(d.getUTCHours()).padStart(2,"0") + ":" + String(d.getUTCMinutes()).padStart(2,"0");
  }
  if (s.includes("T")) return s.slice(11, 16);
  return s.slice(0, 5);
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
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? m+"m" : ""}` : `${m}m`;
}

interface RowState {
  id: number;
  machineCode: string;
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

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token) { router.replace("/admin/login"); return; }
    if (user) { try { setAdminUser(JSON.parse(user)); } catch {} }
  }, [router]);

  const handleLogout = () => {
    sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user");
    router.push("/admin/login");
  };

  const loadData = useCallback(async (date: string) => {
    setLoading(true);
    try {
      const data = await apiFetch(`/mc/timecards/all?work_date=${date}`);
      const cards: any[] = Array.isArray(data) ? data : (data.data ?? []);
      setRows(cards.map((c: any) => ({
        id:          c.id,
        machineCode: c.machine?.machineCode ?? String(c.machine_id),
        startTime:   fmtTime(c.start_time),
        endTime:     fmtTime(c.end_time),
        note:        c.note ?? "",
        dirty:       false,
        saving:      false,
      })));
    } catch (e) {
      console.error("[TC] loadData error", e);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(workDate); }, [workDate, loadData]);

  const updateRow = (idx: number, field: keyof RowState, value: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value, dirty: true } : r));
  };

  // 1行更新（単体）
  const handleUpdate = useCallback(async (idx: number) => {
    const row = rows[idx];
    if (!row.startTime || !row.endTime) { showToast("⚠️ 開始・終了時刻を入力してください"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      await apiFetch(`/mc/timecards/${row.id}`, {
        method: "PUT",
        body: JSON.stringify({ start_time: row.startTime + ":00", end_time: row.endTime + ":00", note: row.note || undefined }),
      });
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.machineCode} 更新しました`);
    } catch {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast("❌ 更新に失敗しました");
    }
  }, [rows, showToast]);

  // 全件一括更新: dirtyな行をすべてPUT → 完了後にDBから再読込して確認
  const handleAllUpdate = useCallback(async () => {
    const dirtyRows = rows.filter(r => r.dirty && r.startTime && r.endTime);
    if (dirtyRows.length === 0) { showToast("変更なし"); return; }
    // 保存中UIに切り替え
    setRows(prev => prev.map(r => r.dirty ? { ...r, saving: true } : r));
    let ok = 0, ng = 0;
    // 並列PUT（Promise.allSettled）
    const results = await Promise.allSettled(
      dirtyRows.map(row =>
        apiFetch(`/mc/timecards/${row.id}`, {
          method: "PUT",
          body: JSON.stringify({
            start_time: row.startTime + ":00",
            end_time:   row.endTime   + ":00",
            note:       row.note || undefined,
          }),
        })
      )
    );
    results.forEach(r => { if (r.status === "fulfilled") ok++; else ng++; });
    // 完了後にDBから再読込（保存済みデータを表示）
    await loadData(workDate);
    if (ng === 0) showToast(`✅ ${ok}件を更新・保存しました`);
    else          showToast(`⚠️ ${ok}件成功、${ng}件失敗`);
  }, [rows, workDate, loadData, showToast]);

  const setAllTime = (field: "startTime" | "endTime", val: string) => {
    setRows(prev => prev.map(r => ({ ...r, [field]: val, dirty: true })));
    showToast(`全機械の${field === "startTime" ? "開始" : "終了"}時刻を ${val} にセットしました`);
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
          {adminUser && <span className="text-xs text-slate-400">{adminUser.name}（管理者）</span>}
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
        </div>
      </header>

      {toast && <div className="fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-bold z-50 bg-slate-800">{toast}</div>}

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

        <main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">
          {/* ツールバー固定 */}
          <div className="bg-white rounded-xl border border-slate-200 px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
            <label className="text-sm font-bold text-slate-600">日付</label>
            <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            <button onClick={() => setWorkDate(TODAY())} className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-bold">今日</button>
            <button onClick={() => loadData(workDate)} className="text-xs px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg font-bold">↺ 再読込</button>
            <span className="text-xs text-slate-400 ml-1">{rows.length}件</span>
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

          {/* テーブル: ヘッダー固定・明細スクロール */}
          <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
            <div className="shrink-0 border-b border-slate-200">
              <table className="w-full text-sm table-fixed">
                <colgroup><col className="w-32"/><col className="w-36"/><col className="w-36"/><col className="w-24"/><col/><col className="w-20"/></colgroup>
                <thead><tr className="bg-teal-50 text-teal-800">
                  <th className="px-4 py-2.5 text-left font-bold text-xs">機械</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">開始時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">終了時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">稼働時間</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">備考</th>
                  <th className="px-3 py-2.5 text-center font-bold text-xs">更新</th>
                </tr></thead>
              </table>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? <div className="p-10 text-center text-slate-400 text-sm">読み込み中...</div>
              : rows.length === 0 ? <div className="p-10 text-center text-slate-400 text-sm">
                  <div className="text-3xl mb-2">⏱️</div>
                  <p>この日のタイムカードがありません</p>
                  <p className="mt-1 text-xs text-slate-300">オペレーターがダッシュボードにログインするとレコードが生成されます</p>
                </div>
              : <table className="w-full text-sm table-fixed">
                  <colgroup><col className="w-32"/><col className="w-36"/><col className="w-36"/><col className="w-24"/><col/><col className="w-20"/></colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((row, idx) => {
                      const kadouMin = calcKadouMin(row.startTime, row.endTime);
                      return (
                        <tr key={row.id} className={row.dirty ? "bg-amber-50" : (idx%2===0?"bg-white":"bg-slate-50/40")}>
                          <td className="px-4 py-2"><span className="font-bold text-teal-700 text-sm">{row.machineCode}</span></td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.startTime} onChange={e => updateRow(idx,"startTime",e.target.value)}
                              className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none font-mono" />
                          </td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.endTime} onChange={e => updateRow(idx,"endTime",e.target.value)}
                              className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none font-mono" />
                          </td>
                          <td className="px-3 py-2">
                            <span className={`font-mono font-bold text-sm ${kadouMin>0?"text-teal-700":"text-slate-400"}`}>{fmtMin(kadouMin)}</span>
                            <div className="text-[10px] text-slate-400">{kadouMin>0?kadouMin+"分":""}</div>
                          </td>
                          <td className="px-3 py-1.5">
                            <input type="text" value={row.note} onChange={e => updateRow(idx,"note",e.target.value)}
                              placeholder="例: 午後から故障停止"
                              className="w-full border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            {row.dirty ? (
                              <button onClick={() => handleUpdate(idx)} disabled={row.saving}
                                className="px-3 py-1 bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white text-xs font-bold rounded-lg">
                                {row.saving ? "..." : "更新"}
                              </button>
                            ) : <span className="text-xs text-slate-300 font-bold">✓</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              }
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
