import { defineConfig } from "vite";

// O frontend conversa APENAS com o backend próprio do ARKHER.
// Em desenvolvimento, /api é proxy para o backend local; em produção,
// o próprio backend serve este build (caminhos relativos).
export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.ARKHER_BACKEND_PROXY ?? "http://127.0.0.1:8710",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
