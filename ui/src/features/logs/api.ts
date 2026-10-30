// Logs API: search pages, counts per level and the live tail stream.
import { apiJson, apiResponse } from "../../api/client";
import { LOG_COUNTS_PATH, LOG_EXPORT_PATH, LOG_SEARCH_PATH, LOG_TAIL_PATH } from "../../constants/api";
import { SEARCH_PAGE_SIZE } from "../../constants/logs";
import type {
  LogCountsResponse,
  LogFilterRequest,
  LogSearchResponse,
  LogTailRequest,
} from "./types";

/**
 * One page of matching logs, newest first.
 *
 * @param cursor - `next_cursor` from the previous page, or null for the first.
 * @throws ApiError, e.g. 400 with a plain-language detail for a bad text query.
 */
export function searchLogs(
  request: LogFilterRequest,
  cursor: string | null,
  signal: AbortSignal,
): Promise<LogSearchResponse> {
  return apiJson<LogSearchResponse>(LOG_SEARCH_PATH, {
    method: "POST",
    body: { ...request, limit: SEARCH_PAGE_SIZE, cursor },
    signal,
  });
}

/** How many logs match, in total and per level. */
export function countLogs(request: LogFilterRequest, signal: AbortSignal): Promise<LogCountsResponse> {
  return apiJson<LogCountsResponse>(LOG_COUNTS_PATH, { method: "POST", body: request, signal });
}

export type ExportFormat = "csv" | "ndjson";

/**
 * The current search as a file (at most 100,000 lines), streamed.
 *
 * @returns The response; its body is the file, Content-Disposition names it.
 * @throws ApiError 403 for viewers, 400 when too many lines match.
 */
export function exportLogs(request: LogFilterRequest, format: ExportFormat): Promise<Response> {
  return apiResponse(LOG_EXPORT_PATH, { method: "POST", body: { ...request, format } });
}

/**
 * Open the live tail: a server-sent events stream of new matching logs.
 *
 * @returns The streaming response; read its body with `readEvents`.
 * @throws ApiError before streaming (bad key, foreign project, bad query).
 */
export function openLogTail(request: LogTailRequest, signal: AbortSignal): Promise<Response> {
  return apiResponse(LOG_TAIL_PATH, { method: "POST", body: request, signal });
}
