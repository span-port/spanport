// Pure helpers for the APIs screen: error rates, where the time goes, and links to the requests.
import { URL_PARAM_PROJECT } from "../constants/logs";
import {
  CHART_BAR_GAP,
  CHART_HEIGHT,
  CHART_WIDTH,
  DEFAULT_REQUEST_RANGE,
  DOMINANT_STEP_PERCENT,
  MS_PER_SECOND,
  N_PLUS_ONE_CALLS,
  ONE_DECIMAL_BELOW_PERCENT,
  P95_RISE_TIMES,
  PERCENT,
  SLOWER_THAN_P50,
  SLOWER_THAN_P95,
  SLOWER_THAN_P99,
  STATUS_GROUP_SIZE,
  STEP_KINDS,
  URL_PARAM_METHOD,
  URL_PARAM_REQUEST_RANGE,
  URL_PARAM_ROUTE,
  URL_PARAM_SERVICE,
} from "../constants/traces";
import { API_DETAIL_ROUTE, REQUESTS_ROUTE } from "../constants/ui";
import type { EndpointLayers, EndpointStats, TimelinePoint } from "../features/endpoints/api";
import { writeRange, type RangeSelection } from "./timeRange";
import type { StepKind, StepTimes } from "./waterfall";
import { formatDuration, stepKindName } from "./waterfall";

/** An endpoint's step times keyed like a trace's, so both screens share the colours and names. */
export function layerTimes(layers: EndpointLayers): StepTimes {
  return { code: layers.code_ms, db: layers.db_ms, external: layers.external_ms, llm: layers.llm_ms };
}

/** e.g. "0%", "0.4%", "1.9%" (one decimal below 10%), "25%". */
export function errorRate(errors: number, requests: number): string {
  if (requests === 0 || errors === 0) return "0%";
  const percent = (errors / requests) * PERCENT;
  return `${percent < ONE_DECIMAL_BELOW_PERCENT ? percent.toFixed(1) : String(Math.round(percent))}%`;
}

/** Each kind of step's share of the time, in display order, as percentages adding up to 100. */
export function stepShares(times: StepTimes): { kind: StepKind; percent: number }[] {
  const totalMs = STEP_KINDS.reduce((sum, kind) => sum + times[kind], 0);
  if (totalMs <= 0) return [];
  return STEP_KINDS.map((kind) => ({ kind, percent: (times[kind] / totalMs) * PERCENT })).filter(
    (share) => share.percent > 0,
  );
}

/** "Database 82%" when one kind of step takes a large share of the time, else an empty string. */
export function dominantStep(times: StepTimes): string {
  const largest = stepShares(times).reduce<{ kind: StepKind; percent: number } | null>(
    (best, share) => (best === null || share.percent > best.percent ? share : best),
    null,
  );
  if (largest === null || largest.percent < DOMINANT_STEP_PERCENT) return "";
  return `${stepKindName(largest.kind)} ${String(Math.round(largest.percent))}%`;
}

/** One API's detail page, in the same range. */
export function endpointDetailLink(
  projectId: string,
  range: RangeSelection,
  endpoint: Pick<EndpointStats, "service" | "http_method" | "route">,
): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId });
  writeRange(range, params);
  params.set(URL_PARAM_SERVICE, endpoint.service);
  params.set(URL_PARAM_METHOD, endpoint.http_method);
  params.set(URL_PARAM_ROUTE, endpoint.route);
  return `${API_DETAIL_ROUTE}?${params.toString()}`;
}

export interface ChartBar {
  x: number;
  width: number;
  requestsHeight: number;
  errorsHeight: number;
  point: TimelinePoint;
}

/**
 * Splits the slow-5% line wherever intervals are missing, so it never suggests a p95 for a time
 * with no requests. Each segment is an SVG polyline `points` string; a lone interval becomes a
 * short flat tick across its bar (a dot would stretch, since the chart doesn't keep its aspect).
 */
function p95Segments(bars: ChartBar[], bucketMs: number, maxP95Ms: number): string[] {
  const runs: ChartBar[][] = [];
  let previousAt = Number.NEGATIVE_INFINITY;
  for (const bar of bars) {
    const at = Date.parse(bar.point.at);
    if (at - previousAt > bucketMs || runs.length === 0) runs.push([]);
    runs[runs.length - 1]?.push(bar);
    previousAt = at;
  }
  const y = (bar: ChartBar) => (CHART_HEIGHT - (bar.point.p95_ms / maxP95Ms) * CHART_HEIGHT).toFixed(1);
  return runs.map((run) => {
    const [only] = run;
    if (run.length === 1 && only) {
      return `${only.x.toFixed(1)},${y(only)} ${(only.x + only.width).toFixed(1)},${y(only)}`;
    }
    return run.map((bar) => `${(bar.x + bar.width / 2).toFixed(1)},${y(bar)}`).join(" ");
  });
}

/**
 * Where each interval's bar goes in the chart (requests, with failures as a part of it), and the
 * slow-5% line across the bars' middles, broken where intervals are empty. Empty intervals get
 * no bar.
 */
export function timelineChart(
  points: TimelinePoint[],
  startIso: string,
  endIso: string,
  bucketSeconds: number,
): { bars: ChartBar[]; p95Segments: string[]; maxRequests: number; maxP95Ms: number } {
  const startMs = Date.parse(startIso);
  const spanMs = Math.max(Date.parse(endIso) - startMs, 1);
  const maxRequests = Math.max(1, ...points.map((point) => point.requests));
  const maxP95Ms = Math.max(1, ...points.map((point) => point.p95_ms));
  const width = Math.max(1, ((bucketSeconds * MS_PER_SECOND) / spanMs) * CHART_WIDTH - CHART_BAR_GAP);
  const bars = points.map((point) => ({
    x: ((Date.parse(point.at) - startMs) / spanMs) * CHART_WIDTH,
    width,
    requestsHeight: (point.requests / maxRequests) * CHART_HEIGHT,
    errorsHeight: (point.errors / maxRequests) * CHART_HEIGHT,
    point,
  }));
  const segments = p95Segments(bars, bucketSeconds * MS_PER_SECOND, maxP95Ms);
  return { bars, p95Segments: segments, maxRequests, maxP95Ms };
}

/** About how many of `requests` took longer than a percentile, e.g. 5% of 1,240 → 62. */
export function slowerCount(requests: number, slowerShare: number): number {
  return Math.floor(requests * slowerShare);
}

/**
 * The percentiles in words for one API, e.g. "Of 1,240 requests to GET /users: 620 took longer
 * than 180 ms (p50), 62 longer than 1.9 s (p95) and 12 longer than 3.4 s (p99)."
 */
export function percentileExample(endpoint: EndpointStats): string {
  const count = (share: number) => slowerCount(endpoint.requests, share).toLocaleString("en");
  return (
    `Of ${endpoint.requests.toLocaleString("en")} requests to ${endpoint.http_method} ${endpoint.route}: ` +
    `${count(SLOWER_THAN_P50)} took longer than ${formatDuration(endpoint.p50_ms)} (p50), ` +
    `${count(SLOWER_THAN_P95)} longer than ${formatDuration(endpoint.p95_ms)} (p95) and ` +
    `${count(SLOWER_THAN_P99)} longer than ${formatDuration(endpoint.p99_ms)} (p99).`
  );
}

/**
 * How the slow-5% time moved since the period just before, e.g. { text: "↑ 0.8 s vs the period
 * before", worse: true }; null when there were no requests before.
 */
export function p95Change(currentMs: number, previousMs: number | null): { text: string; worse: boolean } | null {
  if (previousMs === null) return null;
  const changeMs = currentMs - previousMs;
  const arrow = changeMs > 0 ? "↑" : "↓";
  return { text: `${arrow} ${formatDuration(Math.abs(changeMs))} vs the period before`, worse: changeMs > 0 };
}

/** "p95 up 3× vs the period before" when an API's slow-5% time at least doubled, else "". */
export function p95RiseNote(endpoint: Pick<EndpointStats, "p95_ms" | "previous_p95_ms">): string {
  const previous = endpoint.previous_p95_ms;
  if (previous === null || previous <= 0) return "";
  const times = endpoint.p95_ms / previous;
  if (times < P95_RISE_TIMES) return "";
  return `p95 up ${times.toFixed(times < 10 ? 1 : 0).replace(/\.0$/, "")}× vs the period before`;
}

/** The API with the highest slow-5% time, for the overview's chart; null with none. */
export function slowestEndpoint(endpoints: EndpointStats[]): EndpointStats | null {
  return endpoints.reduce<EndpointStats | null>(
    (slowest, endpoint) => (slowest === null || endpoint.p95_ms > slowest.p95_ms ? endpoint : slowest),
    null,
  );
}

/** The interval with the highest slow-5% time, e.g. to say when an API was at its worst. */
export function worstPoint(points: TimelinePoint[]): TimelinePoint | null {
  return points.reduce<TimelinePoint | null>(
    (worst, point) => (worst === null || point.p95_ms > worst.p95_ms ? point : worst),
    null,
  );
}

/** Whether a query runs so often per request that it is likely in a loop (an N+1 pattern). */
export function looksLikeNPlusOne(callsPerRequest: number): boolean {
  return callsPerRequest >= N_PLUS_ONE_CALLS;
}

/** e.g. "2xx", "5xx"; "No status" when none was recorded (0). */
export function statusGroup(status: number): string {
  if (status <= 0) return "No status";
  return `${String(Math.floor(status / STATUS_GROUP_SIZE))}xx`;
}

/**
 * The Requests screen showing this endpoint's requests, in the same range when it is one of the
 * quick ranges (Requests has only those).
 */
export function endpointRequestsLink(
  projectId: string,
  range: RangeSelection,
  service: string,
  route: string,
): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId });
  if (range.kind === "preset" && range.key !== DEFAULT_REQUEST_RANGE) {
    params.set(URL_PARAM_REQUEST_RANGE, range.key);
  }
  params.set(URL_PARAM_SERVICE, service);
  params.set(URL_PARAM_ROUTE, route);
  return `${REQUESTS_ROUTE}?${params.toString()}`;
}
