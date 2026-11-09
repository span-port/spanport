import { describe, expect, it } from "vitest";

import { bucketEnd, errorChart, errorLogsLink, failedRequestsLink, requestShare, statusMeaning } from "./errors";

const BUCKETS = [
  { at: "2026-11-03T04:00:00Z", requests: 100, client_errors: 2, server_errors: 2 },
  { at: "2026-11-03T04:30:00Z", requests: 50, client_errors: 0, server_errors: 0 },
  { at: "2026-11-03T04:45:00Z", requests: 80, client_errors: 1, server_errors: 7 },
];

describe("Errors helpers", () => {
  it("stacks the shown errors and leaves out intervals without any", () => {
    const chart = errorChart(BUCKETS, "2026-11-03T04:00:00Z", "2026-11-03T05:00:00Z", 60, "all");

    expect(chart.maxErrors).toBe(8);
    expect(chart.bars.map((bar) => bar.leftPercent)).toEqual([0, 75]);
    expect(chart.bars[1]?.serverPercent).toBe(87.5);
    expect(chart.bars[1]?.clientPercent).toBe(12.5);

    const serverOnly = errorChart(BUCKETS, "2026-11-03T04:00:00Z", "2026-11-03T05:00:00Z", 60, "5xx");
    expect(serverOnly.maxErrors).toBe(7);
    expect(serverOnly.bars.every((bar) => bar.clientPercent === 0)).toBe(true);
    expect(errorChart(BUCKETS, "2026-11-03T04:00:00Z", "2026-11-03T05:00:00Z", 60, "4xx").bars).toHaveLength(2);
  });

  it("names status codes and shares", () => {
    expect(statusMeaning(401)).toBe("Not signed in (wrong or missing credentials)");
    expect(statusMeaning(418)).toBe("Request error");
    expect(statusMeaning(599)).toBe("Server error");
    expect(requestShare(31, 12_410)).toBe("0.25%");
    expect(requestShare(0, 0)).toBe("0%");
    expect(bucketEnd("2026-11-03T04:00:00Z", 300)).toBe("2026-11-03T04:05:00.000Z");
  });

  it("links to the interval's error logs and to failed requests over a range that reaches it", () => {
    const logs = new URL(errorLogsLink("p1", "2026-11-03T04:00:00Z", "2026-11-03T04:01:00Z"), "http://x");
    expect([logs.pathname, logs.searchParams.get("query"), logs.searchParams.get("range")]).toEqual([
      "/logs",
      "level:ERROR",
      "absolute",
    ]);

    const now = Date.parse("2026-11-03T06:00:00Z");
    expect(failedRequestsLink("p1", "2026-11-03T04:00:00Z", now, { service: "api", route: "/u" })).toBe(
      "/requests?project=p1&errors=1&range=6h&service=api&route=%2Fu",
    );
    expect(failedRequestsLink("p1", "2026-10-01T00:00:00Z", now, { service: "", route: "" })).toBe(
      "/requests?project=p1&errors=1&range=30d",
    );
  });
});
