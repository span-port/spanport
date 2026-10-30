import { describe, expect, it } from "vitest";

import type { ApiKeyItem } from "../features/apiKeys/api";
import { keySnippets, keyStatus, maskedKey } from "./apiKeys";

const NOW = Date.parse("2026-10-29T07:00:00Z");

function apiKey(overrides: Partial<ApiKeyItem> = {}): ApiKeyItem {
  return {
    id: "k1",
    name: "tracking-prod",
    key_type: "ingest",
    prefix: "sp_ingest_",
    last_four: "a1b2",
    project_id: "p1",
    scopes: [],
    created_at: "2026-10-01T00:00:00Z",
    expires_at: null,
    revoked_at: null,
    ...overrides,
  };
}

describe("API key helpers", () => {
  it("says whether a key still works", () => {
    expect(keyStatus(apiKey(), NOW)).toBe("active");
    expect(keyStatus(apiKey({ expires_at: "2026-10-29T06:59:59Z" }), NOW)).toBe("expired");
    expect(keyStatus(apiKey({ revoked_at: "2026-10-02T00:00:00Z" }), NOW)).toBe("revoked");
  });

  it("shows only the prefix and last four characters", () => {
    expect(maskedKey(apiKey())).toBe("sp_ingest_…a1b2");
  });

  it("keeps the key itself out of the examples", () => {
    const dataExamples = keySnippets("ingest", "http://localhost:8080");
    const adminExamples = keySnippets("admin", "http://localhost:8080");

    expect(dataExamples.map((example) => example.label)).toEqual(["Python", "Node.js"]);
    expect(dataExamples[0]?.code).toContain('os.environ["SPANPORT_DATA_KEY"]');
    expect(adminExamples[0]?.code).toContain("http://localhost:8080/api/v1/logs/search");
    expect(adminExamples[0]?.code).toContain("$SPANPORT_ADMIN_KEY");
  });
});
