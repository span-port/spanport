// The organization's projects, cached like any other server data.
import { useQuery } from "@tanstack/react-query";

import { PROJECTS_QUERY_KEY } from "../../../constants/api";
import { fetchProjects } from "../api";

/** Load the project list for the switcher. */
export function useProjects() {
  return useQuery({
    queryKey: [PROJECTS_QUERY_KEY],
    queryFn: ({ signal }) => fetchProjects(signal),
  });
}
