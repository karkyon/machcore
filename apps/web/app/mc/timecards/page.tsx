"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, Machine } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const TODAY = new Date().toISOString().slice(0, 10);

function fmtTime(dt: any): string {
  if (!dt) return "";
  const s = typeof dt === "string" ? dt : String(dt);
  if (s.includes("T")) return s.slice(11, 16);
  return s.slice(0, 5);
}

function calcKadouMin(start: string, end: string): number {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  let diff = (eh * 60 + em) - (sh * 60 + sm);
  if (diff < 0) diff += 24 * 60; // 日跨ぎ（夜番など）
  // 昼跨ぎ補正（12時前開始 && 13時以降終了）
  if (sh < 13 && eh >= 13) diff -= 60;
  return Math.max(0, diff);
}

function fmtMin(min: number): string {
  if (min <= 0) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? m + "m" : ""}` : `${m}m`;
}

interface RowState {
  id: number;
  machineId: number;
  machineCode: string;
  machineName: string;
  startTime: string;
  endTime: string;
  note: string;
  dirty: boolean;
  saving: boolean;
}

export default function TimecardPage() {
  const router = useRouter();
  const { isAuthenticated, token, operator, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [workDate, setWorkDate] = useState(TODAY);
  const [rows, setRows] = useState<RowState[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const initDone = useRef<Set<string>>(new Set());

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  // 全activeマシン取得
  useEffect(() => {
    machinesApi.list().then(r => {
      const ms = (r as any).data ?? [];
      setMachines(ms.filter((m: Machine) => m.isActive).sort((a: Machine, b: Machine) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0)));
    });
  }, []);

  // 日付変更時：自動init → データ取得
  const loadAndInit = useCallback(async (date: string) => {
    setLoading(true);
    try {
      // 未init日付なら自動initを呼ぶ（認証なしで呼べるようにsystemオペレーターIDを使う）
      // initはJWT必要なので、認証済みの場合のみ
      if (token && !initDone.current.has(date)) {
        try {
          await mcApi.initTimecards(date, token);
          initDone.current.add(date);
        } catch { /* 認証なし or エラー時はスキップ */ }
      }
      const r = await mcApi.timecardsByDate(date);
      const cards: any[] = (r as any).data ?? [];
      // machinesに登録済みのactive機械とcardをマージ
      setRows(cards.map((c: any) => ({
        id:          c.id,
        machineId:   c.machine_id,
        machineCode: c.machine?.machineCode ?? "",
        machineName: c.machine?.machineName ?? "",
        startTime:   fmtTime(c.start_time),
        endTime:     fmtTime(c.end_time),
        note:        c.note ?? "",
        dirty:       false,
        saving:      false,
      })));
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { loadAndInit(workDate); }, [workDate, loadAndInit]);

  // 認証完了後にinitを再実行
  useEffect(() => {
    if (token && !initDone.current.has(workDate)) {
      loadAndInit(workDate);
    }
  }, [token, workDate, loadAndInit]);

  const updateRow = (idx: number, field: keyof RowState, value: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value, dirty: true } : r));
  };

  const handleUpdate = async (idx: number) => {
    const row = rows[idx];
    if (!token) { setAuthOpen(true); return; }
    if (!row.startTime || !row.endTime) { showToast("⚠️ 開始・終了時刻を入力してください"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      await mcApi.updateTimecard(row.id, {
        start_time: row.startTime + ":00",
        end_time:   row.endTime   + ":00",
        note:       row.note || undefined,
      }, token);
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.machineCode} を更新しました`);
    } catch (e: any) {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast("❌ 更新に失敗しました");
    }
  };

  const handleAllUpdate = async () => {
    if (!token) { setAuthOpen(true); return; }
    const dirtyIdxs = rows.map((r, i) => ({ r, i })).filter(({ r }) => r.dirty).map(({ i }) => i);
    if (dirtyIdxs.length === 0) { showToast("変更なし"); return; }
    for (const idx of dirtyIdxs) await handleUpdate(idx);
  };

  const dirtyCount = rows.filter(r => r.dirty).length;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc")}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors">
          ← ダッシュボード
        </button>
        <span className="text-slate-500">|</span>
        <span className="font-mono text-teal-400 font-bold text-sm">MachCore</span>
        <span className="text-sm font-medium">機械タイムカード</span>
        <div className="ml-auto flex items-center gap-3">
          {isAuthenticated && operator ? (
            <div className="flex items-center gap-2">
              <span className="text-xs bg-teal-700 px-2 py-1 rounded font-bold">{operator.name}</span>
              <button onClick={logout} className="text-xs text-slate-400 hover:text-white">ログアウト</button>
            </div>
          ) : (
            <button onClick={() => setAuthOpen(true)}
              className="text-xs bg-slate-600 hover:bg-slate-500 px-3 py-1.5 rounded font-bold text-white transition-colors">
              ログイン
            </button>
          )}
        </div>
      </header>

      <div className="flex-1 p-5 max-w-5xl mx-auto w-full">
        {/* 日付バー */}
        <div className="flex items-center gap-4 mb-5 bg-white border border-slate-200 rounded-xl px-4 py-3">
          <label className="text-sm font-bold text-slate-600">日付</label>
          <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
          <button onClick={() => setWorkDate(TODAY)}
            className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-bold transition-colors">
            今日
          </button>
          <button onClick={() => loadAndInit(workDate)}
            className="text-xs px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg font-bold transition-colors">
            ↺ 再読込
          </button>
          <span className="ml-auto text-xs text-slate-400">{rows.length}件</span>
          {dirtyCount > 0 && (
            <button onClick={handleAllUpdate}
              className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded-lg transition-colors">
              📝 変更した{dirtyCount}件を一括更新
            </button>
          )}
        </div>

        {/* タイムカードテーブル */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex items-center">
            <span className="text-sm font-bold text-slate-700">稼働時間一覧</span>
            <span className="ml-2 text-xs text-slate-400">（昼休み12:00-13:00跨ぎの場合は-60分）</span>
          </div>
          {loading ? (
            <div className="p-10 text-center text-slate-400 text-sm">読み込み中...</div>
          ) : rows.length === 0 ? (
            <div className="p-10 text-center text-slate-400 text-sm">
              <div className="text-3xl mb-2">⏱️</div>
              <p>この日のタイムカードがありません</p>
              {!isAuthenticated && <p className="mt-2 text-xs">ログインするとデフォルトレコードが自動生成されます</p>}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-teal-50 border-b border-teal-100 text-teal-800">
                  <th className="px-4 py-2.5 text-left font-bold text-xs w-28">機械</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs w-36">開始時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs w-36">終了時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs w-24">稼働時間</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">備考</th>
                  <th className="px-3 py-2.5 text-center font-bold text-xs w-20">更新</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row, idx) => {
                  const kadouMin = calcKadouMin(row.startTime, row.endTime);
                  return (
                    <tr key={row.id} className={row.dirty ? "bg-amber-50" : (idx % 2 === 0 ? "bg-white" : "bg-slate-50/50")}>
                      <td className="px-4 py-2.5">
                        <div className="font-bold text-teal-700 text-xs">{row.machineCode}</div>
                        <div className="text-xs text-slate-400 leading-tight">{row.machineName}</div>
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.startTime}
                          onChange={e => updateRow(idx, "startTime", e.target.value)}
                          className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none font-mono" />
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.endTime}
                          onChange={e => updateRow(idx, "endTime", e.target.value)}
                          className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none font-mono" />
                      </td>
                      <td className="px-3 py-2">
                        <span className={`font-mono font-bold text-sm ${kadouMin > 0 ? "text-teal-700" : "text-slate-400"}`}>
                          {fmtMin(kadouMin)}
                        </span>
                        <div className="text-[10px] text-slate-400">{kadouMin}分</div>
                      </td>
                      <td className="px-3 py-2">
                        <input type="text" value={row.note}
                          onChange={e => updateRow(idx, "note", e.target.value)}
                          placeholder="例: 午後から故障停止"
                          className="w-full border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-teal-400 focus:outline-none text-slate-600" />
                      </td>
                      <td className="px-3 py-2 text-center">
                        {row.dirty ? (
                          <button onClick={() => handleUpdate(idx)} disabled={row.saving}
                            className="px-3 py-1 bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors whitespace-nowrap">
                            {row.saving ? "..." : "更新"}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-300 font-bold">✓</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* 説明 */}
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-800 space-y-1">
          <p className="font-bold">📋 機械タイムカードの使い方</p>
          <p>・毎日ログイン時にactiveな全機械設備のデフォルトレコード（08:00〜17:00）が自動生成されます</p>
          <p>・残業や故障停止など実際の稼働時間が異なる場合は終了時刻（または開始時刻）を修正して「更新」ボタンを押してください</p>
          <p>・稼働時間は昼休み（12:00〜13:00）を跨ぐ場合は-60分して計算されます（旧システムHowLong関数準拠）</p>
          <p>・作業記録画面で「📋 TC参照」ボタンを使うと、この機械タイムカードのデータから中断時間が自動計算されます</p>
        </div>
      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="work_record"
          onSuccess={() => { setAuthOpen(false); loadAndInit(workDate); }}
          onCancel={() => setAuthOpen(false)} />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50 transition-opacity">
          {toast}
        </div>
      )}
    </div>
  );
}
