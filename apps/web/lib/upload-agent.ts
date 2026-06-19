/**
 * upload-agent.ts — MachCore UploadAgent (localhost:57300) 連携ライブラリ
 */
const AGENT_BASE = "http://localhost:57300";
const TIMEOUT_MS = 3000;

export type AgentHealth = { status: string; version: string; token: string };
export type AgentMoveResult = {
  agentAvailable: boolean;
  success: boolean;
  moved:   string[];
  failed:  { path: string; error: string }[];
};

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

export async function notifyAgentMove(
  absolutePaths: string[],
  operatorId?: number,
): Promise<AgentMoveResult> {
  const token = await getAgentToken();
  if (!token) return { agentAvailable: false, success: false, moved: [], failed: [] };
  try {
    const res = await fetch(`${AGENT_BASE}/move`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Token": token },
      body:    JSON.stringify({ paths: absolutePaths, reason: "upload_complete", operator_id: operatorId ?? null }),
      signal:  AbortSignal.timeout(5000),
    });
    if (!res.ok) return { agentAvailable: true, success: false, moved: [], failed: absolutePaths.map(p => ({ path: p, error: `HTTP ${res.status}` })) };
    const json = await res.json();
    return {
      agentAvailable: true,
      success:        json.success ?? false,
      moved:          (json.moved ?? []).map((m: any) => m.original as string),
      failed:         json.failed  ?? [],
    };
  } catch { return { agentAvailable: false, success: false, moved: [], failed: [] }; }
}

export async function getRemovableDrives(): Promise<{ letter: string; label: string; totalBytes: number; freeBytes: number }[]> {
  const token = await getAgentToken();
  if (!token) return [];
  try {
    const res = await fetch(`${AGENT_BASE}/drives`, { headers: { "X-Agent-Token": token }, signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) return [];
    return (await res.json()).drives ?? [];
  } catch { return []; }
}

/**
 * FileSystemFileHandle からフルパスを取得する。
 * File System Access API の storageRoot.resolve() でブラウザのOrigin Private File System
 * からの相対パス配列を取得し、ドライブ一覧と組み合わせてWindowsフルパスを構築する。
 * 取得できない場合は null を返す。
 */
export async function getFullPath(fileHandle: FileSystemFileHandle): Promise<string | null> {
  try {
    // まず OPFS (Origin Private File System) root から resolve を試みる
    const root = await (navigator.storage as any).getDirectory();
    const parts: string[] | null = await root.resolve(fileHandle);
    if (parts && parts.length > 0) {
      // OPFS内のパス → 通常は null になる（ローカルファイルはOPFS外）
      console.log("[getFullPath] OPFS resolve:", parts);
    }
  } catch { /* OPFS resolve 失敗は無視 */ }

  // Agent のドライブ一覧を取得してファイル名とサイズでマッチング
  const token = await getAgentToken();
  if (!token) return null;

  try {
    const file = await fileHandle.getFile();
    // GET /drives でリムーバブルドライブ一覧取得
    const drivesRes = await fetch(`${AGENT_BASE}/drives`, {
      headers: { "X-Agent-Token": token },
      signal: AbortSignal.timeout(3000),
    });
    if (!drivesRes.ok) return null;
    const { drives } = await drivesRes.json() as { drives: { letter: string }[] };

    // 各ドライブ下のファイルを Agent の /scan エンドポイントで探索
    // → /scan が未実装のため、フォールバックとして DataTransfer path を試みる
    // Chrome では File オブジェクトの非標準プロパティ path が存在することがある
    const anyFile = file as any;
    if (anyFile.path && typeof anyFile.path === "string" && anyFile.path.length > 3) {
      console.log("[getFullPath] file.path:", anyFile.path);
      return anyFile.path;
    }

    // webkitRelativePath があれば使う（フォルダ選択時のみ設定される）
    if (file.webkitRelativePath && file.webkitRelativePath.length > 0) {
      for (const d of drives) {
        const candidate = `${d.letter}\\${file.webkitRelativePath.replace(/\//g, "\\")}`;
        console.log("[getFullPath] webkitRelativePath candidate:", candidate);
        return candidate;
      }
    }

    // 最終手段: ドライブ一覧の各ルートにファイル名を付けて返す
    // Agent 側の IsAllowedPath でリムーバブルドライブかチェックされるため
    // ドライブが1台なら確定パスとして使える
    if (drives.length === 1) {
      const fullPath = `${drives[0].letter}\\${file.name}`;
      console.log("[getFullPath] single drive fallback:", fullPath);
      return fullPath;
    }

    console.log("[getFullPath] パス特定不可 drives:", drives.length);
    return null;
  } catch(e) {
    console.warn("[getFullPath] エラー:", e);
    return null;
  }
}
