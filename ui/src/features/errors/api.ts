// HTTP errors over time: 4xx and 5xx answers per interval, and one interval's failing requests.
import { apiJson } from "../../api/client";
import { ERROR_SUMMARY_PATH, ERROR_WINDOW_PATH } from "../../constants/api";
import type { ErrorShow } from "../../constants/errors";

/** A project's requests in a range, optionally one API (service, method and route). */
export interface ErrorSearch {
  project_id: string;
  start: string;
  end: string;
  service: string;
  http_method: string;
  route: string;
}

/** One chart bar: `start` and `end` are the interval's edges. */
export interface ErrorWindowSearch extends ErrorSearch {
  show: ErrorShow;
}

export interface ErrorBucket {
  at: string;
  requests: number;
  client_errors: number;
  server_errors: number;
}

/** An API that failed in the range. */
export interface ErrorApi {
  service: string;
  http_method: string;
  route: string;
  errors: number;
}

export interface ErrorSummary {
  bucket_seconds: number;
  buckets: ErrorBucket[];
  totals: { requests: number; client_errors: number; server_errors: number; worst_server: ErrorBucket | null };
  apis: ErrorApi[];
}

export interface ErrorGroup {
  status: number;
  service: string;
  http_method: string;
  route: string;
  requests: number;
}

/** One failing request; `logged` is its most severe log line ("" when it logged nothing). */
export interface FailedRequest {
  trace_id: string;
  span_id: string;
  start_ts: string;
  service: string;
  http_method: string;
  route: string;
  http_status: number;
  duration_ms: number;
  client_ip: string;
  logged: string;
}

export interface ErrorWindow {
  total: number;
  groups: ErrorGroup[];
  requests: FailedRequest[];
}

/**
 * 4xx and 5xx per interval, the totals and the failing APIs.
 *
 * @throws ApiError, e.g. 400 for a range older than 30 days.
 */
export function fetchErrorSummary(search: ErrorSearch, signal: AbortSignal): Promise<ErrorSummary> {
  return apiJson<ErrorSummary>(ERROR_SUMMARY_PATH, { method: "POST", body: search, signal });
}

/**
 * One interval's failing requests: by status and API, and the newest ones.
 *
 * @throws ApiError, e.g. 404 for a project the caller can't see.
 */
export function fetchErrorWindow(search: ErrorWindowSearch, signal: AbortSignal): Promise<ErrorWindow> {
  return apiJson<ErrorWindow>(ERROR_WINDOW_PATH, { method: "POST", body: search, signal });
}
