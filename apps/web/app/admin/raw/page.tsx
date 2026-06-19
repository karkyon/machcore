"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TABLES = [
  "users", "machines", "parts", "nc_programs",
  "work_records", "change_history", "operation_logs", "setup_sheet_logs", "machine_timecards",
];

export default function AdminRawPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [table,   setTable]   = useState(TABLES[0]);
  const [page,    setPage]    = useState(1);
  const [limit]               = useState(50);
  const [data,    setData]    = useState<any[]>([]);
  const [total,   setTotal]   = useState(0);
  const [cols,    setCols]    = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [filter,  setFilter]  = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo,   setDateTo]   = useState("");
  const [fieldKey, setFieldKey] = useState("");
  const [fieldVal, setFieldVal] = useState("");

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token || !user) { router.replace("/admin/login"); }
  }, [router]);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  const fetchData = useCallback(async (tbl: string, pg: number) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`/api/admin/raw/${tbl}?page=${pg}&limit=${limit}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data ?? []);
      setTotal(json.total ?? 0);
      if (json.data?.length > 0) setCols(Object.keys(json.data[0]));
      else setCols([]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => { fetchData(table, page); }, [table, page, fetchData]);

  const filtered = data.filter(row => {
    // キーワードフィルタ
    if (filter && !Object.values(row).some(v => String(v ?? "").includes(filter))) return false;
    // フィールド指定フィルタ
    if (fieldKey && fieldVal && !String(row[fieldKey] ?? "").includes(fieldVal)) return false;
    // 日付範囲フィルタ（created_at / updated_at / work_date / changed_at）
    const dateField = ["created_at","updated_at","work_date","changed_at","accessed_at","printed_at"].find(f => row[f]);
    if (dateField && row[dateField]) {
      const rowDate = String(row[dateField]).slice(0, 10);
      if (dateFrom && rowDate < dateFrom) return false;
      if (dateTo   && rowDate > dateTo)   return false;
    }
    return true;
  });

  const totalPages = Math.ceil(total / limit);

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
  { href: "/admin/special-sheets",label: "SPシート管理",   icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2M12 12h.01M12 16h.01" },
  { href: "/admin/upload-agent", label: "UploadAgent",     icon: "M8 17l4 4 4-4M12 12v9M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29" },
];

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
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">
            ログアウト
          </button>
        </div>
      </header>
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor" && i.href !== "/admin/special-sheets" && i.href !== "/admin/upload-agent").map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {["/admin/pdf-editor", "/admin/special-sheets", "/admin/upload-agent"].map(href => {
            const item = SIDEBAR_ITEMS.find(i => i.href === href)!;
            return (
              <a key={item.href} href={item.href}
                className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                  pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
                {item.label}
              </a>
            );
          })}
        </aside>
        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
        <div className="flex items-center justify-between shrink-0">
          <h1 className="text-xl font-bold text-slate-800">RAWデータ</h1>
        </div>
        {/* コントロール */}
        <div className="bg-white rounded-xl border border-slate-200 p-3 space-y-2 shrink-0">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-bold text-slate-500">テーブル:</label>
            <select value={table} onChange={e => { setTable(e.target.value); setPage(1); setFilter(""); setDateFrom(""); setDateTo(""); setFieldKey(""); setFieldVal(""); }}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              {TABLES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <input type="text" value={filter} onChange={e => setFilter(e.target.value)}
              placeholder="キーワードフィルタ" className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 w-52 focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            <span className="text-xs text-slate-500">DB: {total.toLocaleString()}件 / 表示: {filtered.length}件</span>
            <button onClick={() => fetchData(table, page)} className="text-xs bg-sky-600 text-white px-3 py-1.5 rounded-lg hover:bg-sky-700">🔄 再取得</button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-bold text-slate-500">日付範囲:</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            <span className="text-xs text-slate-400">〜</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            {cols.length > 0 && <>
              <label className="text-xs font-bold text-slate-500 ml-2">フィールド指定:</label>
              <select value={fieldKey} onChange={e => setFieldKey(e.target.value)}
                className="text-sm border border-slate-300 rounded-lg px-2 py-1.5 bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none w-40">
                <option value="">-- 列選択 --</option>
                {cols.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <input type="text" value={fieldVal} onChange={e => setFieldVal(e.target.value)}
                placeholder="値を入力" className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 w-40 focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            </>}
            {(dateFrom || dateTo || fieldKey || filter) && (
              <button onClick={() => { setFilter(""); setDateFrom(""); setDateTo(""); setFieldKey(""); setFieldVal(""); }}
                className="text-xs text-slate-500 hover:text-red-500 px-2 py-1 border border-slate-300 rounded-lg">✕ クリア</button>
            )}
          </div>
        </div>

        {/* エラー */}
        {error && (
          <div className="shrink-0 bg-red-50 border border-red-200 rounded px-4 py-2 text-red-600 text-sm">
            ⚠️ {error}
          </div>
        )}

        {/* テーブル: stickyヘッダー方式（列幅が揃う） */}
        <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200">
          {loading ? (
            <div className="py-20 text-center text-slate-400">読み込み中…</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-slate-400">データなし</div>
          ) : (
            <table className="text-xs whitespace-nowrap w-full">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr>
                  {cols.map(col => (
                    <th key={col} className="px-3 py-2 text-left text-slate-500 font-bold border-b border-slate-200">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filtered.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    {cols.map(col => (
                      <td key={col} className="px-3 py-1.5 font-mono text-slate-700 max-w-[200px] truncate"
                        title={String(row[col] ?? "")}>
                        {row[col] === null ? <span className="text-slate-300">NULL</span>
                          : typeof row[col] === "object" ? JSON.stringify(row[col])
                          : String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ページネーション */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2 justify-center shrink-0">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1 text-sm bg-white border border-slate-300 rounded disabled:opacity-40">
              ← 前
            </button>
            <span className="text-sm text-slate-600">{page} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-3 py-1 text-sm bg-white border border-slate-300 rounded disabled:opacity-40">
              次 →
            </button>
          </div>
        )}
        </main>
      </div>
    </div>
  );
}
