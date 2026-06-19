"use client";
import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",         label: "ユーザ管理",           icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",      label: "機械管理",             icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",        label: "機械タイムカード",     icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",      label: "システム設定",         icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/calendar",      label: "営業カレンダー",       icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" },
  { href: "/admin/raw",           label: "RAWデータ",            icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/system-logs",   label: "システムログ",         icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
  { href: "/admin/clamp-master",  label: "クランプマスタ",       icon: "M4 6h16M4 12h16M4 18h7" },
  { href: "/admin/pdf-editor",    label: "段取りシートエディタ", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
  { href: "/admin/special-sheets",label: "SPシート管理",         icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2M12 12h.01M12 16h.01" },
  { href: "/admin/upload-agent",  label: "UploadAgent",          icon: "M8 17l4 4 4-4M12 12v9M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29" },
];

const VERSION = "1.1.1";
const AGENT_URL = "http://localhost:57300";
const DL_BASE  = "http://192.168.1.11:9100";

export default function UploadAgentPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [agentStatus, setAgentStatus] = useState<"unknown"|"online"|"offline">("unknown");
  const [checking, setChecking] = useState(false);

  const checkAgent = async () => {
    setChecking(true);
    try {
      const res = await fetch(`${AGENT_URL}/health`, { signal: AbortSignal.timeout(3000) });
      setAgentStatus(res.ok ? "online" : "offline");
    } catch {
      setAgentStatus("offline");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* ヘッダー */}
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* サイドバー */}
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor" && i.href !== "/admin/special-sheets" && i.href !== "/admin/upload-agent").map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {["/admin/pdf-editor", "/admin/special-sheets", "/admin/upload-agent"].map(href => {
            const item = SIDEBAR_ITEMS.find(i => i.href === href)!;
            return (
              <a key={item.href} href={item.href}
                className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
                {item.label}
              </a>
            );
          })}
        </aside>

        {/* メインコンテンツ */}
        <main className="flex-1 overflow-y-auto p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-slate-800">UploadAgent 配布・管理</h1>
            <span className="text-xs text-slate-400 font-mono">v{VERSION}</span>
          </div>

          {/* ステータス確認 */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
              このPC の Agent 稼働確認
            </h2>
            <div className="flex items-center gap-4">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-sm ${
                agentStatus === "online"  ? "bg-green-50 text-green-700 border border-green-200" :
                agentStatus === "offline" ? "bg-red-50 text-red-700 border border-red-200" :
                "bg-slate-50 text-slate-500 border border-slate-200"}`}>
                <span className={`w-2 h-2 rounded-full ${
                  agentStatus === "online"  ? "bg-green-500" :
                  agentStatus === "offline" ? "bg-red-500" : "bg-slate-400"}`} />
                {agentStatus === "online"  ? "✅ 稼働中" :
                 agentStatus === "offline" ? "❌ 未起動 / 未インストール" : "— 未確認"}
              </div>
              <button onClick={checkAgent} disabled={checking}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg disabled:opacity-50 transition-colors">
                {checking ? "確認中..." : "稼働確認"}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">※ このボタンはこのPCにインストールされたAgentのみ確認できます</p>
          </div>

          {/* ダウンロード */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-1 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 17l4 4 4-4M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
              インストーラ ダウンロード
            </h2>
            <p className="text-xs text-slate-500 mb-4">各クライアントPCにインストールしてください。インストール後は自動でスタートアップ登録されます。</p>
            <div className="flex flex-col gap-3">
              <a href={`${DL_BASE}/UploadAgent_Setup_latest.exe`}
                className="flex items-center gap-3 px-4 py-3 bg-sky-600 hover:bg-sky-700 text-white rounded-xl font-bold text-sm transition-colors w-fit">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 17l4 4 4-4M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
                ⬇ UploadAgent_Setup_v{VERSION}.exe をダウンロード
              </a>
              <a href={`${DL_BASE}/UploadAgent_v${VERSION}.zip`}
                className="flex items-center gap-3 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-sm transition-colors w-fit">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 17l4 4 4-4M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
                📦 UploadAgent_v{VERSION}.zip（ソース一式）
              </a>
            </div>
          </div>

          {/* インストール手順 */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2"/></svg>
              インストール手順
            </h2>
            <ol className="space-y-2 text-sm text-slate-700">
              {[
                "上記「UploadAgent_Setup_v" + VERSION + ".exe」をダウンロード",
                "ダウンロードしたexeをダブルクリックで実行",
                "インストール完了後、タスクトレイに 🟢 緑のMCアイコンが表示される",
                "以降Windowsログイン時に自動起動（スタートアップ登録済み）",
                "MachCoreでUSBファイルをアップロードすると自動でUSB元ファイルを移動"
              ].map((step, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">{i+1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* 仕様概要 */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-3">機能概要</h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["待受ポート", "localhost:57300（外部アクセス不可）"],
                ["ファイル操作", "USB元ファイルを .machcore_trash/ に移動"],
                ["アイコン", "正常=🟢緑 / エラー=🔴赤 でトレイ表示"],
                ["設定画面", "トレイ右クリック → 設定... で開く"],
                ["ログ", "%APPDATA%\MachCore\UploadAgent\agent.log"],
                ["自動起動", "Windowsログイン時に自動起動"],
              ].map(([k, v]) => (
                <div key={k} className="flex flex-col gap-0.5 bg-slate-50 rounded-lg p-3">
                  <span className="text-xs font-bold text-slate-500">{k}</span>
                  <span className="text-slate-700 font-mono text-xs">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
