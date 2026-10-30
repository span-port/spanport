// Dev server and test settings read by vite.config.ts.

// The repo root holds the .env that names the server's host and port.
export const REPO_ROOT = "..";
export const ENV_PREFIX = "SPANPORT_";
// Requests under this path go to the Spanport server (Vite proxy in dev, nginx in Docker).
export const API_PREFIX = "/api";
export const TEST_ENVIRONMENT = "jsdom";
export const TEST_SETUP_FILE = "src/test/setup.ts";
