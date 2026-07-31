"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, McCommonSearchResult } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";
import { useLanguage } from "@/lib/i18n/LanguageContext";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};

export default function CommonPartsPage() {
  const { t: tr } = useLanguage();
  const router = useRouter();
  const { isAuthenticated, token } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const [drawingNo,   setDrawingNo]   = useState("");
  const [name,        setName]        = useState("");
  const [mainModel,   setMainModel]   = useState("");
  const [partId,      setPartId]      = useState("");
  const [mcId,        setMcId]        = useState("");
  const [machiningId, setMachiningId] = useState("");

  const [results,  setResults]  = useState<McCommonSearchResult[] | null>(null);
  const [total,    setTotal]    = useState(0);
  const [page,     setPage]     = useState(1);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [toast,    setToast]    = useState<string | null>(null);

  const [infoTarget, setInfoTarget] = useState<McCommonSearchResult | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  const doSearch = useCallback(async (p = 1) => {
    setLoading(true); setError(null);
    try {
      const r = await mcApi.searchCommonParts({
        drawing_no:   drawingNo   || undefined,
        name:         name        || undefined,
        main_model:   mainModel   || undefined,
        part_id:      partId      || undefined,
        mc_id:        mcId        ? parseInt(mcId)        : undefined,
        machining_id: machiningId ? parseInt(machiningId) : undefined,
        page: p, limit: 50,
      });
      const d = (r as any).data ?? r;
      setResults(d.data ?? []); setTotal(d.total ?? 0); setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.message ?? e?.message ?? tr("mcCommonPartsPage.searchFailedMsg2","検索失敗"));
    } finally { setLoading(false); }
  }, [drawingNo, name, mainModel, partId, mcId, machiningId]);



  const doUnregister = async (item: McCommonSearchResult) => {
    if (!isAuthenticated) { setAuthOpen(true); return; }
    if (!token) return;
    if (!confirm(tr("mcCommonPartsPage.confirmUnregister","MCID:{id} ({no}) の共通登録を解除しますか？").replace("{id}", String(item.mcProgramId)).replace("{no}", item.drawingNo))) return;
    try {
      await mcApi.unregisterCommonPart(item.mcProgramId, token);
      showToast(tr("mcCommonPartsPage.unregisteredMsg","✅ 解除しました")); doSearch(page);
    } catch (e: any) { alert(e?.response?.data?.message ?? e?.message ?? tr("mcCommonPartsPage.unregisterFailedMsg","解除失敗")); }
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="min-h-screen bg-[#f0f4f8] flex flex-col">
      <div className="bg-[#1b2a41] px-6 py-3 flex items-center gap-4 shrink-0">
        <button onClick={() => router.push("/mc")} className="text-blue-300 hover:text-white text-sm font-semibold">{tr("mcCommonPartsPage.backToMcLink", "← MC")}</button>
        <h1 className="text-white font-bold text-base">{tr("mcCommonPartsPage.pageTitle2", "共通部品登録 — 検索・管理")}</h1>
      </div>

      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-3">
          {([[tr("mcCommonPartsPage.labelDrawingNo","図面番号"), drawingNo, setDrawingNo], [tr("mcCommonPartsPage.labelName","名称"), name, setName],
             [tr("mcCommonPartsPage.labelMainModel","主機種型式"), mainModel, setMainModel], [tr("mcCommonPartsPage.labelPartId","部品ID"), partId, setPartId],
             ["MCID", mcId, setMcId], [tr("mcCommonPartsPage.labelMachiningId","加工ID"), machiningId, setMachiningId]] as [string, string, (v: string) => void][])
            .map(([lbl, val, set]) => (
              <div key={lbl}>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">{lbl}</label>
                <input value={val} onChange={e => set(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && doSearch(1)}
                  className="mt-0.5 w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
                  placeholder={lbl} />
              </div>
            ))}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => doSearch(1)} disabled={loading}
            className="px-5 py-2 bg-teal-600 text-white text-sm font-bold rounded-xl hover:bg-teal-700 disabled:opacity-50">
            {loading ? tr("mcCommonPartsPage.searchingLabel4", "検索中...") : tr("mcCommonPartsPage.searchButton6", "🔍 検索")}
          </button>
          <button onClick={() => { setDrawingNo(""); setName(""); setMainModel(""); setPartId(""); setMcId(""); setMachiningId(""); setResults(null); }}
            className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">
            {tr("mcCommonPartsPage.clearButton2", "クリア")}
          </button>
          {results !== null && <span className="text-sm text-slate-500">{tr("mcCommonPartsPage.resultCountLabel", "{n}件 / {p}ページ").replace("{n}", String(total)).replace("{p}", String(totalPages))}</span>}
        </div>
        {error && <div className="mt-2 text-red-600 text-sm">{error}</div>}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {results === null && !loading && (
          <div className="text-center text-slate-400 py-20 text-sm">{tr("mcCommonPartsPage.inputConditionHint", "条件を入力して検索してください")}<br/><span className="text-xs text-slate-300">{tr("mcCommonPartsPage.commonRegisteredOnlyNote", "（共通登録済み加工のみ表示）")}</span></div>
        )}
        {loading && <div className="text-center text-slate-400 py-20 text-sm">{tr("mcCommonPartsPage.searchingLabel4", "検索中...")}</div>}
        {results !== null && !loading && results.length === 0 && (
          <div className="text-center text-slate-400 py-20 text-sm">{tr("mcCommonPartsPage.noMatchingCommonParts", "該当する共通部品がありません")}</div>
        )}
        {results !== null && results.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <table className="w-full text-xs border-collapse">
              <thead className="bg-[#1b2a41] text-white sticky top-0">
                <tr>
                  {[tr("mcCommonPartsPage.colDrawingNo2","図面番号"), tr("mcCommonPartsPage.colName2","名称"), tr("mcCommonPartsPage.colMainModel2","主機種型式"), tr("mcCommonPartsPage.colPartId2","部品ID"), tr("mcCommonPartsPage.colMcId2","MCID"), tr("mcCommonPartsPage.colMachiningId3","加工ID"), tr("mcCommonPartsPage.colVer2","Ver"), tr("mcCommonPartsPage.colCommonCd","共通CD"), tr("mcCommonPartsPage.colGCount","G件数"), tr("mcCommonPartsPage.colStatus2","状態"), tr("mcCommonPartsPage.colOperation3","操作")].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-bold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map((item, i) => (
                  <tr key={item.mcProgramId}
                    className={`${i % 2 === 0 ? "bg-white" : "bg-slate-50"} hover:bg-teal-50 transition-colors`}>
                    <td className="px-3 py-2 font-mono font-bold text-teal-700 whitespace-nowrap">
                      <button onClick={() => router.push(`/mc/${item.mcProgramId}`)} className="hover:underline">{item.drawingNo}</button>
                    </td>
                    <td className="px-3 py-2 text-slate-700 max-w-[150px] truncate" title={item.name}>{item.name}</td>
                    <td className="px-3 py-2 text-slate-500 max-w-[100px] truncate">{item.mainModel ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-center text-violet-700 font-bold">{item.partId ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-center text-blue-700">{item.legacyMcid ?? item.mcProgramId}</td>
                    <td className="px-3 py-2 font-mono text-center text-slate-600">{item.machiningId}</td>
                    <td className="px-3 py-2 font-mono text-center text-slate-700">{item.version}</td>
                    <td className="px-3 py-2 font-mono text-center text-emerald-700 text-[11px]">{item.commonPartCode ?? "—"}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`font-bold text-[11px] px-1.5 py-0.5 rounded ${item.groupCount > 1 ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-500"}`}>
                        {tr("mcCommonPartsPage.itemsCountSuffix4","{n}件").replace("{n}", String(item.groupCount))}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[item.status] ?? ""}`}>
                        {STATUS_LABEL[item.status] ?? item.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <button onClick={() => router.push(`/mc/${item.mcProgramId}`)}
                          className="px-2 py-1 bg-teal-600 text-white text-[10px] font-bold rounded hover:bg-teal-700">{tr("mcCommonPartsPage.detailButton2","詳細")}</button>
                        <button onClick={() => setInfoTarget(item)}
                          className="px-2 py-1 bg-slate-100 text-slate-600 text-[10px] font-bold rounded hover:bg-slate-200 border border-slate-300">{tr("mcCommonPartsPage.sharedMethodButton","供用方法")}</button>
                        {item.groupCount > 1 && (
                          <button onClick={() => doUnregister(item)}
                            className="px-2 py-1 bg-red-100 text-red-600 text-[10px] font-bold rounded hover:bg-red-200 border border-red-200">{tr("mcCommonPartsPage.releaseButton","解除")}</button>
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
                  className="px-3 py-1 bg-slate-200 text-slate-700 text-xs font-bold rounded disabled:opacity-40">{tr("mcCommonPartsPage.prevPageButton","← 前へ")}</button>
                <span className="text-xs text-slate-600">{page} / {totalPages}</span>
                <button onClick={() => doSearch(page + 1)} disabled={page >= totalPages}
                  className="px-3 py-1 bg-slate-200 text-slate-700 text-xs font-bold rounded disabled:opacity-40">{tr("mcCommonPartsPage.nextPageButton","次へ →")}</button>
              </div>
            )}
          </div>
        )}
      </div>

      {infoTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h2 className="text-base font-bold text-slate-800 mb-3">{tr("mcCommonPartsPage.commonRegisterProcedureTitle", "📋 共通登録の手順")}</h2>
            <div className="bg-teal-50 rounded-xl p-3 mb-4 text-sm space-y-1">
              <div><span className="text-slate-400 text-xs">{tr("mcCommonPartsPage.targetMachiningIdLabel", "対象加工ID:")}</span> <span className="font-mono font-bold text-teal-700">{infoTarget.machiningId}</span></div>
              <div><span className="text-slate-400 text-xs">{tr("mcCommonPartsPage.drawingNoLabel3", "図面番号:")}</span> <span className="font-mono font-bold">{infoTarget.drawingNo}</span></div>
              <div><span className="text-slate-400 text-xs">{tr("mcCommonPartsPage.nameLabel2", "名称:")}</span> <span>{infoTarget.name}</span></div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 text-sm">
              <p className="font-bold text-amber-800 mb-2">{tr("mcCommonPartsPage.commonRegisterProcedureTitle2", "共通登録の操作手順")}</p>
              <ol className="list-decimal list-inside space-y-1.5 text-amber-900 text-xs">
                <li>{tr("mcCommonPartsPage.mcStep1","この加工データを使いたい登録先の部品のMC詳細ページを開く")}</li>
                <li>{tr("mcCommonPartsPage.mcStep2","「共通グループ」タブをクリック")}</li>
                <li>{tr("mcCommonPartsPage.mcStep3","「＋ 新規に共通登録」ボタンを押す")}</li>
                <li>{tr("mcCommonPartsPage.mcStep4","検索で上記の加工（図面番号: {no}）を探して選択").replace("{no}", infoTarget.drawingNo)}</li>
                <li>{tr("mcCommonPartsPage.mcStep5","「✅ 共通登録する」を押して完了")}</li>
              </ol>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setInfoTarget(null)}
                className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">{tr("mcCommonPartsPage.closeButton2","閉じる")}</button>
              <button onClick={() => { setInfoTarget(null); router.push(`/mc/${infoTarget.mcProgramId}`); }}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-bold rounded-xl hover:bg-teal-700">
                {tr("mcCommonPartsPage.openMcDetailButton", "このMCの詳細を開く →")}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 bg-emerald-700 text-white text-sm font-bold px-5 py-3 rounded-xl shadow-xl z-50">{toast}</div>
      )}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="edit" system="MC"
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}
    </div>
  );
}
