import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { include: ["evals/**/*.test.ts", "packages/**/*.test.ts", "apps/**/*.test.ts", "src/IM/ios/Runtime/**/*.test.ts"], testTimeout: 15_000 },
});
