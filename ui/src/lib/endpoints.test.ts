import { describe, expect, it } from "vitest";

import { dominantStep, endpointRequestsLink, errorRate, stepShares } from "./endpoints";

describe("APIs helpers", () => {
  it("writes error rates people can read", () => {
    expect(errorRate(0, 0)).toBe("0%");
    expect(errorRate(4, 1000)).toBe("0.4%");
    expect(errorRate(19, 1000)).toBe("1.9%");
    expect(errorRate(250, 1000)).toBe("25%");
  });

  it("splits time into shares, skipping kinds with none, and names a large one", () => {
    const times = { code: 10, db: 82, external: 8, llm: 0 };

    expect(stepShares(times).map((share) => share.kind)).toEqual(["code", "db", "external"]);
    expect(dominantStep(times)).toBe("Database 82%");
    expect(dominantStep({ code: 30, db: 35, external: 35, llm: 0 })).toBe("");
    expect(stepShares({ code: 0, db: 0, external: 0, llm: 0 })).toEqual([]);
  });

  it("links to the API's requests in the same range", () => {
    expect(endpointRequestsLink("p1", "7d", "api", "/users/:id")).toBe(
      "/requests?project=p1&range=7d&service=api&route=%2Fusers%2F%3Aid",
    );
  });
});
