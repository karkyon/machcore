"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, Machine } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const TODAY = new Date().toISOString().slice(0, 10);

function fmtTime(dt: any): string {
  if (!dt) return "—";
  const s = typeof dt === "string" ? dt : "";
  // "HH:MM:SS" or ISO string
  if (s.includes("T")) return s.slice(11, 16);
  return s.slice(0, 5);
}

export default function TimecardPage() {
  const router   = useRouter();
  const { isAuthenticated, token, operator, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [workDate, setWorkDate] = useState(TODAY);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [cards, setCards]       = useState<any[]>([]);
  const [loading, setLoading]   = useState(false);

  // 入力フォーム
  const [selMachineId, setSelMachineId] = useState<string>("");
  const [startTime, setStartTime]       = useState("08:00");
  const [endTime, setEndTime]           = useState("17:00");
  const [note, setNote]                 = useState("");
  const [saving, setSaving]             = useState(false);
  const [toast, setToast]               = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  const loadCards = useCallback(async () => {
    setLoading(true);
    try {
      const r = await mcApi.timecardsByDate(workDate);
      setCards((r as any).data ?? []);
    } catch { setCards([]); }
    finally { setLoading(false); }
  }, [workDate]);

  useEffect(() => {
    machinesApi.list().then(r => {
      const ms = (r as any).data ?? [];
      setMachines(ms.filter((m: Machine) => m.isActive));
    });
  }, []);

  useEffect(() => { loadCards(); }, [loadCards]);

  const handleSave = async () => {
    if (!token) { setAuthOpen(true); return; }
    if (!selMachineId || !startTime || !endTime) {
      showToast("⚠️ 機械・開始・終了時刻を入力してください"); return;
    }
    if (startTime >= endTime) {
      showToast("⚠️ 終了時刻は開始時刻より後にしてください"); return;
    }
    setSaving(true);
    try {
      await mcApi.createTimecard({
        machine_id: parseInt(selMachineId),
        work_date:  workDate,
        start_time: startTime + ":00",
        end_time:   endTime   + ":00",
        note:       note || undefined,
      }, token);
      showToast("✅ タイムカードを登録しました");
      setNote("");
      loadCards();
    } catch (e: any) {
      showToast("❌ " + (e?.response?.data?.message ?? "登録に失敗しました"));
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: number) => {
    if (!token) { setAuthOpen(true); return; }
    if (!window.confirm("このタイムカードを削除しますか？")) return;
    try {
      await mcApi.deleteTimecard(id, token);
      showToast("🗑️ 削除しました");
      loadCards();
    } catch { showToast("❌ 削除に失敗しました"); }
  };

  // 機械ごとにグループ化
  const grouped = cards.reduce((acc: Record<string, any[]>, c: any) => {
    const key = c.machine?.machineCode ?? String(c.machine_id);
    if (!acc[key]) acc[key] = [];
    acc[key].push(c);
    return acc;
  }, {});

  const usedMachineIds = new Set(cards.map((c: any) => c.machine_id));

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc")}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors">
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          ダッシュボード
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium">機械タイムカード</span>
        <div className="ml-auto flex items-center gap-2">
          {isAuthenticated && operator ? (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name}
            </span>
          ) : (
            <button onClick={() => setAuthOpen(true)}
              className="text-[11px] bg-sky-600 hover:bg-sky-500 text-white px-3 py-1 rounded font-bold transition-colors">
              🔑 認証して登録
            </button>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* 日付選択 */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
          <label className="text-sm font-bold text-slate-600">日付</label>
          <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
          <button onClick={() => setWorkDate(TODAY)}
            className="text-xs text-teal-600 font-bold hover:underline">今日に戻す</button>
          <span className="ml-auto text-xs text-slate-400">{cards.length}件登録済み</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* 登録フォーム */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-teal-600 text-white text-xs flex items-center justify-center font-bold">+</span>
              タイムカード登録
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">機械</label>
                <select value={selMachineId} onChange={e => setSelMachineId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                  <option value="">— 選択 —</option>
                  {machines.map(m => (
                    <option key={m.id} value={String(m.id)}>
                      {m.machineCode}{usedMachineIds.has(m.id) ? " ✓" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">開始時刻</label>
                  <input type="time" value={startTime} onChange={e => setStartTime(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">終了時刻</label>
                  <input type="time" value={endTime} onChange={e => setEndTime(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">備考（任意）</label>
                <input value={note} onChange={e => setNote(e.target.value)}
                  placeholder="例: 午後から故障停止など"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
              </div>

              {/* クイック入力ボタン */}
              <div>
                <p className="text-xs text-slate-400 mb-1.5">クイック入力</p>
                <div className="flex gap-2 flex-wrap">
                  {[
                    { label: "早番 08:00-17:00", s: "08:00", e: "17:00" },
                    { label: "遅番 09:00-18:00", s: "09:00", e: "18:00" },
                    { label: "夜番 17:00-02:00", s: "17:00", e: "02:00" },
                  ].map(q => (
                    <button key={q.label} type="button"
                      onClick={() => { setStartTime(q.s); setEndTime(q.e); }}
                      className="text-xs px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors">
                      {q.label}
                    </button>
                  ))}
                </div>
              </div>

              <button onClick={handleSave} disabled={saving || !selMachineId}
                className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white font-bold py-2.5 rounded-lg text-sm transition-colors">
                {saving ? "登録中..." : "✅ タイムカードを登録"}
              </button>
            </div>
          </div>

          {/* 登録済み一覧 */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-700">
                {workDate} の登録状況
              </h2>
              <button onClick={loadCards} className="text-xs text-teal-600 hover:underline">↺ 更新</button>
            </div>
            {loading ? (
              <div className="p-8 text-center text-slate-400 text-sm">読み込み中...</div>
            ) : cards.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                <div className="text-3xl mb-2">⏱️</div>
                この日のタイムカードがありません
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {Object.entries(grouped).map(([machCode, items]) => (
                  <div key={machCode} className="px-4 py-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-bold text-teal-700 bg-teal-100 px-2 py-0.5 rounded">{machCode}</span>
                    </div>
                    <div className="space-y-1.5">
                      {(items as any[]).map((c: any) => {
                        const s = fmtTime(c.start_time);
                        const e = fmtTime(c.end_time);
                        // 稼動時間計算（昼跨ぎ考慮）
                        const [sh, sm] = s.split(":").map(Number);
                        const [eh, em] = e.split(":").map(Number);
                        let totalMin = (eh * 60 + em) - (sh * 60 + sm);
                        if (totalMin < 0) totalMin += 24 * 60;
                        // 昼跨ぎ（13時前に開始、13時以降に終了）で -60分
                        if (sh < 13 && eh >= 13) totalMin -= 60;
                        const dh = Math.floor(totalMin / 60);
                        const dm = totalMin % 60;
                        return (
                          <div key={c.id} className="flex items-center gap-3 bg-slate-50 rounded-lg px-3 py-2">
                            <span className="font-mono text-sm text-slate-800 font-bold">{s}〜{e}</span>
                            <span className="text-xs text-slate-400">
                              ({dh > 0 ? `${dh}h` : ""}{dm > 0 ? `${dm}m` : ""})
                            </span>
                            <span className="text-xs text-slate-500">{c.operator?.name ?? "—"}</span>
                            {c.note && <span className="text-xs text-slate-400 ml-auto truncate max-w-24">{c.note}</span>}
                            {isAuthenticated && token && (
                              <button onClick={() => handleDelete(c.id)}
                                className="text-red-400 hover:text-red-600 text-xs ml-auto font-bold shrink-0">✕</button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 機械別週間サマリー */}
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h2 className="text-sm font-bold text-slate-700 mb-3">機械タイムカードと作業記録の連携について</h2>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 space-y-1">
            <p className="font-bold">⚙️ 旧システムHowLong関数の仕様</p>
            <p>作業記録の時間計算では、段取開始〜加工終了の時刻差から機械の稼動時間を算出します。</p>
            <p>昼休み（12:00〜13:00）を跨ぐ場合は<strong>-60分</strong>して計算します。</p>
            <p>「機械タイムカード」に各機械の実際の稼動開始・終了時刻を登録することで、作業記録画面の時間集計に反映されます。</p>
          </div>
        </div>
      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="work_record"
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
