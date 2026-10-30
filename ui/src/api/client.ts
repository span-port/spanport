// The one HTTP client: sends the session cookie and CSRF header, and turns problem+json errors into
// ApiError. The session cookie is HttpOnly, so the UI never sees it; the browser sends it.
import * as zod from "zod";

import {
  CSRF_COOKIE,
  CSRF_HEADER,
  JSON_CONTENT_TYPE,
  REQUEST_ID_HEADER,
  UNKNOWN_ERROR_CODE,
} from "../constants/api";
import { readCookie } from "../lib/cookies";

/** An RFC 9457 problem from the server, e.g. 400 invalid_request with a plain-language detail. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly title: string,
    readonly detail: string,
    readonly requestId: string | null,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

const problemSchema = zod.object({
  title: zod.string(),
  detail: zod.string(),
  code: zod.string(),
  request_id: zod.string().nullish(),
});

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Send a request to the Spanport server.
 *
 * Anything but GET carries the CSRF token from its cookie, so the server knows the page sent it.
 *
 * @param path - API path, e.g. "/api/v1/logs/search".
 * @param options - Method, JSON body and abort signal.
 * @returns The successful response, body unread.
 * @throws ApiError for any non-2xx answer, e.g. 401 not_signed_in.
 * @throws TypeError when the server can't be reached.
 */
export async function apiResponse(path: string, options: RequestOptions = {}): Promise<Response> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  const init: RequestInit = { method, headers, credentials: "same-origin" };
  if (method !== "GET") headers[CSRF_HEADER] = readCookie(CSRF_COOKIE) ?? "";
  if (options.body !== undefined) {
    headers["Content-Type"] = JSON_CONTENT_TYPE;
    init.body = JSON.stringify(options.body);
  }
  if (options.signal) init.signal = options.signal;
  const response = await fetch(path, init);
  if (response.ok) return response;
  throw await toApiError(response);
}

/**
 * Send a request and read its JSON body.
 *
 * @returns The parsed body, typed by the caller to match the server's response model.
 * @throws ApiError or TypeError, as for {@link apiResponse}.
 */
export async function apiJson<ResponseBody>(
  path: string,
  options: RequestOptions = {},
): Promise<ResponseBody> {
  const response = await apiResponse(path, options);
  return (await response.json()) as ResponseBody;
}

/** Build an ApiError from an error response; a body that isn't problem+json keeps the status text. */
async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get(REQUEST_ID_HEADER);
  const text = await response.text();
  const problem = problemSchema.safeParse(parseJson(text));
  if (!problem.success) {
    return new ApiError(response.status, UNKNOWN_ERROR_CODE, response.statusText, text, requestId);
  }
  const { title, detail, code, request_id } = problem.data;
  return new ApiError(response.status, code, title, detail, request_id ?? requestId);
}

/** Parse JSON, or undefined when the text isn't JSON (e.g. a proxy's HTML error page). */
function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}
