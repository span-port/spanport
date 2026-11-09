// The APIs screen: the range in the URL, the summary for the selected project, and the slowest
// API's timeline for the overview chart.
import { skipToken, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { ENDPOINT_DETAIL_QUERY_KEY, ENDPOINT_SUMMARY_QUERY_KEY } from "../../../constants/api";
import { endpointDetailLink, slowestEndpoint } from "../../../lib/endpoints";
import { useSelectedProject } from "../../projects";
import {
  fetchEndpointDetail,
  fetchEndpointSummary,
  type EndpointDetailSearch,
  type EndpointSearch,
  type EndpointStats,
} from "../api";
import { useRequestRange } from "./useRequestRange";

/**
 * The selected project's endpoints over the range in the URL.
 *
 * @returns The summary, the slowest API and its timeline, the project, the range with its
 *   controls, `linkTo` / `open` for an API's detail page, loading and errors.
 */
export function useEndpoints() {
  const { selected } = useSelectedProject();
  const navigate = useNavigate();
  const range = useRequestRange();
  const search: EndpointSearch | null =
    selected === null ? null : { project_id: selected.id, start: range.start, end: range.end };
  const summary = useQuery({
    queryKey: [ENDPOINT_SUMMARY_QUERY_KEY, search],
    queryFn: search === null ? skipToken : ({ signal }) => fetchEndpointSummary(search, signal),
  });
  const slowest = slowestEndpoint(summary.data?.data ?? []);
  const slowestSearch: EndpointDetailSearch | null =
    search === null || slowest === null
      ? null
      : { ...search, service: slowest.service, http_method: slowest.http_method, route: slowest.route };
  const slowestDetail = useQuery({
    queryKey: [ENDPOINT_DETAIL_QUERY_KEY, slowestSearch],
    queryFn: slowestSearch === null ? skipToken : ({ signal }) => fetchEndpointDetail(slowestSearch, signal),
  });
  const detailLink = (endpoint: Pick<EndpointStats, "service" | "http_method" | "route">) =>
    endpointDetailLink(selected?.id ?? "", range.range, endpoint);
  return {
    project: selected,
    range,
    summary: summary.data ?? null,
    slowest,
    slowestTimeline: slowestDetail.data ?? null,
    /** One API's detail page (the whole row opens it, not just the link). */
    linkTo: detailLink,
    open: (endpoint: EndpointStats) => {
      void navigate(detailLink(endpoint));
    },
    loading: summary.isPending && search !== null,
    error: summary.error,
  };
}
