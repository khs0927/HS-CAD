import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "bootstrap.test.mjs", "deployment-script.test.mjs"],
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    minify: true,
    target: "es2022",
    cssCodeSplit: false,
  },
  publicDir: "public",
});
