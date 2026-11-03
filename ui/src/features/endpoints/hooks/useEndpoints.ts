// The APIs screen: the range in the URL, the summary for the selected project.
import { skipToken, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { ENDPOINT_SUMMARY_QUERY_KEY } from "../../../constants/api";
import {
  DEFAULT_REQUEST_RANGE,
  MS_PER_MINUTE,
  REQUEST_RANGES,
  URL_PARAM_REQUEST_RANGE,
} from "../../../constants/traces";
import { endpointRequestsLink } from "../../../lib/endpoints";
import { useSelectedProject } from "../../projects";
import { fetchEndpointSummary, type EndpointSearch, type EndpointStats } from "../api";

/**
 * The selected project's endpoints over the range in the URL (the same `range` param as Requests).
 *
 * @returns The summary, the project, the range and `changeRange` / `refresh`, `linkTo` / `open` for an
 *   API's requests, loading and errors.
 */
export function useEndpoints() {
  const { selected } = useSelectedProject();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const requested = params.get(URL_PARAM_REQUEST_RANGE) ?? "";
  const rangeKey = REQUEST_RANGES.some((choice) => choice.key === requested) ? requested : DEFAULT_REQUEST_RANGE;
  const minutes = REQUEST_RANGES.find((choice) => choice.key === rangeKey)?.minutes ?? 0;
  const [endsAtMs, setEndsAtMs] = useState(Date.now);
  const search: EndpointSearch | null =
    selected === null
      ? null
      : {
          project_id: selected.id,
          start: new Date(endsAtMs - minutes * MS_PER_MINUTE).toISOString(),
          end: new Date(endsAtMs).toISOString(),
        };
  const summary = useQuery({
    queryKey: [ENDPOINT_SUMMARY_QUERY_KEY, search],
    queryFn: search === null ? skipToken : ({ signal }) => fetchEndpointSummary(search, signal),
  });
  const requestsLink = (endpoint: EndpointStats) =>
    endpointRequestsLink(selected?.id ?? "", rangeKey, endpoint.service, endpoint.route);
  return {
    project: selected,
    range: rangeKey,
    /** The Requests screen for one API (the whole row opens it, not just the link). */
    linkTo: requestsLink,
    open: (endpoint: EndpointStats) => {
      void navigate(requestsLink(endpoint));
    },
    changeRange: (key: string) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        if (key === DEFAULT_REQUEST_RANGE) next.delete(URL_PARAM_REQUEST_RANGE);
        else next.set(URL_PARAM_REQUEST_RANGE, key);
        return next;
      });
      setEndsAtMs(Date.now());
    },
    refresh: () => {
      setEndsAtMs(Date.now());
    },
    summary: summary.data ?? null,
    loading: summary.isPending && search !== null,
    error: summary.error,
  };
}
