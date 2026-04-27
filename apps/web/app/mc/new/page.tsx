"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, Machine } from "@/lib/api";
import AuthModal from "@/components/nc/AuthModal";

type PartResult = {
  id: number;
  part_id: string;
  drawing_no: string;
  name: string;
  client_name: string | null;
};

export default function McNewPage() {
  const router = useRouter();

  const [searchQ,      setSearchQ]      = useState("");
  const [searchType,   setSearchType]   = useState<"drawing_no"|"part_id"|"part_name">("drawing_no");
  const [parts,        setParts]        = useState<PartResult[]>([]);
  const [partLoading,  setPartLoading]  = useState(false);
  const [selectedPart, setSelectedPart] = useState<PartResult | null>(null);

  const [machiningId,  setMachiningId]  = useState("");
  const [mcProcessNo,  setMcProcessNo]  = useState("");
  const [machineId,    setMachineId]    = useState("");
  const [oNumber,      setONumber]      = useState("");
  const [machiningQty, setMachiningQty] = useState("1");
  const [note,         setNote]         = useState("");
  const [machines,     setMachines]     = useState<Machine[]>([]);

  const [authOpen,  setAuthOpen]  = useState(false);
  const [token,     setToken]     = useState<string | null>(null);
  const [operator,  setOperator]  = useState<{ id: number; name: string } | null>(null);

  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    machinesApi.list().then(r => {
      const d = (r as any).data ?? r;
      setMachines(Array.isArray(d) ? d.filter((m: Machine) => m.isActive) : []);
    }).catch(() => {});
  }, []);

  const handlePartSearch = useCallback(async () => {
    if (!searchQ.trim()) return;
    setPartLoading(true);
    try {
      const res = await mcApi.search(searchType, searchQ.trim(), {});
      const d = (res as any).data ?? res;
      const rows: any[] = d.rows ?? [];
      const map = new Map<string, PartResult>();
      for (const r of rows) {
        if (!map.has(r.drawing_no)) {
          map.set(r.drawing_no, {
            id:          r.part_db_id ?? 0,
            part_id:     (r as any).part_id ?? "",
            drawing_no:  r.drawing_no,
            name:        r.part_name,
            client_name: r.client_name ?? null,
          });
        }
      }
      setParts(Array.from(map.values()));
    } catch { setParts([]); }
    finally { setPartLoading(false); }
  }, [searchQ, searchType]);

  const handleAuthSuccess = (t: string, op: { id: number; name: string }) => {
    setToken(t); setOperator(op); setAuthOpen(false);
  };

  const handleSubmit = async () => {
    if (!token) { setAuthOpen(true); return; }
    if (!selectedPart) { setSaveError("部品を選択してください"); return; }
    if (!machiningId.trim()) { setSaveError("加工IDを入力してください"); return; }
    const machIdNum = parseInt(machiningId);
    if (isNaN(machIdNum)) { setSaveError("加工IDは数値で入力してください"); return; }

    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, any> = { part_id: selectedPart.id, machining_id: machIdNum };
      if (machineId)    body.machine_id    = parseInt(machineId);
      if (mcProcessNo)  body.mc_process_no = parseInt(mcProcessNo);
      if (oNumber)      body.o_number      = oNumber;
      if (machiningQty) body.machining_qty = parseInt(machiningQty);
      if (note)         body.note          = note;

      const res  = await mcApi.create(body, token);
      const d    = (res as any).data ?? res;
      router.push(`/mc/${d.mc_id}/print`);
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? e?.message ?? "登録に失敗しました";
      setSaveError(Array.isArray(msg) ? msg.join(" / ") : msg);
    } finally { setSaving(false); }
  };

  const canSubmit = !!(token && selectedPart && machiningId.trim());

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc/search")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium transition-colors shrink-0">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          MC検索に戻る
        </button>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">MC 新規登録（仮登録）</span>
        <span className="ml-auto">
          {operator
            ? <span className="text-[11px] bg-teal-700 text-white px-2.5 py-1 rounded font-bold">✓ 認証済: {operator.name}</span>
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
              <button key={p.drawing_no} onClick={() => setSelectedPart(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-slate-100 hover:bg-teal-50 transition-colors ${selectedPart?.drawing_no === p.drawing_no ? "bg-teal-50 border-l-4 border-l-teal-500" : ""}`}>
                <div className="font-mono text-xs font-bold text-teal-700">{p.drawing_no}</div>
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
                <div className="font-mono text-teal-700 font-bold">{selectedPart.drawing_no}</div>
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
              <label className="text-xs font-bold text-slate-700 block mb-1">加工ID <span className="text-red-500">*</span></label>
              <input type="number" value={machiningId} onChange={e => setMachiningId(e.target.value)}
                placeholder="例: 7266"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
              <p className="text-[10px] text-slate-400 mt-0.5">同一部品の追加工程は異なる値を使用</p>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">MC工程No.</label>
              <input type="number" value={mcProcessNo} onChange={e => setMcProcessNo(e.target.value)}
                placeholder="例: 1"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">機械</label>
              <select value={machineId} onChange={e => setMachineId(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400">
                <option value="">-- 未設定 --</option>
                {machines.map(m => (
                  <option key={m.id} value={m.id}>{m.machineCode}　{m.machineName}</option>
                ))}
              </select>
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
                <input type="number" min={1} value={machiningQty} onChange={e => setMachiningQty(e.target.value)}
                  className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                <span className="text-xs text-slate-400">個/サイクル</span>
              </div>
            </div>
          </div>

          <div className="mt-3 max-w-xl">
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
            {!token ? (
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
            <p>① 仮登録完了 → 段取シートページへ自動遷移</p>
            <p>② 段取シートを印刷して現場へ配布</p>
            <p>③ MC詳細でツーリング・ワークオフセット・プログラムファイルを登録</p>
            <p>④ 承認者が承認 → ステータスが「承認済」に変わります</p>
          </div>
        </main>
      </div>

      {authOpen && (
        <AuthModal
          isOpen={true}
          ncProgramId={0}
          sessionType="edit"
          onSuccess={(t, op) => handleAuthSuccess(t, op)}
          onCancel={() => setAuthOpen(false)}
        />
      )}
    </div>
  );
}