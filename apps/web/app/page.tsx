"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * ルート"/"は後方互換のためのリダイレクトのみ。
 * MC/NCダッシュボードはそれぞれ独立しており、相互遷移はしない。
 * "/" への直接アクセスはMC側へ送るが、これは便宜上の入口であり
 * MC↔NC間の行き来を意図したものではない。
 */
export default function RootRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/mc"); }, [router]);
  return null;
}
