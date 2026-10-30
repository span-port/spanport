// Downloading the current search as a file.
import { useMutation } from "@tanstack/react-query";

import { CONTENT_DISPOSITION_HEADER } from "../../../constants/api";
import { FALLBACK_EXPORT_NAME, MAX_EXPORT_LINES, TOO_MANY_TO_EXPORT_NOTE, VIEWER_EXPORT_NOTE } from "../../../constants/logs";
import { fileNameFromDisposition } from "../../../lib/download";
import type { Role } from "../../auth/api";
import { exportLogs, type ExportFormat } from "../api";
import type { LogFilterRequest } from "../types";

/** Hand the browser a file to save, under the server's name for it. */
async function saveResponse(response: Response): Promise<void> {
  const name = fileNameFromDisposition(response.headers.get(CONTENT_DISPOSITION_HEADER), FALLBACK_EXPORT_NAME);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Download the current search (same project, range and filters) as CSV or JSON lines.
 *
 * @param request - The search, or null while there is no project.
 * @param matchCount - Lines the search matches, or undefined while counting.
 * @param role - The signed-in person's role; viewers can't download.
 * @returns `download(format)`, why it's unavailable (or null), and the last error.
 */
export function useLogExport(request: LogFilterRequest | null, matchCount: number | undefined, role: Role | undefined) {
  const download = useMutation({
    mutationFn: async (format: ExportFormat) => {
      if (request === null) return;
      await saveResponse(await exportLogs(request, format));
    },
  });
  const unavailable =
    role === "viewer"
      ? VIEWER_EXPORT_NOTE
      : matchCount !== undefined && matchCount > MAX_EXPORT_LINES
        ? TOO_MANY_TO_EXPORT_NOTE
        : null;
  return {
    download: (format: ExportFormat) => {
      download.mutate(format);
    },
    downloading: download.isPending,
    unavailable: request === null ? null : unavailable,
    error: download.error,
  };
}
