import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 중 /api 프록시를 백엔드(FastAPI 8000)로 전달
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
