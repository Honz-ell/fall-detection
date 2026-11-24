import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*.e2b.app"],
  async rewrites() {
    const modelApi = process.env.MODEL_REGISTRY_URL || "http://127.0.0.1:8000";
    const deviceApi = process.env.DEVICE_MANAGER_URL || "http://127.0.0.1:8001";
    return [
      { source: "/api/models/:path*", destination: `${modelApi}/models/:path*` },
      { source: "/api/devices/:path*", destination: `${deviceApi}/devices/:path*` },
    ];
  },
};

export default nextConfig;
