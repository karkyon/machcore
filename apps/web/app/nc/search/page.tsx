"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ncApi, NcSearchResult, RecentAccess } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";

const SEARCH_KEYS = [
  { value: "drawing_no", label: "図面番号" },
  { value: "name",       label: "部品名称" },
  { value: "nc_id",      label: "NC_id" },
  { value: "part_id",    label: "部品ID" },
];

const ACTION_LABELS: Record<string, string> = {
  VIEW:         "閲覧",
  EDIT_START:   "編集",
  EDIT_SAVE:    "登録",
  APPROVE:      "承認",
  SETUP_PRINT:  "印刷",
  WORK_RECORD:  "作業記録",
  USB_DOWNLOAD: "USB",
};

export default function SearchPage() {
  const router = useRouter();

  const [loading, setLoading] = useState(false);
  // ワイヤーフレーム仕様: 各フィールド個別管理
  const [ncIdInput,      setNcIdInput]      = useState("");
  const [partIdInput,    setPartIdInput]    = useState("");
  const [drawingNoInput, setDrawingNoInput] = useState("");
  const [nameInput,      setNameInput]      = useState("");
  const [results, setResults] = useState<NcSearchResult[]>([]);
  const [total, setTotal]     = useState<number | null>(null);
  const [recent, setRecent]   = useState<RecentAccess[]>([]);
  const [selected, setSelected]   = useState<number | null>(null);
  const [isAdmin,  setIsAdmin]    = useState(false);
  const [clientInput,  setClientInput]  = useState("");
  const [machineInput, setMachineInput] = useState("");
  const [clientNames,  setClientNames]  = useState<string[]>([]);
  const [machines,     setMachines]     = useState<{ id: number; machineCode: string }[]>([]);
  const [adminInfo, setAdminInfo] = useState<{ companyName?: string; logoPath?: string } | null>(null);

  // 最近のアクセス取得
  useEffect(() => {
    ncApi.recent().then(r => setRecent(r.data)).catch(() => {});
  }, []);

  // 納入先・機械リスト取得
  useEffect(() => {
    fetch("/api/nc/client-names").then(r => r.json()).then(setClientNames).catch(() => {});
    fetch("/api/machines").then(r => r.json()).then(setMachines).catch(() => {});
  }, []);

  // 管理者ログイン状態チェック
  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    if (!token) return;
    setIsAdmin(true);
    fetch("/api/admin/company", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setAdminInfo(data); })
      .catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    // 優先順位: NC ID > 部品ID > 図面番号 > 名称 > 全件
    let searchKey = "drawing_no";
    let searchQ   = "";
    if (ncIdInput.trim())      { searchKey = "nc_id";      searchQ = ncIdInput.trim(); }
    else if (partIdInput.trim()){ searchKey = "part_id";   searchQ = partIdInput.trim(); }
    else if (drawingNoInput.trim()){ searchKey = "drawing_no"; searchQ = drawingNoInput.trim(); }
    else if (nameInput.trim()) { searchKey = "name";       searchQ = nameInput.trim(); }

    setLoading(true);
    setSelected(null);
    try {
      const params = new URLSearchParams({ key: searchKey, q: searchQ });
      if (clientInput) params.set("client_name", clientInput);
      if (machineInput) params.set("machine_id", machineInput);
      const res = await fetch(`/api/nc/search?${params}`).then(r => r.json());
      setResults(res.data ?? []);
      setTotal(res.total ?? 0);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
    return;
    try {
      const res = await ncApi.search(searchKey, searchQ);
      setResults(res.data.data);
      setTotal(res.data.total);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [ncIdInput, partIdInput, drawingNoInput, nameInput, clientInput, machineInput]);

  const handleSelect = (ncId: number) => {
    setSelected(ncId);
    router.push(`/nc/${ncId}`);
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ── ヘッダー ── */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        {adminInfo?.logoPath && (
          <img src={adminInfo.logoPath.replace(/^apps\/web\/public/, "").replace(/^\/+/, "/")}
            alt="logo" className="h-7 object-contain" />
        )}
        <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">{adminInfo?.companyName ?? "NC 旋盤プログラム管理システム"}</span>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => router.push("/mc/search")} className="text-xs border border-teal-600 hover:border-teal-400 text-teal-400 hover:text-white hover:bg-teal-700 px-2.5 py-1 rounded font-medium transition-all">⇄ MC</button>
          <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>
          {isAdmin ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-700">
              <span className="text-[11px] text-slate-300">{adminInfo?.companyName ?? "管理者"}</span>
              <a href="/admin/users"
                className="text-[11px] bg-slate-700 hover:bg-slate-600 text-sky-400 px-2.5 py-1 rounded transition-colors">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="inline mr-1"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                ユーザ管理
              </a>
              <a href="/admin/machines"
                className="text-[11px] bg-slate-700 hover:bg-slate-600 text-sky-400 px-2.5 py-1 rounded transition-colors">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="inline mr-1"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                機械管理
              </a>
              <a href="/admin/login"
                className="text-[11px] text-slate-400 hover:text-slate-200 transition-colors">
                ログアウト
              </a>
            </div>
          ) : (
            <a href="/admin/login"
              className="flex items-center gap-1 text-[11px] bg-slate-700 hover:bg-slate-600 text-slate-300 px-2.5 py-1 rounded transition-colors border border-slate-600">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
              管理者
            </a>
          )}
        </div>
      </header>

      {/* ── メインコンテンツ（3カラム） ── */}
      <div className="flex flex-1 min-h-0 gap-0">

        {/* ── 左カラム: 検索フォーム（固定260px） ── */}
        <aside className="w-[260px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-700">NC 部品検索</h2>
              <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-bold">認証不要</span>
            </div>

            {/* ── ID 直接指定 ── */}
            <div className="space-y-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">ID 直接指定</div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">NC ID <span className="text-slate-400 text-[10px]">（K_id）</span></label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={ncIdInput}
                    onChange={e => setNcIdInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleSearch()}
                    placeholder="例: 92"
                    className="flex-1 border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  />
                  <button
                    onClick={handleSearch}
                    disabled={loading}
                    className="bg-sky-500 hover:bg-sky-600 disabled:bg-sky-300 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-colors"
                  >
                    検索
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">部品 ID</label>
                <input
                  type="number"
                  value={partIdInput}
                  onChange={e => setPartIdInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="例: 3807"
                  className="w-full border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
                <div className="text-[10px] text-slate-400 mt-0.5">※複数工程は別行で表示</div>
              </div>
            </div>

            {/* ── テキスト条件 ── */}
            <div className="border-t border-slate-100 pt-3 space-y-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">テキスト条件</div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">図面番号</label>
                <input
                  type="text"
                  value={drawingNoInput}
                  onChange={e => setDrawingNoInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="F67487"
                  className="w-full border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">名称</label>
                <input
                  type="text"
                  value={nameInput}
                  onChange={e => setNameInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="部品名称の一部"
                  className="w-full border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">納入先</label>
                <select
                  value={clientInput}
                  onChange={e => setClientInput(e.target.value)}
                  className="w-full border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white"
                >
                  <option value="">— すべて —</option>
                  {clientNames.map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">主機種型式</label>
                <select
                  value={machineInput}
                  onChange={e => setMachineInput(e.target.value)}
                  className="w-full border border-amber-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white"
                >
                  <option value="">— すべて —</option>
                  {machines.map(m => (
                    <option key={m.id} value={String(m.id)}>{m.machineCode}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* ── 検索・クリアボタン ── */}
            <div className="pt-1 space-y-2">
              <button
                onClick={handleSearch}
                disabled={loading}
                className="w-full bg-sky-500 hover:bg-sky-600 disabled:bg-sky-300 text-white font-bold py-2 rounded-lg text-sm transition-colors"
              >
                {loading ? "検索中..." : "🔍 検索"}
              </button>
              {(results.length > 0 || ncIdInput || partIdInput || drawingNoInput || nameInput) && (
                <button
                  onClick={() => {
                    setNcIdInput(""); setPartIdInput("");
                    setDrawingNoInput(""); setNameInput("");
                    setClientInput(""); setMachineInput("");
                    setResults([]); setTotal(null); setSelected(null);
                  }}
                  className="w-full border border-slate-200 text-slate-500 hover:bg-slate-50 py-1.5 rounded-lg text-xs transition-colors"
                >
                  クリア
                </button>
              )}
              <button
                onClick={() => { setDrawingNoInput("旧"); handleSearch(); }}
                className="w-full border border-slate-200 text-slate-400 hover:bg-slate-50 py-1.5 rounded-lg text-xs transition-colors"
              >
                旧ファイルで探す（旧索引）
              </button>
            </div>

            {/* 件数表示 */}
            {total !== null && (
              <div className="mt-4 text-xs text-slate-500 bg-slate-50 rounded p-2">
                {total > 0 ? (
                  <span><b className="text-slate-700">{total}</b> 件 ヒット</span>
                ) : (
                  <span className="text-red-500">0 件（条件を変更してください）</span>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* ── 中央カラム: 検索結果リスト（最大400px） ── */}
        <main className="w-[400px] shrink-0 border-r border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 bg-white shrink-0 flex items-center justify-between">
            <div>
              <span className="text-sm font-bold text-slate-700">検索結果</span>
              {total !== null && total > 0 && (
                <span className="ml-2 text-xs text-slate-400">{total}件</span>
              )}
            </div>
            {results.length > 0 && (
              <span className="text-[11px] text-sky-500 cursor-default">工程ごとに1行表示</span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {results.length === 0 && total === null && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                <div className="text-4xl">🔍</div>
                <p className="text-sm">左の検索フォームから検索してください</p>
              </div>
            )}
            {results.length === 0 && total === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                <div className="text-4xl">📭</div>
                <p className="text-sm">該当なし</p>
              </div>
            )}
            {/* 部品グループ表示 */}
            {(() => {
              // part_db_id でグループ化（順序を保持）
              const groups: { key: string; items: typeof results }[] = [];
              const seen = new Map<string, number>();
              results.forEach(r => {
                const gk = String(r.part_db_id);
                if (!seen.has(gk)) { seen.set(gk, groups.length); groups.push({ key: gk, items: [] }); }
                groups[seen.get(gk)!].items.push(r);
              });
              return groups.map(g => {
                const first = g.items[0];
                return (
                  <div key={g.key} className="border-b border-slate-200">
                    {/* 部品グループヘッダー */}
                    <div className="px-4 pt-3 pb-1.5">
                      <div className="flex items-center gap-0 flex-wrap">
                        <span className="font-bold text-slate-800 text-sm">{first.part_name}</span>
                        <span className="text-slate-300 mx-2 text-xs">—</span>
                        <span className="font-mono text-sky-600 font-bold text-xs">{first.drawing_no}</span>
                        {first.client_name && (
                          <><span className="text-slate-300 mx-2 text-xs">—</span>
                          <span className="text-slate-400 text-xs">{first.client_name}</span></>
                        )}
                      </div>
                    </div>
                    {/* 工程行 */}
                    {g.items.map(r => (
                      <div
                        key={r.nc_id}
                        onClick={() => handleSelect(r.nc_id)}
                        className={`px-4 py-2.5 border-t border-slate-100 cursor-pointer transition-colors flex items-center gap-3 ${
                          selected === r.nc_id
                            ? "bg-sky-50 border-l-[3px] border-l-sky-400 pl-[13px]"
                            : "hover:bg-slate-50"
                        }`}
                      >
                        <ProcessBadge level={r.process_l} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-slate-700 font-medium">
                              工程 L{r.process_l} — {r.machine_code ?? "機械未設定"}
                            </span>
                            <StatusBadge status={r.status} />
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono mt-0.5">
                            <span>NC: {r.nc_id}</span>
                            <span>/</span>
                            <span>{r.file_name || "—"}</span>
                            {r.machining_time != null && <><span>/</span><span>{r.machining_time}分</span></>}
                          </div>
                        </div>
                        <span className="font-mono text-[10px] text-slate-400 shrink-0">Ver.{r.version}</span>
                      </div>
                    ))}
                  </div>
                );
              });
            })()}
          </div>
        </main>

        {/* ── 右カラム: 最近のアクセス ── */}
        <section className="flex-1 flex flex-col overflow-hidden bg-white">
          <div className="px-4 py-3 border-b border-slate-100 shrink-0">
            <h2 className="text-sm font-bold text-slate-700">最近のアクセス</h2>
            <p className="text-[11px] text-slate-400">直近5件の操作履歴</p>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {recent.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-300 gap-2">
                <div className="text-4xl">📋</div>
                <p className="text-sm">操作履歴なし</p>
              </div>
            ) : (
              recent.map((r, i) => (
                <div
                  key={i}
                  onClick={() => r.nc_id && handleSelect(r.nc_id)}
                  className="bg-slate-50 hover:bg-sky-50 border border-slate-100 rounded-xl p-3 cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-sky-600 font-bold text-base">{r.drawing_no}</span>
                    <ProcessBadge level={r.process_l} />
                    <span className="ml-auto text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded font-mono">
                      {ACTION_LABELS[r.action_type] ?? r.action_type}
                    </span>
                  </div>
                  <div className="text-sm text-slate-600 mb-1">{r.part_name}</div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400">
                    <span>{r.machine_code ?? "—"}</span>
                    {r.operator_name && <span>👤 {r.operator_name}</span>}
                    <span className="ml-auto">
                      {new Date(r.accessed_at).toLocaleString("ja-JP", {
                        month: "numeric", day: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
          {/* ── 管理者エリア（ADMIN限定） ── */}
          <div className="border-t border-slate-100 px-4 py-3 shrink-0">
            {isAdmin ? (
              <div className="space-y-2">
                {adminInfo?.logoPath && (
                  <img
                    src={(adminInfo.logoPath ?? "").replace(/^apps\/web\/public/, "").replace(/^\/+/, "/")}
                    alt="company logo"
                    className="h-8 object-contain"
                  />
                )}
                <p className="text-[11px] font-bold text-slate-500 truncate">
                  {adminInfo?.companyName ?? "管理者メニュー"}
                </p>
                <div className="flex flex-col gap-1">
                  <a
                    href="/admin/users"
                    className="text-[11px] text-sky-600 hover:text-sky-700 flex items-center gap-1"
                  >
                    👥 ユーザ管理
                  </a>
                  <a
                    href="/admin/login"
                    className="text-[11px] text-slate-400 hover:text-slate-600 flex items-center gap-1"
                  >
                    ↩ 管理者ログアウト
                  </a>
                </div>
              </div>
            ) : (
              <a
                href="/admin/login"
                className="text-[10px] text-slate-300 hover:text-slate-500 transition-colors"
              >
                ⚙ 管理者
              </a>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
