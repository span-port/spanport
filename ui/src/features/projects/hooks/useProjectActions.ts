// Rename, archive, restore and delete a project, then reload the list.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { PROJECTS_QUERY_KEY } from "../../../constants/api";
import { toSlug } from "../../../lib/slug";
import { deleteProject, setProjectArchived, updateProject } from "../api";

/** Mutations for one project row; each reloads the projects list (and the switcher). */
export function useProjectActions(projectId: string) {
  const queryClient = useQueryClient();
  const reload = () => queryClient.invalidateQueries({ queryKey: [PROJECTS_QUERY_KEY] });
  const rename = useMutation({
    mutationFn: (change: { project: string; environment: string }) =>
      updateProject(projectId, change),
    onSuccess: reload,
  });
  const archive = useMutation({
    mutationFn: (archived: boolean) => setProjectArchived(projectId, archived),
    onSuccess: reload,
  });
  const remove = useMutation({ mutationFn: () => deleteProject(projectId), onSuccess: reload });
  return {
    /** Rename (the name becomes a slug) and/or move to another environment. */
    rename: (name: string, environment: string) =>
      rename.mutateAsync({ project: toSlug(name), environment }),
    setArchived: (archived: boolean) => {
      archive.mutate(archived);
    },
    /** Delete for good: the project, its keys and all its logs. */
    deleteForever: () => {
      remove.mutate();
    },
    busy: rename.isPending || archive.isPending || remove.isPending,
    error: rename.error ?? archive.error ?? remove.error,
  };
}
