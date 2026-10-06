// ══════════════════════════════════════════════════════════════════
// バージョン番号ユーティリティ(MC/NC共通)
//
// 形式: "X.YYZZ"(例: 1.0001)
//   X  = 整数部。大変更/新規登録/試作登録で+1(このときYYは00に戻す)
//   YY = 100分の1位。小変更/追加/修正/削除/訂正/不明 で+1(99を超えたらXへ繰り上げ)
//   ZZ = 10000分の1位(リビジョン)。インクリメントでは変更しない
// 新規作成(仮登録)時は 0.0001、「新規登録」で確定すると 1.0001 になる
// (旧ACCESSの新規段取シートにも「0.00 01」が印字されていた)。
//
// 旧NC(ACC_Lathe.Ver)は整数: 仮登録=1、新規登録/変更ごとに+100(101, 201, ...)。
//   百の位以上 → X、下2桁 → ZZ として "X.00ZZ" に変換する
//   (1 → 0.0001、101 → 1.0001、201 → 2.0001)。
//   scripts/nc_full_import_v2.py の legacy_nc_ver_to_version() と同じ規則。
//
// 従来のMC/NC finalize()は浮動小数点で計算していたため、0.0401→1.0000 のように
// リビジョン(ZZ)が欠ける誤差があった。ここでは整数(1/10000単位)で計算する。
// ══════════════════════════════════════════════════════════════════

export const INITIAL_VERSION = '0.0001';
export const MAJOR_CHANGE_TYPES = ['大変更', '新規登録', '試作登録'];

/** 旧NCの整数Ver → "X.00ZZ" */
export function legacyNcVerToVersion(n: number): string {
  const v = Math.max(0, Math.trunc(n));
  return `${Math.floor(v / 100)}.00${String(v % 100).padStart(2, '0')}`;
}

/** バージョン文字列 → 1/10000単位の整数。legacyNcInt=true なら整数のみの値を旧NC Verとして扱う */
function toUnits(ver: string | number | null | undefined, legacyNcInt: boolean): number {
  const s = String(ver ?? '').trim();
  if (legacyNcInt && /^\d+$/.test(s)) {
    const v = parseInt(s, 10);
    return Math.floor(v / 100) * 10000 + (v % 100);
  }
  const f = parseFloat(s);
  // 従来のMC/NC finalize()と同じく、解析できない値・0 は 1.0001 として扱う
  if (!isFinite(f) || f <= 0) return 10001;
  return Math.round(f * 10000);
}

function formatUnits(u: number): string {
  return `${Math.floor(u / 10000)}.${String(u % 10000).padStart(4, '0')}`;
}

/** "X.YYZZ" 形式にそろえる(旧NCの整数Verも変換する) */
export function normalizeVersion(ver: string | number | null | undefined, opts?: { legacyNcInt?: boolean }): string {
  return formatUnits(toUnits(ver, !!opts?.legacyNcInt));
}

/** 終了確認(finalize)の変更種別に応じて次のバージョンを返す */
export function bumpVersion(ver: string | number | null | undefined, changeType: string, opts?: { legacyNcInt?: boolean }): string {
  const u = toUnits(ver, !!opts?.legacyNcInt);
  let x = Math.floor(u / 10000);
  let y = Math.floor((u % 10000) / 100);
  const z = u % 100;
  if (MAJOR_CHANGE_TYPES.includes(changeType)) {
    x += 1; y = 0;
  } else {
    y += 1;
    if (y > 99) { x += 1; y = 0; }
  }
  return `${x}.${String(y).padStart(2, '0')}${String(z).padStart(2, '0')}`;
}
