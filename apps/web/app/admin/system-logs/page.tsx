"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const LEVEL_COLOR: Record<string, string> = {
  INFO:  "bg-blue-100 text-blue-700",
  WARN:  "bg-amber-100 text-amber-700",
  ERROR: "bg-red-100 text-red-700",
  DEBUG: "bg-slate-100 text-slate-600",
};
const CATEGORY_COLOR: Record<string, string> = {
  CRON:     "bg-purple-100 text-purple-700",
  AUTH:     "bg-green-100 text-green-700",
  API:      "bg-sky-100 text-sky-700",
  PDF:      "bg-orange-100 text-orange-700",
  FILE:     "bg-teal-100 text-teal-700",
  DB:       "bg-indigo-100 text-indigo-700",
  TIMECARD: "bg-emerald-100 text-emerald-700",
  SYSTEM:   "bg-slate-100 text-slate-600",
  MC:       "bg-violet-100 text-violet-700",
  NC:       "bg-cyan-100 text-cyan-700",
};

const LEVELS     = ["", "INFO", "WARN", "ERROR", "DEBUG"];
const CATEGORIES = ["", "CRON", "AUTH", "API", "PDF", "FILE", "DB", "TIMECARD", "SYSTEM", "MC", "NC"];
const LIMIT = 100;

type SysLog = { id: number; level: string; category: string; message: string; detail: any; created_at: string };

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export default function SystemLogsPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [logs,    setLogs]    = useState<SysLog[]>([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(false);
  const [page,    setPage]    = useState(1);
  const [fLevel,    setFLevel]    = useState("");
  const [fCategory, setFCategory] = useState("");
  const [fDateFrom, setFDateFrom] = useState("");
  const [fDateTo,   setFDateTo]   = useState("");
  const [toast,   setToast]   = useState<{ msg: string; ok: boolean } | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  const fetchLogs = useCallback(async (p = 1) => {
    if (!getToken()) { router.push("/admin/login"); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), limit: String(LIMIT) });
      if (fLevel)    params.set("level",     fLevel);
      if (fCategory) params.set("category",  fCategory);
      if (fDateFrom) params.set("date_from", fDateFrom);
      if (fDateTo)   params.set("date_to",   fDateTo);
      const d = await apiFetch(`/admin/system-logs?${params}`);
      setLogs(d.data ?? []);
      setTotal(d.total ?? 0);
      setPage(p);
    } catch (e: any) {
      showToast(`取得失敗: ${e.message}`, false);
    } finally { setLoading(false); }
  }, [router, fLevel, fCategory, fDateFrom, fDateTo]);

  useEffect(() => { fetchLogs(1); }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => fetchLogs(1), 5000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchLogs]);

  const handlePurge = async () => {
    if (!confirm("30日以前のログを削除しますか？")) return;
    try {
      const d = await apiFetch("/admin/system-logs/purge?days=30", { method: "DELETE" });
      showToast(d.message);
      fetchLogs(1);
    } catch (e: any) { showToast(`削除失敗: ${e.message}`, false); }
  };

  const fmtDt = (s: string) => {
    const d = new Date(s);
    const p = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <AdminLayout pathname={pathname}>

      {toast && (
        <div className={"fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow text-white text-sm font-bold " + (toast.ok ? "bg-green-600" : "bg-red-600")}>
          {toast.msg}
        </div>
      )}

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">システムログ</h1>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
                    className="rounded" />
                  自動更新（5秒）
                </label>
                <button onClick={() => fetchLogs(page)}
                  className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-bold">
                  更新
                </button>
                <button onClick={handlePurge}
                  className="text-xs px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded font-bold">
                  30日以前を削除
                </button>
              </div>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <select value={fLevel} onChange={e => setFLevel(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none">
                {LEVELS.map(l => <option key={l} value={l}>{l || "レベル: すべて"}</option>)}
              </select>
            <select value={fCategory} onChange={e => setFCategory(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none">
                {CATEGORIES.map(c => <option key={c} value={c}>{c || "カテゴリ: すべて"}</option>)}
              </select>
            <input type="date" value={fDateFrom} onChange={e => setFDateFrom(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none" />
            <span className="text-xs text-slate-400">〜</span>
            <input type="date" value={fDateTo} onChange={e => setFDateTo(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none" />
            <span className="text-xs text-slate-400 self-center">全 {total} 件</span>
          </div>

          <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-slate-200">
            {loading ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">読み込み中...</div>
            ) : logs.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">ログがありません</div>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead className="bg-slate-50 sticky top-0 z-10">
                  <tr className="border-b border-slate-200">
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-36">日時</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-16">レベル</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-24">カテゴリ</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500">メッセージ</th>
                    <th className="px-3 py-2 text-center font-bold text-slate-500 w-14">詳細</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <>
                      <tr key={log.id} className={"border-b border-slate-100 hover:bg-slate-50 " + (log.level === "ERROR" ? "bg-red-50/40" : log.level === "WARN" ? "bg-amber-50/40" : "")}>
                        <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap">{fmtDt(log.created_at)}</td>
                        <td className="px-3 py-2">
                          <span className={"text-[10px] font-bold px-1.5 py-0.5 rounded " + (LEVEL_COLOR[log.level] ?? "bg-slate-100 text-slate-600")}>
                            {log.level}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={"text-[10px] font-bold px-1.5 py-0.5 rounded " + (CATEGORY_COLOR[log.category] ?? "bg-slate-100 text-slate-600")}>
                            {log.category}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">{log.message}</td>
                        <td className="px-3 py-2 text-center">
                          {log.detail && (
                            <button onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                              className="text-sky-600 hover:text-sky-800 font-bold">
                              {expanded === log.id ? "▲" : "▼"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {expanded === log.id && log.detail && (
                        <tr key={"d" + log.id} className="bg-slate-50 border-b border-slate-100">
                          <td colSpan={5} className="px-4 py-2">
                            <pre className="text-[10px] text-slate-600 whitespace-pre-wrap bg-white border border-slate-200 rounded p-2 max-h-48 overflow-y-auto">
                              {JSON.stringify(log.detail, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 py-3 border-t border-slate-200 shrink-0">
              <button onClick={() => fetchLogs(page - 1)} disabled={page <= 1}
                className="text-xs px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40">前へ</button>
              <span className="text-xs text-slate-600">{page} / {totalPages}</span>
              <button onClick={() => fetchLogs(page + 1)} disabled={page >= totalPages}
                className="text-xs px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40">次へ</button>
            </div>
          )}
        </main>
    </AdminLayout>
  );
}
