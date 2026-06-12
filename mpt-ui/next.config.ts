import type { NextConfig } from "next";

// URL del backend FastAPI. En desarrollo es localhost; en Docker se pasa
// como build-arg/env (ej. http://api:8080, el nombre del servicio).
// OJO: las rewrites se serializan en el build — definir MPT_API_URL al BUILDEAR.
const API_URL = process.env.MPT_API_URL || "http://localhost:8080";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/mpt/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
