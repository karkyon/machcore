"use client";
import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminSettingsApi, adminPrinterApi } from "../../../lib/api";

export default function AdminSettingsPage() {
  const router = useRouter();
  const pathname = usePathname();

  const [companyName, setCompanyName] = useState("");
  const [logoPath,    setLogoPath]    = useState("");
  const [storagePath, setStoragePath] = useState("");
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);
  const [printerList,   setPrinterList]   = useState<string[]>([]);
  const [selectedPrinter, setSelectedPrinter] = useState("");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    Promise.all([
      adminSettingsApi.getCompany(token),
      adminSettingsApi.getStorage(token),
      adminPrinterApi.list(token),
      adminPrinterApi.get(token),
    ]).then(([comp, stor, printers, currentPrinter]) => {
      setCompanyName(comp.data.companyName ?? "");
      setLogoPath(comp.data.logoPath ?? "");
      setStoragePath(stor.data.uploadBasePath ?? "");
    }).catch(() => showToast("設定の取得に失敗しました", false))
      .finally(() => setLoading(false));
  }, [router]);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSaveCompany = async () => {
    setSaving(true);
    try {
      await adminSettingsApi.updateCompany(
        { company_name: companyName, logo_path: logoPath || undefined },
        getToken(),
      );
      showToast("会社設定を保存しました", true);
    } catch {
      showToast("保存に失敗しました", false);
    } finally { setSaving(false); }
  };

  const handleSavePrinter = async () => {
    const token = getToken();
    setSaving(true);
    try {
      await adminPrinterApi.update(selectedPrinter, token);
      setToast({ msg: "✅ プリンタ設定を保存しました", ok: true });
    } catch {
      setToast({ msg: "❌ 保存に失敗しました", ok: false });
    } finally { setSaving(false); }
  };

  const handleSaveStorage = async () => {
    if (!storagePath.trim()) { showToast("パスを入力してください", false); return; }
    setSaving(true);
    try {
      await adminSettingsApi.updateStorage(storagePath.trim(), getToken());
      showToast("ストレージパスを保存しました", true);
    } catch {
      showToast("保存に失敗しました", false);
    } finally { setSaving(false); }
  };

  const SIDEBAR_ITEMS = [
    { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
    { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
    { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
    { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-slate-900 text-white px-5 py-2.5 flex items-center gap-3 shrink-0 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/nc/search"
            className="text-xs bg-slate-600 hover:bg-slate-500 text-slate-200 px-3 py-1.5 rounded transition-colors">
            ← NC画面
          </a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded transition-colors">
            ログアウト
          </button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold transition-all ${toast.ok ? "bg-emerald-500" : "bg-red-500"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <aside className="w-48 shrink-0 bg-slate-800 flex flex-col py-4 gap-1 border-r border-slate-700">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-600 text-white font-bold" : "text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>
        <main className="flex-1 overflow-y-auto p-6 max-w-2xl">
        {loading ? (
          <div className="text-center py-20 text-slate-400">読み込み中…</div>
        ) : (
          <>
            {/* ── 会社情報 ── */}
            <section className="bg-white rounded-xl shadow p-6 space-y-4">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">
                🏢 会社情報
              </h2>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">会社名</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  placeholder="例: 株式会社〇〇製作所"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">ロゴ画像パス（サーバ相対パス）</label>
                <input
                  type="text"
                  value={logoPath}
                  onChange={e => setLogoPath(e.target.value)}
                  placeholder="例: uploads/logo/company_logo.png"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
                <p className="text-[11px] text-slate-400 mt-1">アップロードしたロゴファイルのサーバ上のパスを入力してください</p>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleSaveCompany}
                  disabled={saving}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                >
                  {saving ? "保存中…" : "保存"}
                </button>
              </div>
            </section>

            {/* ── ストレージ設定 ── */}
            <section className="bg-white rounded-xl shadow p-6 space-y-4">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">
                💾 ファイル保存先（ストレージパス）
              </h2>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">アップロードベースパス</label>
                <input
                  type="text"
                  value={storagePath}
                  onChange={e => setStoragePath(e.target.value)}
                  placeholder="例: /home/karkyon/projects/machcore/uploads"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  NCプログラム・写真・図面の保存先ディレクトリを絶対パスで指定してください。変更後は新規アップロード分から適用されます。
                </p>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleSaveStorage}
                  disabled={saving}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                >
                  {saving ? "保存中…" : "保存"}
                </button>
              </div>
            </section>

            {/* ── プリンタ設定 ── */}
            <section className="bg-white rounded-xl shadow p-6 space-y-4">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">
                🖨 ダイレクト印刷プリンタ設定
              </h2>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">使用プリンタ</label>
                <select
                  value={selectedPrinter}
                  onChange={e => setSelectedPrinter(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white"
                >
                  <option value="">— 選択してください —</option>
                  {printerList.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <p className="text-[11px] text-slate-400 mt-1">
                  サーバに登録されているCUPSプリンタが表示されます。段取シート画面のダイレクト印刷で使用されます。
                </p>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleSavePrinter}
                  disabled={saving || !selectedPrinter}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                >
                  {saving ? "保存中…" : "保存"}
                </button>
              </div>
            </section>

            {/* ── RAWデータ閲覧 ── */}
            <section className="bg-white rounded-xl shadow p-6">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2 mb-3">
                🗄 DBデータ閲覧
              </h2>
              <p className="text-sm text-slate-500 mb-3">DBの各テーブルをそのまま閲覧できます（読み取り専用）</p>
              <button
                onClick={() => router.push("/admin/raw")}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white text-sm font-bold rounded-lg transition-colors"
              >
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