// Month grids and day arithmetic for the date picker. Dates are "YYYY-MM-DD" strings (calendar
// days, no time zone), the same format as the time-range form uses.
import {
  DAYS_IN_GRID,
  DAYS_IN_WEEK,
  ISO_DAY_LENGTH,
  ISO_MONTH_LENGTH,
  MONTH_LOCALE,
  MS_PER_DAY,
} from "../constants/ui";

export interface CalendarDay {
  date: string;
  dayOfMonth: number;
  inMonth: boolean;
}

/** "YYYY-MM-DD" for a UTC midnight timestamp. */
function isoDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, ISO_DAY_LENGTH);
}

/** UTC midnight of a "YYYY-MM-DD" day. */
function dayStart(date: string): number {
  return Date.UTC(
    Number(date.slice(0, 4)),
    Number(date.slice(5, ISO_MONTH_LENGTH)) - 1,
    Number(date.slice(8, ISO_DAY_LENGTH)),
  );
}

/** The first day of the month `date` is in. */
export function monthOf(date: string): string {
  return `${date.slice(0, ISO_MONTH_LENGTH)}-01`;
}

/** The first day of the month `count` months after (or before) `month`. */
export function addMonths(month: string, count: number): string {
  const start = new Date(dayStart(monthOf(month)));
  start.setUTCMonth(start.getUTCMonth() + count);
  return isoDay(start.getTime());
}

/** Six weeks starting on the Monday on or before the 1st, so every month fits the same grid. */
export function monthGrid(month: string): CalendarDay[] {
  const first = new Date(dayStart(monthOf(month)));
  // getUTCDay counts from Sunday (0); shift so Monday is 0.
  const daysBackToMonday = (first.getUTCDay() + DAYS_IN_WEEK - 1) % DAYS_IN_WEEK;
  const gridStart = first.getTime() - daysBackToMonday * MS_PER_DAY;
  return Array.from({ length: DAYS_IN_GRID }, (_unused, index) => {
    const day = new Date(gridStart + index * MS_PER_DAY);
    return {
      date: isoDay(day.getTime()),
      dayOfMonth: day.getUTCDate(),
      inMonth: day.getUTCMonth() === first.getUTCMonth(),
    };
  });
}

/** "October 2026". */
export function monthTitle(month: string): string {
  return new Intl.DateTimeFormat(MONTH_LOCALE, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(dayStart(month));
}

/** "30 Oct 2026". */
export function dayLabel(date: string): string {
  return new Intl.DateTimeFormat(MONTH_LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(dayStart(date));
}
