import type { NextConfig } from "next";

const pollMs = Number(process.env.NEXT_WATCH_POLL_MS || 0);

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Self-contained server bundle for the production Docker image (Phase 6).
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Docker Desktop on Windows doesn't forward file-change events into containers, so the dev
  // container polls instead (NEXT_WATCH_POLL_MS is set in docker-compose.yml only).
  ...(pollMs > 0 ? { watchOptions: { pollIntervalMs: pollMs } } : {}),
};

export default nextConfig;
