"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, McSearchResult } from "@/lib/api";
import AuthModal from "@/components/auth/AuthModal";
import { useAuth } from "@/contexts/AuthContext";

type PartResult = {
  id: number;
  part_id: string;
  drawing_no: string;
  name: string;
  client_name: string | null;
};

export default function McNewCommonPage() {
  const router = useRouter();
  const { token, operator, isAuthenticated } = useAuth();

  // ── 左ペイン: 加工検索 ──
  const [searchKey,     setSearchKey]     = useState<"drawing_no"|"part_name"|"mcid"|"machining_id"|"part_id">("drawing_no");
  const [searchQ,       setSearchQ]       = useState("");
  const [searchResults, setSearchResults] = useState<McSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedRow,   setSelectedRow]   = useState<McSearchResult | null>(null);

  // ── 右ペイン: 登録先部品選択 ──
  const [partSearchType,  setPartSearchType]  = useState<"drawing_no"|"part_id"|"part_name">("drawing_no");
  const [partSearchQ,     setPartSearchQ]     = useState("");
  const [partResults,     setPartResults]     = useState<PartResult[]>([]);
  const [partLoading,     setPartLoading]     = useState(false);
  const [selectedPart,    setSelectedPart]    = useState<PartResult | null>(null);

  // ── 登録 ──
  const [authOpen,  setAuthOpen]  = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // 加工検索
  const doSearchMachining = useCallback(async () => {
    if (!searchQ.trim()) return;
    setSearchLoading(true);
    setSelectedRow(null);
    try {
      const res = await mcApi.search(searchKey, searchQ.trim());
      const d = (res as any).data ?? res;
      setSearchResults(d.rows ?? []);
    } catch { setSearchResults([]); }
    finally { setSearchLoading(false); }
  }, [searchKey, searchQ]);

  // 部品検索
  const doSearchPart = useCallback(async () => {
    if (!partSearchQ.trim()) return;
    setPartLoading(true);
    try {
      const res = await mcApi.search(partSearchType, partSearchQ.trim());
      const d = (res as any).data ?? res;
      const rows: any[] = d.rows ?? [];
      const map = new Map<string, PartResult>();
      for (const r of rows) {
        if (!map.has(r.drawing_no)) {
          map.set(r.drawing_no, {
            id:          r.part_db_id ?? 0,
            part_id:     r.part_id ?? "",
            drawing_no:  r.drawing_no,
            name:        r.part_name,
            client_name: r.client_name ?? null,
          });
        }
      }
      setPartResults(Array.from(map.values()));
    } catch { setPartResults([]); }
    finally { setPartLoading(false); }
  }, [partSearchQ, partSearchType]);

  // 供用登録実行
  const handleRegister = async () => {
    if (!isAuthenticated || !token) { setAuthOpen(true); return; }
    if (!selectedRow)  { setSaveError("供用する加工を選択してください"); return; }
    if (!selectedPart) { setSaveError("登録先の部品を選択してください"); return; }
    if (!confirm("両方の図面を見比べて、加工内容に相違ないか確認しましたか？\n\n今、手元に２枚の図面がありますか？")) return;
    setSaving(true); setSaveError(null);
    try {
      const res = await mcApi.registerCommonPart({
        source_machining_id: selectedRow.machining_id,
        target_part_id:      selectedPart.id,
      }, token);
      const d = (res as any).data ?? res;
      router.push(`/mc/${d.mcProgramId}`);
    } catch (e: any) {
      setSaveError(e?.response?.data?.message ?? e?.message ?? "登録失敗");
      setSaving(false);
    }
  };

  const canSubmit = !!selectedRow && !!selectedPart && isAuthenticated && !saving;

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc")}
          className="bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold px-3 py-1.5 rounded transition-colors">
          ← ダッシュボードへ戻る
        </button>
        <button onClick={() => router.push("/mc/search")}
          className="bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold px-3 py-1.5 rounded transition-colors">
          ＋ MC検索に戻る
        </button>
        <span className="font-mono text-violet-400 font-bold text-base ml-2">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">MC 共通加工登録</span>
        {operator && (
          <span className="ml-auto text-xs text-emerald-400">✓ 認証済: {operator.name}</span>
        )}
      </header>

      <div className="flex flex-1 min-h-0">
        {/* ── 左ペイン: 登録先の部品を検索 ── */}
        <aside className="w-[260px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-100">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              ① 登録先の部品を検索
            </p>
            <select value={partSearchType} onChange={e => setPartSearchType(e.target.value as any)}
              className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs font-bold mb-2 focus:outline-none focus:ring-2 focus:ring-teal-400">
              <option value="drawing_no">図面番号</option>
              <option value="part_id">部品ID</option>
              <option value="part_name">名称</option>
            </select>
            <div className="flex gap-1.5">
              <input value={partSearchQ} onChange={e => setPartSearchQ(e.target.value)}
                onKeyDown={e => e.key === "Enter" && doSearchPart()}
                placeholder="Enterで検索"
                className="flex-1 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400" />
              <button onClick={doSearchPart} disabled={partLoading}
                className="px-3 py-1.5 bg-teal-600 text-white text-xs font-bold rounded-lg hover:bg-teal-700 disabled:opacity-50">
                {partLoading ? "…" : "検索"}
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {partResults.length === 0 && !partLoading && (
              <div className="p-4 text-xs text-slate-400 text-center mt-4">
                登録先の部品を検索してください
              </div>
            )}
            {partResults.map(p => (
              <button key={p.id}
                onClick={() => setSelectedPart(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-slate-100 hover:bg-teal-50 transition-colors
                  ${selectedPart?.id === p.id ? "bg-teal-50 border-l-4 border-l-teal-500" : ""}`}>
                <div className="font-mono text-xs font-bold text-teal-700">{p.drawing_no}</div>
                <div className="text-xs text-slate-600 truncate">{p.name}</div>
                {p.client_name && <div className="text-[10px] text-slate-400">{p.client_name}</div>}
              </button>
            ))}
          </div>
        </aside>

        {/* ── メイン: 登録先部品の確認 + 供用する加工の検索 ── */}
        <main className="flex-1 overflow-y-auto p-5">
          {/* 選択した登録先部品 */}
          {!selectedPart ? (
            <div className="bg-slate-100 border-2 border-dashed border-slate-300 rounded-xl p-6 mb-5 text-sm text-slate-400 text-center">
              ← 左ペインで登録先の部品を検索・選択してください
            </div>
          ) : (
            <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 mb-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-bold text-teal-600 uppercase tracking-wider">登録先の部品</p>
                <button onClick={() => setSelectedPart(null)} className="text-xs text-slate-400 hover:text-red-500">✕</button>
              </div>
              <div className="font-mono text-teal-700 font-bold text-sm">{selectedPart.drawing_no}</div>
              <div className="text-xs text-slate-600">{selectedPart.name}</div>
              {selectedPart.client_name && <div className="text-[10px] text-slate-400">{selectedPart.client_name}</div>}
            </div>
          )}

          {/* 供用する加工を検索 */}
          <div className="border-t border-slate-200 pt-5">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">
              ② 供用する加工データを検索
            </h2>
            <div className="flex gap-2 mb-3">
              <select value={searchKey} onChange={e => setSearchKey(e.target.value as any)}
                className="border border-slate-300 rounded-lg px-2 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-violet-400">
                <option value="drawing_no">図面番号</option>
                <option value="part_name">名称</option>
                <option value="mcid">MCID</option>
                <option value="machining_id">加工ID</option>
                <option value="part_id">部品ID</option>
              </select>
              <input value={searchQ} onChange={e => setSearchQ(e.target.value)}
                onKeyDown={e => e.key === "Enter" && doSearchMachining()}
                placeholder="Enterで検索"
                className="flex-1 max-w-xs border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400" />
              <button onClick={doSearchMachining} disabled={searchLoading}
                className="px-4 py-1.5 bg-violet-600 text-white text-xs font-bold rounded-lg hover:bg-violet-700 disabled:opacity-50">
                {searchLoading ? "…" : "検索"}
              </button>
            </div>
            {searchResults.length > 0 && (
              <div className="border border-slate-200 rounded-xl overflow-hidden mb-4 max-h-64 overflow-y-auto">
                {searchResults.map(row => (
                  <button key={row.mc_id} onClick={() => setSelectedRow(row)}
                    className={`w-full text-left px-4 py-2.5 border-b border-slate-100 hover:bg-violet-50 transition-colors
                      ${selectedRow?.mc_id === row.mc_id ? "bg-violet-50 border-l-4 border-l-violet-500" : ""}`}>
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="font-mono text-[10px] text-violet-600 font-bold">加工ID:{row.machining_id}</span>
                      <span className="font-mono text-[10px] text-blue-500">MCID:{row.legacy_mcid ?? "—"}</span>
                    </div>
                    <div className="font-mono text-xs font-bold text-slate-700">{row.drawing_no}</div>
                    <div className="text-xs text-slate-500 truncate">{row.part_name}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {row.machine_code && <span className="text-[10px] text-slate-400">{row.machine_code}</span>}
                      <span className="text-[10px] font-mono text-slate-400">Ver.{row.version}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
            {selectedRow && (
              <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 mb-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-bold text-violet-600 uppercase tracking-wider">供用する加工データ</p>
                  <button onClick={() => setSelectedRow(null)} className="text-xs text-slate-400 hover:text-red-500">✕</button>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
                  <div>
                    <span className="text-[10px] text-slate-400 block">加工ID</span>
                    <span className="font-mono font-bold text-violet-700 text-lg">{selectedRow.machining_id}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">MCID</span>
                    <span className="font-mono font-bold text-blue-600">{selectedRow.legacy_mcid ?? "—"}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">図面番号</span>
                    <span className="font-mono font-bold text-slate-800">{selectedRow.drawing_no}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">名称</span>
                    <span className="text-slate-700">{selectedRow.part_name}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">機械</span>
                    <span className="text-slate-600">{selectedRow.machine_code ?? "—"}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">バージョン</span>
                    <span className="font-mono text-slate-600">{selectedRow.version}</span>
                  </div>
                  {selectedRow.common_part_code && (
                    <div className="col-span-2">
                      <span className="text-[10px] text-slate-400 block">共通部品コード</span>
                      <span className="font-mono text-emerald-600 font-bold">{selectedRow.common_part_code}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* エラー */}
          {saveError && (
            <div className="mb-3 text-red-600 text-sm font-bold">{saveError}</div>
          )}

          {/* 登録ボタン */}
          <div className="flex gap-3 max-w-xl mt-2">
            {!isAuthenticated ? (
              <button onClick={() => setAuthOpen(true)}
                className="flex-1 py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-bold text-sm transition-colors">
                🔒 先に認証してください
              </button>
            ) : (
              <button onClick={handleRegister} disabled={!canSubmit}
                className="flex-1 py-3 rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white font-bold text-sm transition-colors">
                {saving ? "登録中…" : "📋 共通登録（供用）する"}
              </button>
            )}
            <button onClick={() => router.push("/mc")}
              className="px-5 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
              キャンセル
            </button>
          </div>

          <div className="mt-5 max-w-xl bg-slate-100 rounded-xl p-3 text-xs text-slate-500 space-y-0.5">
            <p className="font-bold text-slate-600 mb-1">共通加工登録について</p>
            <p>① 左ペインで「登録先の部品」を検索・選択</p>
            <p>② 右ペインで「供用したい加工データ」を検索・選択</p>
            <p>③ 認証後「図面確認」を経て供用登録を実行</p>
            <p>④ 同一の加工ID（ツーリング・WO・IP含む）を別部品でも使用可能になります</p>
          </div>
        </main>
      </div>

      {authOpen && (
        <AuthModal
          isOpen={true}
          sessionType="edit"
          system="MC"
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)}
        />
      )}
    </div>
  );
}
