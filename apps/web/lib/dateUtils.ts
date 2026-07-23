// ─────────────────────────────────────────────────────────────
// TimeZone(Asia/Tokyo)共通ユーティリティ
// [TZ監査 2026-07-08] DBのDateTime(タイムゾーン情報なし、実質UTCの壁時計値として
//   保存)をISO文字列のまま `.slice(0, 10)` 等で切り出すと**UTCの暦日**になって
//   しまい、JST 00:00〜08:59の間は「前日」と表示される不具合が複数箇所で
//   発生していた(NC編集画面「入力日」など)。
//   日時から「JSTでの暦日/時刻」を取り出す処理は、必ずこのモジュールの
//   関数のみを経由すること。`.slice(0, 10)`によるISO文字列の直接切り出しや、
//   timeZone未指定の toLocaleDateString / toLocaleString / toLocaleTimeString は
//   使用しないこと(ブラウザ側のTZ設定に依存してしまうため)。
// ─────────────────────────────────────────────────────────────

const JST = "Asia/Tokyo";

function parse(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return null;
  return d;
}

/** ISO文字列 or Date を、JSTでの "YYYY-MM-DD" に変換する。null/undefined/不正値はnullを返す。 */
export function toJstDateString(value: string | number | Date | null | undefined): string | null {
  const d = parse(value);
  if (!d) return null;
  return d.toLocaleDateString("sv-SE", { timeZone: JST });
}

/** ISO文字列 or Date を、JSTでの "HH:mm" に変換する。 */
export function toJstTimeString(value: string | number | Date | null | undefined): string | null {
  const d = parse(value);
  if (!d) return null;
  return d.toLocaleTimeString("ja-JP", { timeZone: JST, hour: "2-digit", minute: "2-digit", hour12: false });
}

/** ISO文字列 or Date を、JSTでの "YYYY-MM-DD HH:mm" に変換する。 */
export function toJstDateTimeString(value: string | number | Date | null | undefined): string | null {
  const datePart = toJstDateString(value);
  const timePart = toJstTimeString(value);
  if (!datePart || !timePart) return null;
  return `${datePart} ${timePart}`;
}

/** ISO文字列 or Date を、JSTでの "MM/DD" に変換する(一覧表示等の短縮表記用)。 */
export function toJstMonthDayString(value: string | number | Date | null | undefined): string | null {
  const d = parse(value);
  if (!d) return null;
  return d.toLocaleDateString("ja-JP", { timeZone: JST, month: "2-digit", day: "2-digit" });
}

/** ISO文字列 or Date を、JSTでの "MM/DD HH:mm" に変換する(一覧表示等の短縮表記用)。 */
export function toJstMonthDayTimeString(value: string | number | Date | null | undefined): string | null {
  const d = parse(value);
  if (!d) return null;
  return d.toLocaleDateString("ja-JP", { timeZone: JST, month: "2-digit", day: "2-digit" }) + " " +
         d.toLocaleTimeString("ja-JP", { timeZone: JST, hour: "2-digit", minute: "2-digit", hour12: false });
}

/** ISO文字列 or Date を、JSTでの "YY/MM/DD HH:mm" (西暦下2桁付き)に変換する(一覧表示等の短縮表記用)。 */
export function toJstYearMonthDayTimeString(value: string | number | Date | null | undefined): string | null {
  const d = parse(value);
  if (!d) return null;
  // year:"2-digit"をja-JPロケールで単独指定すると「26年」のように単位文字が
  // 付与されてしまうため、sv-SEロケールの "YYYY-MM-DD" から数字のみ抽出する
  // (toJstDateString と同じ安全な取得方法)。
  const isoDate = d.toLocaleDateString("sv-SE", { timeZone: JST }); // "YYYY-MM-DD"
  const year2 = isoDate.slice(2, 4);
  const monthDay = d.toLocaleDateString("ja-JP", { timeZone: JST, month: "2-digit", day: "2-digit" });
  const time = d.toLocaleTimeString("ja-JP", { timeZone: JST, hour: "2-digit", minute: "2-digit", hour12: false });
  return `${year2}/${monthDay} ${time}`;
}

/** 現在時刻のJSTでの "YYYY-MM-DD" を返す(「今日」判定などに使用)。 */
export function nowJstDateString(): string {
  return toJstDateString(new Date())!;
}
