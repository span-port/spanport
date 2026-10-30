/** SDK constants. Code refers to these by name, never by inline value. */

export const DATA_KEY_PREFIX = "sp_ingest_";
export const DEFAULT_COLLECTOR_URL = "http://localhost:4318";
export const DEFAULT_SERVER_URL = "http://localhost:8000";
export const OTLP_LOGS_PATH = "/v1/logs";
export const CURRENT_API_KEY_PATH = "/api/v1/api-keys/current";
export const AUTHORIZATION_HEADER = "Authorization";
export const BEARER_PREFIX = "Bearer ";
export const ALLOWED_URL_PROTOCOLS: readonly string[] = ["http:", "https:"];
export const KEY_CHECK_TIMEOUT_MS = 5000;
export const VISIBLE_KEY_SUFFIX_LENGTH = 4;
export const HTTP_UNAUTHORIZED = 401;

/** console methods the SDK copies to Spanport; the original output is unchanged. */
export const CAPTURED_CONSOLE_METHODS = ["debug", "log", "info", "warn", "error"] as const;

/** pino's numeric levels (pino's own defaults). */
export const PINO_TRACE = 10;
export const PINO_DEBUG = 20;
export const PINO_INFO = 30;
export const PINO_WARN = 40;
export const PINO_ERROR = 50;
export const PINO_FATAL = 60;

export const SERVICE_NAME_ATTRIBUTE = "service.name";
/** Instrumentation scope name on every log record the SDK emits. */
export const SDK_SCOPE_NAME = "spanport";
/** Prefix on the SDK's own stderr messages, which are never exported. */
export const SDK_MESSAGE_PREFIX = "spanport:";

/** Where a log came from, recorded as the `log.source` attribute. */
export const LOG_SOURCE_ATTRIBUTE = "log.source";
export const CONSOLE_SOURCE = "console";
export const LOG_STREAM_SOURCE = "stream";

/** Fields of a pino or winston JSON line that become part of the record rather than attributes. */
export const MESSAGE_FIELDS: readonly string[] = ["msg", "message"];
export const LEVEL_FIELD = "level";
export const TIME_FIELDS: readonly string[] = ["time", "timestamp"];
export const TRACE_ID_FIELD = "trace_id";
export const SPAN_ID_FIELD = "span_id";
export const LINE_SEPARATOR = "\n";
