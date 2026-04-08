"use client";
// apps/web/app/nc/[nc_id]/print/page.tsx
// SCR-04: 段取シート

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { printApi, PrintData, PrintOptions, NcTool, downloadApi} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW:              "新規",
  PENDING_APPROVAL: "未承認",
  APPROVED:         "承認済",
  CHANGING:         "変更中",
};
const STATUS_COLOR: Record<string, string> = {
  NEW:              "bg-blue-100 text-blue-700",
  PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED:         "bg-green-100 text-green-700",
  CHANGING:         "bg-red-100 text-red-700",
};

export default function PrintPage() {
  const { nc_id } = useParams<{ nc_id: string }>();
  const ncId  = parseInt(nc_id);
  const router = useRouter();

  // ── データ ──
  const [nc,        setNc]        = useState<PrintData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── 認証 ──
  const { operator, isAuthenticated, logout, token } = useAuth();
  const [authModalOpen,    setAuthModalOpen]    = useState(false);
  const [authSessionType,  setAuthSessionType]  = useState("setup_print");

  // ── 印刷オプション ──
  const [includeTools,    setIncludeTools]    = useState(true);
  const [includeClamp,    setIncludeClamp]    = useState(true);
  const [includeDrawings, setIncludeDrawings] = useState(false);

  // ── 状態 ──
  const [printing,  setPrinting]  = useState(false);
  const [directPrinting, setDirectPrinting] = useState(false);
  const [printError, setPrintError] = useState<string | null>(null);
  const [toast,     setToast]     = useState<string | null>(null);

  // 経過タイマー
  const [elapsed,  setElapsed]  = useState(0);
  const timerRef               = useRef<NodeJS.Timeout | null>(null);

  // ── 初期データ取得 ──
  useEffect(() => {
    printApi.getData(ncId)
      .then(r  => setNc(r.data))
      .catch(e => setLoadError(e.message));
  }, [ncId]);

  // ── タイマー（認証後に起動） ──
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
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  // ── トースト ──
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  // ── 印刷実行 ──

  const handleDownload = async () => {
    try {
      if (!token) { alert("先に作業を開始してください"); return; }
      await downloadApi.pgFile(ncId, token);
    } catch {
      alert("ダウンロードに失敗しました");
    }
  };

  const handlePrint = async () => {
    // token は useAuth() から取得（localStorage は使わない）
    if (!token) {
      setPrintError("認証トークンが取得できません。再度「この作業を開始する」から認証してください。");
      return;
    }
    if (!nc) return;

    setPrinting(true);
    setPrintError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      console.log("[print] POST to:", `${apiUrl}/nc/${ncId}/print`);

      const res = await fetch(`${apiUrl}/nc/${ncId}/print`, {
        method:  "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type":  "application/json",
        },
        body: JSON.stringify({
          include_tools:    includeTools,
          include_clamp:    includeClamp,
          include_drawings: includeDrawings,
        } satisfies PrintOptions),
      });

      if (!res.ok) {
        let errMsg = `HTTP ${res.status}`;
        try { const j = await res.json(); errMsg = j.message ?? errMsg; } catch { /* ignore */ }
        throw new Error(errMsg);
      }

      const blob   = await res.blob();
      const pdfUrl = URL.createObjectURL(blob);
      window.open(pdfUrl, "_blank");

      // Work Session 終了（logout が API呼び出し＋ステートクリアを担う）
      logout();

      showToast("✅ 段取シートを発行しました");
      setTimeout(() => router.push(`/nc/${ncId}`), 1500);
    } catch (e: any) {
      console.error("[print] error:", e);
      setPrintError(e.message ?? "PDF生成に失敗しました");
    } finally {
      setPrinting(false);
    }
  };

  // ── ダイレクト印刷 ──
  const handleDirectPrint = async () => {
    if (!token) { setPrintError("認証が必要です"); return; }
    setDirectPrinting(true); setPrintError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiUrl}/nc/${ncId}/direct-print`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ include_tools: includeTools, include_clamp: includeClamp, include_drawings: includeDrawings }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.message ?? `HTTP ${res.status}`);
      }
      const result = await res.json();
      logout();
      showToast(`✅ ${result.message}`);
      setTimeout(() => router.push(`/nc/${ncId}`), 1500);
    } catch (e: any) {
      setPrintError(e.message ?? "印刷に失敗しました");
    } finally { setDirectPrinting(false); }
  };

  // ── キャンセル ──
  const handleCancel = () => {
    // logout() が Work Session 終了 + state クリアを担う
    logout();
    router.push(`/nc/${ncId}`);
  };

  // ── ローディング ──
  if (loadError) return (
    <div className="min-h-screen flex items-center justify-center text-red-500 text-sm">
      読み込みエラー: {loadError}
    </div>
  );
  if (!nc) return (
    <div className="min-h-screen flex items-center justify-center text-slate-400 text-sm">
      読み込み中…
    </div>
  );

  return (
    <>
    <div className="h-screen flex flex-col bg-slate-100 overflow-hidden">

      {/* ── グローバルヘッダー ── */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
          <button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
          >
            <span className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center shrink-0">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            </span>
            NC詳細
          </button>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
          <span className="text-slate-400 text-xs">|</span>
          <span className="text-sm font-medium flex items-center gap-1.5"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート</span>
          <span className="ml-auto">
            {isAuthenticated && operator ? (
              <span className="text-[11px] bg-amber-600 text-white px-3 py-1 rounded font-bold">
                作業中: {operator.name}　{fmtElapsed(elapsed)}
              </span>
            ) : (
              <span className="text-[11px] text-slate-400 bg-slate-700 px-2 py-1 rounded">
                🔒 認証待ち
              </span>
            )}
          </span>
        </header>

      {/* 部品情報エリア */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-sky-600 font-bold text-lg">{nc.part.drawingNo}</span>
          <span className="text-[11px] bg-sky-100 text-sky-700 px-2 py-0.5 rounded font-mono font-bold">L{nc.processL}</span>
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${STATUS_COLOR[nc.status] ?? "bg-slate-100 text-slate-600"}`}>
            {STATUS_LABEL[nc.status] ?? nc.status}
          </span>
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {nc.version}</span>
        </div>
        <div className="text-sm text-slate-700 font-medium mb-1">{nc.part.name}</div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>NC_id: {nc.id}</span>
          <span>部品ID: {nc.part.partId}</span>
          {nc.part.clientName && <span>納入先: {nc.part.clientName}</span>}
        </div>
      </div>

      {/* タブナビ */}
      <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
        <button onClick={() => router.push(`/nc/${ncId}`)}
          className="px-4 py-2 text-xs font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          NC詳細
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/edit`)}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${"border-transparent text-slate-400 hover:text-slate-200"}`}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          変更・登録
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/print`)}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${"text-amber-400 border-amber-400"}`}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          段取シート
          {isAuthenticated && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse ml-0.5" />}
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/record`)}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${"border-transparent text-slate-400 hover:text-slate-200"}`}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          作業記録
        </button>
      </nav>

      {/* ── メインコンテンツ ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-5 max-w-5xl mx-auto">

          {/* ── エラー表示 ── */}
          {printError && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
              ❌ {printError}
            </div>
          )}

          {/* ── ロック状態 ── */}
          {!isAuthenticated && (
            <div className="max-w-lg mx-auto mt-8">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 w-full">
                <div className="text-center mb-6">
                  <div className="w-14 h-14 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto mb-3">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#92400e" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                  </div>
                  <h2 className="text-lg font-bold text-slate-700">段取シート 発行</h2>
                  <p className="text-sm text-slate-500 mt-1">
                    段取シートをA4 PDFで出力します。<br />
                    作業を開始するには認証が必要です。
                  </p>
                </div>

                {/* データプレビュー（50%透過） */}
                <div className="opacity-50 space-y-3 mb-6">
                  <DataPreview nc={nc} />
                </div>

                <button
                  onClick={() => { setAuthSessionType("setup_print"); setAuthModalOpen(true); }}
                  className="w-full py-3 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  この作業を開始する（担当者確認）
                </button>
                <p className="text-xs text-slate-400 text-center mt-2">担当者確認後に印刷・USB書き出しができます</p>
              </div>
            </div>
          )}

          {/* ── アクティブ状態 ── */}
          {isAuthenticated && (
            <div className="flex gap-5">

              {/* 左: データプレビュー */}
              <div className="flex-1 min-w-0">
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                  <h2 className="text-sm font-bold text-slate-600 mb-4 flex items-center gap-2">
                    📋 プレビュー（出力内容確認）
                  </h2>
                  <DataPreview nc={nc} showClamp={includeClamp} showTools={includeTools} />
                </div>
              </div>

              {/* 右: 印刷オプション + ボタン */}
              <div className="w-64 shrink-0 space-y-4">

                {/* 印刷オプション */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">
                    印刷オプション
                  </h3>
                  <div className="space-y-2">
                    <CheckOption
                      label="加工リストを含める"
                      checked={includeTools}
                      onChange={setIncludeTools}
                    />
                    <CheckOption
                      label="クランプ・備考を含める"
                      checked={includeClamp}
                      onChange={setIncludeClamp}
                    />
                    <CheckOption
                      label="図を含める"
                      checked={includeDrawings}
                      onChange={setIncludeDrawings}
                    />
                  </div>
                </div>

                {/* アクションボタン */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-2">
                  <button
                    onClick={handlePrint}
                    disabled={printing}
                    className="w-full py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    {printing
                      ? <><span className="animate-spin">⏳</span> 生成中…</>
                      : <><span>🖨</span> 作業完了（印刷実行）</>
                    }
                  </button>
              <button
                onClick={handleDirectPrint}
                disabled={directPrinting || printing}
                className="w-full py-3 rounded-xl bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-bold text-sm transition-colors flex items-center justify-center gap-2"
              >
                {directPrinting ? "印刷中..." : "🖨 ダイレクト印刷（プリンタへ直接送信）"}
              </button>
                  <button
                    onClick={handleDownload}
                    disabled={printing}
                    className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                  >
                    💾 NCプログラム → USB
                  </button>
                                    <button
                    onClick={handleCancel}
                    disabled={printing}
                    className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 text-sm rounded-lg transition-colors"
                  >
                    ✗ キャンセル
                  </button>
                </div>

                {/* 注意書き */}
                <div className="text-[10px] text-slate-400 space-y-1 px-1">
                  <p>• 印刷実行後、PDFが新しいタブで開きます</p>
                  <p>• 印刷完了で作業セッションが終了します</p>
                  <p>• 発行履歴がDBに記録されます</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>

    {/* ── トースト ── */}
    {toast && (
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-800 text-white text-sm px-5 py-3 rounded-xl shadow-xl">
        {toast}
      </div>
    )}

    {/* ── 認証モーダル ── */}
    <AuthModal
      isOpen={authModalOpen}
      sessionType={authSessionType}
      ncProgramId={ncId}
      onSuccess={() => setAuthModalOpen(false)}
      onCancel={() => setAuthModalOpen(false)}
    />
    </>
  );
}

// ── データプレビューコンポーネント ──────────────────────────────

function DataPreview({
  nc,
  showClamp = true,
  showTools = true,
}: {
  nc: PrintData;
  showClamp?: boolean;
  showTools?: boolean;
}) {
  return (
    <div className="space-y-4">
      {/* 加工情報 + ファイル情報 */}
      <div className="grid grid-cols-2 gap-3">
        <InfoBox title="加工情報">
          <InfoRow label="工程"     value={`L${nc.processL}`} />
          <InfoRow label="機械"     value={nc.machine?.machineName ?? nc.machine?.machineCode ?? "—"} />
          <InfoRow label="加工時間" value={nc.machiningTime != null ? `${nc.machiningTime} 分` : "—"} />
          <InfoRow label="O番号"    value={nc.oNumber ?? "—"} />
        </InfoBox>
        <InfoBox title="ファイル情報">
          <InfoRow label="フォルダ" value={nc.folderName} />
          <InfoRow label="ファイル" value={nc.fileName} />
          <InfoRow label="登録者"   value={nc.registrar.name} />
          <InfoRow label="承認者"   value={nc.approver?.name ?? "未承認"} />
        </InfoBox>
      </div>

      {/* クランプ・備考 */}
      {showClamp && nc.clampNote && (
        <div>
          <p className="text-xs font-bold text-slate-500 mb-1">クランプ・備考</p>
          <pre className="text-xs text-slate-700 bg-yellow-50 border border-yellow-200 rounded-lg p-3 whitespace-pre-wrap font-sans leading-relaxed">
            {nc.clampNote}
          </pre>
        </div>
      )}

      {/* 加工リスト */}
      {showTools && nc.tools.length > 0 && (
        <div>
          <p className="text-xs font-bold text-slate-500 mb-1">加工リスト（{nc.tools.length} 本）</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse bg-white rounded-lg overflow-hidden shadow-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  {["No", "加工種別", "チップ型番", "ホルダー型番", "ノーズR", "T番号"].map(h => (
                    <th key={h} className="px-2 py-1.5 text-left font-bold border-b border-slate-200 text-[10px]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nc.tools.map((t: NcTool, i: number) => (
                  <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                    <td className="px-2 py-1.5 font-mono text-slate-400">{t.sortOrder}</td>
                    <td className="px-2 py-1.5">{t.processType ?? "—"}</td>
                    <td className="px-2 py-1.5 font-mono">{t.chipModel   ?? "—"}</td>
                    <td className="px-2 py-1.5 font-mono">{t.holderModel ?? "—"}</td>
                    <td className="px-2 py-1.5 text-center">{t.noseR   ?? "—"}</td>
                    <td className="px-2 py-1.5 font-mono text-center">{t.tNumber ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!showTools && nc.tools.length > 0 && (
        <p className="text-xs text-slate-400 italic">
          ※ 加工リスト {nc.tools.length} 本（オプションにより非表示）
        </p>
      )}
    </div>
  );
}

// ── ヘルパーコンポーネント ────────────────────────────────────────

function InfoBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{title}</span>
      </div>
      <div className="divide-y divide-slate-50">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center px-3 py-1.5 gap-3">
      <span className="text-[10px] text-slate-400 w-16 shrink-0">{label}</span>
      <span className="text-xs text-slate-700 font-mono truncate">{value}</span>
    </div>
  );
}

function CheckOption({
  label, checked, onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer group">
      <div
        onClick={() => onChange(!checked)}
        className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
          checked
            ? "bg-sky-600 border-sky-600"
            : "bg-white border-slate-300 group-hover:border-sky-400"
        }`}
      >
        {checked && <span className="text-white text-[9px] font-bold">✓</span>}
      </div>
      <span className="text-xs text-slate-600">{label}</span>
    </label>
  );
}