/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Allow importing the shared read-contract fixtures from the repo root.
      allow: ["..", "../../contracts/read/fixtures"],
    },
  },
  test: {
    globals: true,
    env: { TZ: "America/Bogota" },
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/main.tsx",
        "src/api/generated/**",
        "src/mocks/**",
        "src/vite-env.d.ts",
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
});
