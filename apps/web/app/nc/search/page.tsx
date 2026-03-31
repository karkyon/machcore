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

  const [key, setKey]         = useState("drawing_no");
  const [q, setQ]             = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<NcSearchResult[]>([]);
  const [total, setTotal]     = useState<number | null>(null);
  const [recent, setRecent]   = useState<RecentAccess[]>([]);
  const [selected, setSelected] = useState<number | null>(null);

  // 最近のアクセス取得
  useEffect(() => {
    ncApi.recent().then(r => setRecent(r.data)).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setSelected(null);
    try {
      const res = await ncApi.search(key, q);
      setResults(res.data.data);
      setTotal(res.data.total);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [key, q]);

  const handleSelect = (ncId: number) => {
    setSelected(ncId);
    router.push(`/nc/${ncId}`);
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ── ヘッダー ── */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">NC 旋盤プログラム管理システム</span>
        <span className="ml-auto text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">認証不要</span>
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

            {/* 検索キー選択 */}
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block mb-1">
                  検索キー
                </label>
                <select
                  value={key}
                  onChange={e => setKey(e.target.value)}
                  className="w-full border border-amber-300 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-sky-400"
                >
                  {SEARCH_KEYS.map(k => (
                    <option key={k.value} value={k.value}>{k.label}</option>
                  ))}
                </select>
              </div>

              {/* 検索テキスト */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide block mb-1">
                  検索文字列
                </label>
                <input
                  type="text"
                  value={q}
                  onChange={e => setQ(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="空欄 = 全件表示"
                  className="w-full border border-amber-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
              </div>

              {/* 検索ボタン */}
              <button
                onClick={handleSearch}
                disabled={loading}
                className="w-full bg-sky-500 hover:bg-sky-600 disabled:bg-sky-300 text-white font-bold py-2 rounded-lg text-sm transition-colors"
              >
                {loading ? "検索中..." : "🔍 検索"}
              </button>

              {/* クリア */}
              {(results.length > 0 || q) && (
                <button
                  onClick={() => { setQ(""); setResults([]); setTotal(null); setSelected(null); }}
                  className="w-full border border-slate-200 text-slate-500 hover:bg-slate-50 py-2 rounded-lg text-sm transition-colors"
                >
                  クリア
                </button>
              )}
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
          <div className="px-4 py-3 border-b border-slate-100 bg-white shrink-0">
            <h2 className="text-sm font-bold text-slate-700">検索結果</h2>
            <p className="text-[11px] text-slate-400">工程別行表示。行クリックでNC詳細へ</p>
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
            {results.map(r => (
              <div
                key={r.nc_id}
                onClick={() => handleSelect(r.nc_id)}
                className={`px-4 py-3 border-b border-slate-100 cursor-pointer transition-colors ${
                  selected === r.nc_id
                    ? "bg-sky-50 border-l-4 border-l-sky-400 pl-3"
                    : "hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <ProcessBadge level={r.process_l} />
                  <span className="font-mono text-sky-600 font-bold text-sm">{r.drawing_no}</span>
                  <StatusBadge status={r.status} />
                  <span className="ml-auto font-mono text-[10px] text-slate-400">Ver.{r.version}</span>
                </div>
                <div className="text-sm text-slate-700 mb-1">{r.part_name}</div>
                <div className="flex items-center gap-3 text-[11px] text-slate-400">
                  <span>{r.machine_code ?? "機械未設定"}</span>
                  {r.machining_time && <span>⏱ {r.machining_time}分</span>}
                  <span className="font-mono">NC#{r.nc_id}</span>
                  {r.client_name && <span className="ml-auto text-[10px]">{r.client_name}</span>}
                </div>
              </div>
            ))}
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
        </section>
      </div>
    </div>
  );
}
