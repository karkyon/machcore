"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, machinesApi, McDetail, Machine } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};

export default function McEditPage() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();

  const [detail, setDetail]   = useState<McDetail | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [elapsed, setElapsed]  = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // 編集フィールド
  const [machineId,    setMachineId]    = useState<string>("");
  const [oNumber,      setONumber]      = useState("");
  const [clampNote,    setClampNote]    = useState("");
  const [cycleH,       setCycleH]       = useState(0);
  const [cycleM,       setCycleM]       = useState(0);
  const [cycleS,       setCycleS]       = useState(0);
  const [machiningQty, setMachiningQty] = useState(1);
  const [note,         setNote]         = useState("");

  // ツーリング
  const [toolingRows, setToolingRows] = useState<any[]>([]);
  const [toolingText, setToolingText] = useState("");
  const [parseResult, setParseResult] = useState<any[] | null>(null);
  const [activeSection, setActiveSection] = useState<"basic"|"tooling"|"offset"|"index">("basic");

  // ワークオフセット
  const [offsetRows, setOffsetRows] = useState<any[]>([]);
  // インデックス
  const [indexRows, setIndexRows] = useState<any[]>([]);

  const [saving, setSaving]   = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [toast, setToast]     = useState<string | null>(null);
  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    mcApi.findOne(mcId).then(r => {
      const d = (r as any).data ?? r;
      setDetail(d);
      setMachineId(d.machine?.id ? String(d.machine.id) : "");
      setONumber(d.oNumber ?? "");
      setClampNote(d.clampNote ?? "");
      setNote(d.note ?? "");
      setMachiningQty(d.machiningQty ?? 1);
      if (d.cycleTimeSec != null) {
        setCycleH(Math.floor(d.cycleTimeSec / 3600));
        setCycleM(Math.floor((d.cycleTimeSec % 3600) / 60));
        setCycleS(d.cycleTimeSec % 60);
      }
      setToolingRows(d.tooling ?? []);
      setOffsetRows(d.workOffsets ?? []);
      setIndexRows(d.indexPrograms ?? []);
    }).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
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

  const fmtElapsed = (s: number) =>
    `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;

  const handleSave = async () => {
    if (!token) { setSaveError("認証が必要です"); return; }
    setSaving(true); setSaveError(null);
    try {
      const cycleTimeSec = cycleH * 3600 + cycleM * 60 + cycleS;
      await mcApi.update(mcId, {
        machine_id:     machineId ? parseInt(machineId) : undefined,
        o_number:       oNumber   || undefined,
        clamp_note:     clampNote || undefined,
        cycle_time_sec: cycleTimeSec > 0 ? cycleTimeSec : undefined,
        machining_qty:  machiningQty,
        note:           note || undefined,
      }, token);
      // ツーリング保存
      if (toolingRows.length > 0) {
        await mcApi.saveTooling(mcId, toolingRows.map((t, i) => ({ ...t, sort_order: i })), token);
      }
      // ワークオフセット保存
      if (offsetRows.length > 0) {
        await mcApi.saveWorkOffsets(mcId, offsetRows, token);
      }
      // インデックス保存
      if (indexRows.length > 0) {
        await mcApi.saveIndexPrograms(mcId, indexRows.map((r, i) => ({ ...r, sort_order: i })), token);
      }
      showToast("✅ 保存しました");
      logout();
      setTimeout(() => router.push(`/mc/${mcId}`), 1200);
    } catch (e: any) {
      setSaveError(e.message ?? "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleParseTooling = async () => {
    if (!token || !toolingText.trim()) return;
    try {
      const res = await mcApi.parseTooling(mcId, toolingText, token);
      const items = ((res as any).data ?? res).items ?? [];
      setParseResult(items);
    } catch { alert("解析に失敗しました"); }
  };

  const applyParseResult = () => {
    if (!parseResult) return;
    setToolingRows(parseResult.map((item, i) => ({
      sort_order: i, tool_no: item.tool_no, tool_name: item.tool_name ?? "",
      length_offset_no: item.length_offset_no ?? "", dia_offset_no: item.dia_offset_no ?? "",
      raw_program_line: item.raw_program_line ?? "",
    })));
    setParseResult(null);
    setToolingText("");
    showToast("ツーリングデータを取り込みました");
  };

  if (!detail) return (
    <div className="h-screen flex items-center justify-center text-slate-400">読み込み中…</div>
  );

  const d = detail;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button
          onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs bg-white text-slate-800 hover:bg-slate-100 border border-slate-400 px-2.5 py-1 rounded font-medium transition-all shrink-0">⇄ NC</button>
        <span className="text-sm font-medium flex items-center gap-1.5">変更・登録</span>
        <span className="ml-auto">
          {isAuthenticated && operator && (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          )}
          {!isAuthenticated && (
            <span className="text-[11px] bg-slate-600 text-white px-2 py-0.5 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報エリア */}
      {d && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-teal-600 font-bold text-lg">{d.part.drawingNo}</span>
            {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
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
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => router.push(`/mc/${mcId}`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/print`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => router.push(`/mc/${mcId}/record`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41] transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* セッションバナー */}
      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => { logout(); router.push(`/mc/${mcId}`); }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : "作業完了（登録）"}
            </button>
          </div>
        </div>
      )}

            {/* ロック状態 */}
      {!isAuthenticated && detail && (
        <div className="flex-1 flex items-center justify-center bg-slate-100">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-md w-full text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-red-50 border-2 border-red-200 flex items-center justify-center mx-auto">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            <div>
              <h2 className="text-slate-700 font-bold text-lg mb-1">変更・登録 — 作業開始前</h2>
              <p className="text-slate-400 text-sm">現在のデータを確認しています。変更・登録を行うには担当者の確認（パスワード）が必要です。</p>
            </div>
            <div className="border border-slate-200 rounded-xl overflow-hidden text-sm">
              <div className="grid grid-cols-3 divide-x divide-slate-200">
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">機械</div><div className="font-bold">{detail.machine?.machineCode ?? "—"}</div></div>
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">主Oナンバ</div><div className="font-mono font-bold">{detail.oNumber ?? "—"}</div></div>
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">サイクルタイム</div><div className="font-bold">{detail.cycleTimeSec != null ? `${Math.floor(detail.cycleTimeSec/60)} 分` : "—"}</div></div>
              </div>
              {detail.clampNote && (
                <div className="p-2.5 border-t border-slate-200 text-left"><div className="text-slate-400 text-xs mb-1">備考</div><div className="text-slate-600 text-xs">{detail.clampNote.slice(0,60)}{detail.clampNote.length > 60 ? "…" : ""}</div></div>
              )}
            </div>
            <button
              onClick={() => setAuthOpen(true)}
              className="flex items-center gap-2 px-6 py-3 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-sm transition-colors mx-auto"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              この作業を開始する（担当者確認）
            </button>
            <div className="text-xs text-slate-400">担当者の選択とパスワード確認後に編集できます</div>
          </div>
        </div>
      )}

      {/* 編集フォーム */}
      {isAuthenticated && (
        <div className="flex flex-1 overflow-hidden">
          {/* セクションタブ */}
          <div className="w-36 shrink-0 bg-white border-r border-slate-200 flex flex-col pt-2">
            {[
              ["basic",   "基本情報"],
              ["tooling", "ツーリング"],
              ["offset",  "ワークオフセット"],
              ["index",   "インデックスPG"],
            ].map(([k, l]) => (
              <button key={k} onClick={() => setActiveSection(k as any)}
                className={`text-left px-4 py-3 text-xs font-medium border-l-2 transition-colors ${
                  activeSection === k ? "border-teal-500 text-teal-700 bg-teal-50" : "border-transparent text-slate-500 hover:bg-slate-50"}`}>
                {l}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {saveError && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">⚠️ {saveError}</div>
            )}

            {/* 基本情報 */}
            {activeSection === "basic" && (
              <div className="max-w-2xl space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">機械</label>
                    <select value={machineId} onChange={e => setMachineId(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {machines.filter(m => m.isActive).map(m => (
                        <option key={m.id} value={String(m.id)}>{m.machineCode}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">主Oナンバ</label>
                    <input value={oNumber} onChange={e => setONumber(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">クランプ</label>
                  <textarea value={clampNote} onChange={e => setClampNote(e.target.value)} rows={3}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-2">サイクルタイム/1P</label>
                  <div className="flex items-center gap-2">
                    <input type="number" min={0} value={cycleH} onChange={e => setCycleH(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">H</span>
                    <input type="number" min={0} max={59} value={cycleM} onChange={e => setCycleM(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">M</span>
                    <input type="number" min={0} max={59} value={cycleS} onChange={e => setCycleS(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">S</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">加工個数/1サイクル</label>
                  <input type="number" min={1} value={machiningQty} onChange={e => setMachiningQty(Number(e.target.value))}
                    className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm text-center focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">備考</label>
                  <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none" />
                </div>
              </div>
            )}

            {/* ツーリング */}
            {activeSection === "tooling" && (
              <div className="max-w-4xl space-y-4">
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <p className="text-xs font-bold text-amber-700 mb-3">ツーリングプログラム読取り（MC専用機能）</p>
                  <textarea value={toolingText} onChange={e => setToolingText(e.target.value)}
                    placeholder="ツーリングプログラムのテキストをここに貼り付けてください..."
                    rows={6}
                    className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono focus:ring-2 focus:ring-amber-400 focus:outline-none resize-none" />
                  <div className="flex gap-2 mt-2">
                    <button onClick={handleParseTooling}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-4 py-2 rounded-lg font-bold">解析・プレビュー</button>
                    {parseResult && (
                      <button onClick={applyParseResult}
                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs px-4 py-2 rounded-lg font-bold">
                        {parseResult.length}本を取り込む
                      </button>
                    )}
                  </div>
                  {parseResult && (
                    <div className="mt-3 text-xs text-amber-700">{parseResult.length}本の工具を検出しました。「取り込む」で確定します。</div>
                  )}
                </div>

                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ツーリングリスト ({toolingRows.length}本)</span>
                    <button onClick={() => setToolingRows(prev => [...prev, { sort_order: prev.length, tool_no: "", tool_name: "", length_offset_no: "", dia_offset_no: "" }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["T番号","工具名","H補正","D補正","種別",""].map(h =>
                        <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {toolingRows.map((t, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}
                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}
                            className="w-40 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.tool_type ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_type: e.target.value} : x))}
                            className="w-20 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ワークオフセット */}
            {activeSection === "offset" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ワークオフセット ({offsetRows.length}件)</span>
                    <button onClick={() => setOffsetRows(prev => [...prev, { g_code: `G${54 + prev.length}` }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["G座標","X","Y","Z","A","R",""].map(h =>
                        <th key={h} className="px-2 py-2 text-center font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {offsetRows.map((o, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1"><input value={o.g_code ?? o.gCode ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, g_code: e.target.value} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          {["x_offset","y_offset","z_offset","a_offset","r_offset"].map(k => (
                            <td key={k} className="px-2 py-1"><input type="number" step="0.001"
                              value={o[k] ?? o[k.replace("_offset", "Offset")] ?? ""}
                              onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                              className="w-20 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          ))}
                          <td className="px-2 py-1"><button onClick={() => setOffsetRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* インデックスプログラム */}
            {activeSection === "index" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">インデックスプログラム ({indexRows.length}件)</span>
                    <button onClick={() => setIndexRows(prev => [...prev, { sort_order: prev.length, axis_0: "", axis_1: "", axis_2: "" }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["No.","第0軸","第1軸","第2軸","備考",""].map(h =>
                        <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {indexRows.map((p, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1 text-center text-slate-400">{i+1}</td>
                          {["axis_0","axis_1","axis_2"].map(k => (
                            <td key={k} className="px-2 py-1"><input value={p[k] ?? p[k.replace("_","").replace("axis",k==="axis_0"?"axis0":k==="axis_1"?"axis1":"axis2")] ?? ""}
                              onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                              className="w-40 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          ))}
                          <td className="px-2 py-1"><input value={p.note ?? ""}
                            onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><button onClick={() => setIndexRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType="edit" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}
