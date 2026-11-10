import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// В режиме разработки запросы к /api проксируются на бэкенд,
// поэтому CORS настраивать не нужно.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_URL || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
      },
    },
    preview: {
      port: 4173,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
      },
    },
  };
});
