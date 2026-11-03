// API monitoring: per endpoint, how many requests, how fast, how many failed, and where the time went.
import { apiJson } from "../../api/client";
import { ENDPOINT_SUMMARY_PATH } from "../../constants/api";

export interface EndpointSearch {
  project_id: string;
  start: string;
  end: string;
}

/** Average milliseconds per request in each kind of step; they add up to `avg_ms`. */
export interface EndpointLayers {
  code_ms: number;
  db_ms: number;
  external_ms: number;
  llm_ms: number;
}

export interface EndpointStats {
  service: string;
  http_method: string;
  route: string;
  requests: number;
  errors: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  avg_ms: number;
  layers: EndpointLayers;
}

export interface EndpointSummary {
  totals: { requests: number; errors: number; p95_ms: number };
  data: EndpointStats[];
  has_more: boolean;
}

/**
 * The project's request totals and busiest endpoints in the range.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function fetchEndpointSummary(search: EndpointSearch, signal: AbortSignal): Promise<EndpointSummary> {
  return apiJson<EndpointSummary>(ENDPOINT_SUMMARY_PATH, { method: "POST", body: search, signal });
}
