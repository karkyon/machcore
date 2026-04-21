"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, machinesApi, McDetail, Machine } from "@/lib/api";
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
      <header className="bg-slate-800 text-white px-5 py-2 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc/search")} className="text-teal-400 font-bold text-sm font-mono">MachCore MC</button>
        <span className="text-slate-600">›</span>
        <span className="text-xs text-slate-300 truncate">{d.part.drawingNo} / 変更・登録</span>
        {isAuthenticated && operator && (
          <span className="ml-auto flex items-center gap-3">
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          </span>
        )}
      </header>

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

      {/* 部品ヘッダー */}
      <div className="bg-white border-b border-slate-200 px-5 py-2.5 shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-mono text-teal-600 font-bold">{d.part.drawingNo}</span>
          <span className="text-sm text-slate-700">{d.part.name}</span>
          <span className="font-mono text-[11px] text-slate-400">MCID:{d.id} / 加工ID:{d.machiningId} / Ver.{d.version}</span>
        </div>
      </div>

      {/* ナビタブ */}
      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {[
          { href: `/mc/${mcId}`,        label: "MC詳細",    active: false },
          { href: `/mc/${mcId}/edit`,   label: "変更・登録", active: true  },
          { href: `/mc/${mcId}/print`,  label: "段取シート", active: false },
          { href: `/mc/${mcId}/record`, label: "作業記録",  active: false },
        ].map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab.active ? "border-teal-400 text-teal-300" : "border-transparent text-slate-400 hover:text-white"}`}>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* ロック状態 */}
      {!isAuthenticated && (
        <div className="flex-1 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-sm w-full text-center">
            <div className="text-5xl mb-4">🔒</div>
            <h2 className="text-slate-700 font-bold mb-2">変更・登録には認証が必要です</h2>
            <p className="text-slate-400 text-sm mb-6">担当者を選択してパスワードを入力してください</p>
            <button onClick={() => setAuthOpen(true)}
              className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm">
              この作業を開始する
            </button>
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
        <AuthModal isOpen={true} ncProgramId={mcId} sessionType="edit" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}
