import { redirect } from "next/navigation";

/**
 * ルート"/"は後方互換のためのリダイレクトのみ。
 * MC/NCダッシュボードはそれぞれ独立しており、相互遷移はしない。
 * "/" への直接アクセスはMC側へ送るが、これは便宜上の入口であり
 * MC↔NC間の行き来を意図したものではない。
 *
 * サーバーコンポーネントの redirect() を使用する（クライアントコンポーネント+
 * useEffectによるリダイレクトはNext.js 16 Turbopackで
 * "client reference manifest for route / does not exist" の不具合を
 * 引き起こすことがあるため、根本的に回避する）。
 */
export default function RootPage() {
  redirect("/mc");
}
