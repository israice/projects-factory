import { defineConfig } from "vite";

const backendHost = process.env.PF_BACKEND_HOST || "127.0.0.1";
const backendPort = process.env.PF_BACKEND_PORT || "5999";
const backendTarget = `http://${backendHost}:${backendPort}`;

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": backendTarget,
      "/static": backendTarget,
      "/favicon.ico": backendTarget
    }
  }
});
