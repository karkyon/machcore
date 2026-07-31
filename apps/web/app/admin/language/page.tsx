"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import { languageApi } from "@/lib/api";

const getToken = () => sessionStorage.getItem("admin_token") ?? "";

export default function AdminLanguagePage() {
  const router = useRouter();
  const pathname = usePathname();
  const { t, lang, dictionaries, reloadCustomDictionaries } = useLanguage();

  const [defaultLang, setDefaultLang] = useState<"ja" | "vi">("ja");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const fileInputJaRef = useRef<HTMLInputElement>(null);
  const fileInputViRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    languageApi.getConfig().then(res => {
      setDefaultLang(res.data.default_language === "vi" ? "vi" : "ja");
    }).finally(() => setLoading(false));
  }, [router]);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSaveDefault = async (l: "ja" | "vi") => {
    setSaving(true);
    try {
      await languageApi.setDefault(l, getToken());
      setDefaultLang(l);
      showToast(t("common.saveSuccess", "保存しました"), true);
    } catch {
      showToast(t("common.saveFailed", "保存に失敗しました"), false);
    } finally {
      setSaving(false);
    }
  };

  const downloadDictionary = (targetLang: "ja" | "vi") => {
    const data = dictionaries[targetLang];
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `machcore_dictionary_${targetLang}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const uploadDictionary = async (targetLang: "ja" | "vi", file: File) => {
    setSaving(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      await languageApi.setDictionary(targetLang, parsed, getToken());
      await reloadCustomDictionaries();
      showToast(t("languageAdmin.uploadSuccess", "辞書をアップロードしました"), true);
    } catch (e: any) {
      if (e instanceof SyntaxError) {
        showToast(t("languageAdmin.invalidJson", "JSONファイルの形式が正しくありません"), false);
      } else {
        showToast(t("languageAdmin.uploadFailed", "辞書のアップロードに失敗しました。JSON形式を確認してください"), false);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout pathname={pathname}>
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-white text-sm font-bold shadow-lg ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}
      <main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">
        <div className="flex items-center justify-between shrink-0">
          <h1 className="text-xl font-bold text-slate-800">{t("languageAdmin.title", "言語設定")}</h1>
        </div>
        {loading ? (
          <div className="text-center py-20 text-slate-400">{t("common.loading", "読み込み中…")}</div>
        ) : (
          <>
            <section className="bg-white rounded-xl shadow p-6 space-y-4">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">
                🌐 {t("languageAdmin.defaultLanguage", "システム既定言語")}
              </h2>
              <p className="text-xs text-slate-500">{t("languageAdmin.defaultLanguageDesc")}</p>
              <div className="flex gap-3">
                <button
                  disabled={saving}
                  onClick={() => handleSaveDefault("ja")}
                  className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${
                    defaultLang === "ja" ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {t("common.japanese", "日本語")}
                </button>
                <button
                  disabled={saving}
                  onClick={() => handleSaveDefault("vi")}
                  className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${
                    defaultLang === "vi" ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {t("common.vietnamese", "ベトナム語")}
                </button>
              </div>
              <p className="text-[11px] text-slate-400">{t("languageAdmin.switchNote")}</p>
            </section>

            <section className="bg-white rounded-xl shadow p-6 space-y-4">
              <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">
                📖 {t("languageAdmin.customDictionary", "カスタム翻訳辞書")}
              </h2>
              <p className="text-xs text-slate-500">{t("languageAdmin.customDictionaryDesc")}</p>

              <div className="grid grid-cols-2 gap-4">
                <div className="border border-slate-200 rounded-lg p-4 space-y-2">
                  <div className="text-sm font-bold text-slate-700">{t("common.japanese", "日本語")}</div>
                  <button onClick={() => downloadDictionary("ja")}
                    className="w-full px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-colors">
                    ⬇ {t("languageAdmin.downloadJa", "日本語辞書をダウンロード")}
                  </button>
                  <input ref={fileInputJaRef} type="file" accept="application/json" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) uploadDictionary("ja", f); e.target.value = ""; }} />
                  <button onClick={() => fileInputJaRef.current?.click()} disabled={saving}
                    className="w-full px-3 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors">
                    ⬆ {t("languageAdmin.uploadJa", "日本語辞書をアップロード")}
                  </button>
                </div>
                <div className="border border-slate-200 rounded-lg p-4 space-y-2">
                  <div className="text-sm font-bold text-slate-700">{t("common.vietnamese", "ベトナム語")}</div>
                  <button onClick={() => downloadDictionary("vi")}
                    className="w-full px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-colors">
                    ⬇ {t("languageAdmin.downloadVi", "ベトナム語辞書をダウンロード")}
                  </button>
                  <input ref={fileInputViRef} type="file" accept="application/json" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) uploadDictionary("vi", f); e.target.value = ""; }} />
                  <button onClick={() => fileInputViRef.current?.click()} disabled={saving}
                    className="w-full px-3 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors">
                    ⬆ {t("languageAdmin.uploadVi", "ベトナム語辞書をアップロード")}
                  </button>
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </AdminLayout>
  );
}
