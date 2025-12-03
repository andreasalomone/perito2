import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
  reactCompiler: true,
  // Add this headers function
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Cross-Origin-Opener-Policy",
            value: "same-origin-allow-popups", // Essential for Firebase Auth
          },
          {
            key: "Cross-Origin-Embedder-Policy",
            value: "credentialless", // Helps with loading external resources like Firebase scripts
          },
        ],
      },
    ];
  },
};

export default nextConfig;
