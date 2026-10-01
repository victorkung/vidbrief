import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Ports can be overridden to run a second instance (e.g. a demo library) alongside your own.
const apiPort = process.env.VIDBRIEF_API_PORT || "8788";
const uiPort = Number(process.env.VIDBRIEF_UI_PORT || 5174);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: uiPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
});
