import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The backend runs on 8810 (see docs/code/README.md); the dev server proxies /api to it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5190, strictPort: true, proxy: { "/api": "http://127.0.0.1:8810" } },
  test: { globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false },
});
