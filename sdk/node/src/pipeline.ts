/** Builds the OpenTelemetry pipeline: log records → batch → OTLP/HTTP → collector. */

import { type Attributes, type Context, type LogRecord } from "@opentelemetry/api";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchLogRecordProcessor,
  LoggerProvider,
  type LogRecordExporter,
} from "@opentelemetry/sdk-logs";

import {
  AUTHORIZATION_HEADER,
  BEARER_PREFIX,
  LOG_SOURCE_ATTRIBUTE,
  OTLP_LOGS_PATH,
  SERVICE_NAME_ATTRIBUTE,
} from "./constants.js";
import { type Severity } from "./severity.js";
import { joinUrl } from "./urls.js";

/** One log line, whatever logger it came from, before it becomes an OpenTelemetry record. */
export interface LogEntry {
  body: string;
  severity: Severity;
  attributes: Attributes;
  /** Carries the trace and span the log belongs to; the active span is used when absent. */
  context?: Context;
  timestamp?: Date;
}

/**
 * Exporter that sends batches to the collector with the data key as a bearer token.
 *
 * @param collectorUrl - Base URL of the OTel Collector, e.g. "http://localhost:4318".
 * @param dataKey - The raw data key.
 * @returns The OTLP/HTTP log exporter.
 */
export function buildOtlpExporter(collectorUrl: string, dataKey: string): OTLPLogExporter {
  return new OTLPLogExporter({
    url: joinUrl(collectorUrl, OTLP_LOGS_PATH),
    headers: { [AUTHORIZATION_HEADER]: BEARER_PREFIX + dataKey },
  });
}

/**
 * Provider that batches records in the background and hands them to `exporter`.
 *
 * @param service - Service name shown in Spanport, e.g. "orders-api".
 * @param exporter - Where batches go; OTLP in real use, in-memory in tests.
 * @returns The provider; shut it down to send what is still queued.
 */
export function buildLoggerProvider(service: string, exporter: LogRecordExporter): LoggerProvider {
  return new LoggerProvider({
    resource: resourceFromAttributes({ [SERVICE_NAME_ATTRIBUTE]: service }),
    processors: [new BatchLogRecordProcessor({ exporter })],
  });
}

/**
 * Turn a log entry into an OpenTelemetry log record.
 *
 * @param entry - The parsed log line.
 * @param source - Where it came from ("console" or "stream"), kept as the log.source attribute.
 * @returns The record to emit.
 */
export function toLogRecord(entry: LogEntry, source: string): LogRecord {
  const record: LogRecord = {
    body: entry.body,
    severityNumber: entry.severity.number,
    severityText: entry.severity.text,
    attributes: { ...entry.attributes, [LOG_SOURCE_ATTRIBUTE]: source },
  };
  if (entry.context) record.context = entry.context;
  if (entry.timestamp) record.timestamp = entry.timestamp;
  return record;
}
