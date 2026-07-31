/**
 * upload-agent.ts — MachCore UploadAgent (localhost:57301) 連携ライブラリ
 *
 * 新アーキテクチャ（Agent側ダイアログ方式）:
 * Web はファイル選択を一切行わず、Agentへ「ダイアログを開いてアップロードしろ」と
 * 依頼するだけ。ダイアログ表示・重複確認・アップロード・削除はすべてAgent内で完結する。
 *
 * セキュリティは3層防御:
 *  1. Origin検証 (Agent側): MachCore正規オリジン以外のリクエストを拒否
 *  2. ワンタイムチケット: BearerトークンはAgentに渡さず、60秒・1回限りのチケットを発行して渡す
 *  3. 接続先固定: AgentはMachCore APIのURLを自身のappsettings.jsonから読む（Webから指定させない）
 */
const AGENT_BASE = "http://localhost:57301";
const TIMEOUT_MS = 3000;
const DIALOG_TIMEOUT_MS = 5 * 60 * 1000; // ダイアログ操作待ちのため長め

export type AgentHealth = { status: string; version: string; token: string };

export async function getAgentToken(): Promise<string | null> {
  try {
    const res = await fetch(`${AGENT_BASE}/health`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) return null;
    const json: AgentHealth = await res.json();
    return json.token ?? null;
  } catch { return null; }
}

export async function isAgentOnline(): Promise<boolean> {
  const token = await getAgentToken();
  console.log("[UploadAgent] health check:", token ? "ONLINE ✅" : "OFFLINE ❌");
  return token !== null;
}

export type AgentUploadFileResult = {
  originalName: string;
  storedName:   string;
  fileId:       number;
  duplicateHandled: boolean;
  duplicateMovedTo?: string;
  localDeleted: boolean;
  localDeleteError?: string;
};

export type PickAndUploadResult = {
  agentAvailable: boolean;
  cancelled:      boolean;
  success:        boolean;
  files: AgentUploadFileResult[];
  error?: string;
  /** [多言語対応] Agent(v1.2.0+)が返す機械可読なエラー種別。旧Agentとの通信時はundefined。 */
  errorCode?: string;
  errorParams?: Record<string, string>;
};

export type PgToUsbResult = {
  agentAvailable: boolean;
  success:        boolean;
  copiedFiles: string[];
  destPath?:   string;
  error?:      string;
  /** [多言語対応] Agent(v1.2.0+)が返す機械可読なエラー種別。旧Agentとの通信時はundefined。 */
  errorCode?: string;
  errorParams?: Record<string, string>;
};

/**
 * Agentへ「PGファイルをチケットで取得し、設定済みUSBドライブへ直接コピー」を依頼する。
 * ダイアログは一切表示しない（USB保存先はAgent設定で事前固定済み）。
 *
 * [v116] system("mc"|"nc")を必ず渡すこと。Agent側はこれを見て
 * `/mc/files/pg-info-by-ticket` または `/nc/files/pg-info-by-ticket` のどちらを
 * 呼び出すか決定する。省略時はAgent側で"mc"として扱われる(後方互換)。
 */
export async function agentPgToUsb(ticket: string, apiBaseUrl: string, system: "mc" | "nc" = "mc"): Promise<PgToUsbResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, success: false, copiedFiles: [], error: "Agent未起動", errorCode: "AGENT_NOT_RUNNING" };

  try {
    console.log("[Agent] /pg-to-usb 依頼開始 ticket=", ticket, "system=", system);
    const res = await fetch(`${AGENT_BASE}/pg-to-usb`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, apiBaseUrl, system }),
      signal:  AbortSignal.timeout(TIMEOUT_MS * 4),
    });
    const json = await res.json();
    console.log("[Agent] /pg-to-usb 結果:", json);
    if (!res.ok) return { agentAvailable: true, success: false, copiedFiles: [], error: json.error ?? `HTTP ${res.status}`, errorCode: json.errorCode, errorParams: json.errorParams };
    return { agentAvailable: true, success: json.success ?? false, copiedFiles: json.copiedFiles ?? [], destPath: json.destPath, error: json.error, errorCode: json.errorCode, errorParams: json.errorParams };
  } catch (e: any) {
    console.error("[Agent] /pg-to-usb エラー:", e);
    return { agentAvailable: true, success: false, copiedFiles: [], error: e.message, errorCode: "AGENT_COMMUNICATION_ERROR", errorParams: { detail: e.message ?? "" } };
  }
}

/**
 * Agentへ「単体ファイル選択→アップロード→ローカル削除」を一括依頼する。
 * Agent内でネイティブファイルダイアログが表示される。
 */
export async function agentPickAndUpload(ticket: string, fileType?: string, uploadPath?: string): Promise<PickAndUploadResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, cancelled: false, success: false, files: [], error: "Agent未起動", errorCode: "AGENT_NOT_RUNNING" };

  try {
    const res = await fetch(`${AGENT_BASE}/pick-and-upload`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, fileType, uploadPath }),
      signal:  AbortSignal.timeout(DIALOG_TIMEOUT_MS),
    });
    const json = await res.json();
    if (!res.ok) return { agentAvailable: true, cancelled: false, success: false, files: [], error: json.error ?? `HTTP ${res.status}`, errorCode: json.errorCode, errorParams: json.errorParams };
    return {
      agentAvailable: true, cancelled: json.cancelled ?? false, success: json.success ?? false,
      files: json.files ?? [], error: json.error, errorCode: json.errorCode, errorParams: json.errorParams,
    };
  } catch(e: any) {
    console.error("[Agent] /pick-and-upload エラー:", e);
    return { agentAvailable: true, cancelled: false, success: false, files: [], error: e.message, errorCode: "AGENT_COMMUNICATION_ERROR", errorParams: { detail: e.message ?? "" } };
  }
}

/**
 * Agentへ「フォルダ選択→フォルダ内全ファイルアップロード→ローカル削除」を一括依頼する。
 */
export async function agentPickFolderAndUpload(ticket: string, fileType?: string, uploadPath?: string): Promise<PickAndUploadResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, cancelled: false, success: false, files: [], error: "Agent未起動", errorCode: "AGENT_NOT_RUNNING" };

  try {
    const res = await fetch(`${AGENT_BASE}/pick-folder-and-upload`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, fileType, uploadPath }),
      signal:  AbortSignal.timeout(DIALOG_TIMEOUT_MS),
    });
    const json = await res.json();
    if (!res.ok) return { agentAvailable: true, cancelled: false, success: false, files: [], error: json.error ?? `HTTP ${res.status}`, errorCode: json.errorCode, errorParams: json.errorParams };
    return {
      agentAvailable: true, cancelled: json.cancelled ?? false, success: json.success ?? false,
      files: json.files ?? [], error: json.error, errorCode: json.errorCode, errorParams: json.errorParams,
    };
  } catch(e: any) {
    console.error("[Agent] /pick-folder-and-upload エラー:", e);
    return { agentAvailable: true, cancelled: false, success: false, files: [], error: e.message, errorCode: "AGENT_COMMUNICATION_ERROR", errorParams: { detail: e.message ?? "" } };
  }
}

export type CheckUsbTargetResult = {
  agentAvailable: boolean;
  success:        boolean;
  configured:     boolean;
  exists:         boolean;
  path?:          string;
  error?:         string;
  /** [多言語対応] Agent(v1.2.0+)が返す機械可読なエラー種別。旧Agentとの通信時はundefined。 */
  errorCode?: string;
  errorParams?: Record<string, string>;
};

/**
 * Agentへ「USB取込元フォルダ内に指定名のファイル/フォルダが実在するか」を確認させる。
 * ファイル/フォルダ選択ダイアログは表示しない。新規登録時に確定済みのファイル名/
 * フォルダ名(DB由来)をnameに渡すことで、USB内の対象物の存在有無だけを問い合わせる。
 */
export async function agentCheckUsbTarget(name: string, isFolder: boolean): Promise<CheckUsbTargetResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, success: false, configured: false, exists: false, error: "Agent未起動", errorCode: "AGENT_NOT_RUNNING" };

  try {
    const res = await fetch(`${AGENT_BASE}/check-usb-target`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ name, isFolder }),
      signal:  AbortSignal.timeout(TIMEOUT_MS * 2),
    });
    const json = await res.json();
    return {
      agentAvailable: true, success: json.success ?? false, configured: json.configured ?? false,
      exists: json.exists ?? false, path: json.path, error: json.error, errorCode: json.errorCode, errorParams: json.errorParams,
    };
  } catch (e: any) {
    console.error("[Agent] /check-usb-target エラー:", e);
    return { agentAvailable: true, success: false, configured: false, exists: false, error: e.message, errorCode: "AGENT_COMMUNICATION_ERROR", errorParams: { detail: e.message ?? "" } };
  }
}

/**
 * Agentへ「USB取込元フォルダ内の既定名ファイル/フォルダをそのままアップロード」を依頼する。
 * agentCheckUsbTargetで実在確認済みであることを前提とし、選択ダイアログは一切表示しない。
 */
export async function agentAutoUpload(ticket: string, fileType: string, name: string, isFolder: boolean, uploadPath?: string): Promise<PickAndUploadResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, cancelled: false, success: false, files: [], error: "Agent未起動", errorCode: "AGENT_NOT_RUNNING" };

  try {
    const res = await fetch(`${AGENT_BASE}/auto-upload`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, fileType, name, isFolder, uploadPath }),
      signal:  AbortSignal.timeout(DIALOG_TIMEOUT_MS),
    });
    const json = await res.json();
    if (!res.ok) return { agentAvailable: true, cancelled: false, success: false, files: [], error: json.error ?? `HTTP ${res.status}`, errorCode: json.errorCode, errorParams: json.errorParams };
    return {
      agentAvailable: true, cancelled: json.cancelled ?? false, success: json.success ?? false,
      files: json.files ?? [], error: json.error, errorCode: json.errorCode, errorParams: json.errorParams,
    };
  } catch(e: any) {
    console.error("[Agent] /auto-upload エラー:", e);
    return { agentAvailable: true, cancelled: false, success: false, files: [], error: e.message, errorCode: "AGENT_COMMUNICATION_ERROR", errorParams: { detail: e.message ?? "" } };
  }
}

/** errorCode -> [ja.json/vi.jsonのagentErrorsキー, 日本語デフォルト文言] のテーブル。 */
const AGENT_ERROR_TEMPLATES: Record<string, [string, string]> = {
  AGENT_NOT_RUNNING:        ["agentNotRunning",        "UploadAgentが起動していません"],
  AGENT_COMMUNICATION_ERROR:["agentCommunicationError","UploadAgentとの通信に失敗しました: {detail}"],
  USB_DEST_NOT_CONFIGURED:  ["usbDestNotConfigured",   "USB転送先フォルダが設定されていません（設定画面で設定してください）"],
  USB_DEST_NOT_FOUND:       ["usbDestNotFound",        "USB転送先フォルダが見つかりません: {path}（USBが接続されているか確認してください）"],
  USB_SRC_NOT_CONFIGURED:   ["usbSrcNotConfigured",    "USB取込元フォルダが設定されていません（設定画面で設定してください）"],
  USB_SRC_NOT_FOUND:        ["usbSrcNotFound",         "USB取込元フォルダが見つかりません: {path}（USBが接続されているか確認してください）"],
  USB_ITEM_NOT_FOUND_FOLDER:["usbItemNotFoundFolder",  "USBフォルダ内に「{name}」フォルダが見つかりません"],
  USB_ITEM_NOT_FOUND_FILE:  ["usbItemNotFoundFile",    "USBフォルダ内に「{name}」ファイルが見つかりません"],
  FOLDER_NO_FILES:          ["folderNoFiles",          "フォルダ内にファイルがありません"],
  FOLDER_NO_MATCHING_FILES: ["folderNoMatchingFiles",  "フォルダ内に{typeLabel}ファイルが見つかりません（全{total}件中0件）"],
  FOLDER_READ_ERROR:        ["folderReadError",        "フォルダ読み取り失敗: {detail}"],
  TICKET_FETCH_FAILED:      ["ticketFetchFailed",      "チケット情報取得失敗 (HTTP {status}): {detail}"],
  RESPONSE_PARSE_FAILED:    ["responseParseFailed",    "レスポンス解析失敗: {detail}"],
  NO_FILE_INFO:             ["noFileInfo",             "ファイル情報が取得できませんでした"],
  NO_PROGRAM_FILES:         ["noProgramFiles",         "プログラムファイルが見つかりません"],
  COPY_FAILED:              ["copyFailed",             "ファイルのコピーに失敗しました"],
  UPLOAD_PARTIAL_FAILURE:   ["uploadPartialFailure",   "一部または全部のファイルのアップロードに失敗しました"],
  UNEXPECTED_ERROR:         ["unexpectedError",        "{detail}"],
};

/**
 * [多言語対応・旧Agent互換] UploadAgent(C#)側をリビルド/再配置しなくても翻訳できるよう、
 * Agentが返す「生の日本語エラー文字列」をパターン認識してerrorCode+paramsへ変換する。
 * UploadCoordinator.cs内の実際のフォーマット文字列と1:1で対応させている。
 * 新しいAgent(errorCode対応版)を使っている場合はこの関数は使われない(errorCodeが優先される)。
 */
function parseKnownAgentErrorText(raw?: string | null): { code: string; params: Record<string, string> } | null {
  if (!raw) return null;
  const exact: Record<string, string> = {
    "Agent未起動": "AGENT_NOT_RUNNING",
    "USB転送先フォルダが設定されていません（設定画面で設定してください）": "USB_DEST_NOT_CONFIGURED",
    "USB取込元フォルダが設定されていません（設定画面で設定してください）": "USB_SRC_NOT_CONFIGURED",
    "フォルダ内にファイルがありません": "FOLDER_NO_FILES",
    "ファイル情報が取得できませんでした": "NO_FILE_INFO",
    "プログラムファイルが見つかりません": "NO_PROGRAM_FILES",
    "ファイルのコピーに失敗しました": "COPY_FAILED",
    "一部または全部のファイルのアップロードに失敗しました": "UPLOAD_PARTIAL_FAILURE",
  };
  if (exact[raw]) return { code: exact[raw], params: {} };

  const patterns: Array<{ re: RegExp; code: string; params: (m: RegExpMatchArray) => Record<string, string> }> = [
    // "USB転送先フォルダが見つかりません: F:\（USBが接続されているか確認してください）"
    { re: /^USB転送先フォルダが見つかりません: (.+?)(?:（USBが接続されているか確認してください）)?$/,
      code: "USB_DEST_NOT_FOUND", params: (m) => ({ path: m[1] }) },
    // "USB取込元フォルダが見つかりません: F:\（USBが接続されているか確認してください）" または末尾の（）なし版
    { re: /^USB取込元フォルダが見つかりません: (.+?)(?:（USBが接続されているか確認してください）)?$/,
      code: "USB_SRC_NOT_FOUND", params: (m) => ({ path: m[1] }) },
    // "USBフォルダ内に「1846.WPD」フォルダが見つかりません"
    { re: /^USBフォルダ内に「(.+)」フォルダが見つかりません$/,
      code: "USB_ITEM_NOT_FOUND_FOLDER", params: (m) => ({ name: m[1] }) },
    // "USBフォルダ内に「1846.WPD」ファイルが見つかりません"
    { re: /^USBフォルダ内に「(.+)」ファイルが見つかりません$/,
      code: "USB_ITEM_NOT_FOUND_FILE", params: (m) => ({ name: m[1] }) },
    // "フォルダ内に写真(jpg/jpeg/png)ファイルが見つかりません（全12件中0件）"
    { re: /^フォルダ内に(.+)ファイルが見つかりません（全(\d+)件中0件）$/,
      code: "FOLDER_NO_MATCHING_FILES", params: (m) => ({ typeLabel: m[1], total: m[2] }) },
    // "フォルダ読み取り失敗: <詳細>"
    { re: /^フォルダ読み取り失敗: (.+)$/,
      code: "FOLDER_READ_ERROR", params: (m) => ({ detail: m[1] }) },
    // "チケット情報取得失敗 (HTTP 500): <本文>"
    { re: /^チケット情報取得失敗 \(HTTP (\d+)\): ([\s\S]+)$/,
      code: "TICKET_FETCH_FAILED", params: (m) => ({ status: m[1], detail: m[2] }) },
    // "レスポンス解析失敗: <詳細>"
    { re: /^レスポンス解析失敗: (.+)$/,
      code: "RESPONSE_PARSE_FAILED", params: (m) => ({ detail: m[1] }) },
  ];

  for (const p of patterns) {
    const m = raw.match(p.re);
    if (m) return { code: p.code, params: p.params(m) };
  }
  return null;
}

/**
 * [多言語対応] UploadAgentから返るerrorCode(+errorParams)を、現在の表示言語に応じた
 * メッセージへ変換する。
 * - 新しいAgent(errorCode対応版)からの応答: errorCodeをそのまま使う。
 * - 古いAgent(errorCode未対応・リビルドしていない場合)からの応答: fallback(生の日本語error文字列)を
 *   parseKnownAgentErrorText()でパターン認識し、認識できればそれでも翻訳する。
 * - どちらにも該当しない場合のみ、fallbackをそのまま返す(未知のエラー文はそのまま表示)。
 *
 * 使い方: translateAgentError(tr, result.errorCode, result.errorParams, result.error) ?? tr("xxx.generic", "...")
 */
export function translateAgentError(
  tr: (key: string, fallback?: string) => string,
  errorCode?: string | null,
  errorParams?: Record<string, string> | null,
  fallback?: string,
): string | undefined {
  let code = errorCode;
  let params = errorParams ?? {};

  if (!code) {
    const parsed = parseKnownAgentErrorText(fallback);
    if (!parsed) return fallback;
    code = parsed.code;
    params = parsed.params;
  }

  const template = AGENT_ERROR_TEMPLATES[code];
  if (!template) return fallback;
  const [key, def] = template;

  let msg = tr(`agentErrors.${key}`, def);
  for (const [k, v] of Object.entries(params)) {
    msg = msg.split(`{${k}}`).join(v ?? "");
  }
  return msg;
}
