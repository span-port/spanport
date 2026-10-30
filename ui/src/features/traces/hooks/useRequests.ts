// The Requests list: filters in the URL, results newest first, more on scroll.
import { skipToken, useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { TRACE_SEARCH_QUERY_KEY } from "../../../constants/api";
import {
  DEFAULT_REQUEST_RANGE,
  MS_PER_MINUTE,
  REQUEST_RANGES,
  URL_FLAG_ON,
  URL_PARAM_ERRORS,
  URL_PARAM_MIN_MS,
  URL_PARAM_REQUEST_RANGE,
  URL_PARAM_ROUTE,
  URL_PARAM_SERVICE,
} from "../../../constants/traces";
import { useSelectedProject } from "../../projects";
import { searchRequests, type RequestSearch } from "../api";

export interface RequestFilters {
  range: string;
  service: string;
  route: string;
  minMs: number;
  errorsOnly: boolean;
}

function readFilters(params: URLSearchParams): RequestFilters {
  const range = params.get(URL_PARAM_REQUEST_RANGE) ?? "";
  const minMs = Number(params.get(URL_PARAM_MIN_MS));
  return {
    range: REQUEST_RANGES.some((choice) => choice.key === range) ? range : DEFAULT_REQUEST_RANGE,
    service: params.get(URL_PARAM_SERVICE) ?? "",
    route: params.get(URL_PARAM_ROUTE) ?? "",
    minMs: Number.isInteger(minMs) && minMs > 0 ? minMs : 0,
    errorsOnly: params.get(URL_PARAM_ERRORS) === URL_FLAG_ON,
  };
}

function writeFilters(current: URLSearchParams, filters: RequestFilters): URLSearchParams {
  const next = new URLSearchParams(current);
  const set = (name: string, value: string) => {
    if (value) next.set(name, value);
    else next.delete(name);
  };
  set(URL_PARAM_REQUEST_RANGE, filters.range === DEFAULT_REQUEST_RANGE ? "" : filters.range);
  set(URL_PARAM_SERVICE, filters.service);
  set(URL_PARAM_ROUTE, filters.route);
  set(URL_PARAM_MIN_MS, filters.minMs > 0 ? String(filters.minMs) : "");
  set(URL_PARAM_ERRORS, filters.errorsOnly ? URL_FLAG_ON : "");
  return next;
}

/**
 * The project's incoming requests for the filters in the URL.
 *
 * @returns The rows, the filters and `change` to update them, loading state, `loadMore` and errors.
 */
export function useRequests() {
  const { selected } = useSelectedProject();
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  // "Now" is taken when the filters change, so scrolling for more never shifts the window.
  const [endsAtMs, setEndsAtMs] = useState(Date.now);
  const minutes = REQUEST_RANGES.find((choice) => choice.key === filters.range)?.minutes ?? 0;
  const search: RequestSearch | null =
    selected === null
      ? null
      : {
          project_id: selected.id,
          start: new Date(endsAtMs - minutes * MS_PER_MINUTE).toISOString(),
          end: new Date(endsAtMs).toISOString(),
          service: filters.service,
          route: filters.route,
          min_duration_ms: filters.minMs,
          errors_only: filters.errorsOnly,
        };
  const results = useInfiniteQuery({
    queryKey: [TRACE_SEARCH_QUERY_KEY, search],
    // No project yet: nothing to search.
    queryFn:
      search === null
        ? skipToken
        : ({ pageParam, signal }) => searchRequests(search, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
  return {
    projectId: selected?.id ?? null,
    filters,
    change: (patch: Partial<RequestFilters>) => {
      setParams((current) => writeFilters(current, { ...filters, ...patch }));
      setEndsAtMs(Date.now());
    },
    refresh: () => {
      setEndsAtMs(Date.now());
    },
    rows: results.data?.pages.flatMap((page) => page.data) ?? [],
    loading: results.isPending && search !== null,
    hasMore: results.hasNextPage,
    loadMore: () => {
      if (results.hasNextPage && !results.isFetchingNextPage) void results.fetchNextPage();
    },
    error: results.error,
  };
}
