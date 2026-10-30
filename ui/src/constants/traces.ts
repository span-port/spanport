// Requests (traces): ranges, filters and URL params of the list, and the waterfall.

// Traces are kept 30 days, so the longest range is 30 days.
export const REQUEST_RANGES = [
  { key: "15m", label: "15m", minutes: 15 },
  { key: "1h", label: "1h", minutes: 60 },
  { key: "6h", label: "6h", minutes: 360 },
  { key: "1d", label: "1d", minutes: 1440 },
  { key: "7d", label: "7d", minutes: 10_080 },
  { key: "30d", label: "30d", minutes: 43_200 },
] as const;
export const DEFAULT_REQUEST_RANGE = "1h";
export const REQUESTS_PAGE_SIZE = 100;
export const MS_PER_MINUTE = 60_000;

// URL params, so a filtered list can be shared as a link.
export const URL_PARAM_REQUEST_RANGE = "range";
export const URL_PARAM_SERVICE = "service";
export const URL_PARAM_ROUTE = "route";
export const URL_PARAM_MIN_MS = "min_ms";
export const URL_PARAM_ERRORS = "errors";
export const URL_FLAG_ON = "1";

// Logs written during a trace: the logs page opens a little around the trace's own time.
export const TRACE_LOGS_MARGIN_MS = 60_000;
export const TRACE_QUERY_PREFIX = "trace:";

export const WATERFALL_INDENT_PX = 16;
export const TRUNCATED_TRACE_NOTE = "This trace is very large; only its first 2,000 steps are shown.";
// A step failed when its status is ERROR or it answered 5xx.
export const SPAN_STATUS_ERROR = "ERROR";
export const FIRST_SERVER_ERROR_STATUS = 500;
export const PERCENT = 100;
// A bar never gets thinner than this, so instant spans stay visible.
export const MIN_BAR_PERCENT = 0.4;
