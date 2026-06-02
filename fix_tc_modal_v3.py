#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_tc_modal_v3.py
str_replace方式で最小限の変更のみ適用。
1. fetchTimecardStop削除 + tcModalOpen/setupKadouMin/machKadouMin state追加
2. 段取TCボタン(2箇所) → 1箇所のTCバー
3. TimecardModal コンポーネント追加 + JSXマウント
"""
import subprocess, shutil, os, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"
REPO   = "/home/karkyon/projects/machcore"

if not os.path.exists(TARGET):
    print(f"ファイルが見つかりません: {TARGET}")
    sys.exit(1)

shutil.copy(TARGET, TARGET + ".bak_v3")

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

print(f"元ファイル: {len(src.splitlines())}行")
errors = []

# ══════════════════════════════════════════════════════════
# STEP1: tcWarnMsg state の後に tcModalOpen/setupKadouMin/machKadouMin を追加
# ══════════════════════════════════════════════════════════
OLD1 = '  const [tcWarnMsg, setTcWarnMsg] = useState<string | null>(null);'
NEW1 = '''  const [tcWarnMsg, setTcWarnMsg] = useState<string | null>(null);
  const [tcModalOpen, setTcModalOpen] = useState(false);
  const [setupKadouMin, setSetupKadouMin] = useState<number | null>(null);
  const [machKadouMin,  setMachKadouMin]  = useState<number | null>(null);'''
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    print("✅ STEP1: state追加 (tcModalOpen/setupKadouMin/machKadouMin)")
else:
    errors.append("STEP1: tcWarnMsg state が見つかりません")

# ══════════════════════════════════════════════════════════
# STEP2: fetchTimecardStop 関数を削除
# ══════════════════════════════════════════════════════════
OLD2 = '''  // 機械タイムカードから中断時間を算出（HowLong関数準拠）
  const fetchTimecardStop = async (phase: "setup" | "work") => {'''
# 関数の終わりまで削除 → handleSubmit の手前まで
FETCH_END = '''  const handleSubmit = async () => {'''
idx_start = src.find(OLD2)
idx_end   = src.find(FETCH_END)
if idx_start != -1 and idx_end != -1 and idx_start < idx_end:
    src = src[:idx_start] + "\n  " + src[idx_end:]
    print("✅ STEP2: fetchTimecardStop 削除")
else:
    errors.append(f"STEP2: fetchTimecardStop が見つかりません (start={idx_start}, end={idx_end})")

# ══════════════════════════════════════════════════════════
# STEP3: 段取グループのTCボタン(旧) → TCバー(新) に置き換え
# タイムカード未登録警告バナーの後、段取開始inputの前に挿入
# ══════════════════════════════════════════════════════════
OLD3 = '''                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>'''
NEW3 = '''                    {detail?.machine && startedAt && (
                      <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5">
                        <div className="flex-1 min-w-0 flex items-center gap-3 flex-wrap">
                          {setupKadouMin !== null && <span className="text-xs text-blue-700 font-bold">{"段取稼働: " + Math.floor(setupKadouMin/60) + "H " + (setupKadouMin%60) + "M"}</span>}
                          {machKadouMin  !== null && <span className="text-xs text-green-700 font-bold">{"量産稼働: " + Math.floor(machKadouMin/60)  + "H " + (machKadouMin%60)  + "M"}</span>}
                          {setupKadouMin === null && machKadouMin === null && <span className="text-xs text-slate-400">タイムカードを確認して稼働時間を参照</span>}
                        </div>
                        <button type="button" onClick={() => setTcModalOpen(true)}
                          className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-300 hover:bg-teal-50 hover:border-teal-400 text-slate-700 hover:text-teal-700 rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                          &#128197; 機械タイムカード参照
                        </button>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>'''
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1)
    print("✅ STEP3: TCバー統合版挿入")
else:
    errors.append("STEP3: 段取開始 grid が見つかりません")

# ══════════════════════════════════════════════════════════
# STEP4: 段取グループの旧TCボタン(中断h/mの横)を削除
# ══════════════════════════════════════════════════════════
OLD4 = '''                          {detail?.machine && startedAt && (
                            <button type="button" onClick={() => fetchTimecardStop("setup")}
                              className="text-[10px] px-2 py-1 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded font-bold transition-colors whitespace-nowrap ml-1">
                              📋 機械タイムカード参照
                            </button>
                          )}'''
if OLD4 in src:
    src = src.replace(OLD4, "", 1)
    print("✅ STEP4: 段取グループ 旧TCボタン削除")
else:
    errors.append("STEP4: 段取グループ 旧TCボタンが見つかりません")

# ══════════════════════════════════════════════════════════
# STEP5: 量産グループの旧TCボタン(中断h/mの横)を削除
# ══════════════════════════════════════════════════════════
OLD5 = '''                          {detail?.machine && checkedAt && (
                            <button type="button" onClick={() => fetchTimecardStop("work")}
                              className="text-[10px] px-2 py-1 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded font-bold transition-colors whitespace-nowrap ml-1">
                              📋 機械タイムカード参照
                            </button>
                          )}'''
if OLD5 in src:
    src = src.replace(OLD5, "", 1)
    print("✅ STEP5: 量産グループ 旧TCボタン削除")
else:
    errors.append("STEP5: 量産グループ 旧TCボタンが見つかりません")

# ══════════════════════════════════════════════════════════
# STEP6: TimecardModal JSXマウントを認証モーダルの直前に挿入
# ══════════════════════════════════════════════════════════
OLD6 = '''      {/* 認証モーダル */}
      {authOpen && ('''
NEW6 = '''      {tcModalOpen && detail?.machine && (
        <TimecardModal
          open={tcModalOpen}
          onClose={() => setTcModalOpen(false)}
          machineCode={detail.machine.machineCode}
          machineId={parseInt(machineId) || 0}
          startedAt={startedAt}
          checkedAt={checkedAt}
          finishedAt={finishedAt}
          token={token}
          onKadouChange={(s, m) => { setSetupKadouMin(s); setMachKadouMin(m); }}
        />
      )}

      {/* 認証モーダル */}
      {authOpen && ('''
if OLD6 in src:
    src = src.replace(OLD6, NEW6, 1)
    print("✅ STEP6: TimecardModal JSXマウント追加")
else:
    errors.append("STEP6: 認証モーダルコメントが見つかりません")

# ══════════════════════════════════════════════════════════
# STEP7: TimecardModal コンポーネントを McRecordPageInner の直前に追加
# ══════════════════════════════════════════════════════════
OLD7 = 'function McRecordPageInner() {'
TC_MODAL = '''// ─────────────────────────────────────────────────────────────────────
// 機械タイムカード参照モーダル
// ─────────────────────────────────────────────────────────────────────
interface TcRow {
  id: number | null;
  date: string;
  startTime: string;
  endTime: string;
  dirty: boolean;
  saving: boolean;
}
interface TimecardModalProps {
  open: boolean;
  onClose: () => void;
  machineCode: string;
  machineId: number;
  startedAt: string;
  checkedAt: string;
  finishedAt: string;
  token: string | null;
  onKadouChange: (setupKadouMin: number | null, machKadouMin: number | null) => void;
}
function TimecardModal({
  open, onClose, machineCode, machineId,
  startedAt, checkedAt, finishedAt, token, onKadouChange,
}: TimecardModalProps) {
  const [rows, setRows] = React.useState<TcRow[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [tcToast, setTcToast] = React.useState<string | null>(null);
  const showTcToast = (msg: string) => { setTcToast(msg); setTimeout(() => setTcToast(null), 3000); };

  const dateRange = React.useMemo((): string[] => {
    const ws = startedAt ? startedAt.slice(0, 10) : null;
    const we = finishedAt ? finishedAt.slice(0, 10) : checkedAt ? checkedAt.slice(0, 10) : null;
    if (!ws) return [];
    const dates: string[] = [];
    const cur = new Date(ws + "T12:00:00");
    const end = new Date((we ?? ws) + "T12:00:00");
    while (cur <= end) {
      dates.push(cur.toISOString().slice(0, 10));
      cur.setDate(cur.getDate() + 1);
    }
    return dates;
  }, [startedAt, checkedAt, finishedAt]);

  const calcKadou = React.useCallback((wsD: Date, weD: Date, tcRows: TcRow[]): number => {
    let total = 0;
    for (const row of tcRows) {
      if (row.id === null && !row.dirty) continue;
      const tcS = new Date(row.date + "T" + row.startTime + ":00");
      const tcE = new Date(row.date + "T" + row.endTime   + ":00");
      const ovS = tcS > wsD ? tcS : wsD;
      const ovE = tcE < weD ? tcE : weD;
      let diff = Math.round((ovE.getTime() - ovS.getTime()) / 60000);
      if (diff <= 0) continue;
      const sh = ovS.getHours() + ovS.getMinutes() / 60;
      const eh = ovE.getHours() + ovE.getMinutes() / 60;
      if (sh < 12 && eh > 13) diff -= 60;
      if (diff > 0) total += diff;
    }
    return total;
  }, []);

  const loadCards = React.useCallback(async () => {
    if (!open || dateRange.length === 0) return;
    setLoading(true);
    try {
      const newRows: TcRow[] = [];
      for (const dt of dateRange) {
        const res = await mcApi.timecardsByDate(dt);
        const all: any[] = (res as any).data ?? [];
        const card = all.find((c: any) => c.machine?.machineCode === machineCode);
        if (card) {
          const fmtT = (s: string) => s && s.length >= 8 ? s.slice(0, 5) : "08:00";
          newRows.push({ id: card.id, date: dt,
            startTime: fmtT(card.start_time ?? ""),
            endTime:   fmtT(card.end_time   ?? ""),
            dirty: false, saving: false });
        } else {
          newRows.push({ id: null, date: dt, startTime: "08:00", endTime: "17:00", dirty: false, saving: false });
        }
      }
      setRows(newRows);
    } catch { showTcToast("タイムカード取得失敗"); }
    finally  { setLoading(false); }
  }, [open, dateRange, machineCode]);

  React.useEffect(() => { loadCards(); }, [loadCards]);

  React.useEffect(() => {
    if (rows.length === 0) return;
    const ws = startedAt  ? new Date(startedAt)  : null;
    const ck = checkedAt  ? new Date(checkedAt)  : null;
    const we = finishedAt ? new Date(finishedAt) : null;
    onKadouChange(
      ws && ck ? calcKadou(ws, ck, rows) : null,
      ck && we ? calcKadou(ck, we, rows) : null,
    );
  }, [rows, startedAt, checkedAt, finishedAt, calcKadou, onKadouChange]);

  const updateField = (idx: number, field: "startTime" | "endTime", val: string) =>
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val, dirty: true } : r));

  const handleSave = async (idx: number) => {
    const row = rows[idx];
    if (!token) { showTcToast("認証が必要です"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      if (row.id !== null) {
        await mcApi.updateTimecard(row.id, { start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
        showTcToast("更新しました: " + row.date);
      } else {
        const res = await mcApi.createTimecard({ machine_id: machineId, work_date: row.date,
          start_time: row.startTime + ":00", end_time: row.endTime + ":00" }, token);
        const newId: number = (res as any).data?.id ?? (res as any).id ?? -1;
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, id: newId, dirty: false, saving: false } : r));
        showTcToast("登録しました: " + row.date);
      }
    } catch {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showTcToast("保存失敗");
    }
  };

  const fmtK = (min: number) => Math.floor(min/60) + "H " + (min%60) + "M";
  const summaryK = (wsStr: string, weStr: string): string => {
    if (!wsStr || !weStr || rows.length === 0) return "—";
    const w = new Date(wsStr), e = new Date(weStr);
    if (isNaN(w.getTime()) || isNaN(e.getTime())) return "—";
    return fmtK(calcKadou(w, e, rows));
  };
  const dayK = (row: TcRow): string => {
    if (row.id === null && !row.dirty) return "—";
    const w = startedAt  ? new Date(startedAt)  : new Date(row.date + "T00:00:00");
    const e = finishedAt ? new Date(finishedAt) : new Date(row.date + "T23:59:59");
    const m = calcKadou(w, e, [row]);
    return m > 0 ? fmtK(m) : "—";
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-slate-800">&#128197; 機械タイムカード参照 — {machineCode}</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">タイムカードを確認・編集できます。更新すると稼働時間に即反映されます。</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg font-bold px-2">&#10005;</button>
        </div>
        <div className="grid grid-cols-3 gap-3 px-5 py-3 bg-slate-50 border-b border-slate-100 shrink-0">
          <div className="text-center text-xs font-bold">
            <p className="text-slate-400 mb-0.5">段取稼働</p>
            <p className="text-blue-700 text-sm">{summaryK(startedAt, checkedAt || finishedAt)}</p>
          </div>
          <div className="text-center text-xs font-bold">
            <p className="text-slate-400 mb-0.5">量産稼働</p>
            <p className="text-green-700 text-sm">{checkedAt ? summaryK(checkedAt, finishedAt) : "—"}</p>
          </div>
          <div className="text-center text-xs font-bold">
            <p className="text-slate-400 mb-0.5">総稼働</p>
            <p className="text-teal-700 text-sm">{summaryK(startedAt, finishedAt || checkedAt)}</p>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 text-sm">読み込み中...</div>
          ) : (
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="pb-2 text-left font-bold text-slate-500 w-24">日付</th>
                  <th className="pb-2 text-left font-bold text-slate-500 w-20">開始</th>
                  <th className="pb-2 text-left font-bold text-slate-500 w-20">終了</th>
                  <th className="pb-2 text-center font-bold text-slate-500 w-20">稼働時間</th>
                  <th className="pb-2 text-center font-bold text-slate-500 w-14">操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const isHoliday = row.id === null && !row.dirty;
                  const kStr = dayK(row);
                  return (
                    <tr key={row.date} className={"border-b border-slate-100 " + (isHoliday ? "bg-slate-50/60" : "")}>
                      <td className="py-2 font-mono text-slate-700">{row.date.slice(5)}</td>
                      <td className="py-2">
                        {isHoliday
                          ? <span className="text-slate-400 text-[11px]">― 休日 ―</span>
                          : <input type="time" value={row.startTime} onChange={e => updateField(idx,"startTime",e.target.value)}
                              className="border border-slate-200 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-teal-400" />}
                      </td>
                      <td className="py-2">
                        {!isHoliday && <input type="time" value={row.endTime} onChange={e => updateField(idx,"endTime",e.target.value)}
                          className="border border-slate-200 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-teal-400" />}
                      </td>
                      <td className="py-2 text-center">
                        <span className={"font-bold " + (kStr !== "—" ? "text-teal-700" : "text-slate-400")}>{kStr}</span>
                      </td>
                      <td className="py-2 text-center">
                        {row.dirty && (
                          <button onClick={() => handleSave(idx)} disabled={row.saving}
                            className="text-[11px] px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold disabled:opacity-50 transition-colors whitespace-nowrap">
                            {row.saving ? "..." : row.id === null ? "登録" : "更新"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 shrink-0">
          <p className="text-[10px] text-slate-400">※ 稼働時間 = overlap（12:00-13:00は自動控除）</p>
          <button onClick={onClose} className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-bold rounded-lg transition-colors">閉じる</button>
        </div>
        {tcToast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs px-4 py-2 rounded-full shadow-lg whitespace-nowrap">{tcToast}</div>
        )}
      </div>
    </div>
  );
}

'''
if OLD7 in src:
    src = src.replace(OLD7, TC_MODAL + OLD7, 1)
    print("✅ STEP7: TimecardModal コンポーネント追加")
else:
    errors.append("STEP7: McRecordPageInner が見つかりません")

# ══════════════════════════════════════════════════════════
# エラーチェック
# ══════════════════════════════════════════════════════════
if errors:
    print("\n❌ エラーが発生しました:")
    for e in errors:
        print(f"  - {e}")
    shutil.copy(TARGET + ".bak_v3", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)
print(f"\n書き込み完了: {len(src.splitlines())}行")

# ── tsc ──
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print((r.stdout + r.stderr)[-3000:])
    shutil.copy(TARGET + ".bak_v3", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ tsc OK")

# ── next build ──
print("--- next build ---")
r2 = subprocess.run(["npx", "next", "build"],
    cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r2.returncode != 0:
    print("❌ next build エラー:")
    print((r2.stdout + r2.stderr)[-2000:])
    shutil.copy(TARGET + ".bak_v3", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "feat: record page - TC modal (timecard ref modal, 1 btn, kadou summary)"],
    cwd=REPO)
r3 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r3.stderr.strip() or r3.stdout.strip()))

os.remove(TARGET + ".bak_v3")
print("✅ 完了")
