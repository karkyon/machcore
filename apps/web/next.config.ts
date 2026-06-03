import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.1.11", "https://192.168.1.11:8443"],
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
