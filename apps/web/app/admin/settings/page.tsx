"use client";
import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminSettingsApi, adminPrinterApi } from "../../../lib/api";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor", label: "PDFエディタ", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
];

const MC_DEFAULT_PATHS = {
  program: "/mnt/ncfiles/mc_programs",
  photo:   "/mnt/ncfiles/mc_files/photos",
  drawing: "/mnt/ncfiles/mc_files/drawings",
};
const NC_DEFAULT_PATHS = {
  program: "/mnt/ncfiles/nc_programs",
  photo:   "/mnt/ncfiles/nc_files/photos",
  drawing: "/mnt/ncfiles/nc_files/drawings",
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
  const [mcStoragePath, setMcStoragePath] = useState("");
  const [mcPrinter,     setMcPrinter]     = useState("");
  // NC設定
  const [ncStoragePath, setNcStoragePath] = useState("");
  const [ncPrinter,     setNcPrinter]     = useState("");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    Promise.all([
      adminSettingsApi.getCompany(token),
      adminPrinterApi.list(token),
      // MC/NC設定
      fetch("/api/admin/settings/mc-nc", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([comp, printers, mcnc]) => {
      setCompanyName(comp.data.companyName ?? "");
      setLogoPath(comp.data.logoPath ?? "");
      setPrinterList(printers.data?.printers ?? []);
      setMcStoragePath(mcnc.mc_storage_path ?? MC_DEFAULT_PATHS.program);
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
    setSaving(true);
    try {
      await fetch("/api/admin/settings/mc-nc", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({
          mc_storage_path: mcStoragePath, nc_storage_path: ncStoragePath,
          mc_printer: mcPrinter, nc_printer: ncPrinter,
        }),
      });
      showToast("設定を保存しました", true);
    } catch { showToast("保存に失敗しました", false); }
    finally { setSaving(false); }
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
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

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold transition-all ${toast.ok ? "bg-emerald-500" : "bg-red-500"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
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
                <div className="grid grid-cols-3 gap-3 text-[11px] text-slate-400 bg-slate-50 rounded-lg p-3">
                  <div><span className="font-bold text-slate-600">プログラム</span><br/>{MC_DEFAULT_PATHS.program}</div>
                  <div><span className="font-bold text-slate-600">写真</span><br/>{MC_DEFAULT_PATHS.photo}</div>
                  <div><span className="font-bold text-slate-600">図</span><br/>{MC_DEFAULT_PATHS.drawing}</div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">MCアップロードベースパス</label>
                  <input type="text" value={mcStoragePath} onChange={e => setMcStoragePath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">MC用ファイル（プログラム・写真・図）のベースパス</p>
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
            </>
          )}
        </main>
      </div>
    </div>
  );
}
