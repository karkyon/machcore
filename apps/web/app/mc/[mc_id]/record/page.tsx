"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { mcApi, machinesApi, usersApi, McDetail, McSetupSheetLog, McWorkRecord, Machine, UserInfo, CreateMcWorkRecordBody } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const WORK_TYPES = ["量産", "試作", "変更", "新規登録"];

function fmtDate(s: string | null) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" }); }
  catch { return s; }
}
function fmtMin(min: number | null) {
  if (min == null) return "—";
  return `${Math.floor(min / 60)}H ${String(min % 60).padStart(2, "0")}M`;
}

function McRecordPageInner() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId = parseInt(mc_id);
  const router = useRouter();
  const searchParams = useSearchParams();

  const [detail,       setDetail]       = useState<McDetail | null>(null);
  const [setupSheets,  setSetupSheets]  = useState<McSetupSheetLog[]>([]);
  const [selectedSheet,setSelectedSheet]= useState<McSetupSheetLog | null>(null);
  const [records,      setRecords]      = useState<McWorkRecord[]>([]);
  const [machines,     setMachines]     = useState<Machine[]>([]);
  const [users,        setUsers]        = useState<UserInfo[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed,  setElapsed]  = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [editRecordId, setEditRecordId] = useState<number | null>(null);

  // フォーム
  const [workType,       setWorkType]       = useState("量産");
  const [machineId,      setMachineId]      = useState<string>("");
  const [setupH,         setSetupH]         = useState(0);
  const [setupM,         setSetupM]         = useState(0);
  const [machH,          setMachH]          = useState(0);
  const [machM,          setMachM]          = useState(0);
  const [quantity,       setQuantity]       = useState<string>("");
  const [note,           setNote]           = useState("");
  const [saving,         setSaving]         = useState(false);
  const [saveError,      setSaveError]      = useState<string | null>(null);
  const [toast,          setToast]          = useState<string | null>(null);

  const showToast = useCallback((msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); }, []);
  const fmtElapsed = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  useEffect(() => {
    mcApi.findOne(mcId).then(r => setDetail((r as any).data ?? r)).catch(() => {});
    mcApi.setupSheetLogs(mcId).then(r => setSetupSheets((r as any).data ?? [])).catch(() => {});
    mcApi.workRecords(mcId).then(r => setRecords((r as any).data ?? [])).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
  }, [mcId]);

  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const resetForm = () => {
    setEditRecordId(null);
    setWorkType("量産");
    setMachineId("");
    setSetupH(0); setSetupM(0);
    setMachH(0);  setMachM(0);
    setQuantity(""); setNote("");
    setSaveError(null);
  };

  const loadRecord = (r: McWorkRecord) => {
    setEditRecordId(r.id);
    setWorkType(r.work_type ?? "量産");
    setMachineId("");
    const sh = r.setup_time_min ?? 0;
    setSetupH(Math.floor(sh / 60)); setSetupM(sh % 60);
    const mh = r.machining_time_min ?? 0;
    setMachH(Math.floor(mh / 60)); setMachM(mh % 60);
    setQuantity(r.quantity ? String(r.quantity) : "");
    setNote(r.note ?? "");
  };

  const handleSubmit = async () => {
    if (!token) return;
    setSaving(true); setSaveError(null);
    try {
      const body: CreateMcWorkRecordBody = {
        work_type: workType,
        setup_time_min: setupH * 60 + setupM || undefined,
        machining_time_min: machH * 60 + machM || undefined,
        quantity: quantity ? parseInt(quantity) : undefined,
        note: note || undefined,
        machine_id: machineId ? parseInt(machineId) : undefined,
      };
      await mcApi.createWorkRecord(mcId, body, token);
      const r = await mcApi.workRecords(mcId);
      setRecords((r as any).data ?? []);
      resetForm();
      showToast("✅ 作業記録を登録しました");
    } catch { setSaveError("登録に失敗しました"); }
    finally { setSaving(false); }
  };

  const d = detail;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0">
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs bg-white text-slate-800 hover:bg-slate-100 border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>
        <span className="text-sm font-medium">作業記録</span>
        <span className="ml-auto">
          {isAuthenticated && operator ? (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          ) : (
            <span className="text-[11px] bg-slate-600 text-white px-2 py-0.5 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報エリア */}
      {d && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-teal-600 font-bold text-lg">{d.part.drawingNo}</span>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700 font-mono">加工ID: {d.machiningId}</span>
            <StatusBadge status={d.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
          </div>
          <div className="text-sm text-slate-700 font-medium mb-1">{d.part.name}</div>
          <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
            <span>MCID: {d.legacyMcid ?? d.id}</span>
            <span>加工ID: {d.machiningId}</span>
            {d.part.partId && <span>部品ID: {d.part.partId}</span>}
            {d.part.clientName && <span>納入先: {d.part.clientName}</span>}
          </div>
        </div>
      )}

      {/* タブナビ */}
      <nav className="im-tab-bar bg-white border-b border-[#d0d8e4] px-4 pt-1.5 shrink-0">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="im-tab-btn flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="im-tab-btn flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="im-tab-btn flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="im-tab-btn im-tab-active flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* 2ペインレイアウト */}
      <div className="flex flex-1 min-h-0">
        {/* 左ペイン: 段取シートリスト */}
        <div className="w-[280px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <div>
              <span className="text-sm font-bold text-slate-700">🗒 段取シート一覧</span>
              <span className="ml-2 text-[11px] text-slate-400">未回収: {setupSheets.length}件</span>
            </div>
            <span className="text-[10px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded">印刷日付新しい順</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {setupSheets.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2 py-12">
                <span className="text-3xl">📋</span>
                <p className="text-sm">印刷済み段取シートなし</p>
              </div>
            ) : setupSheets.map(s => (
              <div key={s.id}
                onClick={() => { setSelectedSheet(s); if (!isAuthenticated) setAuthOpen(true); }}
                className={`px-4 py-3 border-b border-slate-100 cursor-pointer text-xs transition-colors ${
                  selectedSheet?.id === s.id ? "bg-teal-50 border-l-4 border-l-teal-500" : "hover:bg-slate-50"
                }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-bold text-slate-600">
                    {new Date(s.printedAt).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" })}
                    {" "}{new Date(s.printedAt).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  {s.version && <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono">Ver.{s.version}</span>}
                </div>
                <div className="text-slate-500">印刷者: {s.operator?.name ?? "—"}</div>
                {selectedSheet?.id === s.id && (
                  <div className="mt-1 text-[11px] text-teal-700 font-bold">▶ この段取シートで記録入力中</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 右ペイン: 入力フォーム */}
        <div className="flex-1 overflow-y-auto p-5">
          {!isAuthenticated && (
            <div className="mb-5 p-4 bg-teal-50 border border-teal-200 rounded-xl flex items-center gap-4">
              <span className="text-3xl">⏱</span>
              <div className="flex-1">
                <div className="text-sm font-bold text-teal-800">作業記録 — 作業開始前</div>
                <div className="text-xs text-teal-600 mt-0.5">
                  {selectedSheet ? `段取シート（${new Date(selectedSheet.printedAt).toLocaleDateString("ja-JP")}）を選択中` : "左リストから段取シートを選択してください"}
                </div>
              </div>
              <button onClick={() => setAuthOpen(true)}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm transition-colors whitespace-nowrap">
                この作業を開始する
              </button>
            </div>
          )}

          <div className={!isAuthenticated ? "opacity-40 pointer-events-none select-none" : ""}>
            {/* モードバー */}
            <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold mb-4 ${
              editRecordId ? "bg-amber-100 border border-amber-300 text-amber-800" : "bg-teal-50 border border-teal-200 text-teal-700"
            }`}>
              <span>{editRecordId ? "✏️ 編集モード" : "＋ 新規入力モード"}</span>
              {editRecordId && (
                <button onClick={resetForm} className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50">
                  ＋ 新規に戻す
                </button>
              )}
            </div>

            <div className="space-y-4 max-w-2xl">
              {/* 種別・機械 */}
              <div className="bg-white rounded-xl border border-slate-200 p-4 grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-2">種別 *</label>
                  <div className="flex gap-2 flex-wrap">
                    {WORK_TYPES.map(t => (
                      <button key={t} type="button" onClick={() => setWorkType(t)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-colors ${
                          workType === t ? "bg-teal-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        }`}>{t}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-2">使用機械</label>
                  <select value={machineId} onChange={e => setMachineId(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300 bg-white">
                    <option value="">— 選択 —</option>
                    {machines.filter(m => m.isActive).map(m => (
                      <option key={m.id} value={String(m.id)}>{m.id} : {m.machineCode}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 段取 */}
              <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 space-y-3">
                <div className="text-sm font-bold text-blue-700 border-b border-blue-200 pb-2">🔧 段取</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">段取時間</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min={0} value={setupH} onChange={e => setSetupH(Number(e.target.value))}
                        className="border border-slate-300 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-teal-300" />
                      <span className="text-xs text-slate-400">h</span>
                      <input type="number" min={0} max={59} value={setupM} onChange={e => setSetupM(Number(e.target.value))}
                        className="border border-slate-300 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-teal-300" />
                      <span className="text-xs text-slate-400">m</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 量産/加工 */}
              <div className="bg-green-50 rounded-xl border border-green-200 p-4 space-y-3">
                <div className="text-sm font-bold text-green-700 border-b border-green-200 pb-2">⚙️ {workType}</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">加工時間</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min={0} value={machH} onChange={e => setMachH(Number(e.target.value))}
                        className="border border-slate-300 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-teal-300" />
                      <span className="text-xs text-slate-400">h</span>
                      <input type="number" min={0} max={59} value={machM} onChange={e => setMachM(Number(e.target.value))}
                        className="border border-slate-300 rounded px-2 py-1.5 text-sm text-center w-16 focus:outline-none focus:ring-2 focus:ring-teal-300" />
                      <span className="text-xs text-slate-400">m</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">加工個数</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min={0} value={quantity} onChange={e => setQuantity(e.target.value)}
                        className="border border-slate-300 rounded px-2 py-1.5 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-teal-300" />
                      <span className="text-xs text-slate-400">個</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 備考 */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <label className="text-xs font-bold text-slate-500 block mb-2">備考</label>
                <textarea value={note} onChange={e => setNote(e.target.value)} rows={3} maxLength={1000}
                  placeholder="問題点・注意事項・特記事項"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300 resize-none" />
                <div className="text-right text-xs text-slate-400 mt-1">{note.length} / 1000</div>
              </div>

              {saveError && <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">⚠️ {saveError}</div>}

              <div className="flex gap-3">
                <button onClick={handleSubmit} disabled={saving}
                  className="flex-1 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white font-bold text-sm transition-colors">
                  {saving ? "登録中…" : "✓ 作業完了（登録）"}
                </button>
                <button onClick={() => { logout(); router.push(`/mc/${mcId}`); }}
                  className="px-6 py-3 rounded-xl border border-slate-300 text-slate-600 font-bold text-sm hover:bg-slate-50 transition-colors">
                  ✕ キャンセル
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} sessionType="work_record" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}

export default function McRecordPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>
      <McRecordPageInner />
    </Suspense>
  );
}
