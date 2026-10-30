// Search results and per-level counts for the current filters and time range.
import { skipToken, useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { LOG_COUNTS_QUERY_KEY, LOG_SEARCH_QUERY_KEY } from "../../../constants/api";
import { LIVE_COUNTS_REFRESH_MS } from "../../../constants/logs";
import { rangeWindow, type RangeSelection } from "../../../lib/timeRange";
import { countLogs, searchLogs } from "../api";
import type { LogFilterRequest, LogTailRequest } from "../types";

/**
 * Pages of matching logs, newest first; `fetchNextPage` follows `next_cursor`.
 *
 * @param request - What to search, or null to search nothing (no project yet, or live tail on).
 */
export function useLogSearch(request: LogFilterRequest | null) {
  return useInfiniteQuery({
    queryKey: [LOG_SEARCH_QUERY_KEY, request],
    queryFn: request
      ? ({ pageParam, signal }) => searchLogs(request, pageParam, signal)
      : skipToken,
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
}

/**
 * Total and per-level counts for the filters over the range.
 *
 * While following live, the range ends at the moment of each fetch and is counted again every
 * few seconds, so the level cards keep up with the streamed lines. TanStack Query pauses the
 * refresh while the browser tab is hidden. Otherwise the range ends at `endsAtMs`, counted once.
 *
 * @param filters - Project and filters, or null to count nothing (no project yet).
 */
export function useLogCounts(
  filters: LogTailRequest | null,
  range: RangeSelection,
  endsAtMs: number,
  following: boolean,
) {
  return useQuery({
    queryKey: [LOG_COUNTS_QUERY_KEY, filters, range, following ? "live" : endsAtMs],
    queryFn: filters
      ? ({ signal }) =>
          countLogs({ ...filters, ...rangeWindow(range, following ? Date.now() : endsAtMs) }, signal)
      : skipToken,
    refetchInterval: following ? LIVE_COUNTS_REFRESH_MS : false,
  });
}
