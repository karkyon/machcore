"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TABLES = [
  "users", "machines", "parts", "nc_programs",
  "work_records", "change_history", "operation_logs", "setup_sheet_logs",
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

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token || !user) { router.replace("/admin/login"); }
  }, [router]);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  const fetchData = useCallback(async (tbl: string, pg: number) => {
    setLoading(true); setError(null);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiBase}/admin/raw/${tbl}?page=${pg}&limit=${limit}`, {
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

  const filtered = filter
    ? data.filter(row => Object.values(row).some(v => String(v ?? "").includes(filter)))
    : data;

  const totalPages = Math.ceil(total / limit);

  const SIDEBAR_ITEMS = [
    { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
    { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
    { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
    { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-slate-900 text-white px-5 py-2.5 flex items-center gap-3 shrink-0 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/nc/search"
            className="text-xs bg-slate-600 hover:bg-slate-500 text-slate-200 px-3 py-1.5 rounded transition-colors">
            ← NC画面
          </a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded transition-colors">
            ログアウト
          </button>
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="w-48 shrink-0 bg-slate-800 flex flex-col py-4 gap-1 border-r border-slate-700">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-600 text-white font-bold" : "text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>
        <main className="flex-1 overflow-auto px-4 py-6">
        {/* コントロール */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div>
            <label className="text-xs text-slate-500 mr-1">テーブル:</label>
            <select value={table} onChange={e => { setTable(e.target.value); setPage(1); setFilter(""); }}
              className="text-sm border border-slate-300 rounded px-2 py-1 bg-white">
              {TABLES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <input
            type="text" value={filter} onChange={e => setFilter(e.target.value)}
            placeholder="キーワードフィルタ（クライアント側）"
            className="text-sm border border-slate-300 rounded px-3 py-1 w-64"
          />
          <span className="text-xs text-slate-500">全 {total.toLocaleString()} 件</span>
          <button onClick={() => fetchData(table, page)}
            className="text-xs bg-sky-600 text-white px-3 py-1.5 rounded-lg hover:bg-sky-700">
            🔄 再取得
          </button>
        </div>

        {/* エラー */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded px-4 py-2 text-red-600 text-sm">
            ⚠️ {error}
          </div>
        )}

        {/* テーブル */}
        <div className="bg-white rounded-xl shadow overflow-auto">
          {loading ? (
            <div className="py-20 text-center text-slate-400">読み込み中…</div>
          ) : filtered.length === 0 ? (
            <div className="py-20 text-center text-slate-400">データなし</div>
          ) : (
            <table className="w-full text-xs whitespace-nowrap">
              <thead className="bg-slate-50 sticky top-0">
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
          <div className="flex items-center gap-2 mt-4 justify-center">
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
