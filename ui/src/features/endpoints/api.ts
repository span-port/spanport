// API monitoring: per endpoint, how many requests, how fast, how many failed, and where the time went.
import { apiJson } from "../../api/client";
import { ENDPOINT_DETAIL_PATH, ENDPOINT_SUMMARY_PATH, SERVICE_MAP_PATH } from "../../constants/api";

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
  /** The slow-5% time in the period of the same length just before; null without requests then. */
  previous_p95_ms: number | null;
}

/** A database query an API runs, with how often per request and how long. */
export interface SlowQuery {
  statement: string;
  service: string;
  http_method: string;
  route: string;
  calls: number;
  calls_per_request: number;
  avg_ms: number;
  p95_ms: number;
  total_ms: number;
}

export interface EndpointSummary {
  totals: { requests: number; errors: number; p95_ms: number; previous_p95_ms: number | null };
  data: EndpointStats[];
  slow_queries: SlowQuery[];
  has_more: boolean;
}

/** One endpoint (as the APIs list names it) in a time range. */
export interface EndpointDetailSearch extends EndpointSearch {
  service: string;
  http_method: string;
  route: string;
}

export interface TimelinePoint {
  at: string;
  requests: number;
  errors: number;
  p95_ms: number;
}

/** One step the endpoint makes: `kind` is code, db, external or llm. */
export interface EndpointStep {
  kind: string;
  name: string;
  calls: number;
  calls_per_request: number;
  avg_ms: number;
  p95_ms: number;
  total_ms: number;
}

export interface SlowRequest {
  trace_id: string;
  span_id: string;
  start_ts: string;
  duration_ms: number;
  http_status: number;
  error: boolean;
}

/** `summary` is null when the endpoint had no requests in the range. */
export interface EndpointDetail {
  summary: EndpointStats | null;
  bucket_seconds: number;
  timeline: TimelinePoint[];
  statuses: { status: number; requests: number }[];
  steps: EndpointStep[];
  slowest: SlowRequest[];
}

/**
 * One endpoint over the range: numbers, timeline, status codes, steps and slowest requests.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function fetchEndpointDetail(search: EndpointDetailSearch, signal: AbortSignal): Promise<EndpointDetail> {
  return apiJson<EndpointDetail>(ENDPOINT_DETAIL_PATH, { method: "POST", body: search, signal });
}

export type MapKind = "service" | "db" | "external" | "llm";
export type MapStatus = "ok" | "slow" | "bad";

/** One box: a service of yours, a database, another system or an LLM provider. */
export interface MapNode {
  id: string;
  kind: MapKind;
  name: string;
  calls: number;
  errors: number;
  p50_ms: number;
  p95_ms: number;
  status: MapStatus;
  calls_to: string[];
  called_by: string[];
}

/** One line: calls from `source` to `target` (node ids). */
export interface MapEdge {
  source: string;
  target: string;
  calls: number;
  errors: number;
  p50_ms: number;
  p95_ms: number;
  status: MapStatus;
}

export interface ServiceMap {
  range_seconds: number;
  nodes: MapNode[];
  edges: MapEdge[];
}

/**
 * What calls what in the project over the range.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function fetchServiceMap(search: EndpointSearch, signal: AbortSignal): Promise<ServiceMap> {
  return apiJson<ServiceMap>(SERVICE_MAP_PATH, { method: "POST", body: search, signal });
}

/**
 * The project's request totals and busiest endpoints in the range.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function fetchEndpointSummary(search: EndpointSearch, signal: AbortSignal): Promise<EndpointSummary> {
  return apiJson<EndpointSummary>(ENDPOINT_SUMMARY_PATH, { method: "POST", body: search, signal });
}
