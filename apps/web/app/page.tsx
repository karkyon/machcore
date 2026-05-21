"use client";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { authApi, mcApi, ncApi, usersApi } from "@/lib/api";
import AuthModal from "@/components/auth/AuthModal";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";

type McSheet = {
  id: number; mc_id: number;
  legacy_mcid: number | null; machining_id: number;
  part_id: string; drawing_no: string; part_name: string;
  client_name: string | null; main_model: string | null;
  mc_process_no: number | null;
  machine_code: string | null; machine_name: string | null; machine_sort: number;
  version: string | null; printed_at: string; operator_name: string;
};
type Summary = {
  nc_total: number; mc_total: number;
  nc_pending: number; mc_pending: number;
  nc_uncollected: number; mc_uncollected: number;
};
type Period = "week" | "twoweeks" | "all";

function ageDays(iso: string) { return (Date.now() - new Date(iso).getTime()) / 86400000; }
function rowCls(iso: string) {
  const d = ageDays(iso);
  if (d > 14) return "border-l-4 border-l-red-400 bg-red-50 hover:bg-red-100";
  if (d > 7)  return "border-l-4 border-l-blue-400 bg-blue-50 hover:bg-blue-100";
  return "hover:bg-slate-50";
}
function ageCls(iso: string) {
  const d = ageDays(iso);
  if (d > 14) return "text-red-600 font-bold";
  if (d > 7)  return "text-blue-600 font-bold";
  return "text-amber-600";
}
function elapsed(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000), m = Math.floor((diff % 3600000) / 60000);
  if (h >= 24) return Math.floor(h/24) + "日前";
  if (h > 0)   return h + "時間" + m + "分前";
  return m + "分前";
}
function fmtDt(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("ja-JP",{month:"2-digit",day:"2-digit"}) + " " +
         d.toLocaleTimeString("ja-JP",{hour:"2-digit",minute:"2-digit"});
}
function groupByMachine(items: McSheet[]) {
  const map = new Map<string, McSheet[]>();
  for (const item of items) {
    const key = item.machine_code ?? "未設定";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}
function filterPeriod(items: McSheet[], p: Period) {
  if (p === "all") return items;
  return items.filter(i => ageDays(i.printed_at) <= (p === "week" ? 7 : 14));
}

export default function McDashboard() {
  const router = useRouter();
  const { token: authToken, login } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sheets,  setSheets]  = useState<McSheet[]>([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastAt,  setLastAt]  = useState<Date | null>(null);
  const [period,  setPeriod]  = useState<Period>("week");
  const [collectingId,  setCollectingId]  = useState<{system:"NC"|"MC"; id:number; programId:number} | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [collectErr,    setCollectErr]    = useState<string | null>(null);
  const [users,         setUsers]         = useState<any[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([
        fetch(API_URL + "/dashboard/summary").then(r => r.json()),
        fetch(API_URL + "/dashboard/uncollected-mc").then(r => r.json()),
      ]);
      setSummary(s);
      setSheets(u.items ?? []);
      setTotal(u.total ?? 0);
      setLastAt(new Date());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  useEffect(() => {
    const _API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
    fetch(`${_API}/users`).then(r => r.json()).then(d => setUsers(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const filtered = filterPeriod(sheets, period);
  const grouped  = groupByMachine(filtered);

  const handleCollectClick = (system: "NC" | "MC", id: number, programId: number) => {
    setCollectingId({ system, id, programId });
    setCollectErr(null);
    setShowAuthModal(true);
  };

  const handleAuthSuccess = async () => {
    if (!collectingId) return;
    setShowAuthModal(false);
    // useAuth の login() が呼ばれた直後なので token は次の tick で取れる
    // setTimeout で 1tick 待ってから取得
    setTimeout(async () => {
      const tok = authToken ?? (typeof window !== "undefined" ? localStorage.getItem("work_token") : null);
      if (!tok) { setCollectErr("認証トークンが取得できませんでした"); setCollectingId(null); return; }
      try {
        const { system, id, programId } = collectingId!;
        const _API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
        const res = await fetch(`${_API}/${system.toLowerCase()}/${programId}/setup-sheet-logs/${id}/collect`, {
          method: "PUT",
          headers: { "Authorization": `Bearer ${tok}` },
        });
        if (!res.ok) throw new Error("回収処理に失敗しました");
        await load();
      } catch (e: any) {
        setCollectErr(e.message ?? "エラーが発生しました");
      } finally {
        setCollectingId(null);
      }
    }, 100);
  };

  return (
    <>
      {showAuthModal && (
        <AuthModal
          isOpen={true}
          sessionType="MC_WORK_RECORD"
          mcProgramId={collectingId?.system === "MC" ? collectingId?.programId : undefined}
          ncProgramId={collectingId?.system === "NC" ? collectingId?.programId : undefined}
          onSuccess={handleAuthSuccess}
          onCancel={() => { setShowAuthModal(false); setCollectingId(null); }}
        />
      )}
      {collectErr && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-600 text-white text-sm px-4 py-2 rounded-lg shadow-lg">
          {collectErr}
          <button onClick={() => setCollectErr(null)} className="ml-3 text-red-200 hover:text-white">✕</button>
        </div>
      )}
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">MC マシニング ダッシュボード</span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <button onClick={() => router.push("/")}
            className="bg-sky-600 hover:bg-sky-500 text-white px-3 py-1.5 rounded font-bold transition-colors">
            NC 旋盤 →
          </button>
          {lastAt && <span className="text-slate-400">更新: {lastAt.toLocaleTimeString("ja-JP",{hour:"2-digit",minute:"2-digit"})}</span>}
          <button onClick={load} className="bg-slate-700 hover:bg-slate-600 px-2.5 py-1.5 rounded transition-colors text-slate-300">
            ↺ 更新
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* サイドバー: MCのみ */}
        <aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">MC マシニング</p>
            <nav className="space-y-1">
              {[
                { label: "ダッシュボード", href: "/mc",         active: true },
                { label: "部品検索",       href: "/mc/search",  active: false },
                { label: "新規登録",       href: "/mc/new",     active: false },
              ].map(item => (
                <button key={item.href} onClick={() => router.push(item.href)}
                  className={"w-full px-3 py-2 rounded-lg text-left text-sm transition-colors " +
                    (item.active ? "bg-teal-50 text-teal-700 font-bold border border-teal-200" : "text-slate-600 hover:bg-teal-50 hover:text-teal-700")}>
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
          <div className="p-4 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">管理</p>
            <button onClick={() => router.push("/admin/login")}
              className="w-full px-3 py-2 rounded-lg text-left text-sm text-slate-600 hover:bg-slate-100 transition-colors">
              管理パネル
            </button>
          </div>
          {total > 0 && (
            <div className="mx-3 mt-auto mb-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <p className="text-xs font-bold text-amber-700">未回収 {total}枚</p>
              <p className="text-[10px] text-amber-500 mt-0.5">表示中: {filtered.length}枚</p>
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* サマリー */}
          <section>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">MC システム状況</h2>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "MC 登録数",    value: summary?.mc_total,       cls: "text-teal-600",    bg: "bg-teal-50",    border: "border-teal-200" },
                { label: "MC 未承認",    value: summary?.mc_pending,     cls: summary?.mc_pending ? "text-yellow-600" : "text-slate-400", bg: "bg-white", border: "border-slate-200" },
                { label: "未回収シート", value: summary?.mc_uncollected, cls: summary?.mc_uncollected ? "text-red-600" : "text-emerald-600",
                  bg: summary?.mc_uncollected ? "bg-red-50" : "bg-emerald-50",
                  border: summary?.mc_uncollected ? "border-red-200" : "border-emerald-200" },
              ].map(c => (
                <div key={c.label} className={"rounded-xl px-4 py-3 border " + c.bg + " " + c.border}>
                  <div className="text-[10px] text-slate-400 mb-1">{c.label}</div>
                  <div className={"text-2xl font-bold " + c.cls}>{loading ? "…" : (c.value ?? 0).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </section>

          {/* 段取シート一覧 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">現在発行中の段取シート（MC）</h2>
                <span className="text-[10px] bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-bold">全 {total} 枚</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-3 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1"><span className="w-3 h-2 border-l-2 border-l-slate-300 bg-white inline-block"/>7日以内</span>
                  <span className="flex items-center gap-1 text-blue-600"><span className="w-3 h-2 border-l-2 border-l-blue-400 bg-blue-50 inline-block"/>7〜14日</span>
                  <span className="flex items-center gap-1 text-red-600"><span className="w-3 h-2 border-l-2 border-l-red-400 bg-red-50 inline-block"/>14日超</span>
                </div>
                <div className="flex items-center gap-0.5 bg-white border border-slate-200 rounded-lg p-0.5">
                  {([["week","直近1週間"],["twoweeks","直近2週間"],["all","すべて"]] as const).map(([k,l]) => (
                    <button key={k} onClick={() => setPeriod(k)}
                      className={"px-2.5 py-1 rounded text-xs font-bold transition-colors " + (period===k ? "bg-slate-700 text-white" : "text-slate-500 hover:bg-slate-100")}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {loading ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">読み込み中…</div>
            ) : filtered.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                <div className="text-3xl mb-2">✅</div>
                <p className="text-emerald-600 font-bold text-sm">{total === 0 ? "未回収シートはありません" : "この期間の未回収シートはありません"}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {Array.from(grouped.entries()).map(([mc, items]) => (
                  <div key={mc} className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-amber-400"/>
                      <span className="font-mono font-bold text-sm text-slate-800">{mc}</span>
                      <span className="text-slate-500 text-xs">{items[0]?.machine_name ?? ""}</span>
                      <span className="ml-auto text-xs text-amber-700 font-bold bg-amber-100 px-2 py-0.5 rounded-full">{items.length}枚</span>
                    </div>
                    {/* テーブルヘッダー */}
                    <div className="grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-1.5 bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase">
                      <span>MCID</span><span>加工ID</span><span>部品ID</span><span>工程</span><span>図番 / 部品名 / 納入先</span><span>印刷日時</span><span>印刷者</span><span>経過</span><span/>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {items.map(item => (
                        <button key={item.id}
                          onClick={() => router.push("/mc/" + item.mc_id + "/record")}
                          className={"w-full grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-2.5 items-center text-left transition-colors " + rowCls(item.printed_at)}>
                          <span className="font-mono text-xs text-slate-500">{item.legacy_mcid ?? "-"}</span>
                          <span className="font-mono text-xs text-slate-500">{item.machining_id}</span>
                          <span className="font-mono text-xs text-slate-600">{item.part_id}</span>
                          <span className="text-xs">
                            {item.mc_process_no != null
                              ? <span className="bg-teal-100 text-teal-700 font-bold px-1.5 py-0.5 rounded font-mono">P{item.mc_process_no}</span>
                              : <span className="text-slate-300">-</span>}
                            {item.version && <span className="ml-1 text-slate-400 text-[10px]">v{item.version}</span>}
                          </span>
                          <span className="min-w-0">
                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>
                            <span className="text-slate-600 text-xs ml-2">{item.part_name}</span>
                            {item.client_name && <span className="text-slate-400 text-[10px] ml-2">/ {item.client_name}</span>}
                          </span>
                          <span className="text-[11px] text-slate-500 whitespace-nowrap">{fmtDt(item.printed_at)}</span>
                          <span className="text-xs text-slate-500">{item.operator_name}</span>
                          <span className={"text-xs whitespace-nowrap " + ageCls(item.printed_at)}>{elapsed(item.printed_at)}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300"><path d="M9 18l6-6-6-6"/></svg>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
    </>
  );
}
