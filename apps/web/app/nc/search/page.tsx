"use client";
import { CompanyBrandTag } from "@/components/CompanyBrandTag";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ncApi, NcSearchResult, RecentAccess } from "@/lib/api";
import { toJstMonthDayTimeString } from "@/lib/dateUtils";
import { useLanguage } from "@/lib/i18n/LanguageContext";

// [MC統一] NC部品検索はMC部品検索(apps/web/app/mc/search/page.tsx)と同じ画面構成・
// 表示項目・表示位置・文字サイズにそろえる(配色のみNC用のsky系)。
const STATUS_KEY: Record<string, string> = {
  NEW: "search.statusNew", PENDING_APPROVAL: "search.statusPendingApproval",
  APPROVED: "search.statusApproved", CHANGING: "search.statusChanging",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};
type NcPartGroup = { drawing_no: string; part_name: string; part_id: string | null; client_name: string | null; rows: NcSearchResult[]; };
function groupByPart(results: NcSearchResult[]): NcPartGroup[] {
  const map = new Map<string, NcPartGroup>();
  for (const r of results) {
    if (!map.has(r.drawing_no)) map.set(r.drawing_no, { drawing_no: r.drawing_no, part_name: r.part_name, part_id: r.part_id ?? null, client_name: r.client_name ?? null, rows: [] });
    map.get(r.drawing_no)!.rows.push(r);
  }
  return Array.from(map.values());
}
export default function NcSearchPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [ncIdInput,        setNcIdInput]        = useState("");
  const [partIdInput,      setPartIdInput]      = useState("");
  const [drawingNoInput,   setDrawingNoInput]   = useState("");
  const [nameInput,        setNameInput]        = useState("");
  const [clientInput,      setClientInput]      = useState("");
  const [machineInput,     setMachineInput]     = useState("");
  const [machiningIdInput, setMachiningIdInput] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [results,  setResults]  = useState<NcSearchResult[]>([]);
  const [total,    setTotal]    = useState<number | null>(null);
  const [recent,   setRecent]   = useState<RecentAccess[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [clientNames, setClientNames] = useState<string[]>([]);
  // 右ペインの図面表示(認証なし・FIT表示) — MCと同じ
  const [drawing, setDrawing] = useState<{ ncId: number; drawingNo: string } | null>(null);
  const [drawingState, setDrawingState] = useState<"loading" | "ok" | "error">("loading");
  const openDrawing = (ncId: number, drawingNo: string) => { setDrawingState("loading"); setDrawing({ ncId, drawingNo }); };

  useEffect(() => {
    ncApi.recent().then(r => setRecent((r as any).data ?? [])).catch(() => {});
    fetch("/api/nc/client-names").then(r => r.json()).then(setClientNames).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    let searchKey = "drawing_no", searchQ = "";
    if (ncIdInput.trim())            { searchKey = "nc_id";        searchQ = ncIdInput.trim(); }
    else if (machiningIdInput.trim()){ searchKey = "machining_id"; searchQ = machiningIdInput.trim(); }
    else if (partIdInput.trim())     { searchKey = "part_id";      searchQ = partIdInput.trim(); }
    else if (drawingNoInput.trim())  { searchKey = "drawing_no";   searchQ = drawingNoInput.trim(); }
    else if (nameInput.trim())       { searchKey = "name";         searchQ = nameInput.trim(); }
    setLoading(true); setSelected(null);
    try {
      const params = new URLSearchParams({ key: searchKey, q: searchQ });
      if (clientInput)  params.set("client_name",  clientInput);
      if (machineInput) params.set("machine_code", machineInput);
      const res = await fetch(`/api/nc/search?${params}`).then(r => r.json());
      setResults(res.data ?? []); setTotal(res.total ?? 0);
    } catch { setResults([]); setTotal(0); }
    finally { setLoading(false); }
  }, [ncIdInput, machiningIdInput, partIdInput, drawingNoInput, nameInput, clientInput, machineInput]);

  const handleSelect = (ncId: number) => { setSelected(ncId); router.push(`/nc/${ncId}`); };
  const groups = groupByPart(results);
  const fmtCycle = (sec: number | null | undefined) => {
    if (!sec) return null;
    return `${Math.floor(sec/3600)}h${Math.floor((sec%3600)/60)}m${sec%60}s`;
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
        <CompanyBrandTag />
        <span className="text-base font-medium text-white">{t("search.ncSystemTitle", "NC 旋盤管理システム")}</span>
        <span className="ml-auto flex items-center gap-2"><button onClick={() => router.push("/nc")} className="text-xs bg-slate-600 hover:bg-slate-500 text-white font-bold px-3 py-1.5 rounded-lg transition-colors">{t("search.backToDashboard", "← ダッシュボードへ")}</button>
            <button onClick={() => router.push("/nc/new")} className="text-xs bg-sky-500 hover:bg-sky-400 text-white font-bold px-3 py-1.5 rounded-lg transition-colors">{t("search.newRegister", "＋ 新規登録")}</button><span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">{t("search.noAuthRequired", "認証不要")}</span></span>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="w-[240px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4 space-y-2">
            <h2 className="text-sm font-bold text-slate-700">{t("search.ncPartSearch", "NC 部品検索")}</h2>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide pt-1">{t("search.idDirect", "ID 直接指定")}</div>
            <div>
              <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.ncIdLabel", "NC ID")} <span className="text-[10px] text-slate-400 font-normal">{t("search.legacyNcId", "(旧NC ID)")}</span></label>
              <input type="number" value={ncIdInput} onChange={e => setNcIdInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="2554" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
            </div>
            <div>
              {/* [MC統一] 旧K_idはMCの「加工ID」に相当する。NC IDとは別の検索条件。 */}
              <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.machiningIdKIdLabelNc", "加工ID（K_ID）")}</label>
              <input type="number" value={machiningIdInput} onChange={e => setMachiningIdInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="92" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
            </div>
            <div>
              <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.partIdLabel", "部品ID")}</label>
              <input type="number" value={partIdInput} onChange={e => setPartIdInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="3807" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              <div className="text-[10px] text-slate-400 mt-0.5">{t("search.multiProcessNote", "※複数工程は別行で表示")}</div>
            </div>
            <div className="border-t border-slate-100 pt-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-2">{t("search.textCondition", "テキスト条件")}</div>
              <div className="space-y-2">
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.drawingNoLabel", "図面番号")}</label>
                  <input type="text" value={drawingNoInput} onChange={e => setDrawingNoInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="F67487" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.nameLabel", "名称")}</label>
                  <input type="text" value={nameInput} onChange={e => setNameInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder={t("search.namePlaceholder", "部品名称の一部")} className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.clientLabel", "納入先")}</label>
                  <select value={clientInput} onChange={e => setClientInput(e.target.value)} className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400">
                    <option value="">{t("search.allOption", "— すべて —")}</option>
                    {clientNames.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">{t("search.machineTypeLabel", "主機種型式")}</label>
                  <input type="text" value={machineInput} onChange={e => setMachineInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="NL3000-2" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
              </div>
            </div>
            <button onClick={handleSearch} disabled={loading} className="w-full bg-sky-600 hover:bg-sky-700 disabled:bg-slate-300 text-white py-2 rounded-lg text-sm font-bold transition-colors mt-1">{loading ? t("search.searching", "検索中...") : t("search.searchButton", "● 検索")}</button>
            {results.length > 0 && <button onClick={() => { setNcIdInput(""); setMachiningIdInput(""); setPartIdInput(""); setDrawingNoInput(""); setNameInput(""); setClientInput(""); setMachineInput(""); setResults([]); setTotal(null); }} className="w-full border border-slate-200 text-slate-500 hover:bg-slate-50 py-1.5 rounded-lg text-xs">{t("search.clearButton", "クリア")}</button>}
            {total !== null && <div className="text-xs text-slate-500 bg-slate-50 rounded p-2">{total > 0 ? <span>{t("search.hitCount","{n} 件ヒット").replace("{n}", String(total))}</span> : <span className="text-red-500">{t("search.noHit", "0件（条件を変更してください）")}</span>}</div>}

            {/* 最近のアクセス(直近10件) — MCと同じく検索条件の下に表示。はみ出しはサイドバーごとスクロール */}
            {recent.length > 0 && (
              <div className="border-t border-slate-100 pt-2">
                <h3 className="text-xs font-bold text-slate-600 mb-2">{t("search.recentAccess", "最近のアクセス")} <span className="font-normal text-slate-400 text-[10px]">{t("search.recent10", "直近10件")}</span></h3>
                <div className="space-y-1.5">
                  {recent.map((r, i) => (
                    <div key={i} onClick={() => handleSelect(r.nc_id)} className="bg-white border border-slate-200 rounded-lg px-2 py-1.5 cursor-pointer hover:border-sky-300 hover:shadow-sm transition-all">
                      <div className="font-mono text-sky-600 font-bold text-xs truncate">{r.drawing_no}</div>
                      <div className="font-mono text-[10px] text-slate-400 truncate">
                        {t("search.ncIdColon","NC ID : {id}").replace(" : ", ":").replace("{id}", String(r.legacy_nc_id ?? r.nc_id))}
                        {r.machining_id != null && <> {t("search.machiningIdColon","加工ID:{id}").replace("{id}", String(r.machining_id))}</>}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate">{r.part_name}</div>
                      {r.accessed_at && <div className="text-[10px] text-slate-400">{toJstMonthDayTimeString(r.accessed_at)}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>
        <main className="w-[460px] shrink-0 border-r border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-white shrink-0 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-700">{t("search.resultTitle", "検索結果")}</span>
            {total !== null && total > 0 && <span className="text-xs text-slate-400">{t("search.hitCountShort","{n}件").replace("{n}", String(total))}</span>}
          </div>
          <div className="flex-1 overflow-y-auto">
            {results.length === 0 && total === null && <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2"><div className="text-4xl">🔍</div><p className="text-sm">{t("search.emptyStatePrompt", "左の検索フォームから検索してください")}</p></div>}
            {groups.map((g, gi) => (
              <div key={gi} className="border-b-2 border-slate-300">
                <div className="px-4 py-2 bg-green-50 flex items-center gap-3 border-b border-slate-200">
                  {g.part_id && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-violet-100 text-violet-700 font-mono shrink-0">{t("search.partIdBadge","部品ID:{id}").replace("{id}", g.part_id)}</span>}
                  <span className="font-mono text-slate-800 font-bold text-sm">{g.drawing_no}</span>
                  <span className="text-slate-700 font-medium text-sm truncate flex-1">{g.part_name}</span>
                  {g.client_name && <span className="text-slate-400 text-xs shrink-0 truncate max-w-[120px]">{g.client_name}</span>}
                  {g.drawing_no && g.rows[0] && (
                    <button onClick={e => { e.stopPropagation(); openDrawing(g.rows[0].id, g.drawing_no); }}
                      className={`text-[11px] font-bold px-2 py-0.5 rounded border shrink-0 transition-colors ${drawing?.drawingNo === g.drawing_no ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-indigo-700 border-indigo-300 hover:bg-indigo-50"}`}>
                      📋 図面
                    </button>
                  )}
                </div>
                {g.rows.map((r, ri) => (
                  <div key={r.id} onClick={() => handleSelect(r.id)}
                    className={`px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors border-b border-dashed border-slate-200 ${selected===r.id ? "bg-sky-50" : "hover:bg-slate-50"}`}>
                    <span className="min-w-[28px] h-6 px-1 rounded bg-sky-600 text-white flex items-center justify-center text-xs font-bold shrink-0">{r.process_l != null ? `L${r.process_l}` : ri+1}</span>
                    <span className="font-mono text-xs text-slate-600 shrink-0">{t("search.ncIdColon","NC ID : {id}").replace("{id}", String(r.nc_id))}</span>
                    {r.machine_code && <span className="text-sm text-slate-700 font-medium shrink-0">{r.machine_code}</span>}
                    <span className="text-xs text-slate-400 shrink-0">{t("search.machiningIdColon","加工ID:{id}").replace("{id}", String(r.machining_id))}</span>
                    <span className="ml-auto flex items-center gap-2">
                      {fmtCycle(r.machining_time_sec) && <span className="text-xs text-slate-400">⏱ {fmtCycle(r.machining_time_sec)}</span>}
                      {r.version && <span className="text-xs text-slate-400">Ver. {r.version}</span>}
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${STATUS_COLOR[r.status]??"bg-slate-100 text-slate-600"}`}>{STATUS_KEY[r.status] ? t(STATUS_KEY[r.status]) : r.status}</span>
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </main>
        <section className="flex-1 min-w-0 flex flex-col bg-slate-900" onContextMenu={e => e.preventDefault()}>
          {drawing ? (<>
            {/* 図面は表示のみ(印刷不可): ブラウザ印刷時は白紙にする */}
            <style>{"@media print{body{display:none !important}}"}</style>
            <div className="px-4 py-2 bg-slate-800 text-white text-sm font-bold flex items-center gap-2 shrink-0">
              <span>📋 図面 —</span><span className="font-mono">{drawing.drawingNo}</span>
              <button onClick={() => setDrawing(null)} className="ml-auto text-slate-300 hover:text-white text-lg px-1.5">✕</button>
            </div>
            <div className="flex-1 min-h-0 flex items-center justify-center p-2">
              {drawingState === "loading" && (
                <div className="flex flex-col items-center gap-3 text-slate-400">
                  <div className="w-8 h-8 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
                  <span className="text-sm">図面を取得中…</span>
                </div>
              )}
              {drawingState === "error" && (
                <p className="text-slate-400 text-sm text-center px-8">図面を取得できませんでした<br /><span className="text-xs text-slate-500">（Ridocに図面が無い、またはRidocサーバー未応答）</span></p>
              )}
              <img key={`${drawing.ncId}-${drawing.drawingNo}`} src={`/api/nc/${drawing.ncId}/drawing-image?imgType=ORG`}
                alt={drawing.drawingNo} draggable={false}
                onLoad={() => setDrawingState("ok")} onError={() => setDrawingState("error")}
                className={`max-w-full max-h-full object-contain select-none ${drawingState === "ok" ? "" : "hidden"}`} />
            </div>
          </>) : (
            <div className="flex-1 overflow-y-auto p-5 bg-slate-50">
              <div className="bg-white border border-slate-200 rounded-lg p-5">
                <h3 className="text-sm font-bold text-slate-700 mb-2">{t("search.welcomeNc", "⚙ NC システムへようこそ")}</h3>
                <div className="text-xs text-slate-500 space-y-1">
                  <div>{t("search.ncTip1", "• 図面番号・部品名称・NC ID・加工IDで検索可能")}</div>
                  <div>{t("search.tip2", "• 加工IDが同じ = 共通加工")}</div>
                  <div>{t("search.tip3", "• 空欄のまま検索 = 全件表示")}</div>
                  <div>• 検索結果の「📋 図面」でこの欄に図面を表示（認証不要）</div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
