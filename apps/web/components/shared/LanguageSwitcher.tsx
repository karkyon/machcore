"use client";
import { useLanguage } from "../../lib/i18n/LanguageContext";

/**
 * 言語切替スイッチャー。日本語/ベトナム語をワンクリックで切り替える。
 * 選択結果は端末(localStorage)に保存され、次回アクセス時も維持される。
 */
export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { lang, setLang, t } = useLanguage();

  return (
    <div className={`inline-flex items-center rounded-lg border border-slate-200 bg-white overflow-hidden ${compact ? "text-[11px]" : "text-xs"}`}
      title={t("dashboard.switchLanguage", "言語切替")}>
      <button
        type="button"
        onClick={() => setLang("ja")}
        className={`px-2.5 py-1 font-bold transition-colors ${lang === "ja" ? "bg-sky-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}
      >
        JA
      </button>
      <button
        type="button"
        onClick={() => setLang("vi")}
        className={`px-2.5 py-1 font-bold transition-colors ${lang === "vi" ? "bg-sky-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}
      >
        VI
      </button>
    </div>
  );
}
