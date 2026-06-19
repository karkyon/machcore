"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminSettingsApi, adminPrinterApi } from "../../../lib/api";

const MC_DEFAULT_PATHS = {
  program:    "/mnt/mc_files/MC/files/Programs",
  photo:      "/mnt/mc_files/MC/files/Pictures",
  drawing:    "/mnt/mc_files/MC/files/Drawings",
  setupsheet: "/mnt/mc_files/MC/files/setupsheet",
};
const NC_DEFAULT_PATHS = {
  program: "/mnt/nc_files/nc_files/{ncProgramId}/",
  photo:   "/mnt/nc_files/nc_files/{ncProgramId}/images/",
  drawing: "/mnt/nc_files/nc_files/{ncProgramId}/images/",
};

export default function AdminSettingsPage() {
  const router = useRouter();
  const pathname = usePathname();

  const [companyName, setCompanyName] = useState("");
  const [logoPath,    setLogoPath]    = useState("");
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);
  const [printerList, setPrinterList] = useState<string[]>([]);

  // MC設定
  const [mcStoragePath,    setMcStoragePath]    = useState("");
  const [mcUploadBasePath, setMcUploadBasePath] = useState("");
  const [mcPrinter,        setMcPrinter]        = useState("");
  // NC設定
  const [ncStoragePath, setNcStoragePath] = useState("");
  const [ncPrinter,     setNcPrinter]     = useState("");
  // Cron設定
  const [cronEnabled,  setCronEnabled]  = useState(true);
  const [cronTime,     setCronTime]     = useState("05:00");
  const [tcDefStart,   setTcDefStart]   = useState("08:00");
  const [tcDefEnd,     setTcDefEnd]     = useState("17:00");
  const [cronSaving,   setCronSaving]   = useState(false);
  // PM2
  const [pm2List,      setPm2List]      = useState<any[]>([]);
  const [pm2Loading,   setPm2Loading]   = useState(false);
  const [pm2Restarting, setPm2Restarting] = useState<string | null>(null);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
      fetch("/api/admin/system-settings", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()).then(d => {
      const rows: any[] = d.data ?? [];
      const get = (k: string, def: string) => rows.find((r: any) => r.key === k)?.value ?? def;
      setCronEnabled(get("cron_timecard_enabled", "true") === "true");
      const h = get("cron_timecard_hour", "5").padStart(2,"0");
      const m = get("cron_timecard_minute", "0").padStart(2,"0");
      setCronTime(`${h}:${m}`);
      setTcDefStart(get("timecard_default_start", "08:00"));
      setTcDefEnd(get("timecard_default_end", "17:00"));
    }).catch(() => {});
    fetch("/api/admin/pm2/status", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()).then(d => setPm2List(d.data ?? [])).catch(() => {});
        Promise.all([
      adminSettingsApi.getCompany(token),
      adminPrinterApi.list(token),
      // MC/NC設定
      fetch("/api/admin/settings/mc-nc", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([comp, printers, mcnc]) => {
      setCompanyName(comp.data.companyName ?? "");
      setLogoPath(comp.data.logoPath ?? "");
      setPrinterList(printers.data?.printers ?? []);
      setMcStoragePath(mcnc.mc_storage_path ?? MC_DEFAULT_PATHS.setupsheet);
      setMcUploadBasePath(mcnc.upload_base_path ?? '/mnt/mc_files');
      setNcStoragePath(mcnc.nc_storage_path ?? NC_DEFAULT_PATHS.program);
      setMcPrinter(mcnc.mc_printer ?? "");
      setNcPrinter(mcnc.nc_printer ?? "");
    }).catch(() => showToast("設定の取得に失敗しました", false))
      .finally(() => setLoading(false));
  }, [router]);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok }); setTimeout(() => setToast(null), 3000);
  };

  const handleSaveCompany = async () => {
    setSaving(true);
    try {
      await adminSettingsApi.updateCompany({ company_name: companyName, logo_path: logoPath || undefined }, getToken());
      showToast("会社設定を保存しました", true);
    } catch { showToast("保存に失敗しました", false); }
    finally { setSaving(false); }
  };

  const handleSaveMcNc = async () => {
    // MC/NC 同値チェック
    if (mcUploadBasePath.trim() && ncStoragePath.trim() && mcUploadBasePath.trim() === ncStoragePath.trim()) {
      showToast("MCとNCのパスを同じにすることはできません", false);
      return;
    }
    setSaving(true);
    try {
      await fetch("/api/admin/settings/mc-nc", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({
          mc_storage_path:  mcStoragePath,
          nc_storage_path:  ncStoragePath,
          upload_base_path: mcUploadBasePath,
          mc_printer:       mcPrinter,
          nc_printer:       ncPrinter,
        }),
      });
      showToast("設定を保存しました", true);
    } catch { showToast("保存に失敗しました", false); }
    finally { setSaving(false); }
  };


  const saveCronSettings = async () => {
    const token = getToken();
    setCronSaving(true);
    try {
      await fetch("/api/admin/system-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ settings: [
          { key: "cron_timecard_enabled",  value: String(cronEnabled) },
          { key: "cron_timecard_hour",     value: cronTime.split(":")[0] },
          { key: "cron_timecard_minute",   value: cronTime.split(":")[1] },
          { key: "timecard_default_start", value: tcDefStart },
          { key: "timecard_default_end",   value: tcDefEnd },
        ]}),
      });
      showToast("Cron設定を保存しました", true);
    } catch (e: any) { showToast("保存失敗: " + e.message, false); }
    finally { setCronSaving(false); }
  };

  const restartPm2 = async (name?: string) => {
    const token = getToken();
    const isAll = !name || name === "all";
    setPm2Restarting(name ?? "all");
    try {
      const r = await fetch("/api/admin/pm2/restart", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name }),
      });
      const d = await r.json();
      showToast(d.message, true);
      if (isAll) {
        // 全プロセス再起動: APIも再起動するので3秒後にページリロード
        setTimeout(() => { window.location.reload(); }, 3000);
      } else {
        setTimeout(() => {
          fetch("/api/admin/pm2/status", { headers: { Authorization: `Bearer ${token}` } })
            .then(r => r.json()).then(d => setPm2List(d.data ?? [])).catch(() => {});
        }, 2000);
      }
    } catch {
      // APIが自己再起動中でレスポンスが返らない場合は正常扱い
      if (isAll || name === "machcore-api") {
        showToast("再起動中…3秒後にページを再読み込みします", true);
        setTimeout(() => { window.location.reload(); }, 3000);
      } else {
        showToast("再起動に失敗しました", false);
      }
    }
    finally { setPm2Restarting(null); }
  };

  const savePm2 = async () => {
    const token = getToken();
    try {
      const r = await fetch("/api/admin/pm2/save", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      const d = await r.json();
      showToast(d.message, true);
    } catch (e: any) { showToast("失敗: " + e.message, false); }
  };
  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">


      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}


        <main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">システム設定</h1>
          </div>
          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (
            <>
              {/* ── 会社情報 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">🏢 会社情報</h2>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">会社名</label>
                  <input type="text" value={companyName} onChange={e => setCompanyName(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">ロゴ画像パス（サーバ相対パス）</label>
                  <input type="text" value={logoPath} onChange={e => setLogoPath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">アップロードしたロゴファイルのサーバ上のパスを入力してください</p>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleSaveCompany} disabled={saving} className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors">
                    {saving ? "保存中…" : "保存"}
                  </button>
                </div>
              </section>

              {/* ── MCファイル保存先 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">💾 MCファイル保存先</h2>
                <div className="grid grid-cols-4 gap-3 text-[11px] text-slate-400 bg-slate-50 rounded-lg p-3">
                  <div><span className="font-bold text-slate-600">プログラム</span><br/>{MC_DEFAULT_PATHS.program}</div>
                  <div><span className="font-bold text-slate-600">写真</span><br/>{MC_DEFAULT_PATHS.photo}</div>
                  <div><span className="font-bold text-slate-600">図</span><br/>{MC_DEFAULT_PATHS.drawing}</div>
                  <div><span className="font-bold text-teal-700">段取シート</span><br/>{MC_DEFAULT_PATHS.setupsheet}</div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">MCアップロードベースパス</label>
                  <input type="text" value={mcUploadBasePath} onChange={e => setMcUploadBasePath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">MC用ファイル（プログラム・写真・図）のベースパス（例: /mnt/mc_files）</p>
                </div>
              </section>

              {/* ── NCファイル保存先 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">💾 NCファイル保存先</h2>
                <div className="grid grid-cols-3 gap-3 text-[11px] text-slate-400 bg-slate-50 rounded-lg p-3">
                  <div><span className="font-bold text-slate-600">プログラム</span><br/>{NC_DEFAULT_PATHS.program}</div>
                  <div><span className="font-bold text-slate-600">写真</span><br/>{NC_DEFAULT_PATHS.photo}</div>
                  <div><span className="font-bold text-slate-600">図</span><br/>{NC_DEFAULT_PATHS.drawing}</div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">NCアップロードベースパス</label>
                  <input type="text" value={ncStoragePath} onChange={e => setNcStoragePath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">NC用ファイルのベースパス</p>
                </div>
              </section>

              {/* ── プリンタ設定（MC/NC） ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">🖨 ダイレクト印刷プリンタ設定</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">MCチーム用プリンタ</label>
                    <select value={mcPrinter} onChange={e => setMcPrinter(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white">
                      <option value="">— 選択 —</option>
                      {printerList.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">MC段取シートの印刷で使用</p>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">NCチーム用プリンタ</label>
                    <select value={ncPrinter} onChange={e => setNcPrinter(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white">
                      <option value="">— 選択 —</option>
                      {printerList.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">NC段取シートの印刷で使用</p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleSaveMcNc} disabled={saving} className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors">
                    {saving ? "保存中…" : "保存"}
                  </button>
                </div>
              </section>

              {/* ── DBデータ閲覧 ── */}
              <section className="bg-white rounded-xl shadow p-6">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2 mb-3">🗄 DBデータ閲覧</h2>
                <p className="text-sm text-slate-500 mb-3">DBの各テーブルをそのまま閲覧できます（読み取り専用）</p>
                <button onClick={() => router.push("/admin/raw")}
                  className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white text-sm font-bold rounded-lg transition-colors">
                  RAWデータ閲覧 →
                </button>
              </section>

              {/* ── タイムカードCron設定 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">⏰ タイムカード自動生成（Cron）設定</h2>
                <div className="flex items-center gap-3">
                  <label className="text-sm font-bold text-slate-600">自動生成</label>
                  <button onClick={() => setCronEnabled(v => !v)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-colors ${
                      cronEnabled ? "bg-green-600 text-white" : "bg-slate-200 text-slate-600"
                    }`}>
                    {cronEnabled ? "有効" : "無効"}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">実行時刻（24時間表記）</label>
                    <input type="time" value={cronTime} onChange={e => setCronTime(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">デフォルト開始時刻</label>
                    <input type="time" value={tcDefStart} onChange={e => setTcDefStart(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">デフォルト終了時刻</label>
                    <input type="time" value={tcDefEnd} onChange={e => setTcDefEnd(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                </div>
                <p className="text-xs text-slate-400">毎日 {cronTime} に有効機械全台のタイムカードを自動生成します（営業カレンダーの休日はスキップ）</p>
                <div className="flex justify-end">
                  <button onClick={saveCronSettings} disabled={cronSaving}
                    className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors">
                    {cronSaving ? "保存中…" : "保存"}
                  </button>
                </div>
              </section>

              {/* ── PM2プロセス管理 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">⚙️ PM2プロセス管理</h2>
                <div className="flex gap-2 mb-2">
                  <button onClick={() => restartPm2()} disabled={pm2Restarting !== null}
                    className="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg">
                    {pm2Restarting === "all" ? "再起動中…" : "全プロセス再起動"}
                  </button>
                  <button onClick={savePm2}
                    className="px-3 py-1.5 bg-slate-600 hover:bg-slate-700 text-white text-xs font-bold rounded-lg">
                    pm2 save
                  </button>
                </div>
                {pm2List.length === 0 ? (
                  <p className="text-sm text-slate-400">プロセス情報を取得中…</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-500">
                          <th className="px-3 py-2 text-left font-bold">名前</th>
                          <th className="px-3 py-2 text-left font-bold">状態</th>
                          <th className="px-3 py-2 text-left font-bold">CPU</th>
                          <th className="px-3 py-2 text-left font-bold">再起動</th>
                          <th className="px-3 py-2 text-left font-bold">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {pm2List.map((p: any) => (
                          <tr key={p.name}>
                            <td className="px-3 py-2 font-mono font-bold">{p.name}</td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                p.status === "online" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                              }`}>{p.status}</span>
                            </td>
                            <td className="px-3 py-2">{p.cpu ?? "—"}%</td>
                            <td className="px-3 py-2">{p.restarts ?? 0}回</td>
                            <td className="px-3 py-2">
                              <button onClick={() => restartPm2(p.name)} disabled={pm2Restarting !== null}
                                className="px-2 py-0.5 bg-sky-100 hover:bg-sky-200 text-sky-700 text-[10px] font-bold rounded disabled:opacity-40">
                                {pm2Restarting === p.name ? "…" : "再起動"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}
        </main>
    </AdminLayout>
  );
}
