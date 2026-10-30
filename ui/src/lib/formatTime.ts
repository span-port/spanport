// Show UTC timestamps in the chosen timezone, and read typed times in it. Storage and the API stay UTC.
import {
  BROWSER_ZONE_LABEL,
  GMT_LABEL,
  MONTH_LOCALE,
  MS_PER_SECOND,
  TIME_LOCALE,
  TIME_ZONES,
  UTC_DEFAULT_LABEL,
  UTC_LABEL,
  UTC_OFFSET_ZERO,
  UTC_ZONE,
} from "../constants/ui";

type WallParts = Record<Intl.DateTimeFormatPartTypes, string>;

/** The calendar and clock parts of `ms` as read on a wall clock in `timeZone`. */
function wallParts(ms: number, timeZone: string): WallParts {
  const parts = new Intl.DateTimeFormat(TIME_LOCALE, {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
    hourCycle: "h23",
  }).formatToParts(new Date(ms));
  return Object.fromEntries(parts.map((part) => [part.type, part.value])) as WallParts;
}

/** Short month name, e.g. "Oct", for `ms` in `timeZone`. */
function monthName(ms: number, timeZone: string): string {
  return new Intl.DateTimeFormat(MONTH_LOCALE, { timeZone, month: "short" }).format(new Date(ms));
}

/**
 * Format a timestamp as "2026-10-29 07:00:01.123" in `timeZone`.
 *
 * @param isoTime - An ISO 8601 time from the API.
 * @param timeZone - An IANA zone such as "UTC" or "Asia/Kolkata".
 */
export function formatLogTime(isoTime: string, timeZone: string): string {
  const wall = wallParts(Date.parse(isoTime), timeZone);
  return (
    `${wall.year}-${wall.month}-${wall.day} ` +
    `${wall.hour}:${wall.minute}:${wall.second}.${wall.fractionalSecond}`
  );
}

/** Compact time for the log table, e.g. "29 Oct 07:00:01.123". */
export function formatTableTime(isoTime: string, timeZone: string): string {
  const ms = Date.parse(isoTime);
  const wall = wallParts(ms, timeZone);
  return (
    `${Number(wall.day)} ${monthName(ms, timeZone)} ` +
    `${wall.hour}:${wall.minute}:${wall.second}.${wall.fractionalSecond}`
  );
}

/** A range end for summaries, e.g. "29 Oct 07:00". */
export function formatRangeTime(ms: number, timeZone: string): string {
  const wall = wallParts(ms, timeZone);
  return `${Number(wall.day)} ${monthName(ms, timeZone)} ${wall.hour}:${wall.minute}`;
}

/** How far `timeZone`'s wall clock is ahead of UTC at `ms`, in milliseconds. */
function zoneOffsetMs(ms: number, timeZone: string): number {
  const wall = wallParts(ms, timeZone);
  const wallAsUtc = Date.UTC(
    Number(wall.year),
    Number(wall.month) - 1,
    Number(wall.day),
    Number(wall.hour),
    Number(wall.minute),
    Number(wall.second),
  );
  return wallAsUtc - Math.floor(ms / MS_PER_SECOND) * MS_PER_SECOND;
}

/**
 * The UTC moment a person means by typing `date` and `time` in `timeZone`.
 *
 * @param date - "YYYY-MM-DD", as an `<input type="date">` gives it.
 * @param time - "HH:MM" or "HH:MM:SS", as an `<input type="time">` gives it.
 * @returns Milliseconds since the epoch, or NaN when either input is incomplete.
 */
export function zonedInputsToUtc(date: string, time: string, timeZone: string): number {
  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute, second = 0] = time.split(":").map(Number);
  if (year === undefined || month === undefined || day === undefined) return NaN;
  if (hour === undefined || minute === undefined) return NaN;
  const wallAsUtc = Date.UTC(year, month - 1, day, hour, minute, second);
  // Two passes settle times next to a daylight-saving change.
  const firstGuess = wallAsUtc - zoneOffsetMs(wallAsUtc, timeZone);
  return wallAsUtc - zoneOffsetMs(firstGuess, timeZone);
}

/** `ms` as the date and time inputs would show it in `timeZone`. */
export function utcToZonedInputs(ms: number, timeZone: string): { date: string; time: string } {
  const wall = wallParts(ms, timeZone);
  return {
    date: `${wall.year}-${wall.month}-${wall.day}`,
    time: `${wall.hour}:${wall.minute}:${wall.second}`,
  };
}

/**
 * The zone's offset at a moment, e.g. "UTC+05:30" (daylight saving follows the IANA rules).
 */
export function zoneOffsetLabel(timeZone: string, at: Date): string {
  const name = new Intl.DateTimeFormat(TIME_LOCALE, { timeZone, timeZoneName: "longOffset" })
    .formatToParts(at)
    .find((formatted) => formatted.type === "timeZoneName")?.value;
  if (name === undefined || name === GMT_LABEL) return UTC_OFFSET_ZERO;
  return name.replace(GMT_LABEL, UTC_LABEL);
}

/** The browser's own zone, e.g. "Asia/Kolkata". */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Zones for the timezone menu: UTC first, then the browser's own, then common ones, each once. */
export function timeZoneChoices(at: Date): { zone: string; label: string }[] {
  const choices = [
    { zone: UTC_ZONE, label: UTC_DEFAULT_LABEL },
    { zone: browserTimeZone(), label: `${BROWSER_ZONE_LABEL} · ${zoneOffsetLabel(browserTimeZone(), at)}` },
    ...TIME_ZONES.map(({ zone, label }) => ({ zone, label: `${label} · ${zoneOffsetLabel(zone, at)}` })),
  ];
  return choices.filter((choice, index) => choices.findIndex((other) => other.zone === choice.zone) === index);
}
