// apps/api/src/mc/program-file-naming.util.ts
//
// プログラムファイル/フォルダ命名規則 — バックエンド側の唯一の実装。
// フロント側の同等ロジックは apps/web/lib/programFileNaming.ts (表示プレビュー用)。
// DB書き込みを伴う実際の命名決定は、必ずこのモジュールの関数を経由すること。
//
// 【単体ファイルの場合】
//   加工ID名のフォルダ(例: 8888)の下に、加工IDの下4桁をファイル名とした
//   本体ファイル(例: 8888、5桁IDなら12345→2345、拡張子無)を配置する。
//
// 【フォルダ単位(メインPG+サブPG)の場合】
//   加工ID名のフォルダ(例: 8888)の下に、"{加工ID}.pwd" という名前の
//   サブフォルダ(例: 8888.pwd)を作り、その中にメインPG・サブPGなどの
//   実ファイル(元のファイル名のまま)を格納する。

/** 単体ファイルモードのファイル名(加工IDの下4桁、拡張子無)を算出する。 */
export function calcProgramFileName(machiningId: number): string {
  const s = String(machiningId);
  return s.length <= 4 ? s : s.slice(-4);
}

/** フォルダ単位モードのフォルダ名("{加工ID}.pwd")を算出する。 */
export function calcProgramFolderName(machiningId: number): string {
  return `${machiningId}.pwd`;
}
