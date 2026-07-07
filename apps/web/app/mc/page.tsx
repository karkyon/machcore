"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";
import { useRouter } from "next/navigation";
import { toJstMonthDayTimeString, toJstTimeString } from "@/lib/dateUtils";

const API_URL = "/api";  // Next.js rewrite経由 → サーバー側でlocalhost:3011にproxy

type McSheet = {
  id: number; mc_id: number;
  legacy_mcid: number | null; machining_id: number;
  part_id: string; drawing_no: string; part_name: string;
  client_name: string | null; main_model: string | null;
  mc_process_no: number | null;
  machine_code: string | null; machine_name: string | null; machine_sort: number;
  version: string | null; printed_at: string; operator_name: string;
  sheet_type?: string | null; is_reference?: boolean;
};
type Summary = {
  nc_total: number; mc_total: number;
  nc_pending: number; mc_pending: number;
  nc_uncollected: number; mc_uncollected: number;
};
type Period = "week" | "twoweeks" | "all";

function ageDays(iso: string) { return (Date.now() - new Date(iso).getTime()) / 86400000; }
function rowCls(iso: string) {
  const d = ageDays(iso);
  if (d > 14) return "border-l-4 border-l-red-400 bg-red-50 hover:bg-red-100";
  if (d > 7)  return "border-l-4 border-l-blue-400 bg-blue-50 hover:bg-blue-100";
  return "hover:bg-slate-50";
}
function ageCls(iso: string) {
  const d = ageDays(iso);
  if (d > 14) return "text-red-600 font-bold";
  if (d > 7)  return "text-blue-600 font-bold";
  return "text-amber-600";
}
function elapsed(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000), m = Math.floor((diff % 3600000) / 60000);
  if (h >= 24) return Math.floor(h/24) + "日前";
  if (h > 0)   return h + "時間" + m + "分前";
  return m + "分前";
}
function fmtDt(iso: string) {
  return toJstMonthDayTimeString(iso) ?? iso;
}
function groupByMachine(items: McSheet[]) {
  const map = new Map<string, McSheet[]>();
  for (const item of items) {
    const key = item.machine_code ?? "未設定";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}
function filterPeriod(items: McSheet[], p: Period) {
  if (p === "all") return items;
  return items.filter(i => ageDays(i.printed_at) <= (p === "week" ? 7 : 14));
}

export default function McDashboard() {
  const router = useRouter();
  const { token: authToken } = useAuth();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [sheets,  setSheets]  = useState<McSheet[]>([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastAt,  setLastAt]  = useState<Date | null>(null);
  const [period,  setPeriod]  = useState<Period>("week");

  const [sbMcId,          setSbMcId]          = useState("");
  const [sbResult,        setSbResult]        = useState<any | null>(null);
  const [sbLoading,       setSbLoading]       = useState(false);
  const [sbError,         setSbError]         = useState<string | null>(null);
  const [sbModalOpen,     setSbModalOpen]     = useState(false);
  const [sbSelectedSheet, setSbSelectedSheet] = useState<any | null>(null);
  const [sbAuthOpen,      setSbAuthOpen]      = useState(false);
  const [sbCollecting,    setSbCollecting]    = useState(false);
  const [sbStep1AuthOpen, setSbStep1AuthOpen] = useState(false);
  const [sbStep1McId,     setSbStep1McId]     = useState<number>(0);
  const [sbRepeatAuthOpen, setSbRepeatAuthOpen] = useState(false);
  const [sbRepeatMcId,     setSbRepeatMcId]     = useState<number>(0);
  const [newRegModalOpen,  setNewRegModalOpen]  = useState(false);
  const [lostModalSheet,   setLostModalSheet]   = useState<any | null>(null);
  const [lostReason,       setLostReason]       = useState("紛失");
  const [lostDetail,       setLostDetail]       = useState("");
  const [lostSubmitting,   setLostSubmitting]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([
        fetch(API_URL + "/dashboard/summary").then(r => r.json()),
        fetch(API_URL + "/dashboard/uncollected-mc").then(r => r.json()),
      ]);
      setSummary(s);
      setSheets(u.items ?? []);
      setTotal(u.total ?? 0);
      setLastAt(new Date());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  // ── 段取シートを行方不明として処理 ──
  const handleMarkLost = async () => {
    if (!lostModalSheet) return;
    setLostSubmitting(true);
    try {
      await fetch(`${API_URL}/dashboard/mc-setup-sheet-logs/${lostModalSheet.id}/mark-lost`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: lostReason, detail: lostDetail || undefined }),
      });
      setLostModalSheet(null);
      setLostDetail("");
      setLostReason("紛失");
      setSbModalOpen(false);
      load();
    } catch { /* ignore */ }
    finally { setLostSubmitting(false); }
  };

  // ── ダッシュボード行クリック: そのシートを選択済みでモーダルを開く ──
  const handleSheetRowClick = async (item: McSheet) => {
    const legacyId = item.legacy_mcid ?? "—";
    setSbMcId(String(legacyId));
    setSbLoading(true); setSbError(null); setSbResult(null); setSbSelectedSheet(null);
    try {
      const res = await fetch(`/api/mc/uncollected-by-legacy/${legacyId}`);
      const data = await res.json();
      if (!data.found || data.sheets.length === 0) {
        setSbError("未回収の段取シートが見つかりません");
        setSbLoading(false);
        return;
      }
      setSbResult(data);
      // クリックした行の sheet log id と一致するシートを初期選択
      const target = data.sheets.find((s: any) => s.id === item.id) ?? data.sheets[0];
      setSbSelectedSheet(target);
      setSbModalOpen(true);
    } catch {
      setSbError("取得に失敗しました");
    } finally {
      setSbLoading(false);
    }
  };

  const filtered = filterPeriod(sheets, period);
  const grouped  = groupByMachine(filtered);

  const LostReasonModal = lostModalSheet ? (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <h3 className="text-base font-bold text-red-700 mb-1">⚠ 行方不明として処理</h3>
        <p className="text-xs text-slate-500 mb-4">この段取シートを未回収一覧から除外します(削除ではなく理由付きで記録されます)。</p>
        <label className="block text-xs font-bold text-slate-600 mb-1">理由</label>
        <select value={lostReason} onChange={e => setLostReason(e.target.value)}
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-3">
          {["紛失", "作業者未回収のまま長期経過", "その他"].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <label className="block text-xs font-bold text-slate-600 mb-1">詳細(任意)</label>
        <textarea value={lostDetail} onChange={e => setLostDetail(e.target.value)} rows={3}
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-4" placeholder="詳細な状況があれば入力してください" />
        <div className="flex gap-2 justify-end">
          <button onClick={() => setLostModalSheet(null)} className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-bold rounded-lg hover:bg-slate-200">キャンセル</button>
          <button onClick={handleMarkLost} disabled={lostSubmitting}
            className="px-4 py-2 bg-red-600 text-white text-sm font-bold rounded-lg hover:bg-red-700 disabled:opacity-50">
            {lostSubmitting ? "処理中..." : "行方不明として記録"}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  const handleSbSearch = async () => {
    const legacyId = parseInt(sbMcId);
    if (!legacyId) { setSbError("MCIDを入力してください"); return; }
    setSbLoading(true); setSbError(null); setSbResult(null); setSbSelectedSheet(null);
    try {
      const res = await fetch(`${API_URL}/mc/uncollected-by-legacy/${legacyId}`);
      const data = await res.json();
      if (!data.found) { setSbError("MCIDが見つかりません"); }
      else if (data.sheets.length === 0) { setSbError("未回収の段取シートはありません"); setSbResult(data); }
      else { setSbResult(data); setSbModalOpen(true); }
    } catch { setSbError("取得に失敗しました"); }
    finally { setSbLoading(false); }
  };

  const handleSbAuthSuccess = async () => {
    setSbAuthOpen(false);
    if (!sbSelectedSheet) return;
    // sb_next_record + sb_sheet_log_id をセット → record側でcollect処理する
    if (typeof window !== "undefined") {
      sessionStorage.setItem("sb_next_record", String(sbSelectedSheet.mc_id));
      sessionStorage.setItem("sb_sheet_log_id", String(sbSelectedSheet.id));
    }
    router.push(`/mc/${sbSelectedSheet.mc_id}/record`);
    return;
    // ── 以下は旧collect処理（無効化）──
    setSbCollecting(true);
    const tok = authToken ?? (typeof window !== "undefined" ? localStorage.getItem("work_token") : null);
    try {
      await fetch(
        `${API_URL}/mc/${sbSelectedSheet.mc_id}/setup-sheet-logs/${sbSelectedSheet.id}/collect`,
        { method: "PUT", headers: tok ? { Authorization: `Bearer ${tok}` } : {} }
      );
      setSbResult(null); setSbSelectedSheet(null); setSbMcId(""); setSbModalOpen(false); setSbError(null);
      load();
    } catch { setSbError("回収処理に失敗しました"); }
    finally { setSbCollecting(false); }
  };

  return (
    <>
      {LostReasonModal}
      {/* 段取シートバック 選択モーダル */}
      {sbModalOpen && sbResult?.found && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="bg-slate-800 px-6 py-4 shrink-0">
              <h2 className="text-white font-bold text-lg">段取シートバック</h2>
              <p className="text-slate-400 text-xs mt-1">MCID: {sbMcId} — 未回収シートを選択してください</p>
            </div>
            <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 shrink-0">
              {sbResult.programs.map((prog: any) => (
                <div key={prog.mc_id} className="flex items-center gap-3 flex-wrap">
                  <span className="font-bold text-slate-800 text-sm">{prog.drawing_no}</span>
                  <span className="text-slate-600 text-sm">{prog.part_name}</span>
                  {prog.mc_process_no && (
                    <span className="text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded font-bold">P{prog.mc_process_no}</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded font-bold ${(sbSelectedSheet?.sheet_type ?? prog.sheet_type) === "NEW" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>
                    {(sbSelectedSheet?.sheet_type ?? prog.sheet_type) === "NEW" ? "新規" : "リピート"}
                  </span>
                </div>
              ))}
            </div>
            <div className="overflow-y-auto flex-1 p-4">
              <p className="text-xs font-bold text-slate-500 mb-3">未回収シート一覧 — 回収作業を行うシートを選択</p>
              <div className="space-y-2">
                {sbResult.sheets.map((sheet: any) => {
                  const prog = sbResult.programs.find((p: any) => p.mc_id === sheet.mc_id);
                  const isSel = sbSelectedSheet?.id === sheet.id;
                  return (
                    <button
                      key={"btn-" + sheet.id}
                      onClick={() => setSbSelectedSheet(isSel ? null : sheet)}
                      className={`w-full text-left rounded-xl border-2 px-4 py-3 transition-all ${isSel ? "border-teal-500 bg-teal-50" : "border-slate-200 bg-white hover:border-teal-300 hover:bg-teal-50/40"}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${isSel ? "border-teal-500 bg-teal-500" : "border-slate-300"}`}>
                          {isSel && <span className="text-white text-xs font-bold">✓</span>}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-bold text-slate-700">発行No. {sheet.id}</span>
                            {prog && (
                              <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${(sbSelectedSheet?.sheet_type ?? prog.sheet_type) === "NEW" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>
                                {(sbSelectedSheet?.sheet_type ?? prog.sheet_type) === "NEW" ? "新規" : "リピート"}
                              </span>
                            )}
                            {sheet.version && <span className="font-mono text-xs text-teal-600">v{sheet.version}</span>}
                          </div>
                          <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-3">
                            <span>発行日時: {toJstMonthDayTimeString(sheet.printed_at)}</span>
                            {sheet.operator_name && <span>発行者: {sheet.operator_name}</span>}
                          </div>
                        </div>
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            if (!sheet.has_pdf) {
                              alert(`発行No.${sheet.id} の原本PDFは保存されていません\nこの発行はシステム移行前のデータのため原本ファイルがありません`);
                              return;
                            }
                            window.open(`/api/mc/setup-sheet-logs/${sheet.id}/pdf`, '_blank');
                          }}
                          className={`shrink-0 px-2.5 py-1 text-[10px] font-bold rounded border transition-colors whitespace-nowrap ${sheet.has_pdf ? "bg-teal-50 hover:bg-teal-100 text-teal-700 border-teal-300" : "bg-slate-100 text-slate-400 border-slate-200 cursor-default"}`}
                          title={sheet.has_pdf ? "発行原本PDFを別タブで表示" : "原本PDFは保存されていません（移行前データ）"}
                        >
                          📄 原本確認
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); setLostModalSheet(sheet); }}
                          className="shrink-0 px-2 py-1 text-[10px] font-bold rounded border bg-red-50 hover:bg-red-100 text-red-600 border-red-200 transition-colors"
                          title="行方不明にする"
                        >
                          🗑️
                        </button>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
            {sbSelectedSheet && (() => {
              const prog = sbResult.programs.find((p: any) => p.mc_id === sbSelectedSheet.mc_id);
              const isNew = prog?.sheet_type === "NEW";
              return (
                <div className="border-t border-slate-200 px-6 py-4 bg-slate-50 shrink-0">
                  <p className="text-xs font-bold text-slate-500 mb-3">発行No.{sbSelectedSheet.id} を選択中 — 次の作業を選択してください</p>
                  <div className="space-y-2">
                    {isNew ? (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-1">
                          <p className="text-xs font-bold text-blue-700 mb-1">新規シート — 必須作業フロー</p>
                          <div className="flex items-center gap-2 text-xs text-blue-600">
                            <span className="bg-blue-600 text-white rounded-full w-4 h-4 flex items-center justify-center font-bold shrink-0">1</span>
                            <span>マシニング情報を登録</span>
                            <span className="text-blue-400">→</span>
                            <span className="bg-teal-600 text-white rounded-full w-4 h-4 flex items-center justify-center font-bold shrink-0">2</span>
                            <span>作業記録を入力</span>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            setSbStep1McId(sbSelectedSheet.mc_id);
                            setSbModalOpen(false);
                            setSbStep1AuthOpen(true);
                          }}
                          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors">
                          STEP 1: マシニング情報を登録（新規）— 担当者認証へ
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => { setSbRepeatMcId(sbSelectedSheet.mc_id); setSbModalOpen(false); setSbRepeatAuthOpen(true); }}
                          className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-bold rounded-xl transition-colors">
                          マシニング情報を確認・編集（リピート）
                        </button>
                        <button
                          onClick={() => { setSbModalOpen(false); setSbAuthOpen(true); }}
                          className="w-full py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-xl transition-colors">
                          作業記録を入力
                        </button>
                      </>
                    )}

                  </div>
                </div>
              );
            })()}
            <div className="px-6 py-3 border-t border-slate-100 flex justify-end shrink-0">
              <button
                onClick={() => { setSbModalOpen(false); setSbSelectedSheet(null); }}
                className="px-5 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50">
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP1認証モーダル */}
      {sbStep1AuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="edit"
          mcProgramId={sbStep1McId}
          onSuccess={() => {
            setSbStep1AuthOpen(false);
            if (typeof window !== "undefined") {
              sessionStorage.setItem("sb_next_record", String(sbStep1McId));
              // sbSelectedSheet.id (log_id) を保存 — STEP2完了時のcollect用
              const sheetId = sbSelectedSheet?.id ?? 0;
              sessionStorage.setItem("sb_sheet_log_id", String(sheetId));
            }
            router.push(`/mc/${sbStep1McId}/edit`);
          }}
          onCancel={() => setSbStep1AuthOpen(false)}
        />
      )}

      {/* リピート編集認証モーダル */}
      {sbRepeatAuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="edit"
          mcProgramId={sbRepeatMcId}
          onSuccess={() => {
            setSbRepeatAuthOpen(false);
            if (typeof window !== "undefined") {
              sessionStorage.setItem("sb_repeat_edit", String(sbRepeatMcId));
              const sheetId = sbSelectedSheet?.id ?? 0;
              sessionStorage.setItem("sb_sheet_log_id", String(sheetId));
            }
            router.push(`/mc/${sbRepeatMcId}/edit`);
          }}
          onCancel={() => setSbRepeatAuthOpen(false)}
        />
      )}

      {/* 認証モーダル */}
      {sbAuthOpen && (
        <AuthModal
          isOpen={true}
          sessionType="work_record"
          system="MC"
          mcProgramId={sbSelectedSheet?.mc_id ?? sbResult?.programs?.[0]?.mc_id ?? 0}
          onSuccess={handleSbAuthSuccess}
          onCancel={() => setSbAuthOpen(false)}
        />
      )}

      {/* 新規登録 選択モーダル */}
      {newRegModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h2 className="text-base font-bold text-slate-800 mb-1">登録方法を選択</h2>
            <p className="text-xs text-slate-400 mb-5">新しい加工として登録するか、既存の加工データを流用するかを選択してください</p>
            <div className="space-y-3">
              <button
                onClick={() => { setNewRegModalOpen(false); router.push("/mc/new"); }}
                className="w-full flex items-start gap-4 p-4 border-2 border-teal-200 bg-teal-50 rounded-xl hover:border-teal-400 hover:bg-teal-100 transition-colors text-left">
                <span className="text-2xl shrink-0">✅</span>
                <div>
                  <div className="font-bold text-teal-700 text-sm">仮登録（新規）</div>
                  <div className="text-xs text-slate-500 mt-0.5">新しい加工IDを採番して登録します</div>
                </div>
              </button>
              <button
                onClick={() => { setNewRegModalOpen(false); router.push("/mc/new/common"); }}
                className="w-full flex items-start gap-4 p-4 border-2 border-violet-200 bg-violet-50 rounded-xl hover:border-violet-400 hover:bg-violet-100 transition-colors text-left">
                <span className="text-2xl shrink-0">📋</span>
                <div>
                  <div className="font-bold text-violet-700 text-sm">共通加工として登録</div>
                  <div className="text-xs text-slate-500 mt-0.5">既存の加工データを別の部品で供用使用し登録します</div>
                </div>
              </button>
            </div>
            <button onClick={() => setNewRegModalOpen(false)}
              className="mt-4 w-full py-2 text-xs text-slate-400 hover:text-slate-600">
              キャンセル
            </button>
          </div>
        </div>
      )}

      {/* エラートースト */}
      {sbError && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-600 text-white text-sm px-4 py-2 rounded-lg shadow-lg flex items-center gap-3">
          {sbError}
          <button onClick={() => setSbError(null)} className="text-red-200 hover:text-white">✕</button>
        </div>
      )}

      <div className="h-screen flex flex-col bg-slate-50">
        <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
          <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
          <span className="text-slate-400 text-xs">|</span>
          <span className="text-sm font-medium">MC マシニング ダッシュボード</span>
          <div className="ml-auto flex items-center gap-2 text-xs">
            
            {lastAt && <span className="text-slate-400">更新: {toJstTimeString(lastAt)}</span>}
            <button onClick={load} className="bg-slate-700 hover:bg-slate-600 px-2.5 py-1.5 rounded transition-colors text-slate-300">
              ↺ 更新
            </button>
          </div>
        </header>

        <div className="flex flex-1 min-h-0">
          <aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
            <div className="py-2 border-b border-slate-100">
              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">MC マシニング</div>
              <button onClick={() => router.push("/mc/search")}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-teal-50 hover:text-teal-700">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                部品検索
              </button>
              <button onClick={() => setNewRegModalOpen(true)}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-teal-50 hover:text-teal-700">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
                新規登録
              </button>
            </div>
            <div className="py-2 border-b border-slate-100">
              <div className="px-4 pb-1.5 pt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">管理</div>
              <button onClick={() => router.push("/admin/login")}
                className="mx-2 w-[calc(100%-16px)] px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors text-slate-600 hover:bg-slate-100 hover:text-slate-900">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
                管理パネル
              </button>
            </div>
                        {/* 段取シートバック パネル */}
            <div className="mx-3 mb-3 mt-0 shrink-0">
              <div className="bg-teal-50 border border-teal-200 rounded-lg p-3">
                <p className="text-[10px] font-bold text-teal-700 mb-2">段取シートバック</p>
                <input
                  type="number"
                  value={sbMcId}
                  onChange={e => { setSbMcId(e.target.value); setSbResult(null); setSbError(null); }}
                  onKeyDown={e => e.key === "Enter" && handleSbSearch()}
                  placeholder="MCID"
                  className="w-full border border-teal-300 rounded px-2 py-1.5 text-base font-bold focus:outline-none focus:ring-1 focus:ring-teal-400 bg-white"
                />
                <button
                  onClick={handleSbSearch}
                  disabled={sbLoading}
                  className="mt-1.5 w-full py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-40">
                  {sbLoading ? "検索中..." : "検索"}
                </button>
                {sbError && <p className="text-[10px] text-red-600 mt-1">{sbError}</p>}
                {sbResult?.found && sbResult.sheets.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-teal-700 font-bold">未回収: {sbResult.sheets.length}件</p>
                    <button
                      onClick={() => setSbModalOpen(true)}
                      className="mt-1 w-full py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold rounded">
                      一覧を確認・選択
                    </button>
                  </div>
                )}
              </div>
              {total > 0 && (
                <div className="mt-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  <p className="text-[10px] text-amber-700 font-bold">未回収 {total}枚</p>
                  <p className="text-[10px] text-amber-500 mt-0.5">表示中: {filtered.length}枚</p>
                </div>
              )}
            </div>
          </aside>

          <main className="flex-1 overflow-y-auto p-5 space-y-5">
            <section>
              <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">MC システム状況</h2>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "MC 登録数",    value: summary?.mc_total,        cls: "text-teal-600",    bg: "bg-teal-50",    border: "border-teal-200" },
                  { label: "MC 未承認",    value: summary?.mc_pending,      cls: summary?.mc_pending     ? "text-yellow-600" : "text-slate-400", bg: "bg-white",       border: "border-slate-200" },
                  { label: "未回収シート", value: summary?.mc_uncollected,  cls: summary?.mc_uncollected ? "text-red-600"    : "text-emerald-600", bg: summary?.mc_uncollected ? "bg-red-50" : "bg-emerald-50", border: summary?.mc_uncollected ? "border-red-200" : "border-emerald-200" },
                ].map(c => (
                  <div key={c.label} className={"rounded-xl px-4 py-3 border " + c.bg + " " + c.border}>
                    <div className="text-[10px] text-slate-400 mb-1">{c.label}</div>
                    <div className={"text-2xl font-bold " + c.cls}>{loading ? "..." : (c.value ?? 0).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">現在発行中の段取シート（MC）</h2>
                  <span className="text-[10px] bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-bold">全 {total} 枚</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-3 text-[10px] text-slate-500">
                    <span className="flex items-center gap-1"><span className="w-3 h-2 border-l-2 border-l-slate-300 bg-white inline-block"/>7日以内</span>
                    <span className="flex items-center gap-1 text-blue-600"><span className="w-3 h-2 border-l-2 border-l-blue-400 bg-blue-50 inline-block"/>7〜14日</span>
                    <span className="flex items-center gap-1 text-red-600"><span className="w-3 h-2 border-l-2 border-l-red-400 bg-red-50 inline-block"/>14日超</span>
                  </div>
                  <div className="flex items-center gap-0.5 bg-white border border-slate-200 rounded-lg p-0.5">
                    {([["week","直近1週間"],["twoweeks","直近2週間"],["all","すべて"]] as const).map(([k,l]) => (
                      <button key={k} onClick={() => setPeriod(k)}
                        className={"px-2.5 py-1 rounded text-xs font-bold transition-colors " + (period===k ? "bg-slate-700 text-white" : "text-slate-500 hover:bg-slate-100")}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {loading ? (
                <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">読み込み中...</div>
              ) : filtered.length === 0 ? (
                <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                  <div className="text-3xl mb-2">✅</div>
                  <p className="text-emerald-600 font-bold text-sm">{total === 0 ? "未回収シートはありません" : "この期間の未回収シートはありません"}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {Array.from(grouped.entries()).map(([mc, items]) => (
                    <div key={mc} className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                      <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-amber-400"/>
                        <span className="font-mono font-bold text-sm text-slate-800">{mc}</span>
                        <span className="text-slate-500 text-xs">{items[0]?.machine_name ?? ""}</span>
                        <span className="ml-auto text-xs text-amber-700 font-bold bg-amber-100 px-2 py-0.5 rounded-full">{items.length}枚</span>
                      </div>
                      <div className="grid grid-cols-[56px_70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-1.5 bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase">
                        <span>種別</span><span>MCID</span><span>加工ID</span><span>部品ID</span><span>工程</span><span>図番 / 部品名 / 納入先</span><span>印刷日時</span><span>印刷者</span><span>経過</span><span/>
                      </div>
                      <div className="divide-y divide-slate-100">
                        {items.map(item => (
                          <button key={item.id}
                            onClick={() => handleSheetRowClick(item)}
                            className={"w-full grid grid-cols-[56px_70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-2.5 items-center text-left transition-colors " + rowCls(item.printed_at)}>
                            <span>
                              {item.is_reference
                                ? <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-200 text-gray-600">参考</span>
                                : item.sheet_type === "NEW"
                                  ? <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">新規</span>
                                  : <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">リピート</span>
                              }
                            </span>
                            <span className="font-mono text-xs text-slate-700">{item.legacy_mcid ?? "-"}</span>
                            <span className="font-mono text-xs text-slate-700">{item.machining_id}</span>
                            <span className="font-mono text-xs text-slate-800">{item.part_id}</span>
                            <span className="text-xs">
                              {item.mc_process_no != null
                                ? <span className="bg-teal-100 text-teal-700 font-bold px-1.5 py-0.5 rounded font-mono">P{item.mc_process_no}</span>
                                : <span className="text-slate-300">-</span>}
                              {item.version && <span className="ml-1 text-slate-400 text-[10px]">v{item.version}</span>}
                            </span>
                            <span className="min-w-0">
                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>
                              <span className="text-slate-800 text-xs ml-2">{item.part_name}</span>
                              {item.client_name && <span className="text-slate-400 text-[10px] ml-2">/ {item.client_name}</span>}
                            </span>
                            <span className="text-[11px] text-slate-500 whitespace-nowrap">{fmtDt(item.printed_at)}</span>
                            <span className="text-xs text-slate-700">{item.operator_name}</span>
                            <span className={"text-xs whitespace-nowrap " + ageCls(item.printed_at)}>{elapsed(item.printed_at)}</span>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300"><path d="M9 18l6-6-6-6"/></svg>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </main>
        </div>
      </div>
    </>
  );
}
