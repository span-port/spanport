// Strict, type-aware linting for the SDK source and tests.
import eslint from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["dist", "build", "node_modules", "eslint.config.js"] },
  eslint.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      // The SDK patches console on purpose and writes its own messages to stderr directly.
      "no-console": "off",
      // node:test's describe/it return promises the runner tracks itself.
      "@typescript-eslint/no-floating-promises": [
        "error",
        {
          allowForKnownSafeCalls: [
            { from: "package", name: ["describe", "it", "test"], package: "node:test" },
          ],
        },
      ],
    },
  },
);
