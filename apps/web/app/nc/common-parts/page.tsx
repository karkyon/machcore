"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ncApi, NcCommonSearchResult } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

// [v104] NC 共通部品検索・管理画面(MC側 mc/common-parts/page.tsx と同構成)。

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中", PROVISIONAL: "仮登録",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
  PROVISIONAL: "bg-slate-100 text-slate-500",
};

export default function NcCommonPartsPage() {
  const router = useRouter();
  const { isAuthenticated, token } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const [drawingNo,   setDrawingNo]   = useState("");
  const [name,        setName]        = useState("");
  const [mainModel,   setMainModel]   = useState("");
  const [partId,      setPartId]      = useState("");
  const [ncId,        setNcId]        = useState("");
  const [machiningId, setMachiningId] = useState("");

  const [results,  setResults]  = useState<NcCommonSearchResult[] | null>(null);
  const [total,    setTotal]    = useState(0);
  const [page,     setPage]     = useState(1);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [toast,    setToast]    = useState<string | null>(null);

  const [infoTarget, setInfoTarget] = useState<NcCommonSearchResult | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  const doSearch = useCallback(async (p = 1) => {
    setLoading(true); setError(null);
    try {
      const r = await ncApi.searchCommonParts({
        drawing_no:   drawingNo   || undefined,
        name:         name        || undefined,
        main_model:   mainModel   || undefined,
        part_id:      partId      || undefined,
        nc_id:        ncId        ? parseInt(ncId)        : undefined,
        machining_id: machiningId ? parseInt(machiningId) : undefined,
        page: p, limit: 50,
      });
      const d = (r as any).data ?? r;
      setResults(d.data ?? []); setTotal(d.total ?? 0); setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.message ?? e?.message ?? "検索失敗");
    } finally { setLoading(false); }
  }, [drawingNo, name, mainModel, partId, ncId, machiningId]);

  const doUnregister = async (item: NcCommonSearchResult) => {
    if (!isAuthenticated) { setAuthOpen(true); return; }
    if (!token) return;
    if (!confirm(`NC_id:${item.ncProgramId} (${item.drawingNo}) の共通登録を解除しますか？`)) return;
    try {
      await ncApi.unregisterCommonPart(item.ncProgramId, token);
      showToast("✅ 解除しました"); doSearch(page);
    } catch (e: any) { alert(e?.response?.data?.message ?? e?.message ?? "解除失敗"); }
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="min-h-screen bg-[#f0f4f8] flex flex-col">
      <div className="bg-[#1b2a41] px-6 py-3 flex items-center gap-4 shrink-0">
        <button onClick={() => router.push("/nc")} className="text-sky-300 hover:text-white text-sm font-semibold">← NC</button>
        <h1 className="text-white font-bold text-base">共通部品登録 — 検索・管理</h1>
      </div>

      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-3">
          {([["図面番号", drawingNo, setDrawingNo], ["名称", name, setName],
             ["主機種型式", mainModel, setMainModel], ["部品ID", partId, setPartId],
             ["NC_id", ncId, setNcId], ["加工ID", machiningId, setMachiningId]] as [string, string, (v: string) => void][])
            .map(([lbl, val, set]) => (
              <div key={lbl}>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">{lbl}</label>
                <input value={val} onChange={e => set(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && doSearch(1)}
                  className="mt-0.5 w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  placeholder={lbl} />
              </div>
            ))}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => doSearch(1)} disabled={loading}
            className="px-5 py-2 bg-sky-600 text-white text-sm font-bold rounded-xl hover:bg-sky-700 disabled:opacity-50">
            {loading ? "検索中..." : "🔍 検索"}
          </button>
          <button onClick={() => { setDrawingNo(""); setName(""); setMainModel(""); setPartId(""); setNcId(""); setMachiningId(""); setResults(null); }}
            className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">
            クリア
          </button>
          <button onClick={() => router.push("/nc/new/common")}
            className="ml-auto px-4 py-2 bg-violet-600 text-white text-sm font-bold rounded-xl hover:bg-violet-700">
            ＋ 新規に共通登録
          </button>
          {results !== null && <span className="text-sm text-slate-500">{total}件 / {totalPages}ページ</span>}
        </div>
        {error && <div className="mt-2 text-red-600 text-sm">{error}</div>}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {results === null && !loading && (
          <div className="text-center text-slate-400 py-20 text-sm">条件を入力して検索してください<br/><span className="text-xs text-slate-300">（共通登録済み加工のみ表示）</span></div>
        )}
        {loading && <div className="text-center text-slate-400 py-20 text-sm">検索中...</div>}
        {results !== null && !loading && results.length === 0 && (
          <div className="text-center text-slate-400 py-20 text-sm">該当する共通部品がありません</div>
        )}
        {results !== null && results.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <table className="w-full text-xs border-collapse">
              <thead className="bg-[#1b2a41] text-white sticky top-0">
                <tr>
                  {["図面番号","名称","主機種型式","部品ID","NC_id","加工ID","Ver","共通CD","G件数","状態","操作"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-bold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map((item, i) => (
                  <tr key={item.ncProgramId}
                    className={`${i % 2 === 0 ? "bg-white" : "bg-slate-50"} hover:bg-sky-50 transition-colors`}>
                    <td className="px-3 py-2 font-mono font-bold text-sky-700 whitespace-nowrap">
                      <button onClick={() => router.push(`/nc/${item.ncProgramId}`)} className="hover:underline">{item.drawingNo}</button>
                    </td>
                    <td className="px-3 py-2 text-slate-700 max-w-[150px] truncate" title={item.name}>{item.name}</td>
                    <td className="px-3 py-2 text-slate-500 max-w-[100px] truncate">{item.mainModel ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-center text-violet-700 font-bold">{item.partId ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-center text-blue-700">{item.legacyNcId ?? item.ncProgramId}</td>
                    <td className="px-3 py-2 font-mono text-center text-slate-600">{item.machiningId}</td>
                    <td className="px-3 py-2 font-mono text-center text-slate-700">{item.version}</td>
                    <td className="px-3 py-2 font-mono text-center text-emerald-700 text-[11px]">{item.commonPartCode ?? "—"}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`font-bold text-[11px] px-1.5 py-0.5 rounded ${item.groupCount > 1 ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-500"}`}>
                        {item.groupCount}件
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[item.status] ?? ""}`}>
                        {STATUS_LABEL[item.status] ?? item.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <button onClick={() => router.push(`/nc/${item.ncProgramId}`)}
                          className="px-2 py-1 bg-sky-600 text-white text-[10px] font-bold rounded hover:bg-sky-700">詳細</button>
                        <button onClick={() => setInfoTarget(item)}
                          className="px-2 py-1 bg-slate-100 text-slate-600 text-[10px] font-bold rounded hover:bg-slate-200 border border-slate-300">供用方法</button>
                        {item.groupCount > 1 && (
                          <button onClick={() => doUnregister(item)}
                            className="px-2 py-1 bg-red-100 text-red-600 text-[10px] font-bold rounded hover:bg-red-200 border border-red-200">解除</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {totalPages > 1 && (
              <div className="flex items-center gap-2 justify-center py-3 border-t border-slate-100">
                <button onClick={() => doSearch(page - 1)} disabled={page <= 1}
                  className="px-3 py-1 bg-slate-200 text-slate-700 text-xs font-bold rounded disabled:opacity-40">← 前へ</button>
                <span className="text-xs text-slate-600">{page} / {totalPages}</span>
                <button onClick={() => doSearch(page + 1)} disabled={page >= totalPages}
                  className="px-3 py-1 bg-slate-200 text-slate-700 text-xs font-bold rounded disabled:opacity-40">次へ →</button>
              </div>
            )}
          </div>
        )}
      </div>

      {infoTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h2 className="text-base font-bold text-slate-800 mb-3">📋 共通登録の手順</h2>
            <div className="bg-sky-50 rounded-xl p-3 mb-4 text-sm space-y-1">
              <div><span className="text-slate-400 text-xs">対象加工ID:</span> <span className="font-mono font-bold text-sky-700">{infoTarget.machiningId}</span></div>
              <div><span className="text-slate-400 text-xs">図面番号:</span> <span className="font-mono font-bold">{infoTarget.drawingNo}</span></div>
              <div><span className="text-slate-400 text-xs">名称:</span> <span>{infoTarget.name}</span></div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 text-sm">
              <p className="font-bold text-amber-800 mb-2">共通登録の操作手順</p>
              <ol className="list-decimal list-inside space-y-1.5 text-amber-900 text-xs">
                <li>「＋ 新規に共通登録」ボタンを押す</li>
                <li>登録先の部品を検索・選択</li>
                <li>検索で上記の加工（図面番号: {infoTarget.drawingNo}）を探して選択</li>
                <li>「📋 共通登録（供用）する」を押して完了</li>
              </ol>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setInfoTarget(null)}
                className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">閉じる</button>
              <button onClick={() => { setInfoTarget(null); router.push(`/nc/${infoTarget.ncProgramId}`); }}
                className="px-4 py-2 bg-sky-600 text-white text-sm font-bold rounded-xl hover:bg-sky-700">
                このNCの詳細を開く →
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 bg-emerald-700 text-white text-sm font-bold px-5 py-3 rounded-xl shadow-xl z-50">{toast}</div>
      )}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="edit" system="NC"
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}
    </div>
  );
}
