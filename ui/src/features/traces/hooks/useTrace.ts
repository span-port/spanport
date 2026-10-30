// One trace, laid out as a waterfall.
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { TRACE_QUERY_KEY } from "../../../constants/api";
import { traceLogsLink, waterfallRows } from "../../../lib/waterfall";
import { useSelectedProject } from "../../projects";
import { fetchTrace } from "../api";

/**
 * The trace in the URL (/requests/:traceId) for the selected project.
 *
 * @returns The trace, its waterfall rows, the link to its logs, and loading / error state.
 */
export function useTrace() {
  const { traceId = "" } = useParams();
  const { selected } = useSelectedProject();
  const projectId = selected?.id ?? null;
  const trace = useQuery({
    queryKey: [TRACE_QUERY_KEY, projectId, traceId],
    queryFn: ({ signal }) => fetchTrace(traceId, projectId ?? "", signal),
    enabled: projectId !== null && traceId !== "",
  });
  const detail = trace.data ?? null;
  return {
    traceId,
    detail,
    rows: detail ? waterfallRows(detail.spans) : [],
    logsLink:
      detail && projectId !== null
        ? traceLogsLink(projectId, detail.trace_id, detail.start_ts, detail.duration_ms)
        : null,
    loading: trace.isPending && projectId !== null,
    error: trace.error,
  };
}
