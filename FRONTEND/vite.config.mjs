import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:5999",
      "/static": "http://127.0.0.1:5999",
      "/favicon.ico": "http://127.0.0.1:5999"
    }
  }
});
