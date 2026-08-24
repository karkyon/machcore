import type { NextConfig } from "next";

// 複数インスタンス（自社/グループ会社）共存に対応するため環境変数化。
// 未設定時は従来のデフォルト値（自社環境）を使用する。
const allowedOrigins = (
  process.env.NEXT_ALLOWED_ORIGINS ?? "192.168.1.11,https://192.168.1.11:8443"
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const apiPort = process.env.API_PORT ?? "3011";

const nextConfig: NextConfig = {
  allowedDevOrigins: allowedOrigins,
  serverExternalPackages: ["pdfjs-dist", "react-pdf"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `http://localhost:${apiPort}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
