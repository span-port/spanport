// Pure helpers for the API keys screen: status and the setup snippets for a new key.
import type { ApiKeyItem, KeyType } from "../features/apiKeys/api";

export type KeyStatus = "active" | "expired" | "revoked";

/** Whether a key works now. */
export function keyStatus(key: ApiKeyItem, nowMs: number): KeyStatus {
  if (key.revoked_at !== null) return "revoked";
  if (key.expires_at !== null && Date.parse(key.expires_at) <= nowMs) return "expired";
  return "active";
}

/** How a key is shown: its prefix and last four characters, e.g. "sp_ingest_…a1b2". */
export function maskedKey(key: ApiKeyItem): string {
  return `${key.prefix}…${key.last_four}`;
}

export interface KeySnippet {
  label: string;
  code: string;
}

/**
 * Examples for using a new key, keeping the key itself in an environment variable.
 *
 * @param origin - Where Spanport is opened, e.g. "http://localhost:8080".
 */
export function keySnippets(keyType: KeyType, origin: string): KeySnippet[] {
  if (keyType === "ingest") {
    return [
      {
        label: "Python",
        code:
          'pip install spanport\n\nimport os, spanport\n\nspanport.init(\n    data_key=os.environ["SPANPORT_DATA_KEY"],   # sp_ingest_…\n    service="my-service",\n)',
      },
      {
        label: "Node.js",
        code:
          'npm install spanport\n\nimport * as spanport from "spanport";\n\nspanport.init({\n  dataKey: process.env.SPANPORT_DATA_KEY,   // sp_ingest_…\n  service: "my-service",\n});',
      },
    ];
  }
  return [
    {
      label: "cURL",
      code:
        `curl -X POST ${origin}/api/v1/logs/search \\\n` +
        '  -H "Authorization: Bearer $SPANPORT_ADMIN_KEY" -H "Content-Type: application/json" \\\n' +
        `  -d '{"project_id": "...", "start": "...", "end": "...", "query": "level:ERROR"}'`,
    },
  ];
}
