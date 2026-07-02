/**
 * プログラムファイル/フォルダ命名規則 — 唯一の実装
 *
 * 【単体ファイルの場合】
 *   加工ID名のフォルダ(例: 8888)の下に、加工IDの下4桁をファイル名とした
 *   本体ファイル(例: 8888、5桁IDなら12345→2345)を配置する。
 *   フォルダ名は必ず加工ID(重複なし)のため、下4桁だけのファイル名でも
 *   重複の恐れは無い。
 *
 * 【フォルダ単位(メインPG+サブPG)の場合】
 *   加工ID名のフォルダ(例: 8888)の下に、"{加工ID}.pwd" という名前の
 *   サブフォルダ(例: 8888.pwd)を作り、その中にメインPG(.mpf)・サブPG(.spf)
 *   などの実ファイルを格納する。
 *
 * 単体/フォルダのどちらになるかは機械マスタ(Machine.pgIsFolder)で決まる。
 * このロジックを複数箇所に重複実装しない。新規登録画面・MC編集画面・
 * バックエンドの保存処理など、命名が必要な箇所は必ずこのモジュールを再利用すること。
 */

export type ProgramFileNaming = {
  /** true = フォルダ単位(メインPG+サブPG), false = 単体ファイル */
  isFolder: boolean;
  /** 画面表示用ラベル: "ファイル名" | "フォルダ名" */
  label: string;
  /** 自動決定される値(単体ファイルの場合はファイル名、フォルダ単位の場合はフォルダ名) */
  value: string;
};

/** 単体ファイルモードのファイル名(加工IDの下4桁)を算出する。 */
export function calcProgramFileName(machiningId: number): string {
  const s = String(machiningId);
  return s.length <= 4 ? s : s.slice(-4);
}

/** フォルダ単位モードのフォルダ名("{加工ID}.pwd")を算出する。 */
export function calcProgramFolderName(machiningId: number): string {
  return `${machiningId}.pwd`;
}

/**
 * 機械マスタのpgIsFolder設定に基づき、表示すべきラベルと値をまとめて返す。
 * machiningIdが未確定(null)の場合はnullを返す。
 */
export function calcProgramFileNaming(
  machiningId: number | null | undefined,
  isFolder: boolean,
): ProgramFileNaming | null {
  if (machiningId == null) return null;
  return isFolder
    ? { isFolder: true, label: "フォルダ名", value: calcProgramFolderName(machiningId) }
    : { isFolder: false, label: "ファイル名", value: calcProgramFileName(machiningId) };
}
