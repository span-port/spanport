// The Storage tab's data: what each project keeps.
import { useQuery } from "@tanstack/react-query";

import { STORAGE_QUERY_KEY } from "../../../constants/api";
import { fetchStorage } from "../api";

/** The organization's stored logs and traces per project, with totals and retention. */
export function useStorage() {
  const summary = useQuery({ queryKey: [STORAGE_QUERY_KEY], queryFn: ({ signal }) => fetchStorage(signal) });
  return {
    summary: summary.data ?? null,
    error: summary.error,
    refresh: () => {
      void summary.refetch();
    },
  };
}
