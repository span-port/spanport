// Clients and projects, and API keys (the Setup screens).

// Names become slugs: lower-case letters, digits and dashes, as the server requires.
export const SLUG_MAX_LENGTH = 63;
export const SLUG_SEPARATOR = "-";
export const NOT_SLUG_CHARACTERS = /[^a-z0-9]+/g;
export const EDGE_SEPARATORS = /^-+|-+$/g;

export const ENVIRONMENTS = [
  { value: "production", label: "Production" },
  { value: "staging", label: "Staging" },
  { value: "development", label: "Development" },
] as const;

export const MAX_KEY_NAME_LENGTH = 100;
export const DEFAULT_ADMIN_KEY_DAYS = 30;
export const MAX_ADMIN_KEY_DAYS = 90;
export const ADMIN_SCOPES = [
  { scope: "logs:read", label: "Read logs" },
  { scope: "projects:read", label: "See projects" },
] as const;

// Key types the UI can make today; LLM and browser keys come with the gateway and browser SDK.
export const KEY_TABS = [
  { keyType: "ingest", label: "Data keys", available: true },
  { keyType: "admin", label: "Admin keys", available: true },
  { keyType: "llm", label: "LLM keys", available: false },
  { keyType: "browser", label: "Browser keys", available: false },
] as const;

export const CLIENT_MESSAGE = "Type a client name with letters or digits.";
export const PROJECT_MESSAGE = "Type a project name with letters or digits.";
export const ENVIRONMENT_MESSAGE = "Choose or add an environment.";
export const ARCHIVE_CONFIRM_LABEL = "Click again to archive";
export const DELETE_CONFIRM_LABEL = "Click again to delete";
export const KEY_RENAME_MESSAGE = "A key name can't be empty.";
export const KEY_NAME_MESSAGE = "Give the key a name, e.g. tracking-prod.";
export const KEY_PROJECT_MESSAGE = "Choose the project this key sends data for.";
export const KEY_SCOPES_MESSAGE = "Choose at least one thing the key may do.";
export const KEY_DAYS_MESSAGE = `Admin keys expire within 1 to ${MAX_ADMIN_KEY_DAYS} days.`;
// Two clicks to revoke, so a stray click can't break an app.
export const REVOKE_CONFIRM_LABEL = "Click again to revoke";
