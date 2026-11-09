import { describe, expect, it } from "vitest";

import type { EndpointStats } from "../features/endpoints/api";
import {
  dominantStep,
  endpointDetailLink,
  endpointRequestsLink,
  errorRate,
  looksLikeNPlusOne,
  p95Change,
  p95RiseNote,
  percentileExample,
  slowerCount,
  slowestEndpoint,
  statusGroup,
  stepShares,
  timelineChart,
  worstPoint,
} from "./endpoints";

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

  it("places the chart's bars in time and names status groups", () => {
    const chart = timelineChart(
      [
        { at: "2026-11-03T04:00:00Z", requests: 10, errors: 5, p95_ms: 100 },
        { at: "2026-11-03T04:30:00Z", requests: 20, errors: 0, p95_ms: 400 },
      ],
      "2026-11-03T04:00:00Z",
      "2026-11-03T05:00:00Z",
      60,
    );

    expect(chart.bars.map((bar) => bar.x)).toEqual([0, 500]);
    expect(chart.bars[0]?.requestsHeight).toBe(90);
    expect(chart.bars[0]?.errorsHeight).toBe(45);
    expect([chart.maxRequests, chart.maxP95Ms]).toEqual([20, 400]);
    expect(chart.p95Segments).toHaveLength(2);
    expect(statusGroup(304)).toBe("3xx");
    expect(statusGroup(0)).toBe("No status");
  });

  it("breaks the p95 line where intervals have no requests", () => {
    const point = (at: string, p95: number) => ({ at, requests: 1, errors: 0, p95_ms: p95 });
    const chart = timelineChart(
      [
        point("2026-11-03T04:00:00Z", 100),
        point("2026-11-03T04:01:00Z", 200),
        point("2026-11-03T04:30:00Z", 400),
      ],
      "2026-11-03T04:00:00Z",
      "2026-11-03T05:00:00Z",
      60,
    );

    expect(chart.p95Segments).toHaveLength(2);
    expect(chart.p95Segments[0]?.split(" ")).toHaveLength(2);
    // A lone interval is a flat tick across its bar, not a joined-up line.
    const [left, right] = (chart.p95Segments[1] ?? "").split(" ");
    expect(left?.split(",")[1]).toBe(right?.split(",")[1]);
    expect(left?.split(",")[0]).toBe("500.0");
  });

  it("counts the requests slower than each percentile and explains them with real numbers", () => {
    const endpoint = {
      service: "api",
      http_method: "GET",
      route: "/users/:id",
      requests: 1240,
      errors: 0,
      p50_ms: 180,
      p95_ms: 1900,
      p99_ms: 3400,
      avg_ms: 300,
      layers: { code_ms: 300, db_ms: 0, external_ms: 0, llm_ms: 0 },
      previous_p95_ms: 600,
    };

    expect([slowerCount(1240, 0.5), slowerCount(1240, 0.05), slowerCount(1240, 0.01)]).toEqual([620, 62, 12]);
    expect(percentileExample(endpoint)).toBe(
      "Of 1,240 requests to GET /users/:id: 620 took longer than 180 ms (p50), 62 longer than 1.9 s (p95) and 12 longer than 3.4 s (p99).",
    );
    expect(p95RiseNote(endpoint)).toBe("p95 up 3.2× vs the period before");
    expect(p95RiseNote({ p95_ms: 1900, previous_p95_ms: 1500 })).toBe("");
    expect(p95RiseNote({ p95_ms: 1900, previous_p95_ms: null })).toBe("");
  });

  it("says how the slow-5% time moved, and spots likely N+1 queries", () => {
    expect(p95Change(1900, 1100)).toEqual({ text: "↑ 800 ms vs the period before", worse: true });
    expect(p95Change(900, 1100)).toEqual({ text: "↓ 200 ms vs the period before", worse: false });
    expect(p95Change(900, null)).toBeNull();
    expect([looksLikeNPlusOne(48), looksLikeNPlusOne(1)]).toEqual([true, false]);
  });

  it("finds the slowest API and its worst moment", () => {
    const fast = { p95_ms: 50 } as EndpointStats;
    const slow = { p95_ms: 900 } as EndpointStats;
    expect(slowestEndpoint([fast, slow])).toBe(slow);
    expect(slowestEndpoint([])).toBeNull();
    expect(
      worstPoint([
        { at: "a", requests: 1, errors: 0, p95_ms: 10 },
        { at: "b", requests: 1, errors: 0, p95_ms: 90 },
      ])?.at,
    ).toBe("b");
  });

  it("links to the API's requests in the same quick range, and to its detail page in any range", () => {
    expect(endpointRequestsLink("p1", { kind: "preset", key: "7d" }, "api", "/users/:id")).toBe(
      "/requests?project=p1&range=7d&service=api&route=%2Fusers%2F%3Aid",
    );
    expect(endpointRequestsLink("p1", { kind: "relative", amount: 2, unit: "hours" }, "api", "/u")).toBe(
      "/requests?project=p1&service=api&route=%2Fu",
    );
    const detail = new URL(
      endpointDetailLink("p1", { kind: "relative", amount: 2, unit: "hours" }, { service: "api", http_method: "GET", route: "/u" }),
      "http://x",
    );
    expect([detail.searchParams.get("range"), detail.searchParams.get("amount"), detail.searchParams.get("method")]).toEqual([
      "relative",
      "2",
      "GET",
    ]);
  });
});
