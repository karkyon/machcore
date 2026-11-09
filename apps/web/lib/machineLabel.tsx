"use client";
// [No.64] 機械の表示を「機械コード <機種名>」に統一する。スペース(全角含む)を除いて比べ、機械コードと機種名が同じ機械(SL-25 等)は機械コードだけ表示する。
import { useEffect, useState } from "react";
import { machinesApi } from "@/lib/api";

type MachineLike = { machineCode?: string | null; machineName?: string | null } | null | undefined;

/** スペース(半角・全角)を除いて比べ、同じ表記なら true */
export function sameMachineText(a: string, b: string): boolean {
  const n = (s: string) => s.replace(/[\s\u3000]+/g, "");
  return n(a) === n(b);
}

export function machineLabel(m: MachineLike, fallback = "—"): string {
  const code = (m?.machineCode ?? "").trim();
  const name = (m?.machineName ?? "").trim();
  if (!code && !name) return fallback;
  if (!name) return code;
  if (!code) return name;
  if (sameMachineText(code, name)) return code;
  return `${code} <${name}>`;
}

// 一覧 API が機械コードしか返さない画面用に、機械マスタ(無効含む)を1回だけ読む
let cache: Promise<Map<string, string>> | null = null;
function loadLabels(): Promise<Map<string, string>> {
  if (!cache) {
    cache = machinesApi.list(undefined, true).then(r => {
      const rows: any[] = (r as any).data ?? [];
      return new Map(rows.map(m => [m.machineCode as string, machineLabel(m)]));
    }).catch(() => { cache = null; return new Map<string, string>(); });
  }
  return cache;
}

export function MachineLabel({ code, fallback = "—" }: { code?: string | null; fallback?: string }) {
  const [label, setLabel] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    if (code) loadLabels().then(map => { if (alive) setLabel(map.get(code) ?? null); });
    else setLabel(null);
    return () => { alive = false; };
  }, [code]);
  return <>{code ? (label ?? code) : fallback}</>;
}
