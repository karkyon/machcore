"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

const AGENT_URL = "http://localhost:57300";
const getToken = () => sessionStorage.getItem("admin_token") ?? "";

export default function UploadAgentPage() {
  const router   = useRouter();
  const pathname = usePathname();

  const [agentStatus, setAgentStatus] = useState<"unknown"|"online"|"offline">("unknown");
  const [checking,    setChecking]    = useState(false);

  // バージョン情報
  const [versionInfo, setVersionInfo] = useState<{ version: string; exists: boolean; size_bytes: number; updated_at: string | null } | null>(null);

  // デプロイ
  const [newVersion,   setNewVersion]   = useState("");
  const [deployFile,   setDeployFile]   = useState<File | null>(null);
  const [deploying,    setDeploying]    = useState(false);
  const [deployMsg,    setDeployMsg]    = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // バージョン情報取得
  const fetchVersion = async () => {
    try {
      const res = await fetch("/api/admin/upload-agent/version", {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) setVersionInfo(await res.json());
    } catch { /* ignore */ }
  };

  useEffect(() => { fetchVersion(); }, []);

  // Agent稼働確認
  const checkAgent = async () => {
    setChecking(true);
    try {
      const res = await fetch(`${AGENT_URL}/health`, { signal: AbortSignal.timeout(3000) });
      setAgentStatus(res.ok ? "online" : "offline");
    } catch { setAgentStatus("offline"); }
    finally  { setChecking(false); }
  };

  // 新バージョンデプロイ
  const handleDeploy = async () => {
    if (!deployFile) { setDeployMsg({ ok: false, text: "exeファイルを選択してください" }); return; }
    if (!newVersion.trim()) { setDeployMsg({ ok: false, text: "バージョン番号を入力してください" }); return; }
    setDeploying(true);
    setDeployMsg(null);
    try {
      const fd = new FormData();
      fd.append("file",    deployFile);
      fd.append("version", newVersion.trim());
      const res = await fetch("/api/admin/upload-agent/deploy", {
        method:  "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body:    fd,
      });
      const json = await res.json();
      if (res.ok) {
        setDeployMsg({ ok: true, text: `✅ ${json.message}` });
        setDeployFile(null);
        setNewVersion("");
        if (fileRef.current) fileRef.current.value = "";
        await fetchVersion();
      } else {
        setDeployMsg({ ok: false, text: `❌ ${json.message ?? "デプロイ失敗"}` });
      }
    } catch (e: any) {
      setDeployMsg({ ok: false, text: `❌ ${e.message}` });
    } finally { setDeploying(false); }
  };

  const fmtBytes = (b: number) => b < 1024 * 1024 ? `${(b/1024).toFixed(1)} KB` : `${(b/1024/1024).toFixed(1)} MB`;

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">



        <main className="flex-1 overflow-y-auto p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-slate-800">UploadAgent 配布・管理</h1>
            <span className="text-xs text-slate-400 font-mono">
              配布中: v{versionInfo?.version ?? "—"}
              {versionInfo?.size_bytes ? `  (${fmtBytes(versionInfo.size_bytes)})` : ""}
            </span>
          </div>

          {/* ── Agent稼働確認 ── */}
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
                <span className={`w-2 h-2 rounded-full ${agentStatus === "online" ? "bg-green-500" : agentStatus === "offline" ? "bg-red-500" : "bg-slate-400"}`} />
                {agentStatus === "online" ? "✅ 稼働中" : agentStatus === "offline" ? "❌ 未起動 / 未インストール" : "— 未確認"}
              </div>
              <button onClick={checkAgent} disabled={checking}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg disabled:opacity-50 transition-colors">
                {checking ? "確認中..." : "稼働確認"}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">※ このボタンはこのPCにインストールされたAgentのみ確認できます</p>
          </div>

          {/* ── ダウンロード ── */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-1 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 17l4 4 4-4M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
              インストーラ ダウンロード
            </h2>
            <p className="text-xs text-slate-500 mb-4">各クライアントPCにインストールしてください。インストール後は自動でスタートアップ登録されます。</p>
            {versionInfo?.exists ? (
              <a href="/api/admin/upload-agent/download"
                className="flex items-center gap-3 px-4 py-3 bg-sky-600 hover:bg-sky-700 text-white rounded-xl font-bold text-sm transition-colors w-fit">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 17l4 4 4-4M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
                ⬇ UploadAgent_Setup_v{versionInfo.version}.exe をダウンロード
              </a>
            ) : (
              <div className="text-sm text-slate-400 bg-slate-50 rounded-lg p-4">⚠️ インストーラがまだ配置されていません。下の「バージョン管理」からアップロードしてください。</div>
            )}
          </div>

          {/* ── バージョン管理（アップデータ） ── */}
          <div className="bg-white rounded-xl border-2 border-amber-200 p-5">
            <h2 className="font-bold text-amber-800 mb-1 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              バージョン管理（新バージョンをデプロイ）
            </h2>
            <p className="text-xs text-slate-500 mb-4">
              新しい <code className="bg-slate-100 px-1 rounded">UploadAgent_Setup_vX.X.X.exe</code> をビルドしたら、ここからアップロードするだけで配布が完了します。
            </p>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <label className="text-xs font-bold text-slate-600 w-28 shrink-0">新バージョン番号</label>
                <input value={newVersion} onChange={e => setNewVersion(e.target.value)}
                  placeholder="例: 1.2.0"
                  className="border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-amber-400" />
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs font-bold text-slate-600 w-28 shrink-0">exeファイル</label>
                <label className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-bold cursor-pointer transition-colors">
                  📁 {deployFile ? deployFile.name : "ファイルを選択..."}
                  <input ref={fileRef} type="file" accept=".exe" className="hidden"
                    onChange={e => {
                    const f = e.target.files?.[0] ?? null;
                    setDeployFile(f);
                    if (f) {
                      // ファイル名からバージョン自動検出: UploadAgent_Setup_vX.X.X.exe
                      const m = f.name.match(/[Vv](\d+\.\d+\.\d+)/);
                      if (m) setNewVersion(m[1]);
                    }
                  }} />
                </label>
                {deployFile && <span className="text-xs text-slate-400">{fmtBytes(deployFile.size)}</span>}
              </div>
              <div className="flex items-center gap-3">
                <div className="w-28 shrink-0" />
                <button onClick={handleDeploy} disabled={deploying || !deployFile || !newVersion.trim()}
                  className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2">
                  {deploying ? "⏳ デプロイ中..." : "🚀 デプロイ（配布ファイルを更新）"}
                </button>
              </div>
              {deployMsg && (
                <div className={`text-sm font-bold px-4 py-2 rounded-lg ${deployMsg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                  {deployMsg.text}
                </div>
              )}
            </div>
            <div className="mt-4 text-xs text-slate-400 bg-slate-50 rounded-lg p-3">
              デプロイすると <code>/var/www/machcore-cert/UploadAgent_Setup_vX.X.X.exe</code> と <code>UploadAgent_Setup_latest.exe</code> が同時に更新されます
            </div>
          </div>

          {/* ── インストール手順 ── */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2"/></svg>
              クライアントPCへのインストール手順
            </h2>
            <ol className="space-y-2 text-sm text-slate-700">
              {[
                "上記「UploadAgent_Setup_vX.exe」をダウンロード",
                "ダウンロードしたexeをダブルクリックで実行",
                "インストール完了後、タスクトレイに 🟢 緑のMCアイコンが表示される",
                "以降Windowsログイン時に自動起動（スタートアップ登録済み）",
                "MachCoreでUSBファイルをアップロードすると自動でUSB元ファイルを移動",
              ].map((step, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* ── 機能概要 ── */}
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
    </AdminLayout>
  );
}
