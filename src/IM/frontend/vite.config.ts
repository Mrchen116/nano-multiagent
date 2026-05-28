import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const IM_PROXY_TARGET = process.env.VITE_IM_PROXY_TARGET ?? "http://127.0.0.1:8021";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/im": {
        target: IM_PROXY_TARGET,
        changeOrigin: true
      }
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts"
  }
});
