"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, McDetail, McTooling, McWorkOffset, McIndexProgram,
         McFile, McChangeHistory, McSetupSheetLog, McWorkRecord } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-700", PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700", CHANGING: "bg-red-100 text-red-700",
};

const MAIN_TABS = [
  { key: "mc",      label: "マシニングデータ" },
  { key: "tooling", label: "ツーリング" },
  { key: "offset",  label: "ワークオフセット" },
  { key: "index",   label: "インデックスプログラム" },
  { key: "history", label: "履歴" },
  { key: "files",   label: "写真・図" },
];

export default function McDetailPage() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();

  const [detail,    setDetail]    = useState<McDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mainTab,   setMainTab]   = useState("mc");
  const [histTab,   setHistTab]   = useState("change");

  // 遅延ロードデータ
  const [changes, setChanges] = useState<McChangeHistory[] | null>(null);
  const [works,   setWorks]   = useState<McWorkRecord[]   | null>(null);
  const [prints,  setPrints]  = useState<McSetupSheetLog[]| null>(null);
  const [histLoading, setHistLoading] = useState(false);

  // 認証
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authOpen, setAuthOpen]       = useState(false);
  const [authType, setAuthType]       = useState("edit");
  const [pendingUsb, setPendingUsb]   = useState(false);

  // タイマー
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    if (!mcId) return;
    mcApi.findOne(mcId).then(r => setDetail((r as any).data ?? r)).catch(e => setLoadError(e.message));
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

  useEffect(() => {
    if (mainTab !== "history") return;
    if (histTab === "change" && changes === null) {
      setHistLoading(true);
      mcApi.changeHistory(mcId).then(r => setChanges((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
    if (histTab === "work" && works === null) {
      setHistLoading(true);
      mcApi.workRecords(mcId).then(r => setWorks((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
    if (histTab === "print" && prints === null) {
      setHistLoading(true);
      mcApi.setupSheetLogs(mcId).then(r => setPrints((r as any).data ?? [])).finally(() => setHistLoading(false));
    }
  }, [mainTab, histTab, mcId]);

  // USB pending
  useEffect(() => {
    if (isAuthenticated && pendingUsb && token) {
      setPendingUsb(false);
      showToast("USB書き出し機能は今後実装予定です");
    }
  }, [isAuthenticated, pendingUsb, token]);

  const openAuth = (type: string) => { setAuthType(type); setAuthOpen(true); };

  const fmtDate = (s: string | null | undefined) => {
    if (!s) return "—";
    try { return new Date(s).toLocaleString("ja-JP", { year: "numeric", month: "2-digit", day: "2-digit" }); }
    catch { return s; }
  };

  const fmtCycle = (sec: number | null) => {
    if (!sec) return "—";
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return `${h}H ${String(m).padStart(2,"0")}M ${String(s).padStart(2,"0")}S`;
  };

  const fmtElapsed = (s: number) =>
    `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;

  if (loadError) return (
    <div className="h-screen flex items-center justify-center text-red-500">
      <div className="text-center"><p className="text-2xl mb-2">⚠️</p><p>{loadError}</p>
        <button onClick={() => router.push("/mc/search")} className="mt-4 text-teal-600 text-sm hover:underline">← 検索に戻る</button>
      </div>
    </div>
  );

  if (!detail) return (
    <div className="h-screen flex items-center justify-center text-slate-400">
      <div className="text-center"><div className="animate-spin text-3xl mb-2">⚙️</div><p>読み込み中…</p></div>
    </div>
  );

  const d = detail;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc/search")} className="text-teal-400 font-bold text-sm font-mono hover:text-teal-300">MachCore MC</button>
        <span className="text-slate-600">›</span>
        <span className="text-xs text-slate-300 truncate">{d.part.drawingNo} / {d.part.name}</span>
        <button onClick={() => router.push("/nc/search")} className="text-xs border border-sky-600 hover:border-sky-400 text-sky-400 hover:text-white hover:bg-sky-700 px-2.5 py-1 rounded font-medium transition-all">⇄ NC</button>
        <span className="ml-auto flex items-center gap-3">
          {isAuthenticated && operator ? (
            <>
              <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
                作業中: {operator.name} {fmtElapsed(elapsed)}
              </span>
              <button onClick={logout} className="text-[11px] text-slate-400 hover:text-white">終了</button>
            </>
          ) : (
            <button onClick={() => openAuth("edit")} className="text-[11px] bg-teal-600 hover:bg-teal-700 text-white px-3 py-1 rounded font-bold">
              この作業を開始する
            </button>
          )}
          <button onClick={() => { if (!isAuthenticated) { setPendingUsb(true); openAuth("usb_download"); } }}
            className="text-[11px] bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded font-bold">
            PG→USB
          </button>
        </span>
      </header>

      {/* 部品ヘッダー */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-teal-600 font-bold text-lg">{d.part.drawingNo}</span>
          <span className={`text-[11px] px-2 py-0.5 rounded font-bold ${STATUS_COLOR[d.status] ?? "bg-slate-100 text-slate-600"}`}>
            {STATUS_LABEL[d.status] ?? d.status}
          </span>
          {d.commonGroup.length > 1 && (
            <span className="text-[11px] bg-pink-100 text-pink-700 px-2 py-0.5 rounded font-bold">共通加工 {d.commonGroup.length}部品</span>
          )}
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver.{d.version}</span>
          <div className="ml-auto flex gap-2">
            <button onClick={() => router.push(`/mc/${mcId}/edit`)}
              className="text-xs bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-lg font-bold">変更・登録</button>
            <button onClick={() => router.push(`/mc/${mcId}/print`)}
              className="text-xs bg-teal-600 hover:bg-teal-700 text-white px-3 py-1.5 rounded-lg font-bold">段取シート</button>
          </div>
        </div>
        <div className="text-sm text-slate-700 font-medium mb-1">{d.part.name}</div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>MCID: {d.id}</span>
          <span>加工ID: {d.machiningId}</span>
          {d.machine && <span>機械: {d.machine.machineCode}</span>}
          {d.part.clientName && <span>納入先: {d.part.clientName}</span>}
        </div>
      </div>

      {/* ナビタブ */}
      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {[
          { href: `/mc/${mcId}`,        label: "MC詳細",    active: true  },
          { href: `/mc/${mcId}/edit`,   label: "変更・登録", active: false },
          { href: `/mc/${mcId}/print`,  label: "段取シート", active: false },
          { href: `/mc/${mcId}/record`, label: "作業記録",  active: false },
        ].map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab.active ? "border-teal-400 text-teal-300" : "border-transparent text-slate-400 hover:text-white hover:border-slate-400"}`}>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* コンテンツタブ */}
      <div className="bg-white border-b border-slate-200 px-4 flex gap-0 shrink-0">
        {MAIN_TABS.map(tab => (
          <button key={tab.key} onClick={() => setMainTab(tab.key)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              mainTab === tab.key ? "border-teal-500 text-teal-600" : "border-transparent text-slate-400 hover:text-slate-600"}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* タブコンテンツ */}
      <div className="flex-1 overflow-y-auto p-5">

        {/* ─── マシニングデータ ─── */}
        {mainTab === "mc" && (
          <div className="max-w-3xl mx-auto space-y-5">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200">
                <span className="text-xs font-bold text-slate-600">基本情報</span>
              </div>
              <div className="p-4 grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-slate-400 text-xs block mb-0.5">機械</span><span className="font-medium">{d.machine?.machineName ?? d.machine?.machineCode ?? "—"}</span></div>
                <div><span className="text-slate-400 text-xs block mb-0.5">主Oナンバ</span><span className="font-mono font-medium">{d.oNumber ?? "—"}</span></div>
                <div><span className="text-slate-400 text-xs block mb-0.5">サイクルタイム/1P</span><span className="font-medium">{fmtCycle(d.cycleTimeSec)}</span></div>
                <div><span className="text-slate-400 text-xs block mb-0.5">加工個数/1サイクル</span><span className="font-medium">{d.machiningQty ?? 1} 個</span></div>
                <div><span className="text-slate-400 text-xs block mb-0.5">共通部品コード</span><span className="font-mono">{d.commonPartCode ?? "—"}</span></div>
                <div><span className="text-slate-400 text-xs block mb-0.5">登録日</span><span>{fmtDate(d.registeredAt)}</span></div>
                {d.clampNote && <div className="col-span-2"><span className="text-slate-400 text-xs block mb-0.5">クランプ</span><span className="whitespace-pre-wrap">{d.clampNote}</span></div>}
                {d.note && <div className="col-span-2"><span className="text-slate-400 text-xs block mb-0.5">備考</span><span className="whitespace-pre-wrap text-slate-600">{d.note}</span></div>}
              </div>
            </div>

            {/* 共通加工グループ */}
            {d.commonGroup.length > 1 && (
              <div className="bg-white rounded-xl border border-pink-200 overflow-hidden">
                <div className="bg-pink-50 px-4 py-2 border-b border-pink-200">
                  <span className="text-xs font-bold text-pink-700">共通加工グループ（加工ID: {d.machiningId}）</span>
                </div>
                <div className="p-2">
                  {d.commonGroup.map(g => (
                    <div key={g.id} onClick={() => g.id !== d.id && router.push(`/mc/${g.id}`)}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                        g.id === d.id ? "bg-teal-50 border border-teal-200" : "hover:bg-slate-50 cursor-pointer"}`}>
                      <span className="font-mono text-teal-600 font-bold text-xs">MCID:{g.id}</span>
                      <span className="font-mono text-slate-600 text-xs">{g.part.drawingNo}</span>
                      <span className="text-slate-600 text-xs">{g.part.name}</span>
                      <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded font-bold ${STATUS_COLOR[g.status] ?? ""}`}>
                        {STATUS_LABEL[g.status] ?? g.status}
                      </span>
                      {g.id === d.id && <span className="text-[10px] text-teal-600 font-bold">← 現在</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── ツーリング ─── */}
        {mainTab === "tooling" && (
          <div className="max-w-4xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ツーリングデータ ({d.tooling.length}本)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="text-xs text-teal-600 hover:text-teal-700 font-bold">✏️ 編集</button>
              </div>
              {d.tooling.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ツーリングデータがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["T番号","工具名","径(mm)","H補正","D補正","種別","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.tooling.map((t, i) => (
                      <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 font-mono font-bold text-teal-600">{t.toolNo}</td>
                        <td className="px-3 py-2">{t.toolName ?? "—"}</td>
                        <td className="px-3 py-2 text-center">{t.diameter ? Number(t.diameter).toFixed(1) : "—"}</td>
                        <td className="px-3 py-2 text-center font-mono">{t.lengthOffsetNo ?? "—"}</td>
                        <td className="px-3 py-2 text-center font-mono">{t.diaOffsetNo ?? "—"}</td>
                        <td className="px-3 py-2">{t.toolType ?? ""}</td>
                        <td className="px-3 py-2 text-slate-400">{t.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ─── ワークオフセット ─── */}
        {mainTab === "offset" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ワークオフセット ({d.workOffsets.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.workOffsets.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ワークオフセットデータがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["G座標","X","Y","Z","A","R","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-center font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.workOffsets.map((o, i) => (
                      <tr key={o.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono font-bold text-teal-600">{o.gCode}</td>
                        {[o.xOffset, o.yOffset, o.zOffset, o.aOffset, o.rOffset].map((v, j) => (
                          <td key={j} className="px-3 py-2 text-center font-mono">{v ? Number(v).toFixed(3) : "—"}</td>
                        ))}
                        <td className="px-3 py-2 text-slate-400">{o.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["No.","第0軸","第1軸","第2軸","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.indexPrograms.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono">{p.sortOrder}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}
        {mainTab === "history" && (
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-2 mb-4">
              {[["change","変更履歴"],["work","作業記録"],["print","印刷履歴"]].map(([k, l]) => (
                <button key={k} onClick={() => setHistTab(k)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    histTab === k ? "bg-teal-600 text-white border-teal-600" : "border-slate-300 text-slate-500 hover:border-teal-400"}`}>
                  {l}
                </button>
              ))}
            </div>
            {histLoading && <div className="text-center py-8 text-slate-400">読み込み中…</div>}
            {!histLoading && histTab === "change" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!changes || changes.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">変更履歴がありません</div>
                ) : changes.map((c: any, i) => (
                  <div key={c.id} className={`px-4 py-3 border-b border-slate-100 text-sm ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400 text-xs">{fmtDate(c.changedAt)}</span>
                      <span className="text-slate-500 text-xs">{c.operator?.name ?? "—"}</span>
                      <span className="text-slate-700">{c.content ?? c.changeType}</span>
                      {c.versionAfter && <span className="ml-auto font-mono text-[10px] text-slate-400">Ver.{c.versionAfter}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!histLoading && histTab === "work" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!works || works.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">作業記録がありません</div>
                ) : works.map((r: McWorkRecord, i) => (
                  <div key={r.id} className={`px-4 py-3 border-b border-slate-100 text-xs ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400">{fmtDate(r.work_date)}</span>
                      <span className="font-bold text-slate-600">{r.operator_name ?? "—"}</span>
                      <span className="text-slate-500">{r.machine_code ?? ""}</span>
                      <span>段取: {r.setup_time_min != null ? `${r.setup_time_min}分` : "—"}</span>
                      <span>加工: {r.machining_time_min != null ? `${r.machining_time_min}分` : "—"}</span>
                      {r.quantity && <span>W数: {r.quantity}</span>}
                    </div>
                    {r.note && <div className="text-slate-400 mt-1">{r.note}</div>}
                  </div>
                ))}
              </div>
            )}
            {!histLoading && histTab === "print" && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {!prints || prints.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">印刷履歴がありません</div>
                ) : prints.map((p: McSetupSheetLog, i) => (
                  <div key={p.id} className={`px-4 py-3 border-b border-slate-100 text-xs ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400">{new Date(p.printedAt).toLocaleString("ja-JP")}</span>
                      <span className="text-slate-600">{p.operator?.name ?? "—"}</span>
                      {p.version && <span className="ml-auto font-mono text-slate-400">Ver.{p.version}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── 写真・図 ─── */}
        {mainTab === "files" && (
          <div className="max-w-3xl mx-auto">
            {d.files.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <div className="text-4xl mb-3">📁</div>
                <p className="text-slate-400 text-sm">ファイルがありません</p>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)}
                  className="mt-4 text-teal-600 text-sm hover:underline">編集画面でアップロード →</button>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-4">
                {d.files.map(f => (
                  <div key={f.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <div className="aspect-square bg-slate-100 flex items-center justify-center">
                      {f.thumbnail_path ? (
                        <img src={`/api/files/${f.id}/preview`} alt={f.original_name} className="w-full h-full object-contain" />
                      ) : (
                        <span className="text-3xl">{f.file_type === "PHOTO" ? "📷" : f.file_type === "DRAWING" ? "📐" : "📄"}</span>
                      )}
                    </div>
                    <div className="px-2 py-1.5">
                      <p className="text-[11px] text-slate-600 truncate">{f.original_name}</p>
                      <p className="text-[10px] text-slate-400">{f.uploaded_by}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} sessionType={authType}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)} />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">
          {toast}
        </div>
      )}
    </div>
  );
}
