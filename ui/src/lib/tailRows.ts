// Merge newly tailed logs into the rows on screen.
import type { LogItem } from "../features/logs/types";

/**
 * Put `arrived` (oldest first, as the stream sends them) on top of `shown` (newest first).
 *
 * Rows already shown are skipped: after a reconnect the server resends its recent window.
 *
 * @returns At most `maxRows` rows, newest first.
 */
export function mergeTailRows(shown: LogItem[], arrived: LogItem[], maxRows: number): LogItem[] {
  const shownIds = new Set(shown.map((row) => row.log_id));
  const fresh = arrived.filter((row) => !shownIds.has(row.log_id)).reverse();
  return [...fresh, ...shown].slice(0, maxRows);
}
