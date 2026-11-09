// The API detail page: which API (service, method, route in the URL), its data, and links out.
import { skipToken, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";

import { ENDPOINT_DETAIL_QUERY_KEY } from "../../../constants/api";
import { URL_PARAM_PROJECT } from "../../../constants/logs";
import { URL_PARAM_METHOD, URL_PARAM_ROUTE, URL_PARAM_SERVICE } from "../../../constants/traces";
import { APIS_ROUTE } from "../../../constants/ui";
import { endpointRequestsLink } from "../../../lib/endpoints";
import { writeRange } from "../../../lib/timeRange";
import { traceLink } from "../../../lib/waterfall";
import { useSelectedProject } from "../../projects";
import { fetchEndpointDetail, type EndpointDetailSearch } from "../api";
import { useRequestRange } from "./useRequestRange";

/**
 * The API named in the URL, over the range in the URL, for the selected project.
 *
 * @returns The API (service, method, route), its detail, the range with its controls,
 *   `backLink` to the APIs list, `requestsLink`, `traceLink` / `openTrace` for a slow request,
 *   loading and errors.
 */
export function useEndpointDetail() {
  const { selected } = useSelectedProject();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const range = useRequestRange();
  const projectId = selected?.id ?? "";
  const endpoint = {
    service: params.get(URL_PARAM_SERVICE) ?? "",
    http_method: params.get(URL_PARAM_METHOD) ?? "",
    route: params.get(URL_PARAM_ROUTE) ?? "",
  };
  const search: EndpointDetailSearch | null =
    selected === null || endpoint.route === "" || endpoint.service === ""
      ? null
      : { project_id: selected.id, start: range.start, end: range.end, ...endpoint };
  const detail = useQuery({
    queryKey: [ENDPOINT_DETAIL_QUERY_KEY, search],
    queryFn: search === null ? skipToken : ({ signal }) => fetchEndpointDetail(search, signal),
  });
  const backParams = new URLSearchParams(projectId ? { [URL_PARAM_PROJECT]: projectId } : {});
  writeRange(range.range, backParams);
  return {
    endpoint,
    detail: detail.data ?? null,
    range,
    backLink: `${APIS_ROUTE}?${backParams.toString()}`,
    requestsLink: endpointRequestsLink(projectId, range.range, endpoint.service, endpoint.route),
    traceLink: (traceId: string) => traceLink(traceId, projectId),
    openTrace: (traceId: string) => {
      void navigate(traceLink(traceId, projectId));
    },
    loading: detail.isPending && search !== null,
    error: detail.error,
  };
}
