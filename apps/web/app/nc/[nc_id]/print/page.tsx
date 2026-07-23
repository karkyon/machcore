"use client";
// apps/web/app/nc/[nc_id]/print/page.tsx
// SCR-04: 段取シート

import { useState, useEffect, useLayoutEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { printApi, ncApi, machinesApi, Machine, PrintData, PrintOptions, NcTool, downloadApi} from "@/lib/api";
import { NcPartHeader } from "@/components/nc/NcPartHeader";
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
  const { operator, isAuthenticated, logout, token, isSessionForNc } = useAuth();
  const [authModalOpen,    setAuthModalOpen]    = useState(false);
  const [authSessionType,  setAuthSessionType]  = useState("setup_print");

  // ── 印刷オプション ──
  const [includeTools,    setIncludeTools]    = useState(true);
  const [includeClamp,    setIncludeClamp]    = useState(true);
  const [includeDrawings, setIncludeDrawings] = useState(false);

  // ── [v113] リピート確認ステップ(MC側 mc/[mc_id]/print/page.tsx と同一仕様) ──
  const [repeatPurpose,   setRepeatPurpose]   = useState<'setup' | 'reference' | 'continuous'>('setup');
  const [repeatQty,       setRepeatQty]       = useState<number>(1);
  const [repeatMachineId, setRepeatMachineId] = useState<number | null>(null);
  const [repeatConfirmed, setRepeatConfirmed] = useState(false);
  const [machines,        setMachines]        = useState<Machine[]>([]);

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
      .catch(e => setLoadError(e?.response?.data?.message ?? e.message));
  }, [ncId]);

  // ── [v113] 使用機械一覧取得(リピート確認用) ──
  useEffect(() => {
    machinesApi.list("NC").then(r => {
      const list = Array.isArray((r as any).data) ? (r as any).data : (Array.isArray(r) ? r : []);
      setMachines(list);
    }).catch(() => {});
  }, []);

  // ── [v113] 前回発行時の機械・ワーク数・用途をデフォルト値としてセット(MC側と同一仕様) ──
  useEffect(() => {
    if (!machines.length) return;
    ncApi.setupSheetLogs(ncId).then(r => {
      const logs: any[] = Array.isArray((r as any).data) ? (r as any).data : (Array.isArray(r) ? r : []);
      if (!logs.length) return;
      const latest = logs.find(l => !l.work_collected && (l.sheet_type === 'REPEAT' || l.sheet_type === 'NEW'))
        ?? logs.find(l => l.sheet_type === 'REPEAT' || l.sheet_type === 'NEW')
        ?? logs[0];
      if (!latest) return;
      if (latest.machine_id_log) {
        const found = machines.find((m: any) => m.id === latest.machine_id_log);
        if (found) setRepeatMachineId(found.id);
      }
      if (latest.quantity != null && latest.quantity > 0) setRepeatQty(latest.quantity);
      if (latest.purpose) {
        const purposeMap: Record<string, 'setup' | 'reference' | 'continuous'> = {
          setup: 'setup', reference: 'reference', continuous: 'continuous',
          段取: 'setup', 参考資料: 'reference', 連続使用: 'continuous',
        };
        const mapped = purposeMap[latest.purpose];
        if (mapped) setRepeatPurpose(mapped);
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ncId, machines.length]);

  // ── 別のnc_id向け認証セッションが残っていないか検証（MC側 edit/print/page.tsx と同ロジック）──
  // 「変更・登録」等で認証した状態のまま別画面(段取シート/NC詳細等)へ遷移した場合に、
  // 再認証なしで作業ができてしまうことを防ぐため、不一致を検知したら即座にログアウトする。
  useLayoutEffect(() => {
    if (!ncId) return;
    if (isAuthenticated && !isSessionForNc(ncId)) {
      console.warn("[NC-PRINT] 認証セッションが別のnc_id向けのため強制ログアウト", { ncId });
      logout();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ncId, isAuthenticated]);

  // -- ページ離脱時（アンマウント）に確実にセッションをクリア --
  useLayoutEffect(() => {
    return () => {
      logout();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // [v113] NC印刷画面MC同一仕様化: 新規(NEW)/リピートの区別、用途選択、透かし対応
  const isNew = nc?.status === "NEW";

  const printBody = {
    include_tools:    includeTools,
    include_clamp:    includeClamp,
    include_drawings: includeDrawings,
    ...(!isNew && repeatConfirmed ? {
      purpose:    repeatPurpose,
      quantity:   repeatPurpose !== 'reference' ? repeatQty : undefined,
      machine_id: repeatPurpose !== 'reference' ? repeatMachineId ?? undefined : undefined,
    } : {}),
  };

  const validateRepeat = (): string | null => {
    if (isNew) return null;
    if (!repeatConfirmed) return '発行前の確認を完了してください';
    if (repeatPurpose !== 'reference' && (!repeatQty || repeatQty < 1)) return 'ワーク数を入力してください';
    if (repeatPurpose !== 'reference' && !repeatMachineId) return '使用機械を選択してください';
    return null;
  };

  const handlePrint = async () => {
    // token は useAuth() から取得（localStorage は使わない）
    if (!token) {
      setPrintError("認証トークンが取得できません。再度「この作業を開始する」から認証してください。");
      return;
    }
    if (!nc) return;
    const vErr = validateRepeat();
    if (vErr) { setPrintError(vErr); return; }

    setPrinting(true);
    setPrintError(null);
    try {
      const endpoint = isNew ? `/api/nc/${ncId}/print` : `/api/nc/${ncId}/repeat-print`;
      const res = await fetch(endpoint, {
        method:  "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type":  "application/json",
        },
        body: JSON.stringify(printBody),
      });

      if (!res.ok) {
        let errMsg = `HTTP ${res.status}`;
        try { const j = await res.json(); errMsg = j.message ?? errMsg; } catch { /* ignore */ }
        throw new Error(errMsg);
      }

      const blob   = await res.blob();
      const pdfUrl = URL.createObjectURL(blob);
      window.open(pdfUrl, "_blank");

      // [v113] ブラウザプレビューは(新規・リピート問わず)作業セッションを終了しない。
      //   MC側と同一仕様: 実際にセッションを終える操作は「🖨 ダイレクト印刷」のみ。
      showToast(isNew ? "📄 プレビューを開きました（DBに記録されません）" : "📄 プレビューを開きました（発行履歴に記録されます）");
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
    const vErr = validateRepeat();
    if (vErr) { setPrintError(vErr); return; }
    setDirectPrinting(true); setPrintError(null);
    try {
      const endpoint = isNew ? `/api/nc/${ncId}/direct-print` : `/api/nc/${ncId}/repeat-direct-print`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(printBody),
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

  // [仮登録] 「作業完了（登録）」で確定するまでは段取シートに直接アクセスされても
  // ブロックする(タブの非活性化に加え、URL直打ちに対する防御)。
  if (nc.status === "PROVISIONAL") return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-10 max-w-md w-full text-center">
        <div className="text-5xl mb-4">🔒</div>
        <h2 className="text-slate-700 font-bold text-lg mb-2">段取シートはまだ利用できません</h2>
        <p className="text-slate-400 text-sm mb-6">この新規登録はまだ確定していません。「変更・登録」で「✓ 作業完了（登録）」を行うと利用できるようになります。</p>
        <button onClick={() => router.push(`/nc/${ncId}/edit`)}
          className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-xl transition-colors">
          変更・登録へ戻る
        </button>
      </div>
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
          <button onClick={() => router.push("/nc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>ダッシュボードへ
          </button>
          <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
          <span className="text-sm font-medium flex items-center gap-1.5">段取シート</span>
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

      {/* 部品情報エリア（共通コンポーネント） */}
      <NcPartHeader data={nc} />

      {/* タブナビ（MC側準拠: ブラウザタブ風） */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => router.push(`/nc/${ncId}`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>NC詳細
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/print`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
          {isAuthenticated && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse ml-0.5" />}
        </button>
        <button onClick={() => router.push(`/nc/${ncId}/record`)}
          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
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
            <div>
              {/* [v113] リピート確認ブロック(MC側と同一仕様、新規(NEW)の場合は非表示) */}
              {!isNew && (
                repeatConfirmed ? (
                  <div className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-bold text-emerald-700">✅ 発行前の確認完了</span>
                      <span className="text-slate-600">用途: <span className="font-bold">{repeatPurpose === 'setup' ? '段取' : repeatPurpose === 'reference' ? '参考資料' : '連続使用'}</span></span>
                      {repeatPurpose !== 'reference' && <span className="text-slate-600">W数: <span className="font-bold">{repeatQty}</span></span>}
                      {repeatPurpose !== 'reference' && repeatMachineId && (
                        <span className="text-slate-600">機械: <span className="font-bold">{machines.find(m => m.id === repeatMachineId)?.machineCode ?? '—'}</span></span>
                      )}
                    </div>
                    <button onClick={() => setRepeatConfirmed(false)} className="text-xs text-slate-500 underline ml-4 shrink-0">変更</button>
                  </div>
                ) : (
                  <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 space-y-3">
                    <div className="text-sm font-bold text-amber-800">⚠️ 発行前の確認</div>
                    <div>
                      <label className="text-xs font-bold text-slate-600 mb-1 block">用途</label>
                      <div className="flex gap-3 flex-wrap">
                        {([['setup','段取'],['reference','参考資料'],['continuous','連続使用']] as const).map(([val,label]) => (
                          <label key={val} className="flex items-center gap-1.5 cursor-pointer">
                            <input type="radio" name="repeatPurpose" value={val}
                              checked={repeatPurpose === val}
                              onChange={() => setRepeatPurpose(val)}
                              className="accent-amber-600" />
                            <span className="text-sm">{label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    {repeatPurpose !== 'reference' && (
                      <div>
                        <label className="text-xs font-bold text-slate-600 mb-1 block">ワーク数 <span className="text-red-500">*</span></label>
                        <input type="number" min={1} value={repeatQty}
                          onChange={e => setRepeatQty(Math.max(1, parseInt(e.target.value) || 1))}
                          className="w-24 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-amber-400" />
                      </div>
                    )}
                    {repeatPurpose !== 'reference' && (
                      <div>
                        <label className="text-xs font-bold text-slate-600 mb-1 block">使用機械 <span className="text-red-500">*</span></label>
                        <select value={repeatMachineId ?? ""} onChange={e => setRepeatMachineId(e.target.value ? Number(e.target.value) : null)}
                          className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400">
                          <option value="">選択してください</option>
                          {machines.map(m => <option key={m.id} value={m.id}>{m.machineCode}</option>)}
                        </select>
                      </div>
                    )}
                    <div className="flex justify-end">
                      <button
                        onClick={() => {
                          if (repeatPurpose !== 'reference' && (!repeatQty || repeatQty < 1)) { setPrintError('ワーク数を入力してください'); return; }
                          if (repeatPurpose !== 'reference' && !repeatMachineId) { setPrintError('使用機械を選択してください'); return; }
                          setPrintError(null);
                          setRepeatConfirmed(true);
                        }}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-lg transition-colors"
                      >確認完了</button>
                    </div>
                  </div>
                )
              )}

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
                      : <><span>📄</span> {isNew ? "プレビュー（透かし入り・記録なし）" : "PDFプレビュー（ブラウザで開く）"}</>
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
                  <p>• プレビューはPDFが新しいタブで開きます{isNew ? "（透かし入り・DB記録なし）" : "（発行履歴に記録されます）"}</p>
                  <p>• 「ダイレクト印刷」がプリンタへの実送信で、作業セッションを終了します</p>
                </div>
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

      {/* 掴代 */}
      {showClamp && nc.clampAllowance && (
        <div>
          <p className="text-xs font-bold text-slate-500 mb-1">掴代</p>
          <p className="text-xs text-slate-700 bg-sky-50 border border-sky-200 rounded-lg p-3 font-mono">
            {nc.clampAllowance} mm
          </p>
        </div>
      )}

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