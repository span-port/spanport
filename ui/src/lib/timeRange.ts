// Time ranges: a preset or "last N units" (relative to now, so live) or fixed start and end times.
// Logs and traces are kept for different lengths, so each screen passes its RangeRules.
import {
  LOG_RANGE_RULES,
  RANGE_ABSOLUTE,
  RANGE_AMOUNT_MESSAGE,
  RANGE_INCOMPLETE_MESSAGE,
  RANGE_ORDER_MESSAGE,
  RANGE_RELATIVE,
  RELATIVE_UNITS,
  URL_PARAM_AMOUNT,
  URL_PARAM_END,
  URL_PARAM_RANGE,
  URL_PARAM_START,
  URL_PARAM_UNIT,
} from "../constants/logs";
import { MS_PER_MINUTE } from "../constants/ui";
import { formatRangeTime } from "./formatTime";

export type RelativeUnit = (typeof RELATIVE_UNITS)[number]["unit"];

/** What one screen allows: its quick ranges, how far back data goes, and what to say about it. */
export interface RangeRules {
  presets: readonly { key: string; label: string; name: string; minutes: number }[];
  defaultKey: string;
  maxMinutes: number;
  /** e.g. "logs kept 7 days", shown next to the picker and in the custom range dialog. */
  keptNote: string;
  tooLongMessage: string;
  tooOldMessage: string;
}

export type RangeSelection =
  | { kind: "preset"; key: string }
  | { kind: "relative"; amount: number; unit: RelativeUnit }
  /** Start and end as UTC milliseconds. */
  | { kind: "absolute"; startMs: number; endMs: number };

export const DEFAULT_RANGE: RangeSelection = { kind: "preset", key: LOG_RANGE_RULES.defaultKey };

/** True for ranges that end now, which the explorer follows live. */
export function isLiveRange(range: RangeSelection): boolean {
  return range.kind !== "absolute";
}

/** Length of a range that ends now, in minutes. */
function liveMinutes(range: Exclude<RangeSelection, { kind: "absolute" }>, rules: RangeRules): number {
  if (range.kind === "preset") {
    return rules.presets.find((preset) => preset.key === range.key)?.minutes ?? rules.maxMinutes;
  }
  const unitMinutes = RELATIVE_UNITS.find((choice) => choice.unit === range.unit)?.minutes ?? 1;
  return range.amount * unitMinutes;
}

/**
 * Start and end of `range` as the search API expects them (ISO 8601, UTC).
 *
 * @param nowMs - The moment a live range ends at.
 */
export function rangeWindow(
  range: RangeSelection,
  nowMs: number,
  rules: RangeRules = LOG_RANGE_RULES,
): { start: string; end: string } {
  if (range.kind === "absolute") {
    return { start: new Date(range.startMs).toISOString(), end: new Date(range.endMs).toISOString() };
  }
  return {
    start: new Date(nowMs - liveMinutes(range, rules) * MS_PER_MINUTE).toISOString(),
    end: new Date(nowMs).toISOString(),
  };
}

/** The range in words: "Last 15 minutes", "Last 3 hours" or "29 Oct 07:00 → 29 Oct 09:00". */
export function rangeName(range: RangeSelection, timeZone: string, rules: RangeRules = LOG_RANGE_RULES): string {
  if (range.kind === "preset") {
    return rules.presets.find((preset) => preset.key === range.key)?.name ?? range.key;
  }
  if (range.kind === "relative") {
    const unit = range.amount === 1 ? range.unit.slice(0, -1) : range.unit;
    return `Last ${String(range.amount)} ${unit}`;
  }
  return `${formatRangeTime(range.startMs, timeZone)} → ${formatRangeTime(range.endMs, timeZone)}`;
}

/**
 * Why a custom range can't be searched, in words, or null when it can: it may not reach further
 * back than the data is kept (`rules.maxMinutes`).
 */
export function rangeProblem(
  range: RangeSelection,
  nowMs: number,
  rules: RangeRules = LOG_RANGE_RULES,
): string | null {
  if (range.kind === "preset") return null;
  if (range.kind === "relative") {
    if (!Number.isInteger(range.amount) || range.amount < 1) return RANGE_AMOUNT_MESSAGE;
    return liveMinutes(range, rules) > rules.maxMinutes ? rules.tooLongMessage : null;
  }
  if (Number.isNaN(range.startMs) || Number.isNaN(range.endMs)) return RANGE_INCOMPLETE_MESSAGE;
  if (range.endMs <= range.startMs) return RANGE_ORDER_MESSAGE;
  if (range.startMs < nowMs - rules.maxMinutes * MS_PER_MINUTE) return rules.tooOldMessage;
  return null;
}

/** Read the range from URL params; anything missing or malformed means the screen's default. */
export function readRange(params: URLSearchParams, rules: RangeRules = LOG_RANGE_RULES): RangeSelection {
  const fallback: RangeSelection = { kind: "preset", key: rules.defaultKey };
  const kind = params.get(URL_PARAM_RANGE);
  if (kind === RANGE_RELATIVE) {
    const amount = Number(params.get(URL_PARAM_AMOUNT));
    const unit = RELATIVE_UNITS.find((choice) => choice.unit === params.get(URL_PARAM_UNIT))?.unit;
    const range: RangeSelection | null = unit ? { kind: "relative", amount, unit } : null;
    return range && rangeProblem(range, Date.now(), rules) === null ? range : fallback;
  }
  if (kind === RANGE_ABSOLUTE) {
    const startMs = Date.parse(params.get(URL_PARAM_START) ?? "");
    const endMs = Date.parse(params.get(URL_PARAM_END) ?? "");
    const range: RangeSelection = { kind: "absolute", startMs, endMs };
    return rangeProblem(range, Date.now(), rules) === null ? range : fallback;
  }
  const preset = rules.presets.find((choice) => choice.key === kind);
  return preset ? { kind: "preset", key: preset.key } : fallback;
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
