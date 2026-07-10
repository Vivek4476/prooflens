import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
    env: {
      // Server-only BFF proxy vars (src/app/api/[...path]/route.ts) — dummy
      // values so unit tests can assert header injection without real secrets.
      PROOFLENS_API_URL: "http://localhost:8000",
      PROOFLENS_TENANT_KEY: "test-tenant-key",
      PROOFLENS_ADMIN_TOKEN: "test-admin-token",
    },
  },
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
});
