"use client";
import { useEffect, useState } from "react";

export type PrintMode = "DIRECT" | "MANUAL";

/**
 * 段取シートの出力方式(管理画面 > システム設定。インスタンスごとのDBに保存)。
 * 印刷画面のボタン表記の切り替えだけに使う。実際の出力方式はサーバがDBの設定で決める。
 * /api/admin/company はGET時は認証不要。設定変更をすぐ反映するためキャッシュしない。
 */
export function usePrintMode(): PrintMode | null {
  const [mode, setMode] = useState<PrintMode | null>(null);
  useEffect(() => {
    let alive = true;
    fetch("/api/admin/company", { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (alive) setMode(d?.printMode === "MANUAL" ? "MANUAL" : "DIRECT"); })
      .catch(() => { if (alive) setMode("DIRECT"); });
    return () => { alive = false; };
  }, []);
  return mode;
}
