// Requests (traces): ranges, filters and URL params of the list, and the waterfall.
import { APIS_ROUTE, SERVICE_MAP_ROUTE } from "./ui";

// Traces are kept 30 days, so the longest range is 30 days.
export const REQUEST_RANGES = [
  { key: "15m", label: "15m", name: "Last 15 minutes", minutes: 15 },
  { key: "1h", label: "1h", name: "Last 1 hour", minutes: 60 },
  { key: "6h", label: "6h", name: "Last 6 hours", minutes: 360 },
  { key: "1d", label: "1d", name: "Last 1 day", minutes: 1440 },
  { key: "7d", label: "7d", name: "Last 7 days", minutes: 10_080 },
  { key: "30d", label: "30d", name: "Last 30 days", minutes: 43_200 },
] as const;
export const DEFAULT_REQUEST_RANGE = "1h";
export const TRACE_MAX_RANGE_MINUTES = 43_200;
// The APIs screens' time ranges (see lib/timeRange RangeRules): traces are kept 30 days.
export const TRACE_RANGE_RULES = {
  presets: REQUEST_RANGES,
  defaultKey: DEFAULT_REQUEST_RANGE,
  maxMinutes: TRACE_MAX_RANGE_MINUTES,
  keptNote: "traces kept 30 days",
  tooLongMessage: "Traces are kept 30 days. Choose 30 days or less.",
  tooOldMessage: "Traces are kept 30 days. Choose a start within the last 30 days.",
} as const;
export const REQUESTS_PAGE_SIZE = 100;
export const MS_PER_MINUTE = 60_000;

// URL params, so a filtered list can be shared as a link.
export const URL_PARAM_REQUEST_RANGE = "range";
export const URL_PARAM_SERVICE = "service";
export const URL_PARAM_ROUTE = "route";
export const URL_PARAM_MIN_MS = "min_ms";
export const URL_PARAM_ERRORS = "errors";
export const URL_PARAM_METHOD = "method";

// The API detail page's chart, drawn in an SVG of this size (it scales to the page width).
export const CHART_WIDTH = 1000;
export const CHART_HEIGHT = 180;
// Room between bars, in chart units.
export const CHART_BAR_GAP = 2;
// HTTP status groups: 2xx, 3xx, 4xx, 5xx.
export const STATUS_GROUP_SIZE = 100;

// The APIs screen's tabs, as in the UI canvas; Deploys comes later (no path yet).
export const API_TABS = [
  { key: "overview", label: "Overview", path: APIS_ROUTE },
  { key: "deploys", label: "Deploys", path: null },
  { key: "service-map", label: "Service map", path: SERVICE_MAP_ROUTE },
] as const;

// The service map: boxes in columns (callers on the left), sizes in pixels.
export const MAP_NODE_WIDTH = 180;
export const MAP_NODE_HEIGHT = 64;
// Wide enough for a line's label, e.g. "310 queries/s · 4.0 ms".
export const MAP_COLUMN_GAP = 200;
export const MAP_ROW_GAP = 40;
// Line labels sit this far above the line's middle.
export const MAP_LABEL_LIFT = 6;
// A rate under this per second is shown per minute.
export const MIN_RATE_PER_SECOND = 0.1;
export const SECONDS_PER_MINUTE = 60;
export const MAP_KIND_NAMES = {
  service: "Your service",
  db: "Database",
  external: "Another system",
  llm: "LLM provider",
} as const;
// What a call to each kind of box is called on its lines, e.g. "1 query/min", "310 queries/s".
export const MAP_CALL_NAMES = {
  service: { one: "req", many: "req" },
  db: { one: "query", many: "queries" },
  external: { one: "req", many: "req" },
  llm: { one: "call", many: "calls" },
} as const;
export const MAP_STATUS_NAMES = { ok: "Healthy", slow: "Slower than before", bad: "Errors above normal" } as const;
export const SERVICE_MAP_DESCRIPTION =
  "What calls what, drawn automatically from requests. Red means errors, orange means slower than the period before. Select a box for details.";
export const NO_MAP_NOTE = "No requests in this range, so nothing to draw yet.";

// An API whose slow-5% time is at least this many times the period before gets a warning.
export const P95_RISE_TIMES = 2;
// A query run this many times per request or more is probably in a loop (N+1 pattern).
export const N_PLUS_ONE_CALLS = 5;

// Percentiles: share of requests at or under each time (p50, p95, p99).
export const SLOWER_THAN_P50 = 0.5;
export const SLOWER_THAN_P95 = 0.05;
export const SLOWER_THAN_P99 = 0.01;
export const PERCENTILE_HELP = {
  p50: "Typical (p50): half of the requests were faster than this. What a normal user gets.",
  p95: "Slow 5% (p95): 95 of every 100 requests were faster; the slowest 5 took longer.",
  p99: "Slowest 1% (p99): 99 of every 100 were faster; only 1 in 100 took longer. Your worst cases.",
} as const;
export const URL_FLAG_ON = "1";

// Logs written during a trace: the logs page opens a little around the trace's own time.
export const TRACE_LOGS_MARGIN_MS = 60_000;
export const TRACE_QUERY_PREFIX = "trace:";

export const WATERFALL_INDENT_PX = 16;
// The time axis above the waterfall has at most this many marks; each is a round step
// (1, 2 or 5 times a power of ten milliseconds).
export const MAX_AXIS_TICKS = 5;
export const AXIS_STEP_FACTORS = [1, 2, 5] as const;
// A tick label this close to the right edge ends at its mark, so it never runs off the axis.
export const AXIS_END_PERCENT = 90;
export const DECIMAL_BASE = 10;
export const MS_PER_SECOND = 1000;
// Bars grow in one after another; rows past this many start together, so a big trace isn't slow.
export const MAX_STAGGERED_ROWS = 24;

// The kinds of step a request's time is split into, in display order (APIs and waterfall).
export const STEP_KINDS = ["code", "db", "external", "llm"] as const;
export const EMPTY_STEP_TIMES = { code: 0, db: 0, external: 0, llm: 0 } as const;
// The APIs list names the kind of step that takes the most time once it is at least this share.
export const DOMINANT_STEP_PERCENT = 40;
// Error rates below this keep one decimal ("0.4%"); larger ones are whole numbers.
export const ONE_DECIMAL_BELOW_PERCENT = 10;
export const NO_REQUESTS_NOTE =
  "No requests in this range. Requests appear once your app runs the Spanport SDK (1.0 or later) with tracing on.";
export const MORE_ENDPOINTS_NOTE = "Only the 200 busiest APIs are listed. Pick a service to see the others.";
export const TRUNCATED_TRACE_NOTE = "This trace is very large; only its first 2,000 steps are shown.";
// A step failed when its status is ERROR or it answered 5xx.
export const SPAN_STATUS_ERROR = "ERROR";
export const FIRST_SERVER_ERROR_STATUS = 500;
export const PERCENT = 100;
// A bar never gets thinner than this, so instant spans stay visible.
export const MIN_BAR_PERCENT = 0.4;
