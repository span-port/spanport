// Pure helpers for the Errors screen: the stacked chart, status meanings, shares and links.
import {
  ERROR_LOGS_QUERY,
  FIRST_SERVER_ERROR,
  STATUS_MEANINGS,
  type ErrorShow,
} from "../constants/errors";
import {
  MODE_QUERY,
  RANGE_ABSOLUTE,
  URL_PARAM_END,
  URL_PARAM_MODE,
  URL_PARAM_PROJECT,
  URL_PARAM_QUERY,
  URL_PARAM_RANGE,
  URL_PARAM_START,
} from "../constants/logs";
import {
  CHART_BAR_GAP,
  CHART_WIDTH,
  MS_PER_MINUTE,
  MS_PER_SECOND,
  PERCENT,
  REQUEST_RANGES,
  URL_FLAG_ON,
  URL_PARAM_ERRORS,
  URL_PARAM_REQUEST_RANGE,
  URL_PARAM_ROUTE,
  URL_PARAM_SERVICE,
} from "../constants/traces";
import { LOGS_ROUTE, REQUESTS_ROUTE } from "../constants/ui";
import type { ErrorBucket } from "../features/errors/api";

/** The 5xx and 4xx a choice of "show" keeps of an interval (the other kind counts 0). */
export function shownErrors(bucket: ErrorBucket, show: ErrorShow): { server: number; client: number } {
  return {
    server: show === "4xx" ? 0 : bucket.server_errors,
    client: show === "5xx" ? 0 : bucket.client_errors,
  };
}

export interface ErrorBar {
  bucket: ErrorBucket;
  /** Where the bar starts and how wide it is, in percent of the chart's width. */
  leftPercent: number;
  widthPercent: number;
  /** The bar's 5xx and 4xx parts, in percent of the chart's height. */
  serverPercent: number;
  clientPercent: number;
}

/**
 * Where each interval's bar goes (5xx at the bottom, 4xx on top) and the tallest bar's count.
 * Intervals without shown errors get no bar.
 */
export function errorChart(
  buckets: ErrorBucket[],
  startIso: string,
  endIso: string,
  bucketSeconds: number,
  show: ErrorShow,
): { bars: ErrorBar[]; maxErrors: number } {
  const startMs = Date.parse(startIso);
  const spanMs = Math.max(Date.parse(endIso) - startMs, 1);
  const shown = buckets.map((bucket) => shownErrors(bucket, show));
  const maxErrors = Math.max(1, ...shown.map((errors) => errors.server + errors.client));
  const gapPercent = (CHART_BAR_GAP / CHART_WIDTH) * PERCENT;
  const widthPercent = Math.max(gapPercent, ((bucketSeconds * MS_PER_SECOND) / spanMs) * PERCENT - gapPercent);
  const bars = buckets.map((bucket, index) => {
    const errors = shown[index] ?? { server: 0, client: 0 };
    return {
      bucket,
      leftPercent: Math.max(0, ((Date.parse(bucket.at) - startMs) / spanMs) * PERCENT),
      widthPercent,
      serverPercent: (errors.server / maxErrors) * PERCENT,
      clientPercent: (errors.client / maxErrors) * PERCENT,
    };
  });
  return { bars: bars.filter((bar) => bar.serverPercent + bar.clientPercent > 0), maxErrors };
}

/** What a status code means in words, e.g. 401 → "Not signed in (wrong or missing credentials)". */
export function statusMeaning(status: number): string {
  return STATUS_MEANINGS[status] ?? (status >= FIRST_SERVER_ERROR ? "Server error" : "Request error");
}

/** A share of requests with two decimals, e.g. 31 of 12,410 → "0.25%". */
export function requestShare(errors: number, requests: number): string {
  if (requests === 0) return "0%";
  return `${((errors / requests) * PERCENT).toFixed(2)}%`;
}

/** The end of the interval starting at `at`, as an ISO time. */
export function bucketEnd(at: string, bucketSeconds: number): string {
  return new Date(Date.parse(at) + bucketSeconds * MS_PER_SECOND).toISOString();
}

/** The Logs page searching error lines over one interval. */
export function errorLogsLink(projectId: string, startIso: string, endIso: string): string {
  const params = new URLSearchParams({
    [URL_PARAM_PROJECT]: projectId,
    [URL_PARAM_RANGE]: RANGE_ABSOLUTE,
    [URL_PARAM_START]: startIso,
    [URL_PARAM_END]: endIso,
    [URL_PARAM_QUERY]: ERROR_LOGS_QUERY,
    [URL_PARAM_MODE]: MODE_QUERY,
  });
  return `${LOGS_ROUTE}?${params.toString()}`;
}

/**
 * The Requests page with failed requests (optionally of one API) over the shortest quick range
 * that still reaches back to `startIso` (Requests has quick ranges only).
 */
export function failedRequestsLink(
  projectId: string,
  startIso: string,
  nowMs: number,
  api: { service: string; route: string },
): string {
  const minutesBack = (nowMs - Date.parse(startIso)) / MS_PER_MINUTE;
  const covering = REQUEST_RANGES.find((choice) => choice.minutes >= minutesBack) ?? REQUEST_RANGES.at(-1);
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId, [URL_PARAM_ERRORS]: URL_FLAG_ON });
  if (covering) params.set(URL_PARAM_REQUEST_RANGE, covering.key);
  if (api.service) params.set(URL_PARAM_SERVICE, api.service);
  if (api.route) params.set(URL_PARAM_ROUTE, api.route);
  return `${REQUESTS_ROUTE}?${params.toString()}`;
}
