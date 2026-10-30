// Text forms of log lines for the clipboard.
import type { LogItem } from "../features/logs/types";
import { JSON_INDENT, NDJSON_LINE_END } from "../constants/ui";

/** One line as pretty-printed JSON, for reading. */
export function toPrettyJson(log: LogItem): string {
  return JSON.stringify(log, null, JSON_INDENT);
}

/** Several lines as NDJSON: one JSON object per line. */
export function toNdjson(logs: LogItem[]): string {
  return logs.map((log) => JSON.stringify(log)).join(NDJSON_LINE_END);
}
