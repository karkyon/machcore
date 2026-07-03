"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, Machine } from "@/lib/api";
import { calcProgramFileNaming } from "@/lib/programFileNaming";
import AuthModal from "@/components/auth/AuthModal";
import { useAuth } from "@/contexts/AuthContext";

type PartResult = {
  id: number;
  part_id: string;
  drawing_no: string;
  name: string;
  client_name: string | null;
};

export default function McNewPage() {
  const router = useRouter();
  const { token: authToken, operator: authOperator, isAuthenticated } = useAuth();

  const [searchQ,      setSearchQ]      = useState("");
  const [searchType,   setSearchType]   = useState<"drawing_no"|"part_id"|"part_name">("drawing_no");
  const [parts,        setParts]        = useState<PartResult[]>([]);
  const [partLoading,  setPartLoading]  = useState(false);
  const [selectedPart, setSelectedPart] = useState<PartResult | null>(null);

  const [machiningId,   setMachiningId]   = useState<number | null>(null);
  const [nextIdLoading, setNextIdLoading] = useState(false);
  const [mcProcessNo,   setMcProcessNo]   = useState("");
  const [machineId,     setMachineId]     = useState("");
  const [oNumber,       setONumber]       = useState("");
  const [machiningQty,  setMachiningQty]  = useState("1");
  const [note,          setNote]          = useState("");
  const [machines,      setMachines]      = useState<Machine[]>([]);

  const [authOpen,  setAuthOpen]  = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    machinesApi.list("MC").then(r => {
      const d = (r as any).data ?? r;
      setMachines(Array.isArray(d) ? d.filter((m: Machine) => m.isActive) : []);
    }).catch(() => {});
  }, []);

  // 次の加工ID候補を自動取得
  useEffect(() => {
    setNextIdLoading(true);
    fetch("/api/mc/next-machining-id")
      .then(r => r.json())
      .then(d => { setMachiningId(d.next_machining_id ?? null); })
      .catch(() => {})
      .finally(() => setNextIdLoading(false));
  }, []);

  // [v098] 部品マスタ(Part)を直接検索する。MC情報が未登録の部品(=新規登録
  // すべき部品)も検索対象になる(mc_programsとのJOINは行わない)。
  const handlePartSearch = useCallback(async () => {
    if (!searchQ.trim()) return;
    setPartLoading(true);
    try {
      const res = await mcApi.searchParts(searchType, searchQ.trim());
      const d = (res as any).data ?? res;
      const rows: any[] = d.rows ?? [];
      setParts(rows.map(r => ({
        id:          r.id,
        part_id:     r.part_id ?? "",
        drawing_no:  r.drawing_no,
        name:        r.name,
        client_name: r.client_name ?? null,
      })));
    } catch { setParts([]); }
    finally { setPartLoading(false); }
  }, [searchQ, searchType]);

  const handleAuthSuccess = () => { setAuthOpen(false); };

  const handleSubmit = async () => {
    // ユーザー認証チェック（AuthContextのisAuthenticated + authToken両方確認）
    if (!authToken || !isAuthenticated) { setAuthOpen(true); return; }
    if (!selectedPart)       { setSaveError("部品を選択してください"); return; }
    if (!machiningId)        { setSaveError("加工IDを取得できませんでした"); return; }
    if (!mcProcessNo.trim()) { setSaveError("工程Noを入力してください（必須）"); return; }
    if (!machineId)          { setSaveError("機械を選択してください（必須）"); return; }

    // MCレコードはここでは作成しない（加工IDは仮押さえのみ）
    // 直接印刷ボタン押下時に1トランザクションで確定する
    const pendingData = {
      part_id:       selectedPart.id,
      drawing_no:    selectedPart.drawing_no,
      part_name:     selectedPart.name,
      machining_id:  machiningId,
      machine_id:    machineId ? parseInt(machineId) : null,
      mc_process_no: mcProcessNo ? parseInt(mcProcessNo) : null,
      o_number:      oNumber || null,
      machining_qty: machiningQty ? parseInt(machiningQty) : 1,
      note:          note || null,
    };
    if (typeof window !== "undefined") {
      sessionStorage.setItem("mc_new_pending", JSON.stringify(pendingData));
    }
    router.push(`/mc/new/print?from=new`);
  };

  // authOperatorがセットされている = AuthModalで実際に認証済み（localStorage残存トークンは除外）
  // authOperatorはページリロードでnullになるのでlocalStorage残存tokenの誤認証を防ぐ
  const actuallyAuthenticated = !!(authToken && authOperator);
  const canSubmit = !!mcProcessNo.trim() && !!machineId && !!(actuallyAuthenticated && selectedPart && machiningId);

  // 選択した機械のマスタ設定(pgIsFolder)から、プログラムファイルが単体ファイルか
  // フォルダ単位(メインPG+サブPG)かを判定し、ファイル名/フォルダ名を自動算出する。
  // 命名ロジックは programFileNaming.ts に一本化(重複実装しない)。
  const selectedMachine = machineId ? machines.find(m => String(m.id) === machineId) ?? null : null;
  const programNaming = selectedMachine ? calcProgramFileNaming(machiningId, !!selectedMachine.pgIsFolder) : null;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium transition-colors shrink-0">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          ダッシュボードへ戻る
        </button>
        <button onClick={() => router.push("/mc/search")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 border border-slate-500 rounded-lg text-xs font-medium transition-colors shrink-0">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          MC検索に戻る
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">MC 新規登録（仮登録）</span>
        <span className="ml-auto">
          {isAuthenticated && authOperator
            ? <span className="text-[11px] bg-teal-700 text-white px-2.5 py-1 rounded font-bold">✓ 認証済: {authOperator.name}</span>
            : <button onClick={() => setAuthOpen(true)} className="text-[11px] bg-amber-600 hover:bg-amber-500 text-white px-2.5 py-1 rounded font-bold transition-colors">🔒 要認証 — クリックして認証</button>
          }
        </span>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-[280px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
          <div className="p-3 border-b border-slate-100 space-y-2">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wide">① 部品を選択</h2>
            <div className="flex gap-1.5">
              <select value={searchType} onChange={e => setSearchType(e.target.value as any)}
                className="border border-slate-300 rounded px-1.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400 shrink-0">
                <option value="drawing_no">図面番号</option>
                <option value="part_id">部品ID</option>
                <option value="part_name">名称</option>
              </select>
              <input value={searchQ} onChange={e => setSearchQ(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handlePartSearch()}
                placeholder="検索ワード"
                className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-400" />
            </div>
            <button onClick={handlePartSearch} disabled={partLoading || !searchQ.trim()}
              className="w-full py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white font-bold text-xs transition-colors">
              {partLoading ? "検索中…" : "検索"}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {parts.length === 0 && !partLoading && (
              <p className="text-xs text-slate-400 text-center mt-10">検索結果がありません</p>
            )}
            {parts.map(p => (
              <button key={p.id} onClick={() => setSelectedPart(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-slate-100 hover:bg-teal-50 transition-colors ${selectedPart?.drawing_no === p.drawing_no ? "bg-teal-50 border-l-4 border-l-teal-500" : ""}`}>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-teal-700">{p.drawing_no}</span>
                  {p.part_id && <span className="font-mono text-[10px] text-slate-400">部品ID:{p.part_id}</span>}
                </div>
                <div className="text-xs text-slate-600 truncate">{p.name}</div>
                {p.client_name && <div className="text-[10px] text-slate-400">{p.client_name}</div>}
              </button>
            ))}
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto p-5">
          {selectedPart ? (
            <div className="bg-teal-50 border border-teal-200 rounded-xl p-3 mb-5 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-teal-700 font-bold text-lg">{selectedPart.drawing_no}</span>
                  {selectedPart.part_id && <span className="font-mono text-slate-500 font-bold text-lg">部品ID: {selectedPart.part_id}</span>}
                </div>
                <div className="text-sm text-slate-600">{selectedPart.name}</div>
                {selectedPart.client_name && <div className="text-xs text-slate-400">{selectedPart.client_name}</div>}
              </div>
              <button onClick={() => setSelectedPart(null)} className="text-xs text-slate-400 hover:text-red-500 shrink-0">✕</button>
            </div>
          ) : (
            <div className="bg-slate-100 border-2 border-dashed border-slate-300 rounded-xl p-4 mb-5 text-sm text-slate-400 text-center">
              ← 左ペインで部品を検索・選択してください
            </div>
          )}

          <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">② 加工情報を入力</h2>
          <div className="grid grid-cols-2 gap-3 max-w-xl">
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">加工ID</label>
              <div className="flex items-center gap-2 h-9">
                {nextIdLoading ? (
                  <span className="text-sm text-slate-400">取得中...</span>
                ) : (
                  <span className="font-mono text-lg font-bold text-teal-700">{machiningId ?? "—"}</span>
                )}
                <span className="text-xs text-slate-400">（自動採番）</span>
              </div>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">
                {programNaming ? programNaming.label : "ファイル名／フォルダ名"}
                <span className="text-slate-400 font-normal">（機械選択後に自動設定）</span>
              </label>
              <div className="flex items-center gap-2 h-9">
                <span className="font-mono text-base font-bold text-slate-600 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 select-none">
                  {programNaming ? programNaming.value : "—"}
                </span>
              </div>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">工程No <span className="text-red-500">*</span></label>
              <input type="text" value={mcProcessNo} onChange={e => setMcProcessNo(e.target.value)}
                placeholder="例: 1（負値・小数も可）"
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${!mcProcessNo.trim() ? "border-red-300 bg-red-50" : "border-slate-300"}`} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">機械 <span className="text-red-500">*</span></label>
              <select value={machineId} onChange={e => setMachineId(e.target.value)}
                className={`w-full border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-400 ${!machineId ? "border-red-300 bg-red-50" : "border-slate-300"}`}>
                <option value="">-- 未設定 --</option>
                {machines.map(m => (
                  <option key={m.id} value={String(m.id)}>{m.machineName ?? m.machineCode}</option>
                ))}
              </select>
              {programNaming && (
                <div className={`mt-1.5 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border ${programNaming.isFolder ? "bg-amber-50 border-amber-200 text-amber-700" : "bg-teal-50 border-teal-200 text-teal-700"}`}>
                  <span>{programNaming.isFolder ? "📁 フォルダ単位" : "📄 単体ファイル"}</span>
                  <span className="text-slate-400">|</span>
                  <span className="font-mono font-bold">{programNaming.value}</span>
                </div>
              )}
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">メインOナンバ</label>
              <input type="text" value={oNumber} onChange={e => setONumber(e.target.value)}
                placeholder="例: O7266"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">加工個数</label>
              <div className="flex items-center gap-2">
                <input type="number" value={machiningQty} onChange={e => setMachiningQty(e.target.value)} min="1"
                  className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                <span className="text-xs text-slate-500">個/サイクル</span>
              </div>
            </div>
          </div>

          <div className="mt-4 max-w-xl">
            <label className="text-xs font-bold text-slate-700 block mb-1">備考</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} maxLength={2000}
              placeholder="特記事項・注意事項"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none" />
          </div>

          {saveError && (
            <div className="mt-3 max-w-xl bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2.5 rounded-xl">
              ⚠️ {saveError}
            </div>
          )}

          <div className="mt-4 max-w-xl flex gap-3">
            {!actuallyAuthenticated ? (
              <button onClick={() => setAuthOpen(true)}
                className="flex-1 py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-bold text-sm transition-colors">
                🔒 先に認証してください
              </button>
            ) : (
              <button onClick={handleSubmit} disabled={saving || !canSubmit}
                className="flex-1 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white font-bold text-sm transition-colors">
                {saving ? "登録中…" : "✓ 仮登録 → 段取シート発行へ"}
              </button>
            )}
            <button onClick={() => router.push("/mc/search")}
              className="px-5 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
              キャンセル
            </button>
          </div>

          <div className="mt-5 max-w-xl bg-slate-100 rounded-xl p-3 text-xs text-slate-500 space-y-0.5">
            <p className="font-bold text-slate-600 mb-1">仮登録後の流れ</p>
            <p>① 仮登録完了 → 段取シートページへ表示</p>
            <p>② 段取シートを印刷して現場へ配布</p>
            <p>③ MC詳細でマシニング情報の登録及びツーリング・ワークオフセット・プログラムファイルなどを登録</p>
            <p>④ 承認者が承認 → ステータスが「承認済」に変わります</p>
          </div>
        </main>
      </div>

      {authOpen && (
        <AuthModal
          isOpen={true}
          ncProgramId={0}
          sessionType="edit"
          system="MC"
          onSuccess={() => handleAuthSuccess()}
          onCancel={() => setAuthOpen(false)}
        />
      )}
    </div>
  );
}
