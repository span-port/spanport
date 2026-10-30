/**
 * Spanport SDK: send your Node.js app's logs to Spanport.
 *
 *     import * as spanport from "spanport";
 *     spanport.init({ dataKey: "sp_ingest_...", service: "orders-api" });
 *
 * It never breaks the host app: init() never throws, logs are sent in the background, and if
 * anything is wrong it says so on stderr and the app carries on.
 */

import { type Writable } from "node:stream";

import { type Logger } from "@opentelemetry/api";
import { type LoggerProvider } from "@opentelemetry/sdk-logs";

import { captureConsole } from "./consoleCapture.js";
import {
  CONSOLE_SOURCE,
  DATA_KEY_PREFIX,
  DEFAULT_COLLECTOR_URL,
  DEFAULT_SERVER_URL,
  LOG_STREAM_SOURCE,
  SDK_SCOPE_NAME,
} from "./constants.js";
import { checkDataKey } from "./keyCheck.js";
import { createLogStream } from "./logStream.js";
import { buildLoggerProvider, buildOtlpExporter, toLogRecord } from "./pipeline.js";
import { sdkError, sdkInfo, sdkWarning } from "./sdkMessages.js";
import { consoleSeverity } from "./severity.js";
import { isHttpUrl } from "./urls.js";

export interface SpanportOptions {
  /** The project's data key (sp_ingest_...). */
  dataKey: string;
  /** Name of this app as shown in Spanport, e.g. "orders-api". */
  service: string;
  /** The Spanport OTel Collector (OTLP/HTTP). Default http://localhost:4318. */
  collectorUrl?: string;
  /** The Spanport server, asked once whether the data key is valid. Default http://localhost:8000. */
  serverUrl?: string;
  /** Set false to skip the start-up key check (e.g. no route to the server). Default true. */
  checkKey?: boolean;
  /** Set false to stop copying console.* calls to Spanport. Default true. */
  captureConsole?: boolean;
}

interface ActivePipeline {
  provider: LoggerProvider;
  logger: Logger;
  restoreConsole: (() => void) | undefined;
}

let active: ActivePipeline | undefined;
let exitFlushInstalled = false;

/**
 * Start sending this app's logs to Spanport. Call once at start-up. Never throws.
 *
 * @param options - Data key, service name and where Spanport runs.
 */
export function init(options: SpanportOptions): void {
  try {
    start(options);
  } catch (error) {
    sdkError(`setup failed; the app keeps running but logs are not sent: ${describe(error)}`);
  }
}

/**
 * Send any logs still queued, stop capturing console and stop. Safe to call more than once.
 * Call it on SIGTERM; a normal exit calls it for you. Never rejects.
 */
export async function shutdown(): Promise<void> {
  const pipeline = active;
  active = undefined;
  if (!pipeline) return;
  pipeline.restoreConsole?.();
  try {
    await pipeline.provider.shutdown();
  } catch (error) {
    sdkWarning(`shutdown failed; some queued logs may not have been sent: ${describe(error)}`);
  }
}

/**
 * A stream for pino or winston (JSON lines). Lines written before init() or after shutdown()
 * are dropped.
 *
 *     pino(spanport.logStream())
 *     new winston.transports.Stream({ stream: spanport.logStream() })
 *
 * @returns A new writable stream.
 */
export function logStream(): Writable {
  return createLogStream((entry) => {
    active?.logger.emit(toLogRecord(entry, LOG_STREAM_SOURCE));
  });
}

function start(options: SpanportOptions): void {
  if (active) {
    sdkWarning("init() was already called; ignoring the second call");
    return;
  }
  const collectorUrl = options.collectorUrl ?? DEFAULT_COLLECTOR_URL;
  const problem = findProblem(options, collectorUrl);
  if (problem) {
    sdkError(`${problem}; logs are not sent`);
    return;
  }
  const provider = buildLoggerProvider(
    options.service,
    buildOtlpExporter(collectorUrl, options.dataKey),
  );
  const logger = provider.getLogger(SDK_SCOPE_NAME);
  const restoreConsole =
    options.captureConsole === false
      ? undefined
      : captureConsole((method, message) => {
          logger.emit(
            toLogRecord(
              { body: message, severity: consoleSeverity(method), attributes: {} },
              CONSOLE_SOURCE,
            ),
          );
        });
  active = { provider, logger, restoreConsole };
  installExitFlush();
  sdkInfo(`sending logs for service ${options.service} to ${collectorUrl}`);
  if (options.checkKey !== false) {
    void checkDataKey(options.serverUrl ?? DEFAULT_SERVER_URL, options.dataKey);
  }
}

/** Send what is queued when the app exits normally. Installed once, however often init runs. */
function installExitFlush(): void {
  if (exitFlushInstalled) return;
  exitFlushInstalled = true;
  process.on("beforeExit", () => void shutdown());
}

function findProblem(options: SpanportOptions, collectorUrl: string): string | undefined {
  if (!options.dataKey.startsWith(DATA_KEY_PREFIX)) {
    return `dataKey must be a data key (${DATA_KEY_PREFIX}...)`;
  }
  if (!options.service) return "service must name this app, e.g. service: 'orders-api'";
  if (!isHttpUrl(collectorUrl)) return "collectorUrl must start with http:// or https://";
  return undefined;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
