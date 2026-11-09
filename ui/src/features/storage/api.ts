// Setup -> Data -> Storage: how much each project keeps in ClickHouse, and for how long.
import { apiJson } from "../../api/client";
import { STORAGE_PATH } from "../../constants/api";

/** Rows of one kind (log lines or request steps), their estimated size and time span. */
export interface TableUsage {
  rows: number;
  estimated_bytes: number;
  oldest: string | null;
  newest: string | null;
}

export interface ProjectStorage {
  project_id: string;
  client: string;
  project: string;
  environment: string;
  logs: TableUsage;
  spans: TableUsage;
}

export interface StorageSummary {
  logs_retention_days: number;
  spans_retention_days: number;
  totals: { logs: TableUsage; spans: TableUsage };
  projects: ProjectStorage[];
  redis_in_use: boolean;
}

/**
 * The organization's stored logs and traces per project, biggest first.
 *
 * @throws ApiError 403 for members and viewers (owners and admins only).
 */
export function fetchStorage(signal: AbortSignal): Promise<StorageSummary> {
  return apiJson<StorageSummary>(STORAGE_PATH, { signal });
}
