import { describe, expect, it } from "vitest";

import { readLogUrlState, writeLogUrlState, type LogUrlState } from "./logUrlState";

describe("explorer state in the URL", () => {
  it("round-trips every field", () => {
    const state: LogUrlState = {
      projectId: "01a185ea-4f62-7513-8ab7-e1ac3a0b9476",
      range: { kind: "preset", key: "3h" },
      filters: [{ field: "level", operator: "=", value: "ERROR" }],
      combine: "or",
      query: 'timeout -"health check"',
      queryMode: true,
    };

    expect(readLogUrlState(writeLogUrlState(state))).toEqual(state);
  });

  it("uses defaults for an empty URL and leaves defaults out of links", () => {
    const state = readLogUrlState(new URLSearchParams());

    expect(state).toEqual({
      projectId: null,
      range: { kind: "preset", key: "15m" },
      filters: [],
      combine: "and",
      query: "",
      queryMode: false,
    });
    expect(writeLogUrlState(state).toString()).toBe("range=15m");
  });

  it("ignores hand-edited filters that are not valid chips", () => {
    const broken = new URLSearchParams({ filters: "[{not json" });
    const wrongOperator = new URLSearchParams({
      filters: JSON.stringify([{ field: "level", operator: "~", value: "x" }]),
    });

    expect(readLogUrlState(broken).filters).toEqual([]);
    expect(readLogUrlState(wrongOperator).filters).toEqual([]);
  });
});
