// Requests (traces): search a project's incoming requests, and one trace's spans.
import { apiJson } from "../../api/client";
import { TRACE_SEARCH_PATH, TRACES_PATH } from "../../constants/api";
import { REQUESTS_PAGE_SIZE } from "../../constants/traces";

export interface RequestItem {
  trace_id: string;
  span_id: string;
  service: string;
  name: string;
  http_method: string;
  http_route: string;
  http_status: number;
  error: boolean;
  start_ts: string;
  duration_ms: number;
}

export interface RequestSearch {
  project_id: string;
  start: string;
  end: string;
  service: string;
  route: string;
  min_duration_ms: number;
  errors_only: boolean;
}

interface RequestPage {
  data: RequestItem[];
  next_cursor: string | null;
  has_more: boolean;
}

/** One step of a trace. `label`: incoming_request, code, db, llm, service_call or external. */
export interface SpanItem {
  span_id: string;
  parent_span_id: string;
  service: string;
  name: string;
  kind: string;
  label: string;
  start_ts: string;
  offset_ms: number;
  duration_ms: number;
  self_ms: number;
  status_code: string;
  status_message: string;
  http_method: string;
  http_route: string;
  http_status: number;
  attributes: Record<string, string>;
}

export interface TraceDetail {
  trace_id: string;
  start_ts: string;
  duration_ms: number;
  spans: SpanItem[];
  truncated: boolean;
}

/**
 * One page of incoming requests, newest first.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function searchRequests(search: RequestSearch, cursor: string | null, signal: AbortSignal): Promise<RequestPage> {
  return apiJson<RequestPage>(TRACE_SEARCH_PATH, {
    method: "POST",
    body: { ...search, limit: REQUESTS_PAGE_SIZE, cursor },
    signal,
  });
}

/**
 * Every span of one trace in the project.
 *
 * @throws ApiError 404 when the trace isn't in this project (or older than 30 days).
 */
export function fetchTrace(traceId: string, projectId: string, signal: AbortSignal): Promise<TraceDetail> {
  const query = new URLSearchParams({ project_id: projectId });
  return apiJson<TraceDetail>(`${TRACES_PATH}/${encodeURIComponent(traceId)}?${query.toString()}`, { signal });
}
