"use client";
// [No.64] 機械の表示を「機械コード <機種名>」に統一する。機械コードと機種名が同じ機械は1つだけ表示する。
import { useEffect, useState } from "react";
import { machinesApi } from "@/lib/api";

type MachineLike = { machineCode?: string | null; machineName?: string | null } | null | undefined;

export function machineLabel(m: MachineLike, fallback = "—"): string {
  const code = (m?.machineCode ?? "").trim();
  const name = (m?.machineName ?? "").trim();
  if (!code && !name) return fallback;
  if (!name || name === code) return code || name;
  if (!code) return name;
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
