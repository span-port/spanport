// When a live tail gives up instead of reconnecting.
import { ApiError } from "../api/client";
import { FIRST_SERVER_ERROR_STATUS, STATUS_TOO_MANY_REQUESTS } from "../constants/api";

/**
 * Whether an error ends the live tail for good.
 *
 * A 4xx (bad query, foreign project, signed out) fails the same way every time, so the tail
 * stops and shows it. A 429 (too many requests or tails open) clears after a wait, so the tail
 * reconnects with its usual backoff, like after a dropped stream or a 5xx.
 *
 * @param error - What opening or reading the stream threw.
 * @returns True to stop and show the error, false to reconnect.
 */
export function stopsLiveTail(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status < FIRST_SERVER_ERROR_STATUS &&
    error.status !== STATUS_TOO_MANY_REQUESTS
  );
}
