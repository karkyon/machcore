"use client";
// apps/web/app/nc/[nc_id]/print/page.tsx
// SCR-04: 段取シート

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { printApi, PrintData, PrintOptions, NcTool } from "@/lib/api";
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
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <button
          onClick={() => router.push(`/nc/${ncId}`)}
          className="text-slate-400 hover:text-white text-sm transition-colors"
        >
          ← 戻る
        </button>
        <span className="text-slate-400">|</span>
        <span className="font-bold text-sky-400 tracking-wide">MachCore</span>
        <span className="ml-auto text-xs text-slate-400">NC旋盤プログラム管理</span>
      </header>

      {/* ── 部品ヘッダー ── */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-lg font-bold text-slate-800">
            {nc.part.name} — 工程 L{nc.processL}
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${STATUS_COLOR[nc.status] ?? "bg-slate-100 text-slate-600"}`}>
            {STATUS_LABEL[nc.status] ?? nc.status}
          </span>
          <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">
            Ver. {nc.version}
          </span>
          <span className="text-xs text-slate-500 font-mono">{nc.part.drawingNo}</span>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono mt-1">
          <span>NC_id: {nc.id}</span>
          <span>部品ID: {nc.part.partId}</span>
          {nc.part.clientName && <span>納入先: {nc.part.clientName}</span>}
        </div>
      </div>

      {/* ── 画面ナビゲーションタブ ── */}
      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {([
          { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
          { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
          { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: true  },
          { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: false },
        ] as { href: string; icon: string; label: string; active: boolean }[]).map(tab => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              tab.active
                ? "border-sky-400 text-sky-300"
                : "border-transparent text-slate-400 hover:text-white hover:border-slate-400"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* ── セッションバナー（認証後） ── */}
      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center gap-3 text-xs shrink-0">
          <span className="font-bold">⚡ 作業中:</span>
          <span>{operator.name}</span>
          <span className="font-mono bg-red-700 px-2 py-0.5 rounded">{fmtElapsed(elapsed)}</span>
          <span className="text-red-300">段取シート発行</span>
        </div>
      )}

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
            <div className="flex flex-col items-center justify-center py-12">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-lg w-full">
                <div className="text-center mb-6">
                  <div className="text-5xl mb-3">🖨</div>
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
                  className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-xl transition-colors"
                >
                  🔐 この作業を開始する
                </button>
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
                      label="工具リストを含める"
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

      {/* 工具リスト */}
      {showTools && nc.tools.length > 0 && (
        <div>
          <p className="text-xs font-bold text-slate-500 mb-1">工具リスト（{nc.tools.length} 本）</p>
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
          ※ 工具リスト {nc.tools.length} 本（オプションにより非表示）
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