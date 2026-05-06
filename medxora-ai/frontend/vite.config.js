import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: backendTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: backendTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
