"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { adminLogsApi, type AdminLog } from "@/lib/api";
import axios from "axios";

const ACTION_OPTIONS = [
  { value: "",              label: "すべて" },
  { value: "LOGIN",         label: "管理者ログイン" },
  { value: "SESSION_START", label: "作業開始" },
  { value: "SESSION_END",   label: "作業終了" },
  { value: "EDIT_SAVE",     label: "NC情報編集" },
  { value: "USB_DOWNLOAD",  label: "PGファイルDL" },
  { value: "SETUP_PRINT",   label: "段取シート印刷" },
  { value: "WORK_RECORD",   label: "作業記録" },
  { value: "FILE_UPLOAD",   label: "ファイルUP" },
  { value: "FILE_DELETE",   label: "ファイル削除" },
];

const ACTION_BADGE: Record<string, string> = {
  LOGIN:         "bg-purple-100 text-purple-700",
  SESSION_START: "bg-green-100 text-green-700",
  SESSION_END:   "bg-slate-100 text-slate-600",
  EDIT_SAVE:     "bg-yellow-100 text-yellow-700",
  USB_DOWNLOAD:  "bg-blue-100 text-blue-700",
  SETUP_PRINT:   "bg-orange-100 text-orange-700",
  WORK_RECORD:   "bg-teal-100 text-teal-700",
  FILE_UPLOAD:   "bg-sky-100 text-sky-700",
  FILE_DELETE:   "bg-red-100 text-red-600",
};

export default function AdminLogsPage() {
  const router = useRouter();
  const [logs,      setLogs]      = useState<AdminLog[]>([]);
  const [total,     setTotal]     = useState(0);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [page,      setPage]      = useState(1);
  const LIMIT = 50;

  const [filterAction, setFilterAction] = useState("");
  const [filterNcId,   setFilterNcId]   = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo,   setFilterDateTo]   = useState("");

  const token = typeof window !== "undefined"
    ? sessionStorage.getItem("admin_token") ?? ""
    : "";

  const fetch = useCallback(async (p = 1) => {
    if (!token) { router.push("/admin/login"); return; }
    setLoading(true); setError(null);
    try {
      const res = await adminLogsApi.list({
        action_type: filterAction || undefined,
        nc_id:       filterNcId ? parseInt(filterNcId) : undefined,
        date_from:   filterDateFrom || undefined,
        date_to:     filterDateTo   || undefined,
        page: p, limit: LIMIT,
      });
      // axiosのレスポンスにはdataがネストされている
      const d = (res as any).data ?? res;
      setLogs(d.data ?? []);
      setTotal(d.total ?? 0);
      setPage(p);
    } catch(e: any) {
      if (e?.response?.status === 401) router.push("/admin/login");
      else setError("取得失敗");
    } finally { setLoading(false); }
  }, [token, filterAction, filterNcId, filterDateFrom, filterDateTo, router]);

  useEffect(() => { fetch(1); }, []);

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ヘッダー */}
      <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/admin/users")}
            className="text-slate-400 hover:text-white text-sm">← 管理者メニュー</button>
          <span className="text-slate-600">|</span>
          <h1 className="font-bold text-lg">🔍 操作ログ</h1>
        </div>
        <span className="text-slate-400 text-sm">全 {total.toLocaleString()} 件</span>
      </div>

      {/* フィルター */}
      <div className="bg-white border-b px-6 py-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">操作種別</label>
          <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm text-slate-700 bg-white">
            {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">NC_ID</label>
          <input type="number" value={filterNcId} onChange={e => setFilterNcId(e.target.value)}
            placeholder="例: 3120" className="border rounded px-2 py-1.5 text-sm w-28" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">日付（From）</label>
          <input type="date" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">日付（To）</label>
          <input type="date" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm" />
        </div>
        <button onClick={() => fetch(1)}
          className="px-4 py-1.5 bg-sky-600 text-white text-sm rounded hover:bg-sky-700">
          検索
        </button>
        <button onClick={() => {
            setFilterAction(""); setFilterNcId("");
            setFilterDateFrom(""); setFilterDateTo("");
          }}
          className="px-3 py-1.5 text-sm text-slate-500 border rounded hover:bg-slate-50">
          クリア
        </button>
      </div>

      {/* テーブル */}
      <div className="p-6">
        {error && <div className="text-red-500 text-sm mb-4">{error}</div>}
        {loading ? (
          <div className="text-slate-400 text-center py-20">読み込み中...</div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-xs border-collapse">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  {["日時", "操作", "担当者", "NC_ID", "部品・図番", "詳細"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr><td colSpan={6} className="px-3 py-10 text-center text-slate-400">該当なし</td></tr>
                ) : logs.map((log, i) => {
                  const badgeCls = ACTION_BADGE[log.action_type] ?? "bg-slate-100 text-slate-500";
                  const label    = ACTION_OPTIONS.find(o => o.value === log.action_type)?.label ?? log.action_type;
                  const meta     = log.metadata as Record<string, unknown> | null;
                  const detail   = meta?.fileName ?? meta?.originalName ?? meta?.session_type ?? "";
                  return (
                    <tr key={log.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                      <td className="px-3 py-2 whitespace-nowrap text-slate-500">
                        {new Date(log.created_at).toLocaleString("ja-JP")}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${badgeCls}`}>{label}</span>
                      </td>
                      <td className="px-3 py-2">{log.user_name ?? "—"}</td>
                      <td className="px-3 py-2 font-mono">
                        {log.nc_id ? (
                          <a href={`/nc/${log.nc_id}`}
                            className="text-sky-600 hover:underline">{log.nc_id}</a>
                        ) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {log.drawing_no && <span className="font-mono text-blue-700">{log.drawing_no}</span>}
                        {log.part_name  && <span className="text-slate-600 ml-1">{log.part_name}</span>}
                        {!log.drawing_no && !log.part_name && "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-500">{String(detail || "")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ページネーション */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-4">
            <button disabled={page <= 1} onClick={() => fetch(page - 1)}
              className="px-3 py-1 text-sm border rounded disabled:opacity-40 hover:bg-slate-100">← 前</button>
            <span className="text-sm text-slate-600">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => fetch(page + 1)}
              className="px-3 py-1 text-sm border rounded disabled:opacity-40 hover:bg-slate-100">次 →</button>
          </div>
        )}
      </div>
    </div>
  );
}
