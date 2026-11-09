// The time range of the APIs screens, kept in the URL like the Logs range (a preset, "last N"
// or fixed start and end), with traces' rules: kept 30 days.
import { useState } from "react";
import { useSearchParams } from "react-router";

import { URL_PARAM_AMOUNT, URL_PARAM_END, URL_PARAM_START, URL_PARAM_UNIT } from "../../../constants/logs";
import { TRACE_RANGE_RULES } from "../../../constants/traces";
import { rangeName, rangeWindow, readRange, writeRange, type RangeSelection } from "../../../lib/timeRange";
import { useSessionStore } from "../../../state/sessionStore";

/**
 * The chosen range, its start and end, and the timezone times are shown in. "Now" is taken when
 * the range changes or on refresh, so reading a page never shifts the window.
 *
 * @returns `range`, `name` (e.g. "Last 1 hour"), `start` / `end` as ISO strings, `timeZone`,
 *   `selectRange`, `setTimeZone` and `refresh`.
 */
export function useRequestRange() {
  const [params, setParams] = useSearchParams();
  const timeZone = useSessionStore((session) => session.timeZone);
  const setTimeZone = useSessionStore((session) => session.setTimeZone);
  const range = readRange(params, TRACE_RANGE_RULES);
  const [endsAtMs, setEndsAtMs] = useState(Date.now);
  const window = rangeWindow(range, endsAtMs, TRACE_RANGE_RULES);
  return {
    range,
    name: rangeName(range, timeZone, TRACE_RANGE_RULES),
    start: window.start,
    end: window.end,
    timeZone,
    setTimeZone,
    selectRange: (next: RangeSelection) => {
      setParams((current) => {
        const updated = new URLSearchParams(current);
        for (const name of [URL_PARAM_AMOUNT, URL_PARAM_UNIT, URL_PARAM_START, URL_PARAM_END]) updated.delete(name);
        writeRange(next, updated);
        return updated;
      });
      setEndsAtMs(Date.now());
    },
    refresh: () => {
      setEndsAtMs(Date.now());
    },
  };
}
