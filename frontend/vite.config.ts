import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the backend: port 8810 (docs/code/README.md), or WINGS_BACKEND_PORT when a second
// backend runs next to it (e.g. `WINGS_BACKEND_PORT=8861 npx vite --port 5221`). Read from the environment or frontend/.env.
export default defineConfig(({ mode }) => {
  const port = loadEnv(mode, ".", "WINGS_").WINGS_BACKEND_PORT?.trim() || "8810";
  if (!/^\d+$/.test(port)) throw new Error(`WINGS_BACKEND_PORT must be a port number, not "${port}".`);
  return {
    plugins: [react()],
    server: { port: 5190, strictPort: true, proxy: { "/api": `http://127.0.0.1:${port}` } },
    test: { globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false },
  };
});
