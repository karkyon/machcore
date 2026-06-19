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
