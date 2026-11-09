// The service map: the range in the URL, what calls what, and the chosen box.
import { skipToken, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { SERVICE_MAP_QUERY_KEY } from "../../../constants/api";
import { mapLayout, nodeLink } from "../../../lib/serviceMap";
import { useSelectedProject } from "../../projects";
import { fetchServiceMap, type EndpointSearch, type MapNode } from "../api";
import { useRequestRange } from "./useRequestRange";

/**
 * The selected project's map over the range in the URL.
 *
 * @returns The project, the range with its controls, the map and its layout, the chosen box
 *   (the busiest service until one is chosen) with `select` and its link, loading and errors.
 */
export function useServiceMap() {
  const { selected } = useSelectedProject();
  const range = useRequestRange();
  const [chosenId, setChosenId] = useState<string | null>(null);
  const search: EndpointSearch | null =
    selected === null ? null : { project_id: selected.id, start: range.start, end: range.end };
  const map = useQuery({
    queryKey: [SERVICE_MAP_QUERY_KEY, search],
    queryFn: search === null ? skipToken : ({ signal }) => fetchServiceMap(search, signal),
  });
  const nodes = map.data?.nodes ?? [];
  const busiestService = nodes
    .filter((node) => node.kind === "service")
    .reduce<MapNode | null>((busiest, node) => (busiest && busiest.calls >= node.calls ? busiest : node), null);
  const chosen = nodes.find((node) => node.id === chosenId) ?? busiestService;
  return {
    project: selected,
    range,
    map: map.data ?? null,
    layout: map.data ? mapLayout(map.data) : null,
    chosen,
    chosenLink: chosen && selected ? nodeLink(chosen, selected.id, range.range) : null,
    select: (node: MapNode) => {
      setChosenId(node.id);
    },
    loading: map.isPending && search !== null,
    error: map.error,
  };
}
