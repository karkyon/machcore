// ─────────────────────────────────────────────────────────────
// 稼働時間（段取・量産）計算の共通ロジック
// [v083] MC作業記録画面で「機械タイムカード参照モーダル」が計算する
//   実稼働時間と、フォーム上のプレビュー表示が別々の計算式を使っていたため、
//   同じ画面内で数値が一致しない不具合が発生した（段取19H0M vs 4H0M 等）。
//   稼働時間（＝タイムカードの出退勤時間と作業時間帯のoverlapから、
//   12:00-13:00の昼休みを控除した実働分）を算出する処理は、
//   必ずこのモジュールの calcKadouMinutes() のみを経由すること。
//   別の場所に同じ計算式を再実装しないこと。
// ─────────────────────────────────────────────────────────────

export interface KadouTimecardRow {
  /** タイムカードレコードID。null=その日のタイムカード未登録（休日扱い） */
  id: number | null;
  /** YYYY-MM-DD */
  date: string;
  /** HH:mm */
  startTime: string;
  /** HH:mm */
  endTime: string;
  /** UI上で未保存の変更がある場合true（id===nullでも稼働対象に含める） */
  dirty?: boolean;
}

/**
 * 指定範囲(rangeStart〜rangeEnd)とタイムカード(出退勤時間)のoverlapを日ごとに合計し、
 * 12:00-13:00の昼休み重複分を自動控除した実稼働分数を返す。
 *
 * 「段取開始〜段取終了」「段取終了〜加工終了」のような区間ごとに呼び出す。
 * タイムカード未登録日（id===null && !dirty）は稼働0として扱う。
 */
export function calcKadouMinutes(
  rangeStart: Date,
  rangeEnd: Date,
  rows: KadouTimecardRow[],
): number {
  let total = 0;
  for (const row of rows) {
    if (row.id === null && !row.dirty) continue;
    const tcS = new Date(row.date + "T" + row.startTime + ":00");
    const tcE = new Date(row.date + "T" + row.endTime + ":00");
    const ovS = tcS > rangeStart ? tcS : rangeStart;
    const ovE = tcE < rangeEnd ? tcE : rangeEnd;
    let diff = Math.round((ovE.getTime() - ovS.getTime()) / 60000);
    if (diff <= 0) continue;
    const lS = new Date(row.date + "T12:00:00");
    const lE = new Date(row.date + "T13:00:00");
    const loS = ovS > lS ? ovS : lS;
    const loE = ovE < lE ? ovE : lE;
    const lunchOverlap = Math.round((loE.getTime() - loS.getTime()) / 60000);
    if (lunchOverlap > 0) diff -= lunchOverlap;
    if (diff > 0) total += diff;
  }
  return total;
}

/** 分数を "1H 30M" 形式に整形する（稼働時間表示の共通フォーマッタ） */
export function fmtKadouMinutes(min: number): string {
  return Math.floor(min / 60) + "H " + (min % 60) + "M";
}
