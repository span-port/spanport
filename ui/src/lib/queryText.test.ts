import { describe, expect, it } from "vitest";

import { chipsToQueryText } from "./queryText";

describe("chips as query text", () => {
  it("writes each operator the way the query language reads it", () => {
    const text = chipsToQueryText([
      { field: "level", operator: "=", value: "ERROR" },
      { field: "service", operator: "!=", value: "worker" },
      { field: "ip", operator: ":", value: "45.142." },
      { field: "message", operator: ":", value: "payment failed" },
      { field: "message", operator: "!:", value: "healthcheck" },
    ]);

    expect(text).toBe('level:ERROR AND -service:worker AND ip:*45.142.* AND "payment failed" AND -"healthcheck"');
  });

  it("makes values of one field alternatives and keeps every exclusion", () => {
    expect(
      chipsToQueryText([
        { field: "level", operator: "=", value: "WARN" },
        { field: "service", operator: "=", value: "api" },
        { field: "level", operator: "=", value: "ERROR" },
        { field: "user", operator: "!=", value: 'a "b" c' },
        { field: "user", operator: "!=", value: "bot" },
      ]),
    ).toBe('(level:WARN OR level:ERROR) AND service:api AND -user:"a b c" AND -user:bot');
  });
});
