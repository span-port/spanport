// Pure helpers for the Storage tab: byte sizes and each project's share.
import { BYTE_UNITS, BYTES_PER_UNIT_STEP } from "../constants/storage";
import { PERCENT } from "../constants/traces";

/** e.g. "0 B", "512 B", "3.4 KB", "12 MB", "1.2 GB". */
export function formatBytes(bytes: number): string {
  let size = bytes;
  let unit = 0;
  while (size >= BYTES_PER_UNIT_STEP && unit < BYTE_UNITS.length - 1) {
    size /= BYTES_PER_UNIT_STEP;
    unit += 1;
  }
  const digits = unit === 0 || size >= 10 ? 0 : 1;
  return `${size.toFixed(digits)} ${BYTE_UNITS[unit] ?? ""}`;
}

/** A project's share of everything stored, as a percentage for its bar. */
export function sharePercent(projectBytes: number, totalBytes: number): number {
  return totalBytes > 0 ? (projectBytes / totalBytes) * PERCENT : 0;
}
