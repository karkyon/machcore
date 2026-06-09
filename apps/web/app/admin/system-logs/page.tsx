"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",       label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",    label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",      label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",    label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/calendar",    label: "営業カレンダー",   icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" },
  { href: "/admin/raw",         label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/system-logs", label: "システムログ",     icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
  { href: "/admin/clamp-master",  label: "クランプマスタ",     icon: "M4 6h16M4 12h16M4 18h7" },
  { href: "/admin/pdf-editor",  label: "段取りシートエディタ",      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
  { href: "/admin/special-sheets",label: "SPシート管理",   icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2M12 12h.01M12 16h.01" }
];

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
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={"fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow text-white text-sm font-bold " + (toast.ok ? "bg-green-600" : "bg-red-600")}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor" && i.href !== "/admin/special-sheets").map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={item.icon} />
              </svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {["/admin/pdf-editor", "/admin/special-sheets"].map(href => {
            const item = SIDEBAR_ITEMS.find(i => i.href === href)!;
            return (
              <a key={item.href} href={item.href}
                className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
                {item.label}
              </a>
            );
          })}
        </aside>

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
      </div>
    </div>
  );
}
