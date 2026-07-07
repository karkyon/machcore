"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ncApi, machinesApi, Machine, NcPartSearchResult } from "@/lib/api";
import { calcProgramFileNaming } from "@/lib/programFileNaming";
import AuthModal from "@/components/auth/AuthModal";
import { useAuth } from "@/contexts/AuthContext";

// ── NC-04 新規登録(仮登録)画面 ──
// MC側 /mc/new と同じ構成(部品検索→加工情報入力→登録)。
// MC側の「段取シート印刷プレビュー→create-and-print」という2段階の帳票発行
// フローはNC側では未実装のため、本画面は登録のみを1画面で完結させ、
// 登録後は /nc/{id}/edit へ直接遷移する。
export default function NcNewPage() {
  const router = useRouter();
  const { token: authToken, operator: authOperator, isAuthenticated } = useAuth();

  const [searchQ,      setSearchQ]      = useState("");
  const [searchType,   setSearchType]   = useState<"drawing_no"|"part_id"|"part_name">("drawing_no");
  const [parts,        setParts]        = useState<NcPartSearchResult[]>([]);
  const [partLoading,  setPartLoading]  = useState(false);
  const [selectedPart, setSelectedPart] = useState<NcPartSearchResult | null>(null);

  const [machiningId,   setMachiningId]   = useState<number | null>(null);
  const [nextIdLoading, setNextIdLoading] = useState(false);
  const [processL,      setProcessL]      = useState("");
  const [machineId,     setMachineId]     = useState("");
  const [machiningTime, setMachiningTime] = useState("");
  const [clampNote,     setClampNote]     = useState("");
  const [machines,      setMachines]      = useState<Machine[]>([]);

  const [authOpen,  setAuthOpen]  = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    machinesApi.list("NC").then(r => {
      const d = (r as any).data ?? r;
      setMachines(Array.isArray(d) ? d.filter((m: Machine) => m.isActive) : []);
    }).catch(() => {});
  }, []);

  // 次の加工ID(K_id)候補を自動取得
  useEffect(() => {
    setNextIdLoading(true);
    ncApi.nextMachiningId()
      .then(r => { const d = (r as any).data ?? r; setMachiningId(d.next_machining_id ?? null); })
      .catch(() => {})
      .finally(() => setNextIdLoading(false));
  }, []);

  const handlePartSearch = useCallback(async () => {
    if (!searchQ.trim()) return;
    setPartLoading(true);
    try {
      const res = await ncApi.searchParts(searchType, searchQ.trim());
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
    if (!authToken || !isAuthenticated) { setAuthOpen(true); return; }
    if (!selectedPart)        { setSaveError("部品を選択してください"); return; }
    if (!processL.trim())     { setSaveError("工程No(L)を入力してください（必須）"); return; }
    if (!machineId)           { setSaveError("機械を選択してください（必須）"); return; }

    setSaving(true); setSaveError(null);
    try {
      const res = await ncApi.create({
        part_id:        selectedPart.id,
        process_l:      parseInt(processL, 10),
        machine_id:      machineId ? parseInt(machineId) : null,
        machining_time:  machiningTime ? parseInt(machiningTime, 10) : null,
        clamp_note:      clampNote || null,
      }, authToken);
      const d = (res as any).data ?? res;
      router.push(`/nc/${d.nc_id}/edit`);
    } catch (e: any) {
      const errMsg = e?.response?.data?.message ?? e?.message ?? "登録に失敗しました";
      setSaveError(Array.isArray(errMsg) ? errMsg.join(", ") : errMsg);
    } finally {
      setSaving(false);
    }
  };

  const actuallyAuthenticated = !!(authToken && authOperator);
  const canSubmit = !!processL.trim() && !!machineId && !!(actuallyAuthenticated && selectedPart && machiningId);

  // 選択した機械のマスタ設定(pgIsFolder)から、プログラムファイルが単体ファイルか
  // フォルダ単位かをプレビュー表示する(実際の権威値はサーバー側で自動算出される)。
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
        <button onClick={() => router.push("/nc/search")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 border border-slate-500 rounded-lg text-xs font-medium transition-colors shrink-0">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          NC検索に戻る
        </button>
        <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">NC 新規登録（仮登録）</span>
        <span className="ml-auto">
          {isAuthenticated && authOperator
            ? <span className="text-[11px] bg-sky-700 text-white px-2.5 py-1 rounded font-bold">✓ 認証済: {authOperator.name}</span>
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
                className="border border-slate-300 rounded px-1.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400 shrink-0">
                <option value="drawing_no">図面番号</option>
                <option value="part_id">部品ID</option>
                <option value="part_name">名称</option>
              </select>
              <input value={searchQ} onChange={e => setSearchQ(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handlePartSearch()}
                placeholder="検索ワード"
                className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400" />
            </div>
            <button onClick={handlePartSearch} disabled={partLoading || !searchQ.trim()}
              className="w-full py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white font-bold text-xs transition-colors">
              {partLoading ? "検索中…" : "検索"}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {parts.length === 0 && !partLoading && (
              <p className="text-xs text-slate-400 text-center mt-10">検索結果がありません</p>
            )}
            {parts.map(p => (
              <button key={p.id} onClick={() => setSelectedPart(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-slate-100 hover:bg-sky-50 transition-colors ${selectedPart?.id === p.id ? "bg-sky-50 border-l-4 border-l-sky-500" : ""}`}>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-sky-700">{p.drawing_no}</span>
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
            <div className="bg-sky-50 border border-sky-200 rounded-xl p-3 mb-5 flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sky-700 font-bold text-lg">{selectedPart.drawing_no}</span>
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
              <label className="text-xs font-bold text-slate-700 block mb-1">加工ID (K_id)</label>
              <div className="flex items-center gap-2 h-9">
                {nextIdLoading ? (
                  <span className="text-sm text-slate-400">取得中...</span>
                ) : (
                  <span className="font-mono text-lg font-bold text-sky-700">{machiningId ?? "—"}</span>
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
              <label className="text-xs font-bold text-slate-700 block mb-1">工程No (L) <span className="text-red-500">*</span></label>
              <input type="number" value={processL} onChange={e => setProcessL(e.target.value)}
                placeholder="例: 1"
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 ${!processL.trim() ? "border-red-300 bg-red-50" : "border-slate-300"}`} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">機械 <span className="text-red-500">*</span></label>
              <select value={machineId} onChange={e => setMachineId(e.target.value)}
                className={`w-full border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400 ${!machineId ? "border-red-300 bg-red-50" : "border-slate-300"}`}>
                <option value="">-- 未設定 --</option>
                {machines.map(m => (
                  <option key={m.id} value={String(m.id)}>{m.machineName ?? m.machineCode}</option>
                ))}
              </select>
              {programNaming && (
                <div className={`mt-1.5 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border ${programNaming.isFolder ? "bg-amber-50 border-amber-200 text-amber-700" : "bg-sky-50 border-sky-200 text-sky-700"}`}>
                  <span>{programNaming.isFolder ? "📁 フォルダ単位" : "📄 単体ファイル"}</span>
                  <span className="text-slate-400">|</span>
                  <span className="font-mono font-bold">{programNaming.value}</span>
                </div>
              )}
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">加工時間(分)</label>
              <input type="number" value={machiningTime} onChange={e => setMachiningTime(e.target.value)} min="0"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
            </div>
          </div>

          <div className="mt-4 max-w-xl">
            <label className="text-xs font-bold text-slate-700 block mb-1">掴み代・備考</label>
            <textarea value={clampNote} onChange={e => setClampNote(e.target.value)} rows={2} maxLength={2000}
              placeholder="特記事項・注意事項"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 resize-none" />
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
                className="flex-1 py-3 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white font-bold text-sm transition-colors">
                {saving ? "登録中…" : "✓ 仮登録する"}
              </button>
            )}
            <button onClick={() => router.push("/nc/search")}
              className="px-5 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
              キャンセル
            </button>
          </div>

          <div className="mt-5 max-w-xl bg-slate-100 rounded-xl p-3 text-xs text-slate-500 space-y-0.5">
            <p className="font-bold text-slate-600 mb-1">仮登録後の流れ</p>
            <p>① 仮登録完了 → NC詳細/編集画面へ遷移</p>
            <p>② NC編集画面でツーリング・PGファイルなどを登録</p>
            <p>③ 承認者が承認 → ステータスが「承認済」に変わります</p>
          </div>
        </main>
      </div>

      {authOpen && (
        <AuthModal
          isOpen={true}
          ncProgramId={0}
          sessionType="edit"
          system="NC"
          onSuccess={() => handleAuthSuccess()}
          onCancel={() => setAuthOpen(false)}
        />
      )}
    </div>
  );
}
