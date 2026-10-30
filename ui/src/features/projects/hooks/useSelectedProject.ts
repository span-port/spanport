// The project every screen shows, kept in the URL so the sidebar and the screen agree.
import { useSearchParams } from "react-router";

import { URL_PARAM_PROJECT } from "../../../constants/logs";
import { useProjects } from "./useProjects";

/**
 * The selected project and a way to change it.
 *
 * A missing or unknown project in the URL (another org's link) means the first project.
 */
export function useSelectedProject() {
  const projects = useProjects();
  const [params, setParams] = useSearchParams();
  const projectList = projects.data?.data ?? [];
  const requestedId = params.get(URL_PARAM_PROJECT);
  const selected = projectList.find((project) => project.id === requestedId) ?? projectList[0] ?? null;
  const select = (projectId: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set(URL_PARAM_PROJECT, projectId);
      return next;
    });
  };
  return { projects, projectList, selected, select };
}
