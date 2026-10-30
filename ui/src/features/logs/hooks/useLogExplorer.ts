// Everything the logs screen shows and does: filters from the URL, history, counts and live tail.
import { useState } from "react";

import {
  EQUALS_OPERATOR,
  LEVEL_FIELD,
  MAX_FILTER_CHIPS,
  QUERY_AND,
} from "../../../constants/logs";
import { isLevelChip as isAnyLevelChip } from "../../../lib/chipGroups";
import type { LogUrlState } from "../../../lib/logUrlState";
import { chipsToQueryText } from "../../../lib/queryText";
import { DEFAULT_RANGE, isLiveRange, rangeWindow, type RangeSelection } from "../../../lib/timeRange";
import { useSessionStore } from "../../../state/sessionStore";
import { useSelectedProject } from "../../projects/hooks/useSelectedProject";
import type { FilterChip, LogCountsResponse, LogItem, LogTailRequest } from "../types";
import { useLiveTail, type TailStatus } from "./useLiveTail";
import { useLogCounts, useLogSearch } from "./useLogSearch";
import { useLogUrlState } from "./useLogUrlState";

export type StreamState = "live" | "connecting" | "reconnecting" | "paused" | "stopped" | "historical";

/**
 * The logs screen's data and actions.
 *
 * A range that ends now is shown live: its history loads once, then new lines stream in on
 * top until paused. A fixed range is historical. Each change re-anchors the range at now.
 */
export function useLogExplorer() {
  const { state, update } = useLogUrlState();
  const { projects, selected } = useSelectedProject();
  const timeZone = useSessionStore((session) => session.timeZone);
  const setTimeZone = useSessionStore((session) => session.setTimeZone);
  const [endsAtMs, setEndsAtMs] = useState(Date.now);
  const [paused, setPaused] = useState(false);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  const liveRange = isLiveRange(state.range);
  const following = liveRange && !paused;
  // Chips always join with "and": the server treats values of one field as "one of".
  const tailRequest: LogTailRequest | null =
    selected === null
      ? null
      : { project_id: selected.id, filters: state.filters, combine: "and", query: state.query };
  const filterRequest =
    tailRequest === null ? null : { ...tailRequest, ...rangeWindow(state.range, endsAtMs) };
  // The level cards count every level, so a hidden level still shows how many lines it has.
  const countsRequest =
    tailRequest === null
      ? null
      : { ...tailRequest, filters: state.filters.filter((chip) => !isAnyLevelChip(chip)) };
  const shownLevels = state.filters.filter(isAnyLevelChip).map((chip) => chip.value);
  const searchAsQuery = [chipsToQueryText(state.filters), state.query].filter(Boolean).join(QUERY_AND);

  const search = useLogSearch(filterRequest);
  const counts = useLogCounts(countsRequest, state.range, endsAtMs, following);
  const tail = useLiveTail(following ? tailRequest : null);
  const history = search.data?.pages.flatMap((page) => page.data) ?? [];
  const rows = newestFirst(tail.rows, history);

  // Any change searches again, relative to now.
  const change = (patch: Partial<LogUrlState>) => {
    update(patch);
    setEndsAtMs(Date.now());
    setExpandedLogId(null);
  };
  const setFilters = (filters: FilterChip[]) => {
    change({ filters: filters.slice(0, MAX_FILTER_CHIPS) });
  };

  return {
    state,
    project: selected,
    projects,
    timeZone,
    setTimeZone,
    rows,
    tableMessage: describeResults(
      liveRange,
      rows.length,
      search.isPending && filterRequest !== null,
      search.isFetchingNextPage,
      search.hasNextPage,
    ),
    search,
    counts,
    /** Lines matching every filter, levels included (the cards' counts ignore the level filter). */
    matchCount: matchingLines(counts.data, shownLevels),
    tailError: tail.error,
    streamState: streamState(liveRange, paused, tail.status),
    expandedLogId,
    toggleExpanded: (logId: string) => {
      setExpandedLogId((current) => (current === logId ? null : logId));
    },
    selectRange: (range: RangeSelection) => {
      setPaused(false);
      change({ range });
    },
    /** Pause or resume following; on a fixed range, go back to following the last 15 minutes. */
    togglePause: () => {
      if (!liveRange) {
        change({ range: DEFAULT_RANGE });
      } else if (paused) {
        setPaused(false);
        setEndsAtMs(Date.now());
      } else {
        setPaused(true);
      }
    },
    addFilter: (chip: FilterChip) => {
      setFilters([...state.filters, chip]);
    },
    removeLastFilter: () => {
      setFilters(state.filters.slice(0, -1));
    },
    removeFilter: (index: number) => {
      setFilters(state.filters.filter((_chip, chipIndex) => chipIndex !== index));
    },
    clearFilters: () => {
      change({ filters: [], query: "" });
    },
    /** Levels picked on the cards; empty means every level is shown. */
    shownLevels,
    /** Show or hide one level (a card click). */
    toggleLevel: (level: string) => {
      const others = state.filters.filter((chip) => !isChipForLevel(chip, level));
      const shown = others.length !== state.filters.length;
      setFilters(
        shown ? others : [...state.filters, { field: LEVEL_FIELD, operator: EQUALS_OPERATOR, value: level }],
      );
    },
    showAllLevels: () => {
      setFilters(state.filters.filter((chip) => !isAnyLevelChip(chip)));
    },
    applyQuery: (query: string) => {
      change({ query });
    },
    /** The whole search (chips and text) as one query, e.g. for an alert rule. */
    searchAsQuery,
    /** What a download exports: exactly this search, project, range and filters. */
    exportRequest: filterRequest,
    /** Switch to the text query; the chips carry over as text. */
    switchToQuery: () => {
      change({ queryMode: true, filters: [], query: searchAsQuery });
    },
    switchToChips: () => {
      change({ queryMode: false, query: "" });
    },
    loadMore: () => {
      if (search.hasNextPage && !search.isFetchingNextPage) void search.fetchNextPage();
    },
  };
}

export type LogExplorer = ReturnType<typeof useLogExplorer>;

/** Streamed rows above history, each line once (the stream resends its last 30 seconds). */
function newestFirst(streamed: LogItem[], history: LogItem[]): LogItem[] {
  const historyIds = new Set(history.map((row) => row.log_id));
  return [...streamed.filter((row) => !historyIds.has(row.log_id)), ...history];
}

/** The total for the levels shown, or every level when none is picked. */
function matchingLines(
  counts: LogCountsResponse | undefined,
  shownLevels: string[],
): number | undefined {
  if (counts === undefined) return undefined;
  if (shownLevels.length === 0) return counts.total;
  return shownLevels.reduce((sum, level) => sum + (counts.by_level[level] ?? 0), 0);
}

function isChipForLevel(chip: FilterChip, level: string): boolean {
  return isAnyLevelChip(chip) && chip.value === level;
}

/** What the badge next to the title says. */
function streamState(liveRange: boolean, paused: boolean, tailStatus: TailStatus): StreamState {
  if (!liveRange) return "historical";
  if (paused || tailStatus === "paused") return "paused";
  if (tailStatus === "off") return "connecting";
  return tailStatus;
}

/** The line under the log list: loading, empty, end of results or nothing. */
function describeResults(
  liveRange: boolean,
  rowCount: number,
  loading: boolean,
  loadingMore: boolean,
  hasMore: boolean,
): string | null {
  if (loading) return "Loading logs...";
  if (loadingMore) return "Loading older logs...";
  if (rowCount === 0) {
    return liveRange
      ? "No log lines match yet. New ones appear here as they arrive."
      : "No logs match these filters in this range. Widen the time range or remove a filter.";
  }
  return hasMore ? null : "End of results in this range.";
}
