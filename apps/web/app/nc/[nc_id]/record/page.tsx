"use client";
// apps/web/app/nc/[nc_id]/record/page.tsx
// SCR-05: 作業記録画面

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ncApi, workRecordsApi, machinesApi,
  type WorkRecord, type Machine,
} from "@/lib/api";

// ── 型 ────────────────────────────────────────────────────────────
type NcDetail = Awaited<ReturnType<typeof ncApi.findOne>>;

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

// ── メインコンポーネント ──────────────────────────────────────────
export default function RecordPage() {
  const { nc_id } = useParams<{ nc_id: string }>();
  const ncId = parseInt(nc_id);
  const router = useRouter();

  // ── ステート ──
  const [nc,           setNc]           = useState<NcDetail | null>(null);
  const [machines,     setMachines]     = useState<Machine[]>([]);
  const [prevRecords,  setPrevRecords]  = useState<WorkRecord[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showAuthModal,   setShowAuthModal]   = useState(false);
  const [saving,       setSaving]       = useState(false);
  const [toast,        setToast]        = useState<string | null>(null);

  // セッション情報（JWTデコード相当はlocalStorage経由）
  const [sessionInfo, setSessionInfo]   = useState<{
    operatorName: string; machineId: number | null;
  } | null>(null);

  // 経過タイマー
  const [elapsed,  setElapsed]  = useState(0);
  const timerRef               = useRef<NodeJS.Timeout | null>(null);

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

  // ── 初期データ取得 ──
  useEffect(() => {
    Promise.all([
      ncApi.findOne(ncId),
      machinesApi.list(),
      workRecordsApi.list(ncId),
    ]).then(([ncData, machData, recData]) => {
      setNc(ncData);
      setMachines(machData.filter((m: Machine) => m.is_active));
      setPrevRecords(recData.slice(0, 3));
      // サイクルタイムのデフォルトをncProgram.machiningTimeから設定
      if (ncData?.machiningTime) {
        const [m, s] = toMS(ncData.machiningTime * 60); // machiningTimeは分単位なのでsecに変換
        setCycleM(Math.floor(ncData.machiningTime));
        setCycleS(0);
      }
      setMachineId(ncData?.machineId ?? null);
    });
  }, [ncId]);

  // タイマー
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
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // 認証成功コールバック（AuthModalから呼ばれる想定）
  const handleAuthSuccess = useCallback((opName: string, token: string) => {
    setIsAuthenticated(true);
    setShowAuthModal(false);
    setSessionInfo({ operatorName: opName, machineId });
    // tokenはlocalStorageに保存済み（AuthModal側で行う）
  }, [machineId]);

  // キャンセル
  const handleCancel = async () => {
    if (!confirm("キャンセルしますか？入力内容は保存されません。")) return;
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/work-session`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("work_token")}` },
      });
    } catch (_) {}
    localStorage.removeItem("work_token");
    router.push(`/nc/${ncId}`);
  };

  // 登録
  const handleSubmit = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("work_token");
      const body = {
        setup_time_min:       setupH * 60 + setupM || undefined,
        machining_time_min:   machH  * 60 + machM  || undefined,
        cycle_time_sec:       cycleM * 60 + cycleS || undefined,
        quantity:             quantity !== "" ? Number(quantity) : undefined,
        interruption_time_min: interruption || undefined,
        work_type:             workType,
        note:                  note || undefined,
        machine_id:            machineId ?? undefined,
      };

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/nc/${ncId}/work-records`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) throw new Error("登録失敗");

      // Work Session終了
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/work-session`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      localStorage.removeItem("work_token");

      showToast("✅ 作業記録を登録しました");
      setTimeout(() => router.push(`/nc/${ncId}`), 1200);
    } catch (e) {
      showToast("❌ 登録に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (!nc) return (
    <div className="flex items-center justify-center h-screen text-slate-400">
      読み込み中…
    </div>
  );

  const part = nc.part;

  // ────────────────── RENDER ──────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-slate-100 overflow-hidden">

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
            {part?.name ?? "—"} — 工程 L{nc.processL}
          </span>
          <span className="text-xs text-slate-500 font-mono">{part?.drawingNo}</span>
          <span className="text-xs text-slate-400">{part?.clientName}</span>
          <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">
            NC#{ncId}
          </span>
        </div>
      </div>

      {/* ── 画面ナビゲーションタブ ── */}
      <nav className="bg-slate-700 px-5 flex gap-0 shrink-0">
        {([
          { href: `/nc/${ncId}`,        icon: "📋", label: "NC詳細",    active: false },
          { href: `/nc/${ncId}/edit`,   icon: "✏️",  label: "変更・登録", active: false },
          { href: `/nc/${ncId}/print`,  icon: "🖨",  label: "段取シート", active: false },
          { href: `/nc/${ncId}/record`, icon: "⏱",  label: "作業記録",  active: true  },
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
      {isAuthenticated && sessionInfo && (
        <div className="bg-red-700 text-white px-5 py-2 flex items-center gap-3 text-sm shrink-0">
          <span className="font-bold">⏱ 作業中</span>
          <span className="text-red-200">担当: {sessionInfo.operatorName}</span>
          <span className="ml-auto font-mono text-red-100">{fmtElapsed(elapsed)}</span>
        </div>
      )}

      {/* ── メインコンテンツ ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── 左: 入力フォーム ── */}
        <div className={`flex-1 overflow-y-auto p-5 transition-opacity ${
          isAuthenticated ? "opacity-100" : "opacity-50 pointer-events-none"
        }`}>

          {/* ── ロック状態オーバーレイ ── */}
          {!isAuthenticated && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-transparent" />
          )}

          <div className="max-w-xl space-y-5">

            <h2 className="text-base font-bold text-slate-700">⏱ 作業記録入力</h2>

            {/* 機械選択 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                使用機械
              </label>
              <select
                value={machineId ?? ""}
                onChange={e => setMachineId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300"
              >
                <option value="">— 機械を選択 —</option>
                {machines.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.machine_name}（{m.machine_code}）
                  </option>
                ))}
              </select>
            </div>

            {/* 時間入力 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-4">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                時間入力
              </label>

              {/* 段取時間 */}
              <div className="flex items-center gap-3">
                <span className="w-28 text-sm text-slate-600 shrink-0">段取時間</span>
                <TimeInput h={setupH} m={setupM} onH={setSetupH} onM={setSetupM} />
              </div>

              {/* 加工時間 */}
              <div className="flex items-center gap-3">
                <span className="w-28 text-sm text-slate-600 shrink-0">加工時間</span>
                <TimeInput h={machH} m={machM} onH={setMachH} onM={setMachM} />
              </div>

              {/* サイクルタイム */}
              <div className="flex items-center gap-3">
                <span className="w-28 text-sm text-slate-600 shrink-0">サイクルタイム</span>
                <div className="flex items-center gap-1.5">
                  <NumInput
                    value={cycleM} onChange={setCycleM}
                    min={0} className="w-16"
                  />
                  <span className="text-xs text-slate-400">分</span>
                  <NumInput
                    value={cycleS} onChange={setCycleS}
                    min={0} max={59} className="w-16"
                  />
                  <span className="text-xs text-slate-400">秒</span>
                </div>
              </div>

              {/* 中断時間 */}
              <div className="flex items-center gap-3">
                <span className="w-28 text-sm text-slate-600 shrink-0">中断時間</span>
                <div className="flex items-center gap-1.5">
                  <NumInput
                    value={interruption} onChange={setInterruption}
                    min={0} className="w-20"
                  />
                  <span className="text-xs text-slate-400">分</span>
                </div>
              </div>
            </div>

            {/* 加工個数 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                加工個数
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={0}
                  value={quantity}
                  onChange={e => setQuantity(e.target.value === "" ? "" : parseInt(e.target.value))}
                  placeholder="個数を入力"
                  className="border border-slate-300 rounded px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-sky-300"
                />
                <span className="text-sm text-slate-400">個</span>
              </div>
            </div>

            {/* 種別 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                種別 <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-2 flex-wrap">
                {WORK_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => setWorkType(t)}
                    className={`px-4 py-1.5 rounded text-sm font-medium border transition-colors ${
                      workType === t
                        ? "bg-sky-600 border-sky-600 text-white"
                        : "bg-white border-slate-300 text-slate-600 hover:border-sky-400"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* 備考 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                備考
              </label>
              <textarea
                value={note}
                onChange={e => setNote(e.target.value)}
                maxLength={1000}
                rows={4}
                placeholder="問題点・注意事項・特記事項など"
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-sky-300"
              />
              <div className="text-right text-xs text-slate-400">{note.length}/1000</div>
            </div>

            {/* アクションボタン */}
            <div className="flex gap-3 pt-2">
              <button
                onClick={handleSubmit}
                disabled={saving}
                className="flex-1 bg-sky-600 hover:bg-sky-700 disabled:bg-sky-300 text-white font-bold py-3 rounded-lg text-sm transition-colors"
              >
                {saving ? "登録中…" : "✓ 作業完了（登録）"}
              </button>
              <button
                onClick={handleCancel}
                className="px-5 py-3 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-100 transition-colors"
              >
                ✗ キャンセル
              </button>
            </div>

          </div>
        </div>

        {/* ── 右: 前回記録パネル / ロック状態ボタン ── */}
        <div className="w-72 shrink-0 bg-white border-l border-slate-200 flex flex-col overflow-hidden">

          {/* ロック状態: 作業開始ボタン */}
          {!isAuthenticated && (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 p-5">
              <div className="text-slate-400 text-center text-sm leading-relaxed">
                作業を開始するには<br />認証が必要です
              </div>
              <button
                onClick={() => setShowAuthModal(true)}
                className="w-full bg-sky-600 hover:bg-sky-700 text-white font-bold py-3 rounded-lg text-sm transition-colors shadow"
              >
                この作業を開始する
              </button>
            </div>
          )}

          {/* 前回記録パネル */}
          <div className="flex-1 overflow-y-auto p-4">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              前回の作業記録
            </h3>
            {prevRecords.length === 0 ? (
              <p className="text-xs text-slate-400">記録なし</p>
            ) : (
              <div className="space-y-3">
                {prevRecords.map(r => (
                  <div
                    key={r.id}
                    className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">
                        {new Date(r.work_date).toLocaleDateString("ja-JP")}
                      </span>
                      {r.work_type && (
                        <span className="bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded text-xs">
                          {r.work_type}
                        </span>
                      )}
                    </div>
                    <div className="text-slate-600">{r.operator_name ?? "—"}</div>
                    <div className="grid grid-cols-2 gap-x-2 text-slate-500">
                      <span>段取: {fmtMin(r.setup_time)}</span>
                      <span>加工: {fmtMin(r.machining_time)}</span>
                      <span>個数: {r.quantity ?? "—"}個</span>
                      <span>CT: {fmtSec(r.cycle_time_sec)}</span>
                    </div>
                    {r.note && (
                      <div className="text-slate-400 line-clamp-2 pt-1 border-t border-slate-100">
                        {r.note}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>

      {/* ── 認証モーダル ── */}
      {showAuthModal && (
        <AuthModal
          ncId={ncId}
          sessionType="record"
          onSuccess={handleAuthSuccess}
          onCancel={() => setShowAuthModal(false)}
        />
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">
          {toast}
        </div>
      )}

    </div>
  );
}

// ── サブコンポーネント: 数値入力 ──────────────────────────────────
function NumInput({
  value, onChange, min = 0, max, className = "",
}: {
  value: number; onChange: (v: number) => void;
  min?: number; max?: number; className?: string;
}) {
  return (
    <input
      type="number"
      min={min}
      max={max}
      value={value}
      onChange={e => {
        const v = parseInt(e.target.value) || 0;
        onChange(max !== undefined ? Math.min(v, max) : v);
      }}
      className={`border border-slate-300 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-sky-300 ${className}`}
    />
  );
}

// ── サブコンポーネント: 時間入力（h/m） ──────────────────────────
function TimeInput({
  h, m, onH, onM,
}: {
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

// ── AuthModal（SCR-03と同様のモーダル。既存コンポーネントがあれば流用） ──
function AuthModal({
  ncId, sessionType, onSuccess, onCancel,
}: {
  ncId: number;
  sessionType: string;
  onSuccess: (opName: string, token: string) => void;
  onCancel: () => void;
}) {
  const [users,    setUsers]    = useState<{ id: number; name: string }[]>([]);
  const [selId,    setSelId]    = useState<number | null>(null);
  const [selName,  setSelName]  = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/users`)
      .then(r => r.json())
      .then(setUsers);
  }, []);

  const handleSubmit = async () => {
    if (!selId || !password) { setError("担当者とパスワードを入力してください"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/work-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operator_id:   selId,
          password,
          session_type:  sessionType,
          nc_program_id: ncId,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError("パスワードが違います"); setPassword(""); return; }
      localStorage.setItem("work_token", data.access_token);
      onSuccess(selName, data.access_token);
    } catch {
      setError("通信エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="bg-slate-800 text-white px-5 py-4">
          <h2 className="font-bold text-base">⏱ 作業記録 — 担当者認証</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            担当者を選択してパスワードを入力してください
          </p>
        </div>
        <div className="p-5 space-y-4">
          {/* 担当者選択 */}
          <div className="grid grid-cols-3 gap-2">
            {users.map(u => (
              <button
                key={u.id}
                onClick={() => { setSelId(u.id); setSelName(u.name); setPassword(""); }}
                className={`py-2 px-2 rounded-lg text-sm font-medium border transition-colors ${
                  selId === u.id
                    ? "bg-sky-600 border-sky-600 text-white"
                    : "bg-slate-50 border-slate-200 text-slate-700 hover:border-sky-400"
                }`}
              >
                {u.name}
              </button>
            ))}
          </div>

          {/* パスワード */}
          {selId && (
            <div className="space-y-1">
              <label className="text-xs text-slate-500 font-medium">パスワード</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                autoFocus
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-300"
                placeholder="パスワードを入力"
              />
            </div>
          )}

          {error && (
            <p className="text-sm text-red-500 bg-red-50 px-3 py-2 rounded">{error}</p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              onClick={handleSubmit}
              disabled={!selId || !password || loading}
              className="flex-1 bg-sky-600 hover:bg-sky-700 disabled:bg-sky-300 text-white font-bold py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? "確認中…" : "確認してこの作業を開始する"}
            </button>
            <button
              onClick={onCancel}
              className="px-4 py-2.5 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              キャンセル
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}