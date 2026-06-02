#!/usr/bin/env python3
"""
作業記録画面 機械タイムカード参照モーダル実装スクリプト
1. 段取・量産の「機械タイムカード参照」ボタン2か所を削除
2. datetimeモード時の1か所に統合（段取セクション直下）
3. モーダル実装:
   - WS〜WE の全日付について対象機械のタイムカードを表示
   - タイムカードなし = 休日 表示
   - 開始/終了時刻を編集・更新（PUT /mc/timecards/:id）
   - 稼働時間をHowLongロジックでリアルタイム計算表示
   - 稼働時間合計を親に通知（onKadouChange）→ 段取時間・加工時間の参考表示に反映
4. tcWarnMsg/fetchTimecardStopの旧実装を削除
"""
import subprocess, shutil, os, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"

if not os.path.exists(TARGET):
    print(f"ファイルが見つかりません: {TARGET}")
    sys.exit(1)

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

original = src
count = 0

# ────────────────────────────────────────────────────────────────────────
# 1. TimecardModal コンポーネント追加（ファイル末尾の export default の直前）
# ────────────────────────────────────────────────────────────────────────
MODAL_COMPONENT = '''
// ── 機械タイムカード参照モーダル ─────────────────────────────────────────
interface TcRow {
  id: number | null;       // null = 休日（レコードなし）
  date: string;            // YYYY-MM-DD
  startTime: string;       // HH:MM
  endTime: string;         // HH:MM
  dirty: boolean;
  saving: boolean;
}

interface TimecardModalProps {
  open: boolean;
  onClose: () => void;
  machineCode: string;
  machineId: number;
  startedAt: string;       // datetime-local string or ""
  checkedAt: string;
  finishedAt: string;
  token: string | null;
  /** 稼働時間合計（分）を親に通知 */
  onKadouChange: (setupKadouMin: number | null, machKadouMin: number | null) => void;
}

function TimecardModal({
  open, onClose, machineCode, machineId,
  startedAt, checkedAt, finishedAt, token, onKadouChange,
}: TimecardModalProps) {
  const [rows, setRows] = React.useState<TcRow[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [toast, setToast] = React.useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  // 日付範囲を生成
  const dateRange = React.useMemo(() => {
    const ws = startedAt ? startedAt.slice(0, 10) : null;
    const we = finishedAt ? finishedAt.slice(0, 10) : (checkedAt ? checkedAt.slice(0, 10) : null);
    if (!ws) return [];
    const dates: string[] = [];
    const d = new Date(ws);
    const end = we ? new Date(we) : new Date(ws);
    while (d <= end) {
      dates.push(d.toISOString().slice(0, 10));
      d.setDate(d.getDate() + 1);
    }
    return dates;
  }, [startedAt, checkedAt, finishedAt]);

  // タイムカード取得
  const loadCards = React.useCallback(async () => {
    if (!open || dateRange.length === 0) return;
    setLoading(true);
    try {
      const newRows: TcRow[] = [];
      for (const dt of dateRange) {
        const r = await mcApi.timecardsByDate(dt);
        const allCards: any[] = (r as any).data ?? [];
        const card = allCards.find((c: any) => c.machine?.machineCode === machineCode);
        if (card) {
          const fmt = (dt: string) => dt ? dt.slice(11, 16) : "08:00";
          newRows.push({
            id: card.id,
            date: dt,
            startTime: fmt(card.start_time ?? ""),
            endTime:   fmt(card.end_time ?? ""),
            dirty: false,
            saving: false,
          });
        } else {
          newRows.push({ id: null, date: dt, startTime: "08:00", endTime: "17:00", dirty: false, saving: false });
        }
      }
      setRows(newRows);
    } catch (e) {
      showToast("タイムカード取得失敗");
    } finally {
      setLoading(false);
    }
  }, [open, dateRange, machineCode]);

  React.useEffect(() => { loadCards(); }, [loadCards]);

  // 稼働時間計算（HowLong準拠）
  const calcKadouMin = React.useCallback((ws: Date, we: Date, cards: TcRow[]): number => {
    const LUNCH = 60;
    let total = 0;
    for (const row of cards) {
      if (row.id === null) continue; // 休日
      const tcS = new Date(`${row.date}T${row.startTime}:00`);
      const tcE = new Date(`${row.date}T${row.endTime}:00`);
      const ovS = tcS > ws ? tcS : ws;
      const ovE = tcE < we ? tcE : we;
      let diff = Math.round((ovE.getTime() - ovS.getTime()) / 60000);
      if (diff <= 0) continue;
      // overlap区間が昼をまたぐ（< 12:00 かつ > 13:00）→ -60分
      const sh = ovS.getHours() + ovS.getMinutes() / 60;
      const eh = ovE.getHours() + ovE.getMinutes() / 60;
      if (sh < 12 && eh > 13) diff -= LUNCH;
      if (diff > 0) total += diff;
    }
    return total;
  }, []);

  // 稼働時間を親に通知（rows変更時）
  React.useEffect(() => {
    if (rows.length === 0) return;
    const ws  = startedAt  ? new Date(startedAt)  : null;
    const ck  = checkedAt  ? new Date(checkedAt)  : null;
    const we  = finishedAt ? new Date(finishedAt) : null;
    const setupKadou = (ws && ck) ? calcKadouMin(ws, ck, rows) : null;
    const machKadou  = (ck && we) ? calcKadouMin(ck, we, rows) : null;
    onKadouChange(setupKadou, machKadou);
  }, [rows, startedAt, checkedAt, finishedAt, calcKadouMin, onKadouChange]);

  const updateRow = (idx: number, field: "startTime" | "endTime", val: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val, dirty: true } : r));
  };

  const handleUpdate = async (idx: number) => {
    const row = rows[idx];
    if (!token) { showToast("認証が必要です"); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      if (row.id !== null) {
        // 既存レコードを更新
        await mcApi.updateTimecard(row.id, {
          start_time: row.startTime + ":00",
          end_time:   row.endTime   + ":00",
        }, token);
      } else {
        // 休日レコードを新規作成（その日の作業を追加）
        const newCard = await mcApi.createTimecard({
          machine_id: machineId,
          work_date:  row.date,
          start_time: row.startTime + ":00",
          end_time:   row.endTime   + ":00",
        }, token);
        const newId = (newCard as any).data?.id ?? (newCard as any).id ?? null;
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, id: newId, dirty: false, saving: false } : r));
        showToast(`✅ ${row.date} タイムカード登録しました`);
        return;
      }
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.date} 更新しました`);
    } catch (e) {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast(`❌ 更新失敗`);
    }
  };

  const fmtKadou = (ws: string, we: string): string => {
    if (!ws || !we || rows.length === 0) return "—";
    const wsD = new Date(ws), weD = new Date(we);
    if (isNaN(wsD.getTime()) || isNaN(weD.getTime())) return "—";
    const min = calcKadouMin(wsD, weD, rows);
    return `${Math.floor(min / 60)}H ${min % 60}M`;
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 overflow-hidden flex flex-col max-h-[85vh]"
           onClick={e => e.stopPropagation()}>
        {/* ヘッダー */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-800 text-white shrink-0">
          <div>
            <p className="text-sm font-bold">🗓 機械タイムカード</p>
            <p className="text-xs text-slate-300 mt-0.5">機械: <span className="font-mono font-bold text-teal-300">{machineCode}</span>
              {startedAt && <span className="ml-2">{startedAt.slice(0, 10)} 〜 {(finishedAt || checkedAt || startedAt).slice(0, 10)}</span>}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors text-xl leading-none">✕</button>
        </div>

        {/* 稼働時間サマリー */}
        <div className="flex gap-0 border-b border-slate-100 bg-slate-50 shrink-0">
          {startedAt && checkedAt && (
            <div className="flex-1 px-4 py-2.5 border-r border-slate-200">
              <p className="text-[10px] text-slate-400 font-bold uppercase">段取稼働時間</p>
              <p className="text-base font-mono font-bold text-blue-700">{fmtKadou(startedAt, checkedAt)}</p>
              <p className="text-[10px] text-slate-400">{startedAt.slice(11, 16)} → {checkedAt.slice(11, 16)}</p>
            </div>
          )}
          {checkedAt && finishedAt && (
            <div className="flex-1 px-4 py-2.5 border-r border-slate-200">
              <p className="text-[10px] text-slate-400 font-bold uppercase">量産稼働時間</p>
              <p className="text-base font-mono font-bold text-green-700">{fmtKadou(checkedAt, finishedAt)}</p>
              <p className="text-[10px] text-slate-400">{checkedAt.slice(11, 16)} → {finishedAt.slice(11, 16)}</p>
            </div>
          )}
          {startedAt && finishedAt && (
            <div className="flex-1 px-4 py-2.5">
              <p className="text-[10px] text-slate-400 font-bold uppercase">総稼働時間</p>
              <p className="text-base font-mono font-bold text-slate-700">{fmtKadou(startedAt, finishedAt)}</p>
              <p className="text-[10px] text-slate-400">{startedAt.slice(11, 16)} → {finishedAt.slice(11, 16)}</p>
            </div>
          )}
        </div>

        {/* 凡例 */}
        <div className="flex items-center gap-4 px-5 py-2 bg-slate-50 border-b border-slate-100 text-[10px] text-slate-500 shrink-0">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-teal-100 inline-block border border-teal-300" />稼働日</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-100 inline-block border border-slate-300" />休日（タイムカードなし）</span>
          <span className="ml-auto text-slate-400">変更後「更新」で反映</span>
        </div>

        {/* テーブル */}
        <div className="overflow-y-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-400 text-sm">読み込み中…</div>
          ) : rows.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-slate-400 text-sm">期間を入力してください</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-bold text-slate-500 w-28">日付</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">開始</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">終了</th>
                  <th className="text-left px-3 py-2 text-xs font-bold text-slate-500">稼働</th>
                  <th className="px-3 py-2 w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row, idx) => {
                  const isHoliday = row.id === null && !row.dirty;
                  // この日の稼働分（overlap計算）
                  let dayMin = 0;
                  if (!isHoliday) {
                    const ws2 = startedAt  ? new Date(startedAt)  : new Date(`${row.date}T00:00`);
                    const we2 = finishedAt ? new Date(finishedAt) : new Date(`${row.date}T23:59`);
                    dayMin = calcKadouMin(ws2, we2, [row]);
                  }
                  const dayLabel = new Date(row.date + "T12:00").toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit", weekday: "short" });
                  return (
                    <tr key={row.date} className={`${isHoliday ? "bg-slate-50/80" : row.dirty ? "bg-amber-50" : "bg-white"} transition-colors`}>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-mono font-bold ${isHoliday ? "text-slate-400" : "text-slate-700"}`}>{dayLabel}</span>
                        {isHoliday && <span className="ml-1.5 text-[10px] text-slate-400 italic">― 休日 ―</span>}
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.startTime}
                          onChange={e => updateRow(idx, "startTime", e.target.value)}
                          className={`border rounded px-2 py-1 text-xs w-22 focus:ring-1 focus:ring-teal-400 focus:outline-none
                            ${isHoliday ? "border-slate-200 text-slate-400 bg-slate-50" : "border-slate-300"}`} />
                      </td>
                      <td className="px-3 py-2">
                        <input type="time" value={row.endTime}
                          onChange={e => updateRow(idx, "endTime", e.target.value)}
                          className={`border rounded px-2 py-1 text-xs w-22 focus:ring-1 focus:ring-teal-400 focus:outline-none
                            ${isHoliday ? "border-slate-200 text-slate-400 bg-slate-50" : "border-slate-300"}`} />
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-xs font-mono font-bold ${isHoliday ? "text-slate-300" : dayMin > 0 ? "text-teal-700" : "text-slate-400"}`}>
                          {isHoliday ? "—" : `${Math.floor(dayMin/60)}H${dayMin%60}M`}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        {row.dirty && (
                          <button onClick={() => handleUpdate(idx)} disabled={row.saving}
                            className="text-[11px] px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold disabled:opacity-50 transition-colors whitespace-nowrap">
                            {row.saving ? "…" : (row.id === null ? "登録" : "更新")}
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

        {/* フッター */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-white shrink-0">
          <p className="text-[10px] text-slate-400">
            ※ 稼働時間 = タイムカードと作業区間のoverlap（昼休み12:00〜13:00を自動控除）
          </p>
          <button onClick={onClose}
            className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-bold rounded-lg transition-colors">
            閉じる
          </button>
        </div>

        {/* トースト */}
        {toast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs px-4 py-2 rounded-full shadow-lg">
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
'''

EXPORT_MARKER = "\nexport default function McRecordPage()"
if EXPORT_MARKER in src and "TimecardModal" not in src:
    src = src.replace(EXPORT_MARKER, MODAL_COMPONENT + EXPORT_MARKER, 1)
    count += 1
    print("✅ TimecardModal コンポーネント追加")
else:
    print("⚠️ TimecardModal 追加スキップ（既存 or export行なし）")

# ────────────────────────────────────────────────────────────────────────
# 2. state追加: tcModalOpen, setupKadouMin, machKadouMin
#    (timeValidErr, tcWarnMsg はすでに前回スクリプトで追加済みの想定)
# ────────────────────────────────────────────────────────────────────────
OLD_STATE2 = "  const [timeValidErr, setTimeValidErr] = useState<string | null>(null);\n  const [tcWarnMsg, setTcWarnMsg] = useState<string | null>(null);"
NEW_STATE2 = """  const [timeValidErr, setTimeValidErr] = useState<string | null>(null);
  const [tcModalOpen, setTcModalOpen] = useState(false);
  const [setupKadouMin, setSetupKadouMin] = useState<number | null>(null);
  const [machKadouMin,  setMachKadouMin]  = useState<number | null>(null);"""

if OLD_STATE2 in src:
    src = src.replace(OLD_STATE2, NEW_STATE2, 1)
    count += 1
    print("✅ state追加: tcModalOpen, setupKadouMin, machKadouMin / tcWarnMsg削除")
else:
    # tcWarnMsgなし版（前回スクリプト未適用の場合）
    OLD_STATE2B = "  const [toast, setToast] = useState<string | null>(null);"
    if OLD_STATE2B in src and "tcModalOpen" not in src:
        src = src.replace(OLD_STATE2B,
            "  const [toast, setToast] = useState<string | null>(null);\n"
            "  const [timeValidErr, setTimeValidErr] = useState<string | null>(null);\n"
            "  const [tcModalOpen, setTcModalOpen] = useState(false);\n"
            "  const [setupKadouMin, setSetupKadouMin] = useState<number | null>(null);\n"
            "  const [machKadouMin,  setMachKadouMin]  = useState<number | null>(null);", 1)
        count += 1
        print("✅ state追加（toast後挿入）")
    else:
        print("⚠️ state追加スキップ")

# ────────────────────────────────────────────────────────────────────────
# 3. fetchTimecardStop 全体を削除（旧実装）
# ────────────────────────────────────────────────────────────────────────
# 前回スクリプト適用済みの場合の新版を削除
import re

# fetchTimecardStop 関数全体を削除（コメント行含む）
src_new = re.sub(
    r'  // 機械タイムカードから中断時間を算出.*?  \};\n',
    '',
    src,
    flags=re.DOTALL
)
if src_new != src:
    src = src_new
    count += 1
    print("✅ fetchTimecardStop 旧実装削除")
else:
    print("⚠️ fetchTimecardStop 削除スキップ（既に削除済み or 対象なし）")

# ────────────────────────────────────────────────────────────────────────
# 4. tcWarnMsg 表示ブロックを削除（前回追加分）
# ────────────────────────────────────────────────────────────────────────
src_new = re.sub(
    r'\s*\{/\* タイムカード未登録警告 \*/\}.*?\}\}\n',
    '\n',
    src,
    flags=re.DOTALL
)
if src_new != src:
    src = src_new
    count += 1
    print("✅ tcWarnMsg 表示ブロック削除")
else:
    print("⚠️ tcWarnMsg 削除スキップ")

# ────────────────────────────────────────────────────────────────────────
# 5. 段取セクションの「📋 TC参照」ボタン（段取中断横）を削除
# ────────────────────────────────────────────────────────────────────────
OLD_TC_BTN_SETUP = """                          {detail?.machine && startedAt && (
                            <button type="button" onClick={() => fetchTimecardStop("setup")}
                              className="text-[10px] px-2 py-1 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded font-bold transition-colors whitespace-nowrap ml-1">
                              📋 機械タイムカード参照
                            </button>
                          )}"""
if OLD_TC_BTN_SETUP in src:
    src = src.replace(OLD_TC_BTN_SETUP, "", 1)
    count += 1
    print("✅ 段取の旧TC参照ボタン削除")
else:
    print("⚠️ 段取の旧TC参照ボタン削除スキップ")

# ────────────────────────────────────────────────────────────────────────
# 6. 量産セクションの「📋 TC参照」ボタン（量産中断横）を削除
# ────────────────────────────────────────────────────────────────────────
OLD_TC_BTN_WORK = """                          {detail?.machine && checkedAt && (
                            <button type="button" onClick={() => fetchTimecardStop("work")}
                              className="text-[10px] px-2 py-1 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded font-bold transition-colors whitespace-nowrap ml-1">
                              📋 機械タイムカード参照
                            </button>
                          )}"""
if OLD_TC_BTN_WORK in src:
    src = src.replace(OLD_TC_BTN_WORK, "", 1)
    count += 1
    print("✅ 量産の旧TC参照ボタン削除")
else:
    print("⚠️ 量産の旧TC参照ボタン削除スキップ")

# ────────────────────────────────────────────────────────────────────────
# 7. 「機械タイムカード参照」ボタンを1か所に統合
#    段取グループの「段取開始」input の直後 (checkedAt input の後) に稼働時間+ボタンを追加
#    バリデーションエラー表示ブロックの直前（space-y-3の中の最初のgrid直前）に挿入
# ────────────────────────────────────────────────────────────────────────
OLD_GRID_START = """                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>"""

NEW_GRID_START = """                    {/* 機械タイムカード参照ボタン（1か所） */}
                    {detail?.machine && startedAt && (
                      <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 flex-wrap">
                            {setupKadouMin !== null && (
                              <span className="text-xs text-blue-700 font-bold">
                                段取稼働: {Math.floor(setupKadouMin/60)}H {setupKadouMin%60}M
                              </span>
                            )}
                            {machKadouMin !== null && (
                              <span className="text-xs text-green-700 font-bold">
                                量産稼働: {Math.floor(machKadouMin/60)}H {machKadouMin%60}M
                              </span>
                            )}
                            {setupKadouMin === null && machKadouMin === null && (
                              <span className="text-xs text-slate-400">タイムカードを確認して稼働時間を参照</span>
                            )}
                          </div>
                        </div>
                        <button type="button" onClick={() => setTcModalOpen(true)}
                          className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-300 hover:bg-teal-50 hover:border-teal-400 text-slate-700 hover:text-teal-700 rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                          🗓 機械タイムカード参照
                        </button>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>"""

if OLD_GRID_START in src:
    src = src.replace(OLD_GRID_START, NEW_GRID_START, 1)
    count += 1
    print("✅ 機械タイムカード参照ボタン（統合版）追加")
else:
    print("⚠️ TC参照ボタン統合版追加スキップ")

# ────────────────────────────────────────────────────────────────────────
# 8. TimecardModal コンポーネントをJSX内にマウント
#    AuthModal の直後に追加
# ────────────────────────────────────────────────────────────────────────
# AuthModalの閉じタグを探してTimecardModalを追加
OLD_AUTH_MODAL_END = """        {authOpen && (
          <AuthModal"""

# JSX末尾の </div> の手前（最後のreturn内）にTimecardModalを追加
# 安全のため、saveErrorの表示ブロック後に追加
OLD_SAVE_BTN_AREA = "        {/* セッションバナー */}"
NEW_SAVE_BTN_AREA = """        {/* 機械タイムカード参照モーダル */}
        {tcModalOpen && detail?.machine && (
          <TimecardModal
            open={tcModalOpen}
            onClose={() => setTcModalOpen(false)}
            machineCode={detail.machine.machineCode}
            machineId={detail.machine.id ?? parseInt(machineId) ?? 0}
            startedAt={startedAt}
            checkedAt={checkedAt}
            finishedAt={finishedAt}
            token={token}
            onKadouChange={(s, m) => { setSetupKadouMin(s); setMachKadouMin(m); }}
          />
        )}
        {/* セッションバナー */}"""

if OLD_SAVE_BTN_AREA in src:
    src = src.replace(OLD_SAVE_BTN_AREA, NEW_SAVE_BTN_AREA, 1)
    count += 1
    print("✅ TimecardModal JSXマウント追加")
else:
    print("⚠️ TimecardModal JSXマウント追加スキップ")

# ────────────────────────────────────────────────────────────────────────
# 書き込み
# ────────────────────────────────────────────────────────────────────────
if src == original:
    print("⚠️ 変更なし")
    sys.exit(0)

shutil.copy(TARGET, TARGET + ".bak")
with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)
print(f"\n✅ {count}件修正完了")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"],
                   cwd="/home/karkyon/projects/machcore/apps/web",
                   capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print(r.stdout[-4000:])
    print(r.stderr[-1000:])
    shutil.copy(TARGET + ".bak", TARGET)
    os.remove(TARGET + ".bak")
    sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r = subprocess.run(["npx", "next", "build"],
                   cwd="/home/karkyon/projects/machcore/apps/web",
                   capture_output=True, text=True)
if r.returncode != 0:
    print("❌ next build エラー:")
    print(r.stdout[-4000:])
    print(r.stderr[-1000:])
    shutil.copy(TARGET + ".bak", TARGET)
    os.remove(TARGET + ".bak")
    sys.exit(1)
print("✅ next build OK")

# pm2
subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True, text=True)
print("✅ pm2 restart")

# git
subprocess.run(["git", "add", "-A"], cwd="/home/karkyon/projects/machcore")
subprocess.run(["git", "commit", "-m",
    "feat: timecard modal - unified TC button, HowLong kadou calc, holiday display, inline edit"],
    cwd="/home/karkyon/projects/machcore")
r = subprocess.run(["git", "push"], cwd="/home/karkyon/projects/machcore",
                   capture_output=True, text=True)
print("✅ git push")
print(r.stderr.strip() or r.stdout.strip())

if os.path.exists(TARGET + ".bak"):
    os.remove(TARGET + ".bak")
