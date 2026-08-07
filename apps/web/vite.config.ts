import { defineConfig } from "vitest/config";
import solid from "vite-plugin-solid";
import path from "node:path";

export default defineConfig({
  plugins: [solid()],
  resolve: {
    alias: {
      debug: path.resolve(__dirname, "src/shims/debug.ts"),
      extend: path.resolve(__dirname, "src/shims/extend.ts"),
    },
  },
  server: {
    proxy: {
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  optimizeDeps: {
    include: [],
  },
  build: {
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    globals: true,
    poolTimeout: 10000,
    teardownTimeout: 5000,
  },
});
