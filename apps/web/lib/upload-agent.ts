/**
 * upload-agent.ts — MachCore UploadAgent (localhost:57300) 連携ライブラリ
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
const AGENT_BASE = "http://localhost:57300";
const TIMEOUT_MS = 3000;

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

export type AgentUploadedFile = {
  fileName:      string;
  storedName?:   string;
  duplicate:     boolean;   // 既存ファイルとの重複があり trash へ退避したか
  sourceDeleted: boolean;   // 元ファイル（USB/ローカル）の削除に成功したか
};

export type AgentPickAndUploadResult = {
  ok:        boolean;
  message?:  string;
  uploaded?: AgentUploadedFile[];
};

/**
 * Agentへ「ファイル選択ダイアログを開いてアップロードしろ」と依頼する。
 * Bearerトークンそのものは渡さず、MachCore APIで発行したワンタイムチケットのみを渡す。
 *
 * 処理フロー（Agent側で完結）:
 *  1. ネイティブファイル/フォルダ選択ダイアログを表示
 *  2. 選択されたファイルを MachCore API (upload-by-ticket) へ直接アップロード
 *  3. アップロード成功を確認後、ローカル元ファイルを .machcore_trash へ移動
 *  4. 結果をWebへ返す
 */
export async function requestAgentPickAndUpload(params: {
  mcId: number;
  token: string;
  fileType: 'PHOTO' | 'DRAWING' | 'PROGRAM';
  mode: 'file' | 'folder';
  replaceFileId?: number;
}): Promise<AgentPickAndUploadResult> {
  const { mcId, token, fileType, mode, replaceFileId } = params;

  // ① MachCore API でワンタイムチケットを発行（通常のBearer認証）
  console.log("[AGENT_UPLOAD] チケット発行リクエスト:", { mcId, fileType, mode, replaceFileId });
  let ticketRes: Response;
  try {
    ticketRes = await fetch(`/api/mc/${mcId}/files/upload-ticket`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        file_type: fileType,
        replace_file_id: replaceFileId,
        is_folder_upload: mode === "folder",
      }),
    });
  } catch (e: any) {
    console.error("[AGENT_UPLOAD] チケット発行通信エラー:", e);
    return { ok: false, message: "チケット発行に失敗しました（通信エラー）" };
  }
  if (!ticketRes.ok) {
    console.error("[AGENT_UPLOAD] チケット発行失敗:", ticketRes.status);
    return { ok: false, message: `チケット発行に失敗しました（HTTP ${ticketRes.status}）` };
  }
  const ticketJson = await ticketRes.json();
  const ticket = ticketJson.ticket as string;
  console.log("[AGENT_UPLOAD] チケット発行成功:", ticket, "有効期限:", ticketJson.expires_in_sec, "秒");

  // ② Agentへチケットのみを渡してダイアログ表示〜アップロードを依頼
  const agentToken = await getAgentToken();
  if (!agentToken) {
    return { ok: false, message: "UploadAgentが起動していません" };
  }

  const endpoint = mode === "folder" ? "/pick-folder-and-upload" : "/pick-and-upload";
  console.log("[AGENT_UPLOAD] Agentへ依頼:", endpoint);
  try {
    const res = await fetch(`${AGENT_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": agentToken },
      body: JSON.stringify({ ticket, file_type: fileType }),
      // ダイアログ表示〜ユーザー操作待ちのため長めのタイムアウト（5分）
      signal: AbortSignal.timeout(5 * 60 * 1000),
    });
    const json = await res.json();
    console.log("[AGENT_UPLOAD] Agentレスポンス:", res.status, json);

    if (!res.ok) {
      return { ok: false, message: json.message ?? json.error ?? `Agentエラー（HTTP ${res.status}）` };
    }
    if (json.cancelled) {
      console.log("[AGENT_UPLOAD] ユーザーがダイアログをキャンセル");
      return { ok: false, message: "ファイル選択がキャンセルされました" };
    }
    return {
      ok: true,
      uploaded: (json.uploaded ?? []) as AgentUploadedFile[],
    };
  } catch (e: any) {
    console.error("[AGENT_UPLOAD] Agent通信エラー:", e);
    return { ok: false, message: "UploadAgentとの通信に失敗しました: " + (e.message ?? "不明なエラー") };
  }
}
