// Read request-log lines ("GET /api/users/42 500 402ms user=a@b") into columns, so method, path,
// status and duration are scannable instead of being cut off at the end of a long message.
import {
  CLIENT_ERROR_CLASS,
  PATH_ID_PLACEHOLDER,
  PATH_ID_SEGMENT_PATTERN,
  REDIRECT_CLASS,
  REQUEST_LINE_PATTERN,
  SERVER_ERROR_CLASS,
  STATUS_CLASS_SIZE,
} from "../constants/logs";

export interface RequestLine {
  method: string;
  path: string;
  /** The path with ids replaced, e.g. /environments/:id/components/:id. */
  template: string;
  status: number;
  durationMs: number;
  /** Whatever follows the duration, e.g. "user=a@b". */
  rest: string;
}

export type StatusTone = "ok" | "redirect" | "client-error" | "server-error";

/** The request in a log message, or null when the message isn't a request line. */
export function parseRequestLine(message: string): RequestLine | null {
  const match = REQUEST_LINE_PATTERN.exec(message);
  if (!match) return null;
  const [, method = "", path = "", status = "", duration = "", rest = ""] = match;
  return {
    method,
    path,
    template: path.replace(PATH_ID_SEGMENT_PATTERN, PATH_ID_PLACEHOLDER),
    status: Number(status),
    durationMs: Number(duration),
    rest: rest.trim(),
  };
}

/** The color class of an HTTP status. */
export function statusTone(status: number): StatusTone {
  const statusClass = Math.floor(status / STATUS_CLASS_SIZE);
  if (statusClass >= SERVER_ERROR_CLASS) return "server-error";
  if (statusClass === CLIENT_ERROR_CLASS) return "client-error";
  if (statusClass === REDIRECT_CLASS) return "redirect";
  return "ok";
}
