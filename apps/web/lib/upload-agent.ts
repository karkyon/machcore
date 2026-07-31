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

/**
 * [多言語対応] UploadAgentから返るerrorCode(+errorParams)を、現在の表示言語に応じた
 * メッセージへ変換する。errorCodeが無い場合(旧バージョンのAgentと通信した場合)は
 * fallback(通常は生のresult.error、あるいは各画面の汎用エラー文言)をそのまま返す。
 *
 * 使い方: translateAgentError(tr, result.errorCode, result.errorParams, result.error) ?? tr("xxx.generic", "...")
 */
export function translateAgentError(
  tr: (key: string, fallback?: string) => string,
  errorCode?: string | null,
  errorParams?: Record<string, string> | null,
  fallback?: string,
): string | undefined {
  if (!errorCode) return fallback;
  const params = errorParams ?? {};
  const apply = (key: string, def: string): string => {
    let msg = tr(`agentErrors.${key}`, def);
    for (const [k, v] of Object.entries(params)) {
      msg = msg.split(`{${k}}`).join(v ?? "");
    }
    return msg;
  };

  switch (errorCode) {
    case "AGENT_NOT_RUNNING":
      return apply("agentNotRunning", "UploadAgentが起動していません");
    case "AGENT_COMMUNICATION_ERROR":
      return apply("agentCommunicationError", "UploadAgentとの通信に失敗しました: {detail}");
    case "USB_DEST_NOT_CONFIGURED":
      return apply("usbDestNotConfigured", "USB転送先フォルダが設定されていません（設定画面で設定してください）");
    case "USB_DEST_NOT_FOUND":
      return apply("usbDestNotFound", "USB転送先フォルダが見つかりません: {path}（USBが接続されているか確認してください）");
    case "USB_SRC_NOT_CONFIGURED":
      return apply("usbSrcNotConfigured", "USB取込元フォルダが設定されていません（設定画面で設定してください）");
    case "USB_SRC_NOT_FOUND":
      return apply("usbSrcNotFound", "USB取込元フォルダが見つかりません: {path}（USBが接続されているか確認してください）");
    case "USB_ITEM_NOT_FOUND_FOLDER":
      return apply("usbItemNotFoundFolder", "USBフォルダ内に「{name}」フォルダが見つかりません");
    case "USB_ITEM_NOT_FOUND_FILE":
      return apply("usbItemNotFoundFile", "USBフォルダ内に「{name}」ファイルが見つかりません");
    case "FOLDER_NO_FILES":
      return apply("folderNoFiles", "フォルダ内にファイルがありません");
    case "FOLDER_NO_MATCHING_FILES":
      return apply("folderNoMatchingFiles", "フォルダ内に{typeLabel}ファイルが見つかりません（全{total}件中0件）");
    case "FOLDER_READ_ERROR":
      return apply("folderReadError", "フォルダ読み取り失敗: {detail}");
    case "TICKET_FETCH_FAILED":
      return apply("ticketFetchFailed", "チケット情報取得失敗 (HTTP {status}): {detail}");
    case "RESPONSE_PARSE_FAILED":
      return apply("responseParseFailed", "レスポンス解析失敗: {detail}");
    case "NO_FILE_INFO":
      return apply("noFileInfo", "ファイル情報が取得できませんでした");
    case "NO_PROGRAM_FILES":
      return apply("noProgramFiles", "プログラムファイルが見つかりません");
    case "COPY_FAILED":
      return apply("copyFailed", "ファイルのコピーに失敗しました");
    case "UPLOAD_PARTIAL_FAILURE":
      return apply("uploadPartialFailure", "一部または全部のファイルのアップロードに失敗しました");
    case "UNEXPECTED_ERROR":
      return apply("unexpectedError", "{detail}");
    default:
      return fallback;
  }
}
