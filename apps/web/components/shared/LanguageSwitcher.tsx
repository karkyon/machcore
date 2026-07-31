"use client";
import { useLanguage } from "../../lib/i18n/LanguageContext";

/**
 * 言語切替スイッチャー。
 * [仕様変更] 個人・端末ごとの言語切替は廃止し、表示言語は管理画面
 * (/admin/language)の既定言語設定に一元化した。このコンポーネントは
 * 削除せず残しつつ、通常の呼び出し箇所では hidden=true を指定して
 * 非表示にする(将来的な個別プレビュー等での再利用に備えるため)。
 */
export function LanguageSwitcher({ compact = false, hidden = false }: { compact?: boolean; hidden?: boolean }) {
  const { lang, setLang, t } = useLanguage();

  return (
    <div className={`${hidden ? "hidden" : "inline-flex"} items-center rounded-lg border border-slate-200 bg-white overflow-hidden ${compact ? "text-[11px]" : "text-xs"}`}
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
