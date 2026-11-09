// Setup -> Data: the Storage tab (the others come in later releases) and byte sizes.

export const DATA_TABS = [
  { key: "storage", label: "Storage", ready: true },
  { key: "integrations", label: "Integrations", ready: false },
  { key: "settings", label: "Settings", ready: false },
] as const;
export const COMING_LATER = "Coming in a later release";
// Byte sizes are shown in 1024 steps: 512 B, 3.4 KB, 12 MB, 1.2 GB.
export const BYTES_PER_UNIT_STEP = 1024;
export const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;
export const REDIS_NOT_USED_NOTE = "Not used yet. The LLM gateway adds it for rate limits, budgets and caching.";
export const ESTIMATE_NOTE =
  "Sizes are estimates: each project's rows times the average size of a row on disk. ClickHouse compresses, so a row usually takes a few dozen bytes.";
