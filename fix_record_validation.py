#!/usr/bin/env python3
"""
作業記録画面 修正スクリプト
1. 時間入力バリデーション: 段取開始 < 段取終了(checkedAt) < 加工終了(finishedAt)
2. 「TC参照」ボタン → 「機械タイムカード参照」に変更
3. fetchTimecardStop の HowLong ロジック修正
   - 現在: タイムカードのoverlapで昼跨ぎ補正（誤）
   - 正しくは: 作業区間(ws〜we)が昼をまたぐか否かで-60分
   - 複数日またがり時は終了日のタイムカードも取得
4. タイムカードなし時のUI警告バナー追加
"""
import re, subprocess, shutil, os, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"

if not os.path.exists(TARGET):
    print(f"ファイルが見つかりません: {TARGET}")
    sys.exit(1)

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

original = src
count = 0

# ────────────────────────────────────────────────────
# 1. state追加: timeValidErr, tcWarnMsg
# ────────────────────────────────────────────────────
OLD_STATE_BLOCK = "  const [toast, setToast] = useState<string | null>(null);"
NEW_STATE_BLOCK = """  const [toast, setToast] = useState<string | null>(null);
  const [timeValidErr, setTimeValidErr] = useState<string | null>(null);
  const [tcWarnMsg, setTcWarnMsg] = useState<string | null>(null);"""

if OLD_STATE_BLOCK in src and "timeValidErr" not in src:
    src = src.replace(OLD_STATE_BLOCK, NEW_STATE_BLOCK, 1)
    count += 1
    print("✅ state追加: timeValidErr, tcWarnMsg")
else:
    print("⚠️ state追加スキップ（既存または対象行なし）")

# ────────────────────────────────────────────────────
# 2. バリデーション関数追加（fetchTimecardStop の直前に挿入）
# ────────────────────────────────────────────────────
VALDATE_FN = """
  // ── 日時バリデーション: 段取開始 < 段取終了 < 加工終了 ───────────────
  const validateDateOrder = (sa: string, ca: string, fa: string): string | null => {
    if (sa && ca) {
      if (new Date(ca) <= new Date(sa)) return "段取終了は段取開始より後の日時を入力してください";
    }
    if (ca && fa) {
      if (new Date(fa) <= new Date(ca)) return "加工終了は段取終了（チェックTime）より後の日時を入力してください";
    }
    if (sa && fa && !ca) {
      if (new Date(fa) <= new Date(sa)) return "加工終了は段取開始より後の日時を入力してください";
    }
    return null;
  };

"""

TC_FETCH_MARKER = "  // 機械タイムカードから中断時間を算出（HowLong関数準拠）"
if TC_FETCH_MARKER in src and "validateDateOrder" not in src:
    src = src.replace(TC_FETCH_MARKER, VALDATE_FN + TC_FETCH_MARKER, 1)
    count += 1
    print("✅ validateDateOrder 関数追加")
else:
    print("⚠️ validateDateOrder 追加スキップ")

# ────────────────────────────────────────────────────
# 3. fetchTimecardStop 全体を差し替え（HowLong準拠の正しいロジックに）
# ────────────────────────────────────────────────────
OLD_TC_FETCH = """  // 機械タイムカードから中断時間を算出（HowLong関数準拠）
  const fetchTimecardStop = async (phase: "setup" | "work") => {
    if (!detail?.machine) return;
    const refStart = phase === "setup" ? startedAt  : checkedAt;
    const refEnd   = phase === "setup" ? checkedAt  : finishedAt;
    if (!refStart) { alert("開始日時を先に入力してください"); return; }
    const workDate = refStart.slice(0, 10);
    try {
      const r = await mcApi.timecardsByDate(workDate);
      const allCards: any[] = (r as any).data ?? [];
      // この機械のタイムカードを抽出（machineCodeで突き合わせ）
      const machCode = detail.machine?.machineCode;
      const cards = allCards.filter((c: any) => c.machine?.machineCode === machCode);
      if (cards.length === 0) {
        alert(`${workDate} の機械(${machCode})のタイムカードがありません`);
        return;
      }
      // HowLong関数：タイムカードから稼働時間を計算
      // 参照区間（phase開始〜終了）に被るタイムカードを合算
      // 昼跨ぎ（開始<13:00 && 終了>=13:00）は-60分
      const ws = refStart ? new Date(refStart) : null;
      const we = refEnd   ? new Date(refEnd)   : null;
      let totalKadouMin = 0;
      for (const c of cards) {
        const tcDate = c.work_date?.slice(0, 10) ?? workDate;
        const tcS = new Date(`${tcDate}T${c.start_time?.slice(0, 8) ?? "00:00:00"}`);
        const tcE = new Date(`${tcDate}T${c.end_time?.slice(0,   8) ?? "00:00:00"}`);
        // タイムカードと参照区間の重複を計算
        const overlapS = ws ? (tcS > ws ? tcS : ws) : tcS;
        const overlapE = we ? (tcE < we ? tcE : we) : tcE;
        let diffMin = Math.round((overlapE.getTime() - overlapS.getTime()) / 60000);
        if (diffMin <= 0) continue;
        // 昼跨ぎ補正（-60分）
        const sh = tcS.getHours();
        const eh = tcE.getHours();
        if (sh < 13 && eh >= 13) diffMin -= 60;
        if (diffMin > 0) totalKadouMin += diffMin;
      }
      // 参照区間の経過時間
      let elapsedMin = 0;
      if (ws && we) elapsedMin = Math.round((we.getTime() - ws.getTime()) / 60000);
      else if (ws)  elapsedMin = 0;
      // 中断時間 = 経過時間 - 機械稼働時間
      const stopMin = Math.max(0, elapsedMin - totalKadouMin);
      const h = Math.floor(stopMin / 60);
      const m = stopMin % 60;
      if (phase === "setup") { setDStopH(h); setDStopM(m); }
      else                   { setYStopH(h); setYStopM(m); }
      console.log(`[TC参照] phase=${phase} elapsed=${elapsedMin}min kadou=${totalKadouMin}min stop=${stopMin}min`);
    } catch (e) {
      console.error("[TC参照] エラー", e);
      alert("タイムカード取得に失敗しました");
    }
  };"""

NEW_TC_FETCH = """  // 機械タイムカードから中断時間を算出（HowLong関数準拠）
  const fetchTimecardStop = async (phase: "setup" | "work") => {
    if (!detail?.machine) return;
    const refStart = phase === "setup" ? startedAt  : checkedAt;
    const refEnd   = phase === "setup" ? checkedAt  : finishedAt;
    if (!refStart) { alert("開始日時を先に入力してください"); return; }
    const machCode = detail.machine?.machineCode;
    const ws = new Date(refStart);
    const we = refEnd ? new Date(refEnd) : null;
    const startDate = refStart.slice(0, 10);
    const endDate   = refEnd   ? refEnd.slice(0, 10) : startDate;

    try {
      // 開始日〜終了日のタイムカードを全て取得（複数日またがり対応）
      const dateSet: string[] = [];
      let d = new Date(startDate);
      const dEnd = new Date(endDate);
      while (d <= dEnd) {
        dateSet.push(d.toISOString().slice(0, 10));
        d.setDate(d.getDate() + 1);
      }

      const allCardsByDate: Record<string, any[]> = {};
      for (const dt of dateSet) {
        const r = await mcApi.timecardsByDate(dt);
        const cards: any[] = ((r as any).data ?? []).filter((c: any) => c.machine?.machineCode === machCode);
        if (cards.length > 0) allCardsByDate[dt] = cards;
      }

      const missingDates = dateSet.filter(dt => !allCardsByDate[dt]);
      if (missingDates.length > 0) {
        setTcWarnMsg(`⚠️ 機械(${machCode})のタイムカードが未登録の日付があります: ${missingDates.join(", ")} — 正確な中断時間を計算できません`);
        // タイムカードが一切ない場合は中断できない
        if (Object.keys(allCardsByDate).length === 0) return;
      } else {
        setTcWarnMsg(null);
      }

      /**
       * HowLong関数 準拠の稼働時間計算
       * 正しい昼跨ぎ判定: 作業区間 (ws〜we) が 12:00未満〜13:00以降をまたぐか
       * ただしタイムカードの実稼働記録と作業区間のoverlapを使う
       */
      const LUNCH_MIN = 60; // 昼休み60分

      // タイムカードの overlap 稼働時間を合算
      let totalKadouMin = 0;
      for (const [dt, cards] of Object.entries(allCardsByDate)) {
        for (const c of cards) {
          const tcS = new Date(`${dt}T${(c.start_time ?? "00:00:00").slice(0, 8)}`);
          const tcE = new Date(`${dt}T${(c.end_time   ?? "00:00:00").slice(0, 8)}`);
          // タイムカードと作業区間のoverlap
          const ovS = tcS > ws ? tcS : ws;
          const ovE = we ? (tcE < we ? tcE : we) : tcE;
          let diffMin = Math.round((ovE.getTime() - ovS.getTime()) / 60000);
          if (diffMin <= 0) continue;

          // 昼跨ぎ補正: overlap区間が 12:00未満 → 13:00以降 をまたぐ場合 -60分
          const ovSh = ovS.getHours() + ovS.getMinutes() / 60;
          const ovEh = ovE.getHours() + ovE.getMinutes() / 60;
          if (ovSh < 12 && ovEh > 13) diffMin -= LUNCH_MIN;

          if (diffMin > 0) totalKadouMin += diffMin;
        }
      }

      // 参照区間の経過時間 (単純な時刻差)
      const elapsedMin = we ? Math.round((we.getTime() - ws.getTime()) / 60000) : 0;

      // 中断時間 = 経過時間 - 機械稼働時間
      const stopMin = Math.max(0, elapsedMin - totalKadouMin);
      const h = Math.floor(stopMin / 60);
      const m = stopMin % 60;
      if (phase === "setup") { setDStopH(h); setDStopM(m); }
      else                   { setYStopH(h); setYStopM(m); }
      console.log(`[TC参照] phase=${phase} elapsed=${elapsedMin}min kadou=${totalKadouMin}min stop=${stopMin}min`);
    } catch (e) {
      console.error("[TC参照] エラー", e);
      alert("タイムカード取得に失敗しました");
    }
  };"""

if OLD_TC_FETCH in src:
    src = src.replace(OLD_TC_FETCH, NEW_TC_FETCH, 1)
    count += 1
    print("✅ fetchTimecardStop HowLong ロジック修正")
else:
    print("⚠️ fetchTimecardStop 差し替えスキップ（対象行なし）")

# ────────────────────────────────────────────────────
# 4. handleSubmit に日時バリデーション追加
# ────────────────────────────────────────────────────
OLD_SUBMIT_TOP = """  const handleSubmit = async () => {
    console.log("[STEP2] handleSubmit sbMode=", sbMode, "token=", token ? "あり" : "なし", "isAuthenticated=", isAuthenticated);
    if (!token) { setSaveError("認証セッションが切れています。再認証してください。"); setAuthOpen(true); return; }"""

NEW_SUBMIT_TOP = """  const handleSubmit = async () => {
    console.log("[STEP2] handleSubmit sbMode=", sbMode, "token=", token ? "あり" : "なし", "isAuthenticated=", isAuthenticated);
    if (!token) { setSaveError("認証セッションが切れています。再認証してください。"); setAuthOpen(true); return; }
    // 日時バリデーション
    if (timeMode === "datetime") {
      const vErr = validateDateOrder(startedAt, checkedAt, finishedAt);
      if (vErr) { setTimeValidErr(vErr); return; }
    }
    setTimeValidErr(null);"""

if OLD_SUBMIT_TOP in src:
    src = src.replace(OLD_SUBMIT_TOP, NEW_SUBMIT_TOP, 1)
    count += 1
    print("✅ handleSubmit バリデーション追加")
else:
    print("⚠️ handleSubmit バリデーション追加スキップ")

# ────────────────────────────────────────────────────
# 5. onChange でリアルタイムバリデーション: 段取終了
# ────────────────────────────────────────────────────
OLD_CHECKED_INPUT = """        <input type="datetime-local" value={checkedAt} onChange={e => setCheckedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />"""

NEW_CHECKED_INPUT = """        <input type="datetime-local" value={checkedAt}
                          onChange={e => { setCheckedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, e.target.value, finishedAt)); }}
                          className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("段取終了") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />"""

if OLD_CHECKED_INPUT in src:
    src = src.replace(OLD_CHECKED_INPUT, NEW_CHECKED_INPUT, 1)
    count += 1
    print("✅ checkedAt バリデーション onChange追加")
else:
    print("⚠️ checkedAt onChange スキップ")

# ────────────────────────────────────────────────────
# 6. onChange でリアルタイムバリデーション: 加工終了
# ────────────────────────────────────────────────────
OLD_FINISHED_INPUT = """        <input type="datetime-local" value={finishedAt} onChange={e => setFinishedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />"""

NEW_FINISHED_INPUT = """        <input type="datetime-local" value={finishedAt}
                          onChange={e => { setFinishedAt(e.target.value); setTimeValidErr(validateDateOrder(startedAt, checkedAt, e.target.value)); }}
                          className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 ${timeValidErr && timeValidErr.includes("加工終了") ? "border-red-400 bg-red-50" : "border-slate-200"}`} />"""

if OLD_FINISHED_INPUT in src:
    src = src.replace(OLD_FINISHED_INPUT, NEW_FINISHED_INPUT, 1)
    count += 1
    print("✅ finishedAt バリデーション onChange追加")
else:
    print("⚠️ finishedAt onChange スキップ")

# ────────────────────────────────────────────────────
# 7. 段取開始 input にも onChange バリデーション追加
# ────────────────────────────────────────────────────
OLD_STARTED_INPUT = """        <input type="datetime-local" value={startedAt} onChange={e => setStartedAt(e.target.value)}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />"""

NEW_STARTED_INPUT = """        <input type="datetime-local" value={startedAt}
                          onChange={e => { setStartedAt(e.target.value); setTimeValidErr(validateDateOrder(e.target.value, checkedAt, finishedAt)); }}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />"""

if OLD_STARTED_INPUT in src:
    src = src.replace(OLD_STARTED_INPUT, NEW_STARTED_INPUT, 1)
    count += 1
    print("✅ startedAt バリデーション onChange追加")
else:
    print("⚠️ startedAt onChange スキップ")

# ────────────────────────────────────────────────────
# 8. バリデーションエラー表示 & タイムカード警告表示を段取ブロックに追加
#    段取開始ラベルの前（ timeMode === "datetime" の <div className="space-y-3"> 直後）
# ────────────────────────────────────────────────────
OLD_SPACE_Y3 = """                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>"""

NEW_SPACE_Y3 = """                ) : (
                  <div className="space-y-3">
                    {/* 日時バリデーションエラー */}
                    {timeValidErr && (
                      <div className="flex items-center gap-2 bg-red-50 border border-red-300 rounded-lg px-3 py-2 text-xs text-red-700 font-bold">
                        <span>⛔</span><span>{timeValidErr}</span>
                      </div>
                    )}
                    {/* タイムカード未登録警告 */}
                    {tcWarnMsg && (
                      <div className="flex items-start gap-2 bg-amber-50 border border-amber-300 rounded-lg px-3 py-2 text-xs text-amber-800">
                        <span className="shrink-0 mt-0.5">⚠️</span>
                        <div>
                          <p className="font-bold">機械タイムカード未登録</p>
                          <p className="mt-0.5 font-normal">{tcWarnMsg.replace("⚠️ ", "")}</p>
                          <p className="mt-1 text-amber-600">中断時間を手動で入力してください</p>
                        </div>
                        <button className="ml-auto shrink-0 text-amber-500 hover:text-amber-700" onClick={() => setTcWarnMsg(null)}>✕</button>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-bold text-slate-500 block mb-1.5">段取開始</label>"""

if OLD_SPACE_Y3 in src:
    src = src.replace(OLD_SPACE_Y3, NEW_SPACE_Y3, 1)
    count += 1
    print("✅ バリデーションエラー表示 & タイムカード警告バナー追加")
else:
    print("⚠️ 警告バナー追加スキップ")

# ────────────────────────────────────────────────────
# 9. 「TC参照」→「機械タイムカード参照」ラベル変更（2箇所）
# ────────────────────────────────────────────────────
tc_count = src.count("📋 TC参照")
if tc_count > 0:
    src = src.replace("📋 TC参照", "📋 機械タイムカード参照")
    count += tc_count
    print(f"✅ 「TC参照」→「機械タイムカード参照」変更: {tc_count}箇所")
else:
    print("⚠️ TC参照ラベル変更スキップ（対象なし）")

# ────────────────────────────────────────────────────
# 書き込み
# ────────────────────────────────────────────────────
if src == original:
    print("⚠️ 変更なし")
    sys.exit(0)

shutil.copy(TARGET, TARGET + ".bak")
with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)
print(f"\n✅ {count}件修正完了")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"], cwd="/home/karkyon/projects/machcore/apps/web", capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print(r.stdout[-3000:]); print(r.stderr[-1000:])
    # リストア
    shutil.copy(TARGET + ".bak", TARGET)
    os.remove(TARGET + ".bak")
    sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r = subprocess.run(["npx", "next", "build"], cwd="/home/karkyon/projects/machcore/apps/web", capture_output=True, text=True)
if r.returncode != 0:
    print("❌ next build エラー:")
    print(r.stdout[-3000:]); print(r.stderr[-1000:])
    shutil.copy(TARGET + ".bak", TARGET)
    os.remove(TARGET + ".bak")
    sys.exit(1)
print("✅ next build OK")

# pm2 restart
r = subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True, text=True)
print("✅ pm2 restart")

# git
subprocess.run(["git", "add", "-A"], cwd="/home/karkyon/projects/machcore")
subprocess.run(["git", "commit", "-m", "feat: record page - datetime validation, HowLong fix, TC button label, TC warning banner"],
               cwd="/home/karkyon/projects/machcore")
r = subprocess.run(["git", "push"], cwd="/home/karkyon/projects/machcore", capture_output=True, text=True)
print("✅ git push")
print(r.stderr.strip() or r.stdout.strip())

# .bakを削除
if os.path.exists(TARGET + ".bak"):
    os.remove(TARGET + ".bak")
