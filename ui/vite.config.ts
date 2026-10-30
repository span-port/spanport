// Dev server, build and tests. In development, /api goes to the server named in the repo's .env.
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

import {
  API_PREFIX,
  ENV_PREFIX,
  REPO_ROOT,
  TEST_ENVIRONMENT,
  TEST_SETUP_FILE,
} from "./src/constants/build.ts";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, REPO_ROOT, ENV_PREFIX);
  const serverUrl = `http://${env.SPANPORT_SERVER_HOST ?? ""}:${env.SPANPORT_SERVER_PORT ?? ""}`;
  return {
    plugins: [react()],
    server: { proxy: { [API_PREFIX]: serverUrl } },
    test: { environment: TEST_ENVIRONMENT, setupFiles: [TEST_SETUP_FILE] },
  };
});
