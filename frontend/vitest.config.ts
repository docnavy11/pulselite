import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    env: {
      VITE_API_URL: "http://localhost:8000",
    },
    coverage: {
      reporter: ["text", "html"],
      include: ["src/lib/**", "src/stores/**"],
      exclude: ["src/lib/sse.ts"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
