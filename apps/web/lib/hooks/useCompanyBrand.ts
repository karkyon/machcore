import { useEffect, useState } from "react";

export type CompanyBrand = {
  companyName: string | null;
  logoPath: string | null;
  trademarkMark: string | null;
  showTrademark: boolean;
};

const EMPTY: CompanyBrand = { companyName: null, logoPath: null, trademarkMark: null, showTrademark: false };

let cache: CompanyBrand | null = null;
let inflight: Promise<CompanyBrand> | null = null;

/**
 * 会社設定(会社名・ロゴ・TMマーク)を取得する。 /api/admin/company はGET時は認証不要。
 * プロセス内でキャッシュし、複数ページで再取得しないようにする。
 */
export function useCompanyBrand(): CompanyBrand | null {
  const [info, setInfo] = useState<CompanyBrand | null>(cache);
  useEffect(() => {
    if (cache) { setInfo(cache); return; }
    if (!inflight) {
      inflight = fetch("/api/admin/company")
        .then(r => (r.ok ? r.json() : null))
        .then(data => {
          cache = data
            ? {
                companyName: data.companyName ?? null,
                logoPath: data.logoPath ?? null,
                trademarkMark: data.trademarkMark ?? null,
                showTrademark: !!data.showTrademark,
              }
            : EMPTY;
          return cache;
        })
        .catch(() => EMPTY);
    }
    inflight.then(setInfo);
  }, []);
  return info;
}
