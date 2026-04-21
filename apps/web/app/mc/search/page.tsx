"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, McSearchResult, Machine } from "@/lib/api";

const SEARCH_KEYS = [
  { value: "drawing_no", label: "図面番号" },
  { value: "part_name",  label: "部品名称" },
  { value: "mcid",       label: "MCID" },
  { value: "machining_id", label: "加工ID" },
];

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};

export default function McSearchPage() {
  const router = useRouter();
  const [key,      setKey]      = useState("drawing_no");
  const [q,        setQ]        = useState("");
  const [loading,  setLoading]  = useState(false);
  const [results,  setResults]  = useState<McSearchResult[]>([]);
  const [total,    setTotal]    = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [recent,   setRecent]   = useState<any[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [machineInput, setMachineInput] = useState("");
  const [clientInput,  setClientInput]  = useState("");

  useEffect(() => {
    mcApi.recent().then(r => setRecent(r.data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r.data ?? []).filter((m: Machine) => m.isActive))).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    setLoading(true); setSelected(null);
    try {
      const res = await mcApi.search(key, q, {
        client_name: clientInput || undefined,
        machine_id:  machineInput ? parseInt(machineInput) : undefined,
      });
      const d = (res as any).data ?? res;
      setResults(d.rows ?? []);
      setTotal(d.total ?? 0);
    } catch { setResults([]); setTotal(0); }
    finally  { setLoading(false); }
  }, [key, q, clientInput, machineInput]);

  const handleSelect = (mcId: number) => { setSelected(mcId); router.push(`/mc/${mcId}`); };

  const fmtCycle = (sec: number | null) => {
    if (!sec) return "";
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return `${h}H ${String(m).padStart(2,"0")}M ${String(s).padStart(2,"0")}S`;
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <span className="font-mono text-teal-400 font-bold text-sm">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs bg-white text-slate-800 hover:bg-slate-100 border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>
        <span className="text-sm font-medium text-teal-300">MC マシニング管理システム</span>
        <span className="ml-auto text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 左: 検索フォーム */}
        <aside className="w-[260px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-700">MC 部品検索</h2>
              <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-bold">認証不要</span>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block mb-1">検索キー</label>
                <select value={key} onChange={e => setKey(e.target.value)}
                  className="w-full border border-teal-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-400">
                  {SEARCH_KEYS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block mb-1">検索文字列</label>
                <input type="text" value={q} onChange={e => setQ(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="空欄 = 全件表示"
                  className="w-full border border-teal-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">機械</label>
                <select value={machineInput} onChange={e => setMachineInput(e.target.value)}
                  className="w-full border border-teal-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-400">
                  <option value="">— すべて —</option>
                  {machines.map(m => <option key={m.id} value={String(m.id)}>{m.machineCode}</option>)}
                </select>
              </div>
            </div>
            <div className="pt-3 space-y-2">
              <button onClick={handleSearch} disabled={loading}
                className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-2 rounded-lg text-sm transition-colors">
                {loading ? "検索中..." : "🔍 検索"}
              </button>
              {results.length > 0 && (
                <button onClick={() => { setQ(""); setResults([]); setTotal(null); }}
                  className="w-full border border-slate-200 text-slate-500 hover:bg-slate-50 py-1.5 rounded-lg text-xs">クリア</button>
              )}
            </div>
            {total !== null && (
              <div className="mt-3 text-xs text-slate-500 bg-slate-50 rounded p-2">
                {total > 0 ? <span><b className="text-slate-700">{total}</b> 件ヒット</span>
                           : <span className="text-red-500">0件（条件を変更してください）</span>}
              </div>
            )}
            {/* 最近のアクセス */}
            {recent.length > 0 && (
              <div className="mt-4">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-2">最近のアクセス</div>
                {recent.slice(0, 5).map((r, i) => (
                  <div key={i} onClick={() => handleSelect(r.mc_id)}
                    className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 text-[11px]">
                    <span className="font-mono text-teal-600 font-bold w-10">{r.mc_id}</span>
                    <span className="text-slate-600 truncate">{r.part_name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>

        {/* 中: 検索結果 */}
        <main className="w-[420px] shrink-0 border-r border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 bg-white shrink-0 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-700">検索結果</span>
            {total !== null && total > 0 && <span className="text-xs text-slate-400">{total}件</span>}
          </div>
          <div className="flex-1 overflow-y-auto">
            {results.length === 0 && total === null && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                <div className="text-4xl">🔍</div>
                <p className="text-sm">左の検索フォームから検索してください</p>
              </div>
            )}
            {results.map(r => (
              <div key={r.mc_id} onClick={() => handleSelect(r.mc_id)}
                className={`px-4 py-3 border-b border-slate-100 cursor-pointer transition-colors ${
                  selected === r.mc_id ? "bg-teal-50 border-l-4 border-l-teal-400 pl-3" : "hover:bg-slate-50"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-teal-600 font-bold text-xs">MCID:{r.mc_id}</span>
                  <span className="font-mono text-slate-600 text-xs">{r.drawing_no}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[r.status] ?? "bg-slate-100 text-slate-600"}`}>
                    {STATUS_LABEL[r.status] ?? r.status}
                  </span>
                  {r.common_part_code && (
                    <span className="text-[10px] bg-pink-100 text-pink-700 px-1.5 py-0.5 rounded font-bold">共通</span>
                  )}
                  <span className="ml-auto font-mono text-[10px] text-slate-400">Ver.{r.version}</span>
                </div>
                <div className="text-sm text-slate-700 mb-1">{r.part_name}</div>
                <div className="flex items-center gap-3 text-[11px] text-slate-400">
                  {r.machine_code && <span>🔧 {r.machine_code}</span>}
                  {r.client_name  && <span>🏭 {r.client_name}</span>}
                  {r.cycle_time_sec && <span>⏱ {fmtCycle(r.cycle_time_sec)}</span>}
                  <span className="ml-auto font-mono">加工ID:{r.machining_id}</span>
                </div>
              </div>
            ))}
          </div>
        </main>

        {/* 右: ガイド */}
        <aside className="flex-1 flex flex-col overflow-hidden bg-white">
          <div className="px-4 py-3 border-b border-slate-100 shrink-0">
            <span className="text-sm font-bold text-slate-700">操作ガイド</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-3 text-xs text-slate-500">
              <div className="bg-teal-50 rounded-lg p-3 border border-teal-100">
                <p className="font-bold text-teal-700 mb-1">🔧 MC システムへようこそ</p>
                <p>マシニングセンタ（MC）のNCプログラム・ツーリング・作業記録を管理します。</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="font-bold text-slate-600 mb-1">検索のヒント</p>
                <ul className="space-y-1 text-slate-400">
                  <li>• 図面番号・部品名称・MCID・加工IDで検索可能</li>
                  <li>• 加工IDが同じ = 共通加工（複数部品が同プログラムを使用）</li>
                  <li>• 空欄のまま検索 = 全件表示</li>
                </ul>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
