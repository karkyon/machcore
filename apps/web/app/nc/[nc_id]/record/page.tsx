"use client";
// apps/web/app/nc/[nc_id]/record/page.tsx
// SCR-05: 作業記録画面  v2 – ?edit=id 対応・2ペイン・更新/削除

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ncApi, workRecordsApi, machinesApi,
  type WorkRecord, type Machine, type NcDetail,
  type CreateWorkRecordBody, type UpdateWorkRecordBody,
} from "@/lib/api";

const WORK_TYPES = ["量産", "試作", "変更", "新規登録"] as const;

// ── ユーティリティ ────────────────────────────────────────────────
function toHM(totalMin: number | null): [number, number] {
  if (!totalMin) return [0, 0];
  return [Math.floor(totalMin / 60), totalMin % 60];
}
function toMS(totalSec: number | null): [number, number] {
  if (!totalSec) return [0, 0];
  return [Math.floor(totalSec / 60), totalSec % 60];
}
function fmtMin(min: number | null) {
  if (min == null) return "—";
  const [h, m] = toHM(min);
  return h > 0 ? `${h}h${m}m` : `${m}分`;
}
function fmtSec(sec: number | null) {
  if (sec == null) return "—";
  const [m, s] = toMS(sec);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}
function fmtDate(s: string) {
  return new Date(s).toLocaleString("ja-JP", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── 数値入力コンポーネント ────────────────────────────────────────
function NumInput({ value, onChange, min = 0, max, className = "" }: {
  value: number; onChange: (v: number) => void;
  min?: number; max?: number; className?: string;
}) {
  return (
    <input
      type="number" min={min} max={max} value={value}
      onChange={e => {
        const v = parseInt(e.target.value) || 0;
        onChange(max !== undefined ? Math.min(v, max) : v);
      }}
      className={`border border-slate-300 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-sky-300 ${className}`}
    />
  );
}

function TimeInput({ h, m, onH, onM }: {
  h: number; m: number; onH: (v: number) => void; onM: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <NumInput value={h} onChange={onH} min={0} className="w-16" />
      <span className="text-xs text-slate-400">h</span>
      <NumInput value={m} onChange={onM} min={0} max={59} className="w-16" />
      <span className="text-xs text-slate-400">m</span>
    </div>
  );
}

// ── 認証モーダル ──────────────────────────────────────────────────
function AuthModal({ ncId, sessionType, onSuccess, onCancel }: {
  ncId: number; sessionType: string;
  onSuccess: (opName: string) => void; onCancel: () => void;
}) {
  const [users,    setUsers]    = useState<{ id: number; name: string }[]>([]);
  const [selId,    setSelId]    = useState<number | null>(null);
  const [selName,  setSelName]  = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/users`)
      .then(r => r.json()).then(setUsers);
  }, []);

  const handleSubmit = async () => {
    if (!selId || !password) { setError("担当者とパスワードを入力してください"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/work-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator_id: selId, password, session_type: sessionType, nc_program_id: ncId }),
      });
      const data = await res.json();
      if (!res.ok) { setError("パスワードが違います"); setPassword(""); return; }
      localStorage.setItem("work_token", data.access_token);
      onSuccess(selName);
    } catch { setError("通信エラーが発生しました"); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="bg-slate-800 text-white px-5 py-4">
          <h2 className="font-bold text-base">⏱ 作業記録 — 担当者認証</h2>
          <p className="text-xs text-slate-400 mt-0.5">担当者を選択してパスワードを入力してください</p>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            {users.map(u => (
              <button key={u.id}
                onClick={() => { setSelId(u.id); setSelName(u.name); setPassword(""); }}
                className={`py-2 px-2 rounded-lg text-sm font-medium border transition-colors ${
                  selId === u.id
                    ? "bg-sky-600 border-sky-600 text-white"
                    : "bg-slate-50 border-slate-200 text-slate-700 hover:border-sky-400"
                }`}
              >{u.name}</button>
            ))}
          </div>
          {selId && (
            <div className="space-y-1">
              <label className="text-xs text-slate-500 font-medium">パスワード</label>
              <input type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                autoFocus
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300"
                placeholder="パスワードを入力"
              />
            </div>
          )}
          {error && <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button onClick={handleSubmit}
              disabled={!selId || !password || loading}
              className="flex-1 bg-sky-600 hover:bg-sky-700 disabled:bg-sky-300 text-white font-bold py-2.5 rounded-lg text-sm transition-colors"
            >{loading ? "確認中…" : "確認してこの作業を開始する"}</button>
            <button onClick={onCancel}
              className="px-4 py-2.5 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >キャンセル</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── メインコンポーネント（useSearchParams を使うため Suspense でラップ） ──
function RecordPageInner() {
  const { nc_id }    = useParams<{ nc_id: string }>();
  const ncId         = parseInt(nc_id);
  const router       = useRouter();
  const searchParams = useSearchParams();

  const [nc,           setNc]           = useState<NcDetail | null>(null);
  const [machines,     setMachines]     = useState<Machine[]>([]);
  const [allRecords,   setAllRecords]   = useState<WorkRecord[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showAuthModal,   setShowAuthModal]   = useState(false);
  const [saving,       setSaving]       = useState(false);
  const [deleting,     setDeleting]     = useState(false);
  const [toast,        setToast]        = useState<string | null>(null);
  const [sessionInfo,  setSessionInfo]  = useState<{ operatorName: string } | null>(null);

  // 編集モード
  const [editMode,      setEditMode]      = useState(false);
  const [editRecordId,  setEditRecordId]  = useState<number | null>(null);

  // 経過タイマー
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // フォーム値
  const [setupH,       setSetupH]       = useState(0);
  const [setupM,       setSetupM]       = useState(0);
  const [machH,        setMachH]        = useState(0);
  const [machM,        setMachM]        = useState(0);
  const [cycleM,       setCycleM]       = useState(0);
  const [cycleS,       setCycleS]       = useState(0);
  const [quantity,     setQuantity]     = useState<number | "">("");
  const [interruption, setInterruption] = useState(0);
  const [workType,     setWorkType]     = useState<string>("量産");
  const [note,         setNote]         = useState("");
  const [machineId,    setMachineId]    = useState<number | null>(null);

  // ── フォームリセット ──
  const resetForm = useCallback((nc: NcDetail | null) => {
    setEditMode(false);
    setEditRecordId(null);
    setSetupH(0); setSetupM(0);
    setMachH(0);  setMachM(0);
    if (nc?.machiningTime) { setCycleM(nc.machiningTime); setCycleS(0); }
    else { setCycleM(0); setCycleS(0); }
    setQuantity("");
    setInterruption(0);
    setWorkType("量産");
    setNote("");
    setMachineId(nc?.machineId ?? null);
  }, []);

  // ── レコードをフォームにロード（編集モード） ──
  const loadRecord = useCallback((r: WorkRecord) => {
    const [sh, sm] = toHM(r.setup_time);
    const [mh, mm] = toHM(r.machining_time);
    const [cm, cs] = toMS(r.cycle_time_sec);
    setSetupH(sh); setSetupM(sm);
    setMachH(mh);  setMachM(mm);
    setCycleM(cm); setCycleS(cs);
    setQuantity(r.quantity ?? "");
    setInterruption(r.interruption_time_min ?? 0);
    setWorkType(r.work_type ?? "量産");
    setNote(r.note ?? "");
    // machine_code から machineId は直接持っていないため、
    // allRecords / nc.machineId から解決は困難 → 既存値を維持
    setEditMode(true);
    setEditRecordId(r.id);
  }, []);

  // ── 初期データ取得 ──
  useEffect(() => {
    Promise.all([
      ncApi.findOne(ncId),
      machinesApi.list(),
      workRecordsApi.list(ncId),
    ]).then(([ncRes, machRes, recRes]) => {
      const d = ncRes.data as NcDetail;
      setNc(d);
      setMachines(machRes.data.filter((m: Machine) => m.isActive));
      setAllRecords(recRes.data);
      setMachineId(d.machineId ?? null);
      if (d.machiningTime) { setCycleM(d.machiningTime); setCycleS(0); }

      // ?edit=id が指定されていれば編集モードで開く
      const editId = searchParams.get("edit");
      if (editId) {
        const target = (recRes.data as WorkRecord[]).find(r => r.id === parseInt(editId));
        if (target) loadRecord(target);
      }
    });
  }, [ncId, searchParams, loadRecord]);

  // ── タイマー ──
  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const fmtElapsed = (sec: number) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"00")}:${String(s).padStart(2,"00")}`;
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleAuthSuccess = useCallback((opName: string) => {
    setIsAuthenticated(true);
    setShowAuthModal(false);
    setSessionInfo({ operatorName: opName });
  }, []);

  const endSession = async () => {
    try {
      const token = localStorage.getItem("work_token");
      if (token) {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/work-session`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch (_) {}
    localStorage.removeItem("work_token");
  };

  const handleCancel = async () => {
    if (!confirm("キャンセルしますか？入力内容は保存されません。")) return;
    await endSession();
    router.push(`/nc/${ncId}`);
  };

  // ── WR-02: 新規登録 ──
  const handleSubmit = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("work_token");
      const body: CreateWorkRecordBody = {
        setup_time_min:        (setupH * 60 + setupM) || undefined,
        machining_time_min:    (machH  * 60 + machM)  || undefined,
        cycle_time_sec:        (cycleM * 60 + cycleS) || undefined,
        quantity:              quantity !== "" ? Number(quantity) : undefined,
        interruption_time_min: interruption || undefined,
        work_type:             workType,
        note:                  note || undefined,
        machine_id:            machineId ?? undefined,
      };
      const res = await workRecordsApi.create(ncId, body);
      if (!res.data?.id) throw new Error("登録失敗");
      await endSession();
      showToast("✅ 作業記録を登録しました");
      setTimeout(() => router.push(`/nc/${ncId}`), 1200);
    } catch {
      showToast("❌ 登録に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  // ── WR-03: 更新 ──
  const handleUpdate = async () => {
    if (saving || !editRecordId) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("work_token");
      const body: UpdateWorkRecordBody = {
        setup_time_min:        (setupH * 60 + setupM) || undefined,
        machining_time_min:    (machH  * 60 + machM)  || undefined,
        cycle_time_sec:        (cycleM * 60 + cycleS) || undefined,
        quantity:              quantity !== "" ? Number(quantity) : undefined,
        interruption_time_min: interruption || undefined,
        work_type:             workType,
        note:                  note || undefined,
        machine_id:            machineId ?? undefined,
      };
      await workRecordsApi.update(ncId, editRecordId, body);
      // 一覧を再取得
      const recRes = await workRecordsApi.list(ncId);
      setAllRecords(recRes.data);
      await endSession();
      showToast("✅ 作業記録を更新しました");
      setTimeout(() => router.push(`/nc/${ncId}`), 1200);
    } catch {
      showToast("❌ 更新に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  // ── WR-04: 削除 ──
  const handleDelete = async () => {
    if (!editRecordId) return;
    if (!confirm("この作業記録を削除しますか？")) return;
    setDeleting(true);
    try {
      await workRecordsApi.delete(ncId, editRecordId);
      const recRes = await workRecordsApi.list(ncId);
      setAllRecords(recRes.data);
      await endSession();
      showToast("🗑 作業記録を削除しました");
      setTimeout(() => router.push(`/nc/${ncId}`), 1200);
    } catch {
      showToast("❌ 削除に失敗しました");
    } finally {
      setDeleting(false);
    }
  };

  if (!nc) return (
    <div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>
  );

  const part = nc.part;

  return (
    <div className="flex flex-col h-screen bg-slate-100 overflow-hidden">

      {/* グローバルヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push(`/nc/${ncId}`)}
          className="text-slate-400 hover:text-white text-sm transition-colors">← 戻る</button>
        <span className="text-slate-400">|</span>
        <span className="font-bold text-sky-400 tracking-wide">MachCore</span>
        <span className="ml-auto text-xs text-slate-400">NC旋盤プログラム管理</span>
      </header>

      {/* 部品ヘッダー */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-lg font-bold text-slate-800">{part?.name ?? "—"} — 工程 L{nc.processL}</span>
          <span className="text-xs text-slate-500 font-mono">{part?.drawingNo}</span>
          <span className="text-xs text-slate-400">{part?.clientName}</span>
          <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">NC#{ncId}</span>
        </div>
      </div>

      {/* ナビゲーションタブ */}
      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {([
          { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
          { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
          { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: false },
          { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: true  },
        ] as { href: string; icon: string; label: string; active: boolean }[]).map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              tab.active
                ? "border-sky-400 text-sky-300"
                : "border-transparent text-slate-400 hover:text-white hover:border-slate-400"
            }`}>
            <span>{tab.icon}</span><span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* セッションバナー */}
      {isAuthenticated && sessionInfo && (
        <div className="bg-red-700 text-white px-5 py-2 flex items-center gap-3 text-sm shrink-0">
          <span className="font-bold">⏱ 作業中</span>
          <span className="text-red-200">担当: {sessionInfo.operatorName}</span>
          {editMode && (
            <span className="bg-amber-500 text-white text-xs px-2 py-0.5 rounded font-bold">✏️ 編集モード</span>
          )}
          <span className="ml-auto font-mono text-red-100">{fmtElapsed(elapsed)}</span>
        </div>
      )}

      {/* ── 2ペインレイアウト（上: 一覧 / 下: フォーム） ── */}
      <div className="flex flex-col flex-1 overflow-hidden">

        {/* ── 上ペイン: 過去作業記録一覧 ── */}
        <div className="bg-white border-b border-slate-200 shrink-0" style={{ maxHeight: "40%" }}>
          <div className="flex items-center justify-between px-5 py-2 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              過去の作業記録 ({allRecords.length}件)
            </h3>
            {!isAuthenticated && (
              <button onClick={() => setShowAuthModal(true)}
                className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-colors shadow">
                この作業を開始する
              </button>
            )}
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: "calc(40vh - 40px)" }}>
            {allRecords.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">記録なし</p>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead className="bg-slate-50 sticky top-0 z-10">
                  <tr>
                    {["作業日", "担当者", "機械", "段取", "加工", "個数", "CT", "種別", "備考", ""].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-bold text-slate-500 border-b border-slate-200 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allRecords.map((r, i) => (
                    <tr key={r.id}
                      className={`transition-colors ${
                        editRecordId === r.id
                          ? "bg-amber-50 border-l-2 border-l-amber-400"
                          : i % 2 === 0 ? "bg-white hover:bg-slate-50" : "bg-slate-50 hover:bg-slate-100"
                      }`}>
                      <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(r.work_date)}</td>
                      <td className="px-3 py-2">{r.operator_name ?? "—"}</td>
                      <td className="px-3 py-2 font-mono">{r.machine_code ?? "—"}</td>
                      <td className="px-3 py-2 text-right">{fmtMin(r.setup_time)}</td>
                      <td className="px-3 py-2 text-right">{fmtMin(r.machining_time)}</td>
                      <td className="px-3 py-2 text-right">{r.quantity ?? "—"}</td>
                      <td className="px-3 py-2 text-right">{fmtSec(r.cycle_time_sec)}</td>
                      <td className="px-3 py-2">
                        {r.work_type && (
                          <span className="bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded">{r.work_type}</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-400 max-w-[200px] truncate">{r.note ?? ""}</td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => {
                            if (!isAuthenticated) { setShowAuthModal(true); return; }
                            loadRecord(r);
                          }}
                          className={`text-[10px] font-bold px-2 py-0.5 rounded transition-colors ${
                            editRecordId === r.id
                              ? "bg-amber-400 text-white"
                              : "bg-slate-100 hover:bg-amber-100 text-slate-600 hover:text-amber-700"
                          }`}>
                          ✏️ 編集
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ── 下ペイン: 入力フォーム ── */}
        <div className={`flex-1 overflow-y-auto transition-opacity ${
          isAuthenticated ? "opacity-100" : "opacity-50 pointer-events-none select-none"
        }`}>
          <div className="max-w-2xl mx-auto p-5 space-y-4">

            {/* モードバー */}
            <div className={`flex items-center justify-between px-4 py-2 rounded-lg text-sm font-bold ${
              editMode
                ? "bg-amber-100 border border-amber-300 text-amber-800"
                : "bg-sky-50 border border-sky-200 text-sky-700"
            }`}>
              <span>{editMode ? "✏️ 編集モード — 選択した記録を修正します" : "＋ 新規入力モード"}</span>
              {editMode && (
                <button onClick={() => resetForm(nc)}
                  className="text-xs bg-white border border-slate-300 text-slate-600 px-2 py-1 rounded hover:bg-slate-50 transition-colors">
                  ＋ 新規に戻す
                </button>
              )}
            </div>

            {/* 機械選択 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">使用機械</label>
              <select
                value={machineId ?? ""}
                onChange={e => setMachineId(e.target.value ? Number(e.target.value) : null)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300">
                <option value="">— 機械を選択 —</option>
                {machines.map(m => (
                  <option key={m.id} value={m.id}>{m.machineCode} — {m.machineName}</option>
                ))}
              </select>
            </div>

            {/* 時間入力 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">作業時間</label>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <span className="text-xs text-slate-500">段取時間</span>
                  <TimeInput h={setupH} m={setupM} onH={setSetupH} onM={setSetupM} />
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-slate-500">加工時間</span>
                  <TimeInput h={machH} m={machM} onH={setMachH} onM={setMachM} />
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-slate-500">サイクルタイム</span>
                  <div className="flex items-center gap-1.5">
                    <NumInput value={cycleM} onChange={setCycleM} min={0} className="w-16" />
                    <span className="text-xs text-slate-400">m</span>
                    <NumInput value={cycleS} onChange={setCycleS} min={0} max={59} className="w-16" />
                    <span className="text-xs text-slate-400">s</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 個数・中断 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">個数</label>
                <div className="flex items-center gap-2">
                  <input type="number" min={0} value={quantity}
                    onChange={e => setQuantity(e.target.value === "" ? "" : parseInt(e.target.value))}
                    placeholder="個数を入力"
                    className="border border-slate-300 rounded px-3 py-2 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                  <span className="text-sm text-slate-400">個</span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">中断時間</label>
                <div className="flex items-center gap-2">
                  <NumInput value={interruption} onChange={setInterruption} min={0} className="w-20" />
                  <span className="text-xs text-slate-400">分</span>
                </div>
              </div>
            </div>

            {/* 種別 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                種別 <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-2 flex-wrap">
                {WORK_TYPES.map(t => (
                  <button key={t} onClick={() => setWorkType(t)}
                    className={`px-4 py-1.5 rounded text-sm font-medium border transition-colors ${
                      workType === t
                        ? "bg-sky-600 border-sky-600 text-white"
                        : "bg-white border-slate-300 text-slate-600 hover:border-sky-400"
                    }`}>{t}</button>
                ))}
              </div>
            </div>

            {/* 備考 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">備考</label>
              <textarea value={note} onChange={e => setNote(e.target.value)}
                maxLength={1000} rows={3}
                placeholder="問題点・注意事項・特記事項など"
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-sky-300" />
              <div className="text-right text-xs text-slate-400">{note.length}/1000</div>
            </div>

            {/* アクションボタン */}
            <div className="flex gap-3 pt-2 pb-8">
              {!editMode ? (
                /* 新規登録ボタン */
                <button onClick={handleSubmit} disabled={saving}
                  className="flex-1 bg-sky-600 hover:bg-sky-700 disabled:bg-sky-300 text-white font-bold py-3 rounded-lg text-sm transition-colors">
                  {saving ? "登録中…" : "✓ 作業完了（登録）"}
                </button>
              ) : (
                /* 編集モード: 更新 + 削除 */
                <>
                  <button onClick={handleUpdate} disabled={saving}
                    className="flex-1 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-white font-bold py-3 rounded-lg text-sm transition-colors">
                    {saving ? "更新中…" : "✓ 更新（保存）"}
                  </button>
                  <button onClick={handleDelete} disabled={deleting || saving}
                    className="px-5 py-3 bg-red-500 hover:bg-red-600 disabled:bg-red-300 text-white font-bold rounded-lg text-sm transition-colors">
                    {deleting ? "削除中…" : "🗑 削除"}
                  </button>
                </>
              )}
              <button onClick={handleCancel}
                className="px-5 py-3 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-100 transition-colors">
                ✗ キャンセル
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 認証モーダル */}
      {showAuthModal && (
        <AuthModal ncId={ncId} sessionType="record"
          onSuccess={handleAuthSuccess}
          onCancel={() => setShowAuthModal(false)} />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">
          {toast}
        </div>
      )}
    </div>
  );
}

// useSearchParams は Suspense が必要
export default function RecordPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>
    }>
      <RecordPageInner />
    </Suspense>
  );
}
