// Pure helpers for the trace waterfall: tree order, bar positions, labels and links.
import {
  FIRST_SERVER_ERROR_STATUS,
  MIN_BAR_PERCENT,
  PERCENT,
  SPAN_STATUS_ERROR,
  TRACE_LOGS_MARGIN_MS,
  TRACE_QUERY_PREFIX,
} from "../constants/traces";
import { LOGS_ROUTE, REQUESTS_ROUTE } from "../constants/ui";
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
import type { SpanItem } from "../features/traces/api";

export interface WaterfallRow {
  span: SpanItem;
  depth: number;
}

/**
 * Spans in tree order (each parent before its children, children by start time), with their
 * depth. A span whose parent isn't in the trace (e.g. sent by another project) starts a root.
 */
export function waterfallRows(spans: SpanItem[]): WaterfallRow[] {
  const ids = new Set(spans.map((span) => span.span_id));
  const children = Map.groupBy(spans, (span) => (ids.has(span.parent_span_id) ? span.parent_span_id : ""));
  const rows: WaterfallRow[] = [];
  const visit = (parentId: string, depth: number) => {
    const ordered = [...(children.get(parentId) ?? [])].sort((first, second) => first.offset_ms - second.offset_ms);
    for (const span of ordered) {
      rows.push({ span, depth });
      visit(span.span_id, depth + 1);
    }
  };
  visit("", 0);
  return rows;
}

/** Where a span's bar starts and how wide it is, as percentages of the whole trace. */
export function barPosition(span: SpanItem, totalMs: number): { left: number; width: number } {
  if (totalMs <= 0) return { left: 0, width: PERCENT };
  const left = (span.offset_ms / totalMs) * PERCENT;
  const width = Math.max((span.duration_ms / totalMs) * PERCENT, MIN_BAR_PERCENT);
  return { left: Math.min(left, PERCENT - MIN_BAR_PERCENT), width: Math.min(width, PERCENT - left) };
}

/** Whether a step failed: an ERROR status or a 5xx answer. */
export function spanFailed(span: Pick<SpanItem, "status_code" | "http_status">): boolean {
  return span.status_code === SPAN_STATUS_ERROR || span.http_status >= FIRST_SERVER_ERROR_STATUS;
}

/** How a span's label reads. */
export function labelName(label: string): string {
  switch (label) {
    case "incoming_request":
      return "Request";
    case "db":
      return "Database";
    case "llm":
      return "LLM";
    case "service_call":
      return "Service call";
    case "external":
      return "External";
    default:
      return "Code";
  }
}

/** e.g. "885 ms", "4.2 s", "0.3 ms". */
export function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  if (ms >= 10) return `${String(Math.round(ms))} ms`;
  return `${ms.toFixed(1)} ms`;
}

/** One request's waterfall page, for this project. */
export function traceLink(traceId: string, projectId: string): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId });
  return `${REQUESTS_ROUTE}/${encodeURIComponent(traceId)}?${params.toString()}`;
}

/** The Logs page showing the lines written during this trace, a minute either side. */
export function traceLogsLink(projectId: string, traceId: string, startTs: string, durationMs: number): string {
  const startMs = Date.parse(startTs);
  const params = new URLSearchParams({
    [URL_PARAM_PROJECT]: projectId,
    [URL_PARAM_RANGE]: RANGE_ABSOLUTE,
    [URL_PARAM_START]: new Date(startMs - TRACE_LOGS_MARGIN_MS).toISOString(),
    [URL_PARAM_END]: new Date(startMs + durationMs + TRACE_LOGS_MARGIN_MS).toISOString(),
    [URL_PARAM_QUERY]: `${TRACE_QUERY_PREFIX}${traceId}`,
    [URL_PARAM_MODE]: MODE_QUERY,
  });
  return `${LOGS_ROUTE}?${params.toString()}`;
}
