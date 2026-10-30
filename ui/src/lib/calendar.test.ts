import { describe, expect, it } from "vitest";

import { addMonths, dayLabel, monthGrid, monthOf, monthTitle } from "./calendar";

describe("calendar", () => {
  it("lays a month out in six Monday-first weeks", () => {
    const grid = monthGrid("2026-10-30");

    expect(grid).toHaveLength(42);
    // 1 October 2026 is a Thursday, so the grid starts on Monday 28 September.
    expect(grid[0]).toEqual({ date: "2026-09-28", dayOfMonth: 28, inMonth: false });
    expect(grid[3]).toEqual({ date: "2026-10-01", dayOfMonth: 1, inMonth: true });
    expect(grid.filter((day) => day.inMonth)).toHaveLength(31);
  });

  it("moves between months across a year end", () => {
    expect(monthOf("2026-10-30")).toBe("2026-10-01");
    expect(addMonths("2026-12-15", 1)).toBe("2027-01-01");
    expect(addMonths("2026-01-31", -1)).toBe("2025-12-01");
  });

  it("names months and days in words", () => {
    expect(monthTitle("2026-10-01")).toBe("October 2026");
    expect(dayLabel("2026-10-30")).toBe("30 Oct 2026");
  });
});
