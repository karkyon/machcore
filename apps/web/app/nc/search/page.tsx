"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ncApi, NcSearchResult, RecentAccess } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};
const PROCESS_COLOR: Record<string, string> = {
  L1: "bg-sky-600 text-white", L2: "bg-violet-600 text-white",
  L3: "bg-orange-500 text-white", SL: "bg-teal-600 text-white",
};
type PartGroup = { drawing_no: string; part_name: string; part_id: string | null; client_name: string | null; rows: NcSearchResult[]; };
function groupByPart(results: NcSearchResult[]): PartGroup[] {
  const map = new Map<string, PartGroup>();
  for (const r of results) {
    if (!map.has(r.drawing_no)) map.set(r.drawing_no, { drawing_no: r.drawing_no, part_name: r.part_name, part_id: (r as any).part_id ?? null, client_name: r.client_name ?? null, rows: [] });
    map.get(r.drawing_no)!.rows.push(r);
  }
  return Array.from(map.values());
}
export default function NcSearchPage() {
  const router = useRouter();
  const [ncIdInput,      setNcIdInput]      = useState("");
  const [partIdInput,    setPartIdInput]    = useState("");
  const [drawingNoInput, setDrawingNoInput] = useState("");
  const [nameInput,      setNameInput]      = useState("");
  const [clientInput,    setClientInput]    = useState("");
  const [machineInput,   setMachineInput]   = useState("");
  const [loading,  setLoading]  = useState(false);
  const [results,  setResults]  = useState<NcSearchResult[]>([]);
  const [total,    setTotal]    = useState<number | null>(null);
  const [recent,   setRecent]   = useState<RecentAccess[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [clientNames, setClientNames] = useState<string[]>([]);
  const [isAdmin,  setIsAdmin]  = useState(false);
  const [adminInfo, setAdminInfo] = useState<{ companyName?: string; logoPath?: string } | null>(null);

  useEffect(() => {
    ncApi.recent().then(r => setRecent(r.data)).catch(() => {});
    fetch("/api/nc/client-names").then(r => r.json()).then(setClientNames).catch(() => {});
    const token = sessionStorage.getItem("admin_token");
    if (!token) return;
    setIsAdmin(true);
    fetch("/api/admin/company", { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null).then(data => { if (data) setAdminInfo(data); }).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    let searchKey = "drawing_no", searchQ = "";
    if (ncIdInput.trim())           { searchKey = "nc_id";      searchQ = ncIdInput.trim(); }
    else if (partIdInput.trim())    { searchKey = "part_id";    searchQ = partIdInput.trim(); }
    else if (drawingNoInput.trim()) { searchKey = "drawing_no"; searchQ = drawingNoInput.trim(); }
    else if (nameInput.trim())      { searchKey = "name";       searchQ = nameInput.trim(); }
    setLoading(true); setSelected(null);
    try {
      const params = new URLSearchParams({ key: searchKey, q: searchQ });
      if (clientInput)  params.set("client_name", clientInput);
      if (machineInput) params.set("machine_id",  machineInput);
      const res = await fetch(`/api/nc/search?${params}`).then(r => r.json());
      setResults(res.data ?? []); setTotal(res.total ?? 0);
    } catch { setResults([]); setTotal(0); }
    finally { setLoading(false); }
  }, [ncIdInput, partIdInput, drawingNoInput, nameInput, clientInput, machineInput]);

  const handleSelect = (ncId: number) => { setSelected(ncId); router.push(`/nc/${ncId}`); };
  const groups = groupByPart(results);
  const fmtTime = (sec: number | null) => {
    if (!sec) return null;
    return `${Math.floor(sec/3600)}H ${String(Math.floor((sec%3600)/60)).padStart(2,"0")}M`;
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        {adminInfo?.logoPath && <img src={adminInfo.logoPath.replace(/^apps\/web\/public/,"").replace(/^\/+/,"/")} alt="logo" className="h-7 object-contain" />}
        <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
        <span className="text-base font-medium">{adminInfo?.companyName ?? "NC 旋盤管理システム"}</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>
          {isAdmin && <div className="flex items-center gap-2 pl-2 border-l border-slate-700">
            <span className="text-[11px] text-slate-300">管理者</span>
            <button onClick={() => router.push("/admin")} className="text-xs bg-sky-600 hover:bg-sky-700 px-2 py-0.5 rounded font-medium">管理画面</button>
          </div>}
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="w-[240px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4 space-y-2">
            <h2 className="text-sm font-bold text-slate-700">NC 部品検索</h2>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide pt-1">ID 直接指定</div>
            <div>
              <label className="text-sm font-bold text-slate-700 block mb-1">NC ID（K_id）</label>
              <input type="number" value={ncIdInput} onChange={e => setNcIdInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="例: 92" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
            </div>
            <div>
              <label className="text-sm font-bold text-slate-700 block mb-1">部品ID</label>
              <input type="number" value={partIdInput} onChange={e => setPartIdInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="例: 3807" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              <div className="text-[10px] text-slate-400 mt-0.5">※複数工程は別行で表示</div>
            </div>
            <div className="border-t border-slate-100 pt-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-2">テキスト条件</div>
              <div className="space-y-2">
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">図面番号</label>
                  <input type="text" value={drawingNoInput} onChange={e => setDrawingNoInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="F67487" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">名称</label>
                  <input type="text" value={nameInput} onChange={e => setNameInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="部品名称の一部" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">納入先</label>
                  <select value={clientInput} onChange={e => setClientInput(e.target.value)} className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400">
                    <option value="">— すべて —</option>
                    {clientNames.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-1">主機種型式</label>
                  <input type="text" value={machineInput} onChange={e => setMachineInput(e.target.value)} onKeyDown={e => e.key==="Enter" && handleSearch()} placeholder="例: SL-25" className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
              </div>
            </div>
            <button onClick={handleSearch} disabled={loading} className="w-full bg-sky-600 hover:bg-sky-700 disabled:bg-slate-300 text-white py-2 rounded-lg text-sm font-bold transition-colors mt-1">{loading ? "検索中..." : "● 検索"}</button>
            {results.length > 0 && <button onClick={() => { setNcIdInput(""); setPartIdInput(""); setDrawingNoInput(""); setNameInput(""); setClientInput(""); setMachineInput(""); setResults([]); setTotal(null); }} className="w-full border border-slate-200 text-slate-500 hover:bg-slate-50 py-1.5 rounded-lg text-xs">クリア</button>}
            {total !== null && <div className="text-xs text-slate-500 bg-slate-50 rounded p-2">{total > 0 ? <span><b className="text-slate-700">{total}</b> 件ヒット</span> : <span className="text-red-500">0件（条件を変更してください）</span>}</div>}
            {recent.length > 0 && <div className="pt-2 border-t border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-2">最近のアクセス</div>
              {recent.slice(0,5).map((r: any,i) => (
                <div key={i} onClick={() => handleSelect(r.nc_id)} className="flex items-center gap-2 py-1.5 px-1 rounded cursor-pointer hover:bg-slate-50 text-[11px]">
                  <span className="font-mono text-sky-600 font-bold w-10 shrink-0">{r.nc_id}</span>
                  <span className="text-slate-600 truncate">{r.drawing_no}</span>
                </div>
              ))}
            </div>}
            {isAdmin && <div className="pt-2 border-t border-slate-100 text-center"><button onClick={() => router.push("/admin")} className="text-xs text-sky-500 hover:underline">▶ 管理画面へ</button></div>}
          </div>
        </aside>
        <main className="w-[460px] shrink-0 border-r border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-white shrink-0 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-700">検索結果</span>
            {total !== null && total > 0 && <span className="text-xs text-slate-400">{total}件</span>}
          </div>
          <div className="flex-1 overflow-y-auto">
            {results.length === 0 && total === null && <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2"><div className="text-4xl">🔍</div><p className="text-sm">左の検索フォームから検索してください</p></div>}
            {groups.map((g, gi) => (
              <div key={gi} className="border-b-2 border-slate-300">
                <div className="px-4 py-2 bg-green-50 flex items-center gap-3 border-b border-slate-200">
                  <span className="font-mono text-slate-800 font-bold text-sm">{g.drawing_no}</span>
                  <span className="text-slate-700 font-medium text-sm truncate flex-1">{g.part_name}</span>
                  {g.part_id && <span className="text-slate-500 text-xs shrink-0">/ {g.part_id}</span>}
                  {g.client_name && <span className="text-slate-400 text-xs shrink-0 truncate max-w-[120px]">{g.client_name}</span>}
                </div>
                {g.rows.map((r, ri) => {
                  const proc = String(r.process_l ?? "");
                  const colorClass = Object.entries(PROCESS_COLOR).find(([k]) => proc.startsWith(k))?.[1] ?? "bg-slate-500 text-white";
                  return (
                    <div key={r.nc_id} onClick={() => handleSelect(r.nc_id)}
                      className={`px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors border-b border-dashed border-slate-200 ${selected===r.nc_id ? "bg-sky-50" : "hover:bg-slate-50"}`}>
                      <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold shrink-0 ${colorClass}`}>{ri+1}</span>
                      <span className="font-mono text-xs text-slate-600 shrink-0">NC ID : {r.nc_id}</span>
                      {r.machine_code && <span className="text-sm text-slate-700 font-medium shrink-0">{r.machine_code}</span>}
                      {(r as any).machining_time_sec && <span className="text-xs text-slate-400 shrink-0">⏱ {fmtTime((r as any).machining_time_sec)}</span>}
                      <span className="ml-auto flex items-center gap-2">
                        {r.version && <span className="text-xs text-slate-400">Ver. {r.version}</span>}
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${STATUS_COLOR[r.status]??"bg-slate-100 text-slate-600"}`}>{STATUS_LABEL[r.status]??r.status}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </main>
        <section className="flex-1 overflow-y-auto p-5">
          {recent.length > 0 ? (<>
            <h3 className="text-sm font-bold text-slate-600 mb-3">最近のアクセス <span className="font-normal text-slate-400 text-xs">直近5件の操作履歴</span></h3>
            <div className="space-y-2">
              {recent.map((r: any,i) => (
                <div key={i} onClick={() => handleSelect(r.nc_id)} className="bg-white border border-slate-200 rounded-lg px-4 py-3 cursor-pointer hover:border-sky-300 hover:shadow-sm transition-all flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono text-sky-600 font-bold text-sm">{r.drawing_no}</span>
                      {r.process_l && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${PROCESS_COLOR[String(r.process_l)]??"bg-slate-500 text-white"}`}>{r.process_l}</span>}
                    </div>
                    <div className="text-xs text-slate-500 truncate">{r.part_name}</div>
                  </div>
                  <div className="text-right shrink-0">
                    {r.operator_name && <div className="text-[11px] text-slate-500">👤 {r.operator_name}</div>}
                    {r.accessed_at && <div className="text-[10px] text-slate-400">{new Date(r.accessed_at).toLocaleString("ja-JP",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}</div>}
                  </div>
                </div>
              ))}
            </div>
          </>) : (<div className="flex flex-col items-center justify-center h-full text-slate-300 gap-3"><div className="text-5xl">📋</div><p className="text-sm">操作履歴はまだありません</p></div>)}
        </section>
      </div>
    </div>
  );
}
