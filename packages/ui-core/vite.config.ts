import { defineConfig } from "vitest/config";
import solid from "vite-plugin-solid";
import path from "node:path";

export default defineConfig({
  plugins: [solid()],
  resolve: {
    alias: {
      debug: path.resolve(__dirname, "src/shims/debug.ts"),
    },
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, "src/index.ts"),
      formats: ["es", "cjs"],
      fileName: (format) => `index.${format === "es" ? "js" : "cjs"}`,
    },
    rollupOptions: {
      external: [
        "solid-js",
        "solid-markdown",
        "remark-gfm",
        "highlight.js",
        "@inkstatute/platform-sdk-ts",
        "@inkstatute/platform-sdk-ts/events",
      ],
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    globals: true,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx", "tests/**/test_*.ts"],
  },
});
