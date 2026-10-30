// Pure helpers for file downloads.
import { ATTACHMENT_FILENAME_PATTERN } from "../constants/logs";

/** The file name in `attachment; filename="..."`, or `fallback` when there isn't one. */
export function fileNameFromDisposition(header: string | null, fallback: string): string {
  return header?.match(ATTACHMENT_FILENAME_PATTERN)?.[1] ?? fallback;
}
