import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["pdfjs-dist", "react-pdf"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:3011/api/:path*",
      },
    ];
  },
};

export default nextConfig;
