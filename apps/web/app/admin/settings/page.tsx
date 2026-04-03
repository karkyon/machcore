"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { adminSettingsApi } from "../../../lib/api";

export default function AdminSettingsPage() {
  const router = useRouter();

  const [companyName, setCompanyName] = useState("");
  const [logoPath,    setLogoPath]    = useState("");
  const [storagePath, setStoragePath] = useState("");
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    Promise.all([
      adminSettingsApi.getCompany(token),
      adminSettingsApi.getStorage(token),
    ]).then(([comp, stor]) => {
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

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shadow">
        <div className="flex items-center gap-3">
          <span className="font-bold text-lg">MachCore</span>
          <span className="text-slate-400 text-sm">/ 管理者設定</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/admin/users")}
            className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg transition-colors">
            ← ユーザ管理
          </button>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg transition-colors">
            ログアウト
          </button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold transition-all ${toast.ok ? "bg-emerald-500" : "bg-red-500"}`}>
          {toast.msg}
        </div>
      )}

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
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
  );
}