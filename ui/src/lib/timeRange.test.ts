import { describe, expect, it } from "vitest";

import { isLiveRange, rangeName, rangeProblem, rangeWindow, readRange, writeRange, type RangeSelection } from "./timeRange";

const NOW = Date.parse("2026-10-29T07:00:00Z");

function roundTrip(range: RangeSelection): RangeSelection {
  const params = new URLSearchParams();
  writeRange(range, params);
  return readRange(params);
}

describe("time ranges", () => {
  it("ends presets and relative ranges at now, in UTC", () => {
    expect(rangeWindow({ kind: "preset", key: "1h" }, NOW)).toEqual({
      start: "2026-10-29T06:00:00.000Z",
      end: "2026-10-29T07:00:00.000Z",
    });
    expect(rangeWindow({ kind: "relative", amount: 3, unit: "days" }, NOW).start).toBe(
      "2026-10-26T07:00:00.000Z",
    );
  });

  it("keeps fixed ranges as they are and treats only them as historical", () => {
    const fixed: RangeSelection = { kind: "absolute", startMs: NOW - 7_200_000, endMs: NOW - 3_600_000 };

    expect(rangeWindow(fixed, Date.now()).end).toBe("2026-10-29T06:00:00.000Z");
    expect(isLiveRange(fixed)).toBe(false);
    expect(isLiveRange({ kind: "preset", key: "5m" })).toBe(true);
  });

  it("names ranges in words, fixed ones in the chosen zone", () => {
    expect(rangeName({ kind: "preset", key: "1w" }, "UTC")).toBe("Last 1 week");
    expect(rangeName({ kind: "relative", amount: 1, unit: "hours" }, "UTC")).toBe("Last 1 hour");
    expect(rangeName({ kind: "relative", amount: 90, unit: "minutes" }, "UTC")).toBe("Last 90 minutes");
    expect(
      rangeName({ kind: "absolute", startMs: NOW - 3_600_000, endMs: NOW }, "Asia/Kolkata"),
    ).toBe("29 Oct 11:30 → 29 Oct 12:30");
  });

  it("refuses ranges past the 7-day retention or in the wrong order", () => {
    expect(rangeProblem({ kind: "relative", amount: 8, unit: "days" }, NOW)).toContain("7 days");
    expect(rangeProblem({ kind: "relative", amount: 0, unit: "hours" }, NOW)).toContain("whole number");
    expect(rangeProblem({ kind: "absolute", startMs: NOW, endMs: NOW - 1 }, NOW)).toContain("after the start");
    expect(
      rangeProblem({ kind: "absolute", startMs: NOW - 8 * 86_400_000, endMs: NOW }, NOW),
    ).toContain("last 7 days");
    expect(rangeProblem({ kind: "relative", amount: 7, unit: "days" }, NOW)).toBeNull();
  });

  it("round-trips through the URL and falls back to the last 15 minutes", () => {
    const recent: RangeSelection = { kind: "absolute", startMs: Date.now() - 3_600_000, endMs: Date.now() };

    expect(roundTrip({ kind: "preset", key: "12h" })).toEqual({ kind: "preset", key: "12h" });
    expect(roundTrip({ kind: "relative", amount: 2, unit: "weeks" })).toEqual({ kind: "preset", key: "15m" });
    expect(roundTrip({ kind: "relative", amount: 6, unit: "hours" })).toEqual({
      kind: "relative",
      amount: 6,
      unit: "hours",
    });
    expect(roundTrip(recent)).toEqual(recent);
    expect(readRange(new URLSearchParams("range=30d"))).toEqual({ kind: "preset", key: "15m" });
  });
});
