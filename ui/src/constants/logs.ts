// Logs explorer: time ranges, filters, paging and live tail.
import type { FilterOperator } from "../features/logs/types";

export const TIME_PRESETS = [
  { key: "5m", label: "5m", name: "Last 5 minutes", minutes: 5 },
  { key: "15m", label: "15m", name: "Last 15 minutes", minutes: 15 },
  { key: "1h", label: "1h", name: "Last 1 hour", minutes: 60 },
  { key: "3h", label: "3h", name: "Last 3 hours", minutes: 180 },
  { key: "12h", label: "12h", name: "Last 12 hours", minutes: 720 },
  { key: "1d", label: "1d", name: "Last 1 day", minutes: 1440 },
  { key: "1w", label: "1w", name: "Last 1 week", minutes: 10080 },
] as const;
export const DEFAULT_PRESET_KEY = "15m";

// Units for a custom "Last N ..." range.
export const RELATIVE_UNITS = [
  { unit: "minutes", label: "Minutes", minutes: 1 },
  { unit: "hours", label: "Hours", minutes: 60 },
  { unit: "days", label: "Days", minutes: 1440 },
  { unit: "weeks", label: "Weeks", minutes: 10080 },
] as const;
// Logs are kept 7 days, so no range reaches further back.
export const MAX_RANGE_MINUTES = 10080;
// The custom range dialog starts at the last hour.
export const CUSTOM_RANGE_START_MINUTES = 60;
export const DEFAULT_RELATIVE_AMOUNT = 1;
export const DEFAULT_RELATIVE_UNIT = "hours";

export const RANGE_AMOUNT_MESSAGE = "Enter a whole number of 1 or more.";
export const RANGE_TOO_LONG_MESSAGE = "Logs are kept 7 days. Choose 7 days or less.";
export const RANGE_INCOMPLETE_MESSAGE = "Enter a start and an end.";
export const RANGE_ORDER_MESSAGE = "The end must be after the start.";
export const RANGE_TOO_OLD_MESSAGE = "Logs are kept 7 days. Choose a start within the last 7 days.";

export const SEARCH_PAGE_SIZE = 100;
// Matches the server's limits on filter chips and the text query.
export const MAX_FILTER_CHIPS = 20;
export const MAX_FILTER_VALUE_LENGTH = 500;
export const MAX_QUERY_LENGTH = 2000;

export const FILTER_PROPERTIES: readonly {
  field: string;
  label: string;
  hint: string;
  operators: readonly FilterOperator[];
}[] = [
  { field: "message", label: "Message", hint: "text in the log line", operators: [":", "!:"] },
  { field: "level", label: "Level", hint: "ERROR, WARN, INFO, DEBUG", operators: ["=", "!="] },
  { field: "service", label: "Service", hint: "service.name", operators: ["=", "!=", ":", "!:"] },
  { field: "ip", label: "Client IP", hint: "client.ip", operators: ["=", "!=", ":", "!:"] },
  { field: "user", label: "User ID", hint: "user.id", operators: ["=", "!=", ":", "!:"] },
  { field: "trace", label: "Trace ID", hint: "trace_id", operators: ["=", "!="] },
];
export const MESSAGE_FIELD = "message";
export const LEVEL_FIELD = "level";
export const CONTAINS_OPERATOR: FilterOperator = ":";
export const EQUALS_OPERATOR: FilterOperator = "=";
export const NOT_EQUALS_OPERATOR: FilterOperator = "!=";
export const NEGATIVE_OPERATORS: readonly FilterOperator[] = ["!=", "!:"];
export const CONTAINS_OPERATORS: readonly FilterOperator[] = [":", "!:"];
// Attributes the value dropdown suggests from the logs on screen.
export const CLIENT_IP_ATTRIBUTE = "client.ip";
export const USER_ID_ATTRIBUTE = "user.id";

// Query language pieces used to write chips as text (see the server's log_query_parser).
export const QUERY_AND = " AND ";
export const QUERY_OR = " OR ";
export const QUERY_NOT = "-";
export const QUERY_QUOTE = '"';
export const QUERY_WILDCARD = "*";
export const QUERY_VALUE_NEEDS_QUOTES = /[\s"()]/;

// The levels offered as values and shown as cards.
export const MAIN_LEVELS = ["ERROR", "WARN", "INFO", "DEBUG"] as const;
// The value dropdown shows at most this many suggestions.
export const MAX_SUGGESTIONS = 8;

// A request line as request loggers write it: "GET /api/users/42 500 402ms user=...".
export const REQUEST_LINE_PATTERN =
  /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (\S+) (\d{3}) (\d+(?:\.\d+)?) ?ms\b\s*([\s\S]*)$/;
// Path segments that are ids (UUIDs or numbers) are shown as ":id", so paths group together.
export const PATH_ID_SEGMENT_PATTERN =
  /\/(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d+)(?=\/|\?|$)/gi;
export const PATH_ID_PLACEHOLDER = "/:id";
// Status classes: 2xx ok, 3xx redirect, 4xx client error, 5xx server error.
export const STATUS_CLASS_SIZE = 100;
export const SERVER_ERROR_CLASS = 5;
export const CLIENT_ERROR_CLASS = 4;
export const REDIRECT_CLASS = 3;

// URL search params that hold the explorer's state, so a search can be shared as a link.
export const URL_PARAM_PROJECT = "project";
export const URL_PARAM_RANGE = "range";
export const URL_PARAM_AMOUNT = "amount";
export const URL_PARAM_UNIT = "unit";
export const URL_PARAM_START = "start";
export const URL_PARAM_END = "end";
export const URL_PARAM_FILTERS = "filters";
export const URL_PARAM_COMBINE = "combine";
export const URL_PARAM_QUERY = "query";
export const URL_PARAM_MODE = "mode";
export const RANGE_RELATIVE = "relative";
export const RANGE_ABSOLUTE = "absolute";
export const MODE_QUERY = "query";

// Export: the server's limit for one file (larger exports by email come later).
export const MAX_EXPORT_LINES = 100_000;
export const EXPORT_FORMATS = [
  { format: "csv", label: "Download CSV", detail: "for spreadsheets" },
  { format: "ndjson", label: "Download JSON lines", detail: "every field, one log per line" },
] as const;
// attachment; filename="spanport-logs-....csv"
export const ATTACHMENT_FILENAME_PATTERN = /filename="([^"]+)"/;
export const FALLBACK_EXPORT_NAME = "spanport-logs";
export const VIEWER_EXPORT_NOTE = "Viewers can't download logs";
export const TOO_MANY_TO_EXPORT_NOTE = "Over 100,000 lines: narrow the range or filter";

// Table: rows grow when expanded, so this is only the first estimate.
export const LOG_ROW_HEIGHT_PX = 40;
export const LOG_ROWS_OVERSCAN = 20;
// Load the next page once the user scrolls within this many rows of the end.
export const LOAD_MORE_WITHIN_ROWS = 20;
// The Trace column shows this many characters of the trace ID.
export const TRACE_PREVIEW_LENGTH = 8;

export const SSE_LOGS_EVENT = "logs";
export const SSE_FRAME_END = "\n\n";
export const SSE_LINE_END = "\n";
export const SSE_FIELD_SEPARATOR = ":";
// Incoming tail rows are buffered and shown at most this often, so bursts cost few re-renders.
export const TAIL_FLUSH_MS = 250;
// While following live, the level cards are counted again this often.
export const LIVE_COUNTS_REFRESH_MS = 5000;
// Live tail keeps only the newest rows on screen.
export const TAIL_MAX_ROWS = 1000;
export const TAIL_RETRY_FIRST_MS = 1000;
export const TAIL_RETRY_MAX_MS = 30_000;
// Each failed reconnect waits this many times longer than the last, up to the maximum.
export const TAIL_RETRY_BACKOFF_FACTOR = 2;
