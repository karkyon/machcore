"use client";
// ─────────────────────────────────────────────────────────────
// 備考などの自由入力テキスト中の URL / ファイル共有パスを開ける・コピーできる形で表示する
//   - http(s)://… → 新しいタブで開くリンク
//   - \\サーバー\共有\…（UNCパス）→ クリックでパスをコピー（＋file: リンクとして開く試行）
//     ブラウザはセキュリティ上 https のページから社内共有フォルダ(file:)を直接開けないため、
//     コピーしたパスをエクスプローラーのアドレス欄に貼り付けて開く運用を基本とする。
// テキストはHTMLとして解釈せず、Reactの文字列として描画する（スクリプト混入の心配なし）。
// ─────────────────────────────────────────────────────────────
import React, { useState } from "react";

type Part = { kind: "text" | "url" | "unc"; value: string };

// URL: 空白・全角空白・括弧閉じ等で終端。UNC: 行末まで（共有パスは空白を含むことがあるため）
const TOKEN_RE = /(https?:\/\/[^\s\u3000<>"'）」』]+)|(\\\\[^\\\s\u3000][^\r\n]*)/g;

function splitParts(text: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) });
    if (m[1]) {
      parts.push({ kind: "url", value: m[1] });
    } else if (m[2]) {
      // 行末の空白は除く（パスの一部ではない）
      const raw = m[2];
      const trimmed = raw.replace(/[\s\u3000]+$/, "");
      parts.push({ kind: "unc", value: trimmed });
      if (trimmed.length < raw.length) parts.push({ kind: "text", value: raw.slice(trimmed.length) });
    }
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}

function uncToFileUrl(unc: string): string {
  // \\host\share\a b\c.xlsx → file://host/share/a%20b/c.xlsx
  const segs = unc.replace(/^\\\\/, "").split("\\").map(s => encodeURIComponent(s));
  return "file://" + segs.join("/");
}

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* フォールバックへ */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch { return false; }
}

export default function LinkifiedText({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState<string | null>(null);
  const parts = splitParts(text ?? "");

  const onUncClick = async (e: React.MouseEvent, unc: string) => {
    e.preventDefault();
    const ok = await copyText(unc);
    setCopied(ok ? unc : null);
    if (ok) setTimeout(() => setCopied(c => (c === unc ? null : c)), 4000);
  };

  return (
    <span className={className}>
      {parts.map((p, i) => {
        if (p.kind === "url") {
          return (
            <a key={i} href={p.value} target="_blank" rel="noopener noreferrer"
              className="text-blue-600 underline break-all hover:text-blue-800">{p.value}</a>
          );
        }
        if (p.kind === "unc") {
          return (
            <span key={i} className="inline">
              <a href={uncToFileUrl(p.value)} onClick={e => onUncClick(e, p.value)}
                title="クリックでパスをコピーします。エクスプローラーのアドレス欄に貼り付けると開けます"
                className="text-blue-600 underline break-all hover:text-blue-800 cursor-pointer">{p.value}</a>
              <button type="button" onClick={e => onUncClick(e, p.value)}
                className="ml-1 align-middle text-[10px] px-1.5 py-0.5 rounded border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 whitespace-nowrap">
                {copied === p.value ? "✓ コピーしました（エクスプローラーに貼り付けて開けます）" : "📋 パスをコピー"}
              </button>
            </span>
          );
        }
        return <React.Fragment key={i}>{p.value}</React.Fragment>;
      })}
    </span>
  );
}
