// Strict, type-aware linting plus the React hooks rules.
import eslint from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["dist", "node_modules", "eslint.config.js"] },
  eslint.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "no-console": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
    },
  },
  {
    // Components only display: data comes through hooks, never straight from fetch or api modules.
    files: ["src/**/components/**/*.tsx"],
    rules: {
      "no-restricted-globals": ["error", { name: "fetch", message: "Fetch data in a hook." }],
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            // A feature's api.ts ("../api"), not the shared client in src/api/.
            { regex: "(^|/)api$", allowTypeImports: true, message: "Call a feature's API from a hook." },
          ],
        },
      ],
    },
  },
);
