// How many lines a rule's search matches right now, so its settings can be checked before saving.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ALERT_PREVIEW_QUERY_KEY } from "../../../constants/api";
import { MAX_ALERT_WINDOW_MINUTES, MS_PER_MINUTE, PREVIEW_DEBOUNCE_MS } from "../../../constants/alerts";
import { countLogs } from "../../logs/api";

/**
 * Count the project's lines matching `query` in the last `windowMinutes`, once typing pauses.
 *
 * @returns The query result: `data.total`, or an ApiError (e.g. 400 for a search that isn't valid yet).
 */
export function useRulePreview(projectId: string, query: string, windowMinutes: number) {
  const [settled, setSettled] = useState({ query, windowMinutes });
  useEffect(() => {
    const timer = setTimeout(() => {
      setSettled({ query, windowMinutes });
    }, PREVIEW_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [query, windowMinutes]);
  const windowValid =
    Number.isInteger(settled.windowMinutes) &&
    settled.windowMinutes >= 1 &&
    settled.windowMinutes <= MAX_ALERT_WINDOW_MINUTES;
  return useQuery({
    queryKey: [ALERT_PREVIEW_QUERY_KEY, projectId, settled.query, settled.windowMinutes],
    enabled: windowValid,
    queryFn: ({ signal }) => {
      const endMs = Date.now();
      return countLogs(
        {
          project_id: projectId,
          filters: [],
          combine: "and",
          query: settled.query,
          start: new Date(endMs - settled.windowMinutes * MS_PER_MINUTE).toISOString(),
          end: new Date(endMs).toISOString(),
        },
        signal,
      );
    },
  });
}
