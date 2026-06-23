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
};

/**
 * Agentへ「単体ファイル選択→アップロード→ローカル削除」を一括依頼する。
 * Agent内でネイティブファイルダイアログが表示される。
 */
export async function agentPickAndUpload(ticket: string, fileType?: string): Promise<PickAndUploadResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, cancelled: false, success: false, files: [], error: "Agent未起動" };

  try {
    console.log("[Agent] /pick-and-upload 依頼開始 ticket=", ticket);
    const res = await fetch(`${AGENT_BASE}/pick-and-upload`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, fileType }),
      signal:  AbortSignal.timeout(DIALOG_TIMEOUT_MS),
    });
    const json = await res.json();
    console.log("[Agent] /pick-and-upload 結果:", json);
    if (!res.ok) return { agentAvailable: true, cancelled: false, success: false, files: [], error: json.error ?? `HTTP ${res.status}` };
    return { agentAvailable: true, cancelled: json.cancelled ?? false, success: json.success ?? false, files: json.files ?? [], error: json.error };
  } catch(e: any) {
    console.error("[Agent] /pick-and-upload エラー:", e);
    return { agentAvailable: true, cancelled: false, success: false, files: [], error: e.message };
  }
}

/**
 * Agentへ「フォルダ選択→フォルダ内全ファイルアップロード→ローカル削除」を一括依頼する。
 */
export async function agentPickFolderAndUpload(ticket: string, fileType?: string): Promise<PickAndUploadResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, cancelled: false, success: false, files: [], error: "Agent未起動" };

  try {
    console.log("[Agent] /pick-folder-and-upload 依頼開始 ticket=", ticket);
    const res = await fetch(`${AGENT_BASE}/pick-folder-and-upload`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ ticket, fileType }),
      signal:  AbortSignal.timeout(DIALOG_TIMEOUT_MS),
    });
    const json = await res.json();
    console.log("[Agent] /pick-folder-and-upload 結果:", json);
    if (!res.ok) return { agentAvailable: true, cancelled: false, success: false, files: [], error: json.error ?? `HTTP ${res.status}` };
    return { agentAvailable: true, cancelled: json.cancelled ?? false, success: json.success ?? false, files: json.files ?? [], error: json.error };
  } catch(e: any) {
    console.error("[Agent] /pick-folder-and-upload エラー:", e);
    return { agentAvailable: true, cancelled: false, success: false, files: [], error: e.message };
  }
}
