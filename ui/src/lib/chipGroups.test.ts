import { describe, expect, it } from "vitest";

import { groupChips, groupVerb } from "./chipGroups";

describe("chip groups", () => {
  it("groups values by property and operator, keeps positions and leaves levels to the cards", () => {
    const groups = groupChips([
      { field: "service", operator: "=", value: "api" },
      { field: "level", operator: "=", value: "ERROR" },
      { field: "service", operator: "=", value: "worker" },
      { field: "service", operator: "!=", value: "cron" },
    ]);

    expect(groups).toEqual([
      {
        field: "service",
        operator: "=",
        values: [
          { value: "api", index: 0 },
          { value: "worker", index: 2 },
        ],
      },
      { field: "service", operator: "!=", values: [{ value: "cron", index: 3 }] },
    ]);
  });

  it("reads naturally", () => {
    expect(groupVerb("=", 1)).toBe("is");
    expect(groupVerb("=", 2)).toBe("is one of");
    expect(groupVerb("!:", 2)).toBe("doesn't contain");
  });
});
