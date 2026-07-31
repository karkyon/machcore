"use client";
import { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from "react";
import jaBase from "./dictionaries/ja.json";
import viBase from "./dictionaries/vi.json";

export type LangCode = "ja" | "vi";

type Dict = Record<string, any>;

/** ネストしたオブジェクトを浅く再帰マージする（カスタム辞書での部分上書き用） */
function deepMerge(base: Dict, override: Dict | null | undefined): Dict {
  if (!override) return base;
  const out: Dict = { ...base };
  for (const key of Object.keys(override)) {
    const bv = base[key];
    const ov = override[key];
    if (bv && typeof bv === "object" && !Array.isArray(bv) && ov && typeof ov === "object" && !Array.isArray(ov)) {
      out[key] = deepMerge(bv, ov);
    } else {
      out[key] = ov;
    }
  }
  return out;
}

function getByPath(dict: Dict, path: string): string | undefined {
  const parts = path.split(".");
  let cur: any = dict;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

type LanguageContextType = {
  lang: LangCode;
  setLang: (l: LangCode) => void;
  t: (key: string, fallback?: string) => string;
  dictionaries: { ja: Dict; vi: Dict };
  reloadCustomDictionaries: () => Promise<void>;
};

const LanguageContext = createContext<LanguageContextType>({
  lang: "ja",
  setLang: () => {},
  t: (key: string, fallback?: string) => fallback ?? key,
  dictionaries: { ja: jaBase, vi: viBase },
  reloadCustomDictionaries: async () => {},
});

const STORAGE_KEY = "machcore_lang";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>("ja");
  const [customJa, setCustomJa] = useState<Dict | null>(null);
  const [customVi, setCustomVi] = useState<Dict | null>(null);
  const [ready, setReady] = useState(false);

  const loadServerConfig = useCallback(async () => {
    try {
      const res = await fetch("/api/language/config");
      if (!res.ok) return;
      const data = await res.json();
      setCustomJa(data?.custom_dictionaries?.ja ?? null);
      setCustomVi(data?.custom_dictionaries?.vi ?? null);
      const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      if (stored === "ja" || stored === "vi") {
        setLangState(stored);
      } else if (data?.default_language === "ja" || data?.default_language === "vi") {
        setLangState(data.default_language);
      }
    } catch {
      // サーバー未応答時は日本語既定 + ローカル保存値で継続
      const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      if (stored === "ja" || stored === "vi") setLangState(stored);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => { loadServerConfig(); }, [loadServerConfig]);

  const setLang = useCallback((l: LangCode) => {
    setLangState(l);
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, l);
    if (typeof document !== "undefined") document.documentElement.lang = l === "vi" ? "vi" : "ja";
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = lang === "vi" ? "vi" : "ja";
  }, [lang]);

  const dictionaries = useMemo(() => ({
    ja: deepMerge(jaBase as Dict, customJa),
    vi: deepMerge(viBase as Dict, customVi),
  }), [customJa, customVi]);

  const t = useCallback((key: string, fallback?: string) => {
    const dict = dictionaries[lang];
    const v = getByPath(dict, key);
    if (v !== undefined) return v;
    // 現在言語に無ければ日本語にフォールバックし、それも無ければキー/fallbackを返す
    const jaV = getByPath(dictionaries.ja, key);
    return jaV ?? fallback ?? key;
  }, [dictionaries, lang]);

  const reloadCustomDictionaries = useCallback(async () => { await loadServerConfig(); }, [loadServerConfig]);

  if (!ready) {
    // 初回サーバー応答待ちの間もUIが崩れないよう、既定辞書でそのまま描画する
  }

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, dictionaries, reloadCustomDictionaries }}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useLanguage = () => useContext(LanguageContext);
