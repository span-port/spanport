// The Errors screen: range, "show" and API in the URL, the chart's numbers, and the chosen bar's
// failing requests.
import { skipToken, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { ERROR_SUMMARY_QUERY_KEY, ERROR_WINDOW_QUERY_KEY } from "../../../constants/api";
import { DEFAULT_ERROR_SHOW, ERROR_SHOW_CHOICES, URL_PARAM_SHOW, type ErrorShow } from "../../../constants/errors";
import { URL_PARAM_METHOD, URL_PARAM_ROUTE, URL_PARAM_SERVICE } from "../../../constants/traces";
import { bucketEnd, errorLogsLink, failedRequestsLink } from "../../../lib/errors";
import { traceLink } from "../../../lib/waterfall";
import { useRequestRange } from "../../endpoints";
import { useSelectedProject } from "../../projects";
import {
  fetchErrorSummary,
  fetchErrorWindow,
  type ErrorApi,
  type ErrorBucket,
  type ErrorSearch,
  type ErrorWindowSearch,
} from "../api";

export type ApiChoice = Pick<ErrorApi, "service" | "http_method" | "route">;

const EVERY_API: ApiChoice = { service: "", http_method: "", route: "" };

function readShow(params: URLSearchParams): ErrorShow {
  const value = params.get(URL_PARAM_SHOW);
  return ERROR_SHOW_CHOICES.find((choice) => choice.key === value)?.key ?? DEFAULT_ERROR_SHOW;
}

function readApi(params: URLSearchParams): ApiChoice {
  return {
    service: params.get(URL_PARAM_SERVICE) ?? "",
    http_method: params.get(URL_PARAM_METHOD) ?? "",
    route: params.get(URL_PARAM_ROUTE) ?? "",
  };
}

/**
 * The selected project's 4xx and 5xx over the range in the URL, and the requests behind the
 * chosen bar.
 *
 * @returns The project, range controls, `show` / `api` with setters, the summary, the chosen
 *   bar with `selectBar`, its window, `openTrace`, loading and errors.
 */
export function useErrors() {
  const { selected } = useSelectedProject();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const range = useRequestRange();
  const show = readShow(params);
  const api = readApi(params);
  const [chosenAt, setChosenAt] = useState<string | null>(null);
  const search: ErrorSearch | null =
    selected === null ? null : { project_id: selected.id, start: range.start, end: range.end, ...api };
  const summary = useQuery({
    queryKey: [ERROR_SUMMARY_QUERY_KEY, search],
    queryFn: search === null ? skipToken : ({ signal }) => fetchErrorSummary(search, signal),
  });
  const bucketSeconds = summary.data?.bucket_seconds ?? 0;
  // A bar from an earlier range or filter is no longer on the chart.
  const chosen: ErrorBucket | null = summary.data?.buckets.find((bucket) => bucket.at === chosenAt) ?? null;
  const windowSearch: ErrorWindowSearch | null =
    search === null || chosen === null
      ? null
      : { ...search, start: chosen.at, end: bucketEnd(chosen.at, bucketSeconds), show };
  const windowQuery = useQuery({
    queryKey: [ERROR_WINDOW_QUERY_KEY, windowSearch],
    queryFn: windowSearch === null ? skipToken : ({ signal }) => fetchErrorWindow(windowSearch, signal),
  });
  const setParam = (name: string, value: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      return next;
    });
  };
  return {
    project: selected,
    range,
    show,
    selectShow: (next: ErrorShow) => {
      setParam(URL_PARAM_SHOW, next === DEFAULT_ERROR_SHOW ? "" : next);
    },
    api,
    selectApi: (next: ApiChoice | null) => {
      const choice = next ?? EVERY_API;
      setParams((current) => {
        const updated = new URLSearchParams(current);
        for (const [name, value] of [
          [URL_PARAM_SERVICE, choice.service],
          [URL_PARAM_METHOD, choice.http_method],
          [URL_PARAM_ROUTE, choice.route],
        ] as const) {
          if (value) updated.set(name, value);
          else updated.delete(name);
        }
        return updated;
      });
    },
    summary: summary.data ?? null,
    chosen,
    chosenEnd: windowSearch?.end ?? null,
    /** The chosen bar's failed requests on the Requests page, and its error lines on Logs. */
    requestsLink: windowSearch ? failedRequestsLink(windowSearch.project_id, windowSearch.start, Date.parse(range.end), api) : null,
    logsLink: windowSearch ? errorLogsLink(windowSearch.project_id, windowSearch.start, windowSearch.end) : null,
    /** Choose a bar, or choose it again to clear it. */
    selectBar: (bucket: ErrorBucket) => {
      setChosenAt(bucket.at === chosenAt ? null : bucket.at);
    },
    window: windowQuery.data ?? null,
    windowLoading: windowQuery.isPending && windowSearch !== null,
    traceLinkOf: (traceId: string) => traceLink(traceId, selected?.id ?? ""),
    openTrace: (traceId: string) => {
      void navigate(traceLink(traceId, selected?.id ?? ""));
    },
    loading: summary.isPending && search !== null,
    error: summary.error ?? windowQuery.error,
  };
}
