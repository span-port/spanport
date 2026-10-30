// Live tail: one stream per filter set, reconnecting with backoff and paused while the tab is hidden.
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import { ApiError } from "../../../api/client";
import { FIRST_SERVER_ERROR_STATUS } from "../../../constants/api";
import {
  SSE_LOGS_EVENT,
  TAIL_FLUSH_MS,
  TAIL_MAX_ROWS,
  TAIL_RETRY_BACKOFF_FACTOR,
  TAIL_RETRY_FIRST_MS,
  TAIL_RETRY_MAX_MS,
} from "../../../constants/logs";
import { usePageVisible } from "../../../hooks/usePageVisible";
import { readEvents } from "../../../lib/serverSentEvents";
import { mergeTailRows } from "../../../lib/tailRows";
import { openLogTail } from "../api";
import type { LogItem, LogTailRequest } from "../types";

export type TailStatus = "off" | "connecting" | "live" | "reconnecting" | "paused" | "stopped";

interface TailState {
  /** The request these rows belong to; rows from an older filter set are never shown. */
  requestKey: string;
  rows: LogItem[];
  status: TailStatus;
  error: unknown;
}

interface LiveTail {
  rows: LogItem[];
  status: TailStatus;
  error: unknown;
}

/**
 * Stream new logs matching `request`.
 *
 * @param request - What to tail, or null when live tail is off.
 * @returns Rows newest first, the stream status and the last error (if any).
 */
export function useLiveTail(request: LogTailRequest | null): LiveTail {
  const pageVisible = usePageVisible();
  const requestKey = request === null ? null : JSON.stringify(request);
  const [tail, setTail] = useState<TailState | null>(null);

  useEffect(() => {
    if (requestKey === null || !pageVisible) return;
    return startTail(requestKey, setTail);
  }, [requestKey, pageVisible]);

  const current = tail !== null && tail.requestKey === requestKey ? tail : null;
  const rows = current?.rows ?? [];
  if (requestKey === null) return { rows, status: "off", error: null };
  if (!pageVisible) return { rows, status: "paused", error: null };
  return { rows, status: current?.status ?? "connecting", error: current?.error ?? null };
}

/**
 * Open the stream and keep it open until the returned cleanup runs.
 *
 * Arriving rows are buffered and flushed to state every 250 ms. A dropped stream or a 5xx
 * reconnects with growing waits; a 4xx (bad query, foreign project) stops and shows the error.
 */
function startTail(
  requestKey: string,
  setTail: Dispatch<SetStateAction<TailState | null>>,
): () => void {
  const request = JSON.parse(requestKey) as LogTailRequest;
  const controller = new AbortController();
  let pending: LogItem[] = [];
  let retryMs = TAIL_RETRY_FIRST_MS;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const update = (change: Partial<Omit<TailState, "requestKey">>) => {
    setTail((previous) => {
      const base: TailState =
        previous?.requestKey === requestKey
          ? previous
          : { requestKey, rows: [], status: "connecting", error: null };
      return { ...base, ...change };
    });
  };

  const flushTimer = setInterval(() => {
    if (pending.length === 0) return;
    const arrived = pending;
    pending = [];
    setTail((previous) => {
      if (previous?.requestKey !== requestKey) return previous;
      return { ...previous, rows: mergeTailRows(previous.rows, arrived, TAIL_MAX_ROWS) };
    });
  }, TAIL_FLUSH_MS);

  const connect = async (): Promise<void> => {
    try {
      const response = await openLogTail(request, controller.signal);
      update({ status: "live", error: null });
      retryMs = TAIL_RETRY_FIRST_MS;
      if (response.body) {
        await readEvents(response.body, (event) => {
          if (event.event === SSE_LOGS_EVENT) pending.push(...(JSON.parse(event.data) as LogItem[]));
        });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status < FIRST_SERVER_ERROR_STATUS) {
        update({ status: "stopped", error });
        return;
      }
      update({ error });
    }
    if (controller.signal.aborted) return;
    update({ status: "reconnecting" });
    retryTimer = setTimeout(() => void connect(), retryMs);
    retryMs = Math.min(retryMs * TAIL_RETRY_BACKOFF_FACTOR, TAIL_RETRY_MAX_MS);
  };

  void connect();
  return () => {
    controller.abort();
    clearInterval(flushTimer);
    clearTimeout(retryTimer);
  };
}
