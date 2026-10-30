// Time ranges: a preset or "last N units" (relative to now, so live) or fixed start and end times.
import {
  DEFAULT_PRESET_KEY,
  MAX_RANGE_MINUTES,
  RANGE_ABSOLUTE,
  RANGE_AMOUNT_MESSAGE,
  RANGE_INCOMPLETE_MESSAGE,
  RANGE_ORDER_MESSAGE,
  RANGE_RELATIVE,
  RANGE_TOO_LONG_MESSAGE,
  RANGE_TOO_OLD_MESSAGE,
  RELATIVE_UNITS,
  TIME_PRESETS,
  URL_PARAM_AMOUNT,
  URL_PARAM_END,
  URL_PARAM_RANGE,
  URL_PARAM_START,
  URL_PARAM_UNIT,
} from "../constants/logs";
import { MS_PER_MINUTE } from "../constants/ui";
import { formatRangeTime } from "./formatTime";

export type PresetKey = (typeof TIME_PRESETS)[number]["key"];
export type RelativeUnit = (typeof RELATIVE_UNITS)[number]["unit"];

export type RangeSelection =
  | { kind: "preset"; key: PresetKey }
  | { kind: "relative"; amount: number; unit: RelativeUnit }
  /** Start and end as UTC milliseconds. */
  | { kind: "absolute"; startMs: number; endMs: number };

export const DEFAULT_RANGE: RangeSelection = { kind: "preset", key: DEFAULT_PRESET_KEY };

/** True for ranges that end now, which the explorer follows live. */
export function isLiveRange(range: RangeSelection): boolean {
  return range.kind !== "absolute";
}

/** Length of a range that ends now, in minutes. */
function liveMinutes(range: Exclude<RangeSelection, { kind: "absolute" }>): number {
  if (range.kind === "preset") {
    return TIME_PRESETS.find((preset) => preset.key === range.key)?.minutes ?? MAX_RANGE_MINUTES;
  }
  const unitMinutes = RELATIVE_UNITS.find((choice) => choice.unit === range.unit)?.minutes ?? 1;
  return range.amount * unitMinutes;
}

/**
 * Start and end of `range` as the search API expects them (ISO 8601, UTC).
 *
 * @param nowMs - The moment a live range ends at.
 */
export function rangeWindow(range: RangeSelection, nowMs: number): { start: string; end: string } {
  if (range.kind === "absolute") {
    return { start: new Date(range.startMs).toISOString(), end: new Date(range.endMs).toISOString() };
  }
  return {
    start: new Date(nowMs - liveMinutes(range) * MS_PER_MINUTE).toISOString(),
    end: new Date(nowMs).toISOString(),
  };
}

/** The range in words: "Last 15 minutes", "Last 3 hours" or "29 Oct 07:00 → 29 Oct 09:00". */
export function rangeName(range: RangeSelection, timeZone: string): string {
  if (range.kind === "preset") {
    return TIME_PRESETS.find((preset) => preset.key === range.key)?.name ?? range.key;
  }
  if (range.kind === "relative") {
    const unit = range.amount === 1 ? range.unit.slice(0, -1) : range.unit;
    return `Last ${range.amount} ${unit}`;
  }
  return `${formatRangeTime(range.startMs, timeZone)} → ${formatRangeTime(range.endMs, timeZone)}`;
}

/**
 * Why a custom range can't be searched, in words, or null when it can.
 *
 * Logs are kept 7 days, so a range may not start earlier than that.
 */
export function rangeProblem(range: RangeSelection, nowMs: number): string | null {
  if (range.kind === "preset") return null;
  if (range.kind === "relative") {
    if (!Number.isInteger(range.amount) || range.amount < 1) return RANGE_AMOUNT_MESSAGE;
    return liveMinutes(range) > MAX_RANGE_MINUTES ? RANGE_TOO_LONG_MESSAGE : null;
  }
  if (Number.isNaN(range.startMs) || Number.isNaN(range.endMs)) return RANGE_INCOMPLETE_MESSAGE;
  if (range.endMs <= range.startMs) return RANGE_ORDER_MESSAGE;
  if (range.startMs < nowMs - MAX_RANGE_MINUTES * MS_PER_MINUTE) return RANGE_TOO_OLD_MESSAGE;
  return null;
}

/** Read the range from URL params; anything missing or malformed means the default range. */
export function readRange(params: URLSearchParams): RangeSelection {
  const kind = params.get(URL_PARAM_RANGE);
  if (kind === RANGE_RELATIVE) {
    const amount = Number(params.get(URL_PARAM_AMOUNT));
    const unit = RELATIVE_UNITS.find((choice) => choice.unit === params.get(URL_PARAM_UNIT))?.unit;
    const range: RangeSelection | null = unit ? { kind: "relative", amount, unit } : null;
    return range && rangeProblem(range, Date.now()) === null ? range : DEFAULT_RANGE;
  }
  if (kind === RANGE_ABSOLUTE) {
    const startMs = Date.parse(params.get(URL_PARAM_START) ?? "");
    const endMs = Date.parse(params.get(URL_PARAM_END) ?? "");
    const range: RangeSelection = { kind: "absolute", startMs, endMs };
    return rangeProblem(range, Date.now()) === null ? range : DEFAULT_RANGE;
  }
  const preset = TIME_PRESETS.find((choice) => choice.key === kind);
  return preset ? { kind: "preset", key: preset.key } : DEFAULT_RANGE;
}

/** Add `range` to `params`. */
export function writeRange(range: RangeSelection, params: URLSearchParams): void {
  if (range.kind === "preset") {
    params.set(URL_PARAM_RANGE, range.key);
    return;
  }
  if (range.kind === "relative") {
    params.set(URL_PARAM_RANGE, RANGE_RELATIVE);
    params.set(URL_PARAM_AMOUNT, String(range.amount));
    params.set(URL_PARAM_UNIT, range.unit);
    return;
  }
  params.set(URL_PARAM_RANGE, RANGE_ABSOLUTE);
  params.set(URL_PARAM_START, new Date(range.startMs).toISOString());
  params.set(URL_PARAM_END, new Date(range.endMs).toISOString());
}
