import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def run(cmd, cwd=ROOT):
    label = cmd.split()[0]
    print(f"--- {label} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ── 1. timecards/page.tsx 完全書き直し ──────────────────────────────
TC_PAGE = f"{ROOT}/apps/web/app/mc/timecards/page.tsx"

PAGE = '''"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mcApi, machinesApi, Machine } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const TODAY = () => new Date().toISOString().slice(0, 10);

// APIはTime(0)型を "1970-01-01T08:00:00.000Z" 形式で返す → UTC時刻として取り出す
function fmtTime(dt: any): string {
  if (!dt) return "";
  const s = typeof dt === "string" ? dt : String(dt);
  if (s.includes("T") && s.endsWith("Z")) {
    const d = new Date(s);
    return String(d.getUTCHours()).padStart(2,"0") + ":" + String(d.getUTCMinutes()).padStart(2,"0");
  }
  if (s.includes("T")) return s.slice(11, 16);
  return s.slice(0, 5);
}

function calcKadouMin(start: string, end: string): number {
  if (!start || !end || start === "--:--" || end === "--:--") return 0;
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  if (isNaN(sh) || isNaN(eh)) return 0;
  let diff = (eh * 60 + em) - (sh * 60 + sm);
  if (diff < 0) diff += 24 * 60;
  if (sh < 13 && eh >= 13) diff -= 60; // 昼跨ぎ-60分
  return Math.max(0, diff);
}

function fmtMin(min: number): string {
  if (min <= 0) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? m+"m" : ""}` : `${m}m`;
}

interface RowState {
  id: number;
  machineId: number;
  machineCode: string;
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
  const [workDate, setWorkDate] = useState(TODAY());
  const [rows, setRows] = useState<RowState[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  const loadData = useCallback(async (date: string, doInit = false) => {
    setLoading(true);
    try {
      if (doInit && token) {
        try { await mcApi.initTimecards(date, token); } catch { /* ignore */ }
      }
      const r = await mcApi.timecardsByDate(date);
      const cards: any[] = (r as any).data ?? [];
      setRows(cards.map((c: any) => ({
        id:          c.id,
        machineId:   c.machine_id,
        machineCode: c.machine?.machineCode ?? String(c.machine_id),
        startTime:   fmtTime(c.start_time),
        endTime:     fmtTime(c.end_time),
        note:        c.note ?? "",
        dirty:       false,
        saving:      false,
      })));
    } finally {
      setLoading(false);
    }
  }, [token]);

  // 日付変更 or 初回
  useEffect(() => { loadData(workDate, true); }, [workDate, loadData]);

  const updateRow = (idx: number, field: keyof RowState, value: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value, dirty: true } : r));
  };

  const handleUpdate = useCallback(async (idx: number) => {
    const row = rows[idx];
    if (!token) { setAuthOpen(true); return; }
    if (!row.startTime || !row.endTime) { showToast("⚠️ 開始・終了時刻を入力してください"); return; }
    console.log(`[TC更新] id=${row.id} start=${row.startTime} end=${row.endTime}`);
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      const res = await mcApi.updateTimecard(row.id, {
        start_time: row.startTime + ":00",
        end_time:   row.endTime   + ":00",
        note:       row.note || undefined,
      }, token);
      console.log("[TC更新] 成功", res);
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.machineCode} 更新しました`);
    } catch (e: any) {
      console.error("[TC更新] エラー", e);
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast(`❌ 更新失敗: ${e?.response?.data?.message ?? e?.message ?? "エラー"}`);
    }
  }, [rows, token, showToast]);

  const handleAllUpdate = async () => {
    if (!token) { setAuthOpen(true); return; }
    const idxs = rows.map((r, i) => i).filter(i => rows[i].dirty);
    if (idxs.length === 0) { showToast("変更なし"); return; }
    for (const i of idxs) await handleUpdate(i);
  };

  // 全機械一括セット（旧システムCtl5ボタン相当）
  const setAllTime = (field: "startTime" | "endTime", val: string) => {
    setRows(prev => prev.map(r => ({ ...r, [field]: val, dirty: true })));
    showToast(`全機械の${field === "startTime" ? "開始" : "終了"}時刻を ${val} にセットしました`);
  };

  const dirtyCount = rows.filter(r => r.dirty).length;

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-4 py-2 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/mc")}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium transition-colors">
          ← ダッシュボード
        </button>
        <span className="text-slate-500">|</span>
        <span className="font-mono text-teal-400 font-bold text-sm">MachCore</span>
        <span className="text-sm font-medium">機械タイムカード</span>
        <div className="ml-auto flex items-center gap-2">
          {isAuthenticated && operator ? (
            <>
              <span className="text-xs bg-teal-700 px-2 py-1 rounded font-bold">{operator.name}</span>
              <button onClick={logout} className="text-xs text-slate-400 hover:text-white">ログアウト</button>
            </>
          ) : (
            <button onClick={() => setAuthOpen(true)}
              className="text-xs bg-slate-600 hover:bg-slate-500 px-3 py-1.5 rounded font-bold text-white transition-colors">
              ログイン
            </button>
          )}
        </div>
      </header>

      {/* ツールバー（固定） */}
      <div className="bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-2 flex-wrap shrink-0">
        <label className="text-sm font-bold text-slate-600">日付</label>
        <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
        <button onClick={() => setWorkDate(TODAY())}
          className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-bold transition-colors">
          今日
        </button>
        <button onClick={() => loadData(workDate, true)}
          className="text-xs px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg font-bold transition-colors">
          ↺ 再読込
        </button>
        <span className="text-xs text-slate-400 ml-1">{rows.length}件</span>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {/* 旧システム Ctl5相当ボタン */}
          <button onClick={() => setAllTime("startTime", "08:00")}
            className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg font-bold transition-colors whitespace-nowrap">
            全機械 08:00開始
          </button>
          <button onClick={() => setAllTime("endTime", "17:00")}
            className="text-xs px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 border border-blue-200 rounded-lg font-bold transition-colors whitespace-nowrap">
            全機械 17:00終了
          </button>
          <button onClick={() => setAllTime("endTime", "19:00")}
            className="text-xs px-3 py-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 border border-purple-200 rounded-lg font-bold transition-colors whitespace-nowrap">
            全機械 19:00終了
          </button>
          {dirtyCount > 0 && (
            <button onClick={handleAllUpdate}
              className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded-lg transition-colors whitespace-nowrap">
              💾 {dirtyCount}件を一括更新
            </button>
          )}
        </div>
      </div>

      {/* テーブル（ヘッダー固定・明細スクロール） */}
      <div className="flex-1 overflow-hidden px-4 py-3">
        <div className="h-full bg-white rounded-xl border border-slate-200 flex flex-col overflow-hidden">
          {/* 固定ヘッダー */}
          <div className="shrink-0 border-b border-slate-200">
            <table className="w-full text-sm table-fixed">
              <colgroup>
                <col className="w-32" />
                <col className="w-36" />
                <col className="w-36" />
                <col className="w-24" />
                <col />
                <col className="w-20" />
              </colgroup>
              <thead>
                <tr className="bg-teal-50 text-teal-800">
                  <th className="px-4 py-2.5 text-left font-bold text-xs">機械</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">開始時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">終了時刻</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">稼働時間</th>
                  <th className="px-3 py-2.5 text-left font-bold text-xs">備考</th>
                  <th className="px-3 py-2.5 text-center font-bold text-xs">更新</th>
                </tr>
              </thead>
            </table>
          </div>
          {/* スクロール明細 */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-10 text-center text-slate-400 text-sm">読み込み中...</div>
            ) : rows.length === 0 ? (
              <div className="p-10 text-center text-slate-400 text-sm">
                <div className="text-3xl mb-2">⏱️</div>
                <p>この日のタイムカードがありません</p>
                {!isAuthenticated && <p className="mt-1 text-xs">ログインするとデフォルトレコードが自動生成されます</p>}
              </div>
            ) : (
              <table className="w-full text-sm table-fixed">
                <colgroup>
                  <col className="w-32" />
                  <col className="w-36" />
                  <col className="w-36" />
                  <col className="w-24" />
                  <col />
                  <col className="w-20" />
                </colgroup>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((row, idx) => {
                    const kadouMin = calcKadouMin(row.startTime, row.endTime);
                    return (
                      <tr key={row.id}
                        className={row.dirty ? "bg-amber-50" : (idx % 2 === 0 ? "bg-white" : "bg-slate-50/40")}>
                        <td className="px-4 py-2">
                          <span className="font-bold text-teal-700 text-sm">{row.machineCode}</span>
                        </td>
                        <td className="px-3 py-1.5">
                          <input type="time" value={row.startTime}
                            onChange={e => updateRow(idx, "startTime", e.target.value)}
                            className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none font-mono" />
                        </td>
                        <td className="px-3 py-1.5">
                          <input type="time" value={row.endTime}
                            onChange={e => updateRow(idx, "endTime", e.target.value)}
                            className="w-32 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none font-mono" />
                        </td>
                        <td className="px-3 py-2">
                          <span className={`font-mono font-bold text-sm ${kadouMin > 0 ? "text-teal-700" : "text-slate-400"}`}>
                            {fmtMin(kadouMin)}
                          </span>
                          <div className="text-[10px] text-slate-400">{kadouMin > 0 ? kadouMin+"分" : ""}</div>
                        </td>
                        <td className="px-3 py-1.5">
                          <input type="text" value={row.note}
                            onChange={e => updateRow(idx, "note", e.target.value)}
                            placeholder="例: 午後から故障停止"
                            className="w-full border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-teal-400 focus:outline-none" />
                        </td>
                        <td className="px-3 py-1.5 text-center">
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
        </div>
      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} sessionType="work_record"
          onSuccess={() => { setAuthOpen(false); loadData(workDate, true); }}
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
'''

write(TC_PAGE, PAGE)
print("OK: mc/timecards/page.tsx 完全書き直し")

# ── 2. ビルド & デプロイ ────────────────────────────────────────────
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: タイムカード画面完全作り直し ヘッダー固定/UTC修正/19:00ボタン追加 v59" && git push')
print("DONE")
