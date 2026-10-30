// The keys of one type, ready to show: what each covers and whether it works.
import { useState } from "react";

import { keyStatus, type KeyStatus } from "../../../lib/apiKeys";
import { useProjects } from "../../projects";
import type { ApiKeyItem, KeyType } from "../api";
import { useApiKeys } from "./useApiKeys";

export interface KeyListRow {
  apiKey: ApiKeyItem;
  /** Its project for a data key, its scopes for an admin key. */
  covers: string;
  status: KeyStatus;
}

/**
 * Rows for the keys table, how many keys each type has, and the load error, if any.
 *
 * Statuses are worked out against the time the page opened.
 */
export function useKeyList(keyType: KeyType) {
  const keys = useApiKeys();
  const projects = useProjects();
  const [openedAtMs] = useState(Date.now);
  const projectNames = new Map(
    (projects.data?.data ?? []).map((project) => [
      project.id,
      `${project.client} · ${project.project} · ${project.environment}` +
        (project.archived ? " (archived, key stopped)" : ""),
    ]),
  );
  const allKeys = keys.data?.data ?? [];
  const rows: KeyListRow[] = allKeys
    .filter((apiKey) => apiKey.key_type === keyType)
    .map((apiKey) => ({
      apiKey,
      covers:
        apiKey.key_type === "ingest"
          ? (projectNames.get(apiKey.project_id ?? "") ?? "Unknown project")
          : apiKey.scopes.join(", "),
      status: keyStatus(apiKey, openedAtMs),
    }));
  return {
    rows,
    countOf: (type: KeyType) => allKeys.filter((apiKey) => apiKey.key_type === type).length,
    /** Projects a new data key can be for: archived ones get no new keys. */
    projects: (projects.data?.data ?? []).filter((project) => !project.archived),
    loaded: keys.isSuccess,
    error: keys.error,
  };
}
