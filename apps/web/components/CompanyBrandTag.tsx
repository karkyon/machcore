"use client";
import { useCompanyBrand } from "@/lib/hooks/useCompanyBrand";

/**
 * ヘッダーの "MachCore" ロゴの右に会社名(+設定時はTMマーク)を小さく表示する共通タグ。
 * 会社名が未設定の場合は何も表示しない。
 */
export function CompanyBrandTag() {
  const info = useCompanyBrand();
  if (!info || !info.companyName) return null;
  return (
    <span className="text-slate-300 font-medium inline-flex items-center gap-1.5">
      {info.logoPath && (
        <span className="bg-white rounded px-1.5 py-1 inline-flex items-center">
          <img
            src={info.logoPath.replace(/^apps\/web\/public/, "").replace(/^\/+/, "/")}
            alt="logo"
            className="h-6 object-contain align-middle"
          />
        </span>
      )}
      <span className="text-sm">{info.companyName}</span>
    </span>
  );
}
