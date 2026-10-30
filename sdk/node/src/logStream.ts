/**
 * A writable stream for loggers that write JSON lines: pino (as its destination) and winston (with
 * the Stream transport and JSON format). The SDK depends on neither.
 */

import { Writable } from "node:stream";

import {
  type Attributes,
  type Context,
  ROOT_CONTEXT,
  TraceFlags,
  isSpanContextValid,
  trace,
} from "@opentelemetry/api";

import {
  LEVEL_FIELD,
  LINE_SEPARATOR,
  MESSAGE_FIELDS,
  SPAN_ID_FIELD,
  TIME_FIELDS,
  TRACE_ID_FIELD,
} from "./constants.js";
import { type LogEntry } from "./pipeline.js";
import { INFO, type Severity, pinoSeverity, winstonSeverity } from "./severity.js";

type JsonFields = Record<string, unknown>;

/** Fields that become part of the record itself, not attributes. */
const RECORD_FIELDS = new Set([
  ...MESSAGE_FIELDS,
  LEVEL_FIELD,
  ...TIME_FIELDS,
  TRACE_ID_FIELD,
  SPAN_ID_FIELD,
]);

/**
 * Create a stream that turns each line written to it into a log entry.
 *
 * Lines split across writes are joined before parsing.
 *
 * @param onEntry - Receives each parsed entry.
 * @returns The stream to give to pino or winston.
 */
export function createLogStream(onEntry: (entry: LogEntry) => void): Writable {
  let partialLine = "";
  return new Writable({
    write(chunk: Buffer | string, _encoding, done): void {
      const lines = (partialLine + chunk.toString()).split(LINE_SEPARATOR);
      partialLine = lines.pop() ?? "";
      for (const line of lines) {
        if (line.trim()) onEntry(parseLogLine(line));
      }
      done();
    },
  });
}

/**
 * Parse one pino or winston JSON line. A line that isn't JSON becomes an INFO entry with the line
 * as its message.
 *
 * @param line - One line, without the newline.
 * @returns The log entry.
 */
export function parseLogLine(line: string): LogEntry {
  const fields = parseJsonObject(line);
  if (!fields) return { body: line, severity: INFO, attributes: {} };
  const entry: LogEntry = {
    body: messageOf(fields) ?? line,
    severity: severityOf(fields[LEVEL_FIELD]),
    attributes: attributesOf(fields),
  };
  const context = traceContextOf(fields);
  if (context) entry.context = context;
  const timestamp = timestampOf(fields);
  if (timestamp) entry.timestamp = timestamp;
  return entry;
}

function parseJsonObject(line: string): JsonFields | undefined {
  try {
    const parsed: unknown = JSON.parse(line);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as JsonFields)
      : undefined;
  } catch {
    return undefined;
  }
}

function messageOf(fields: JsonFields): string | undefined {
  for (const name of MESSAGE_FIELDS) {
    const value = fields[name];
    if (typeof value === "string") return value;
  }
  return undefined;
}

function severityOf(level: unknown): Severity {
  if (typeof level === "number") return pinoSeverity(level);
  if (typeof level === "string") return winstonSeverity(level);
  return INFO;
}

function attributesOf(fields: JsonFields): Attributes {
  const attributes: Attributes = {};
  for (const [name, value] of Object.entries(fields)) {
    if (!RECORD_FIELDS.has(name)) attributes[name] = toAttributeValue(value);
  }
  return attributes;
}

function toAttributeValue(value: unknown): Attributes[string] {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  return JSON.stringify(value);
}

/** Use the line's trace_id/span_id (as written by pino's OpenTelemetry integration) if valid. */
function traceContextOf(fields: JsonFields): Context | undefined {
  const traceId = fields[TRACE_ID_FIELD];
  const spanId = fields[SPAN_ID_FIELD];
  if (typeof traceId !== "string" || typeof spanId !== "string") return undefined;
  const spanContext = { traceId, spanId, traceFlags: TraceFlags.SAMPLED, isRemote: true };
  return isSpanContextValid(spanContext)
    ? trace.setSpanContext(ROOT_CONTEXT, spanContext)
    : undefined;
}

/** pino writes epoch milliseconds in `time`; winston's timestamp format writes an ISO string. */
function timestampOf(fields: JsonFields): Date | undefined {
  for (const name of TIME_FIELDS) {
    const value = fields[name];
    if (typeof value !== "number" && typeof value !== "string") continue;
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date;
  }
  return undefined;
}
