import { describe, expect, it } from "vitest";

import type { SpanItem } from "../features/traces/api";
import {
  axisTicks,
  barPosition,
  formatDuration,
  labelName,
  spanFailed,
  stepKindName,
  stepTimes,
  traceLink,
  traceLogsLink,
  visibleRows,
  waterfallRows,
} from "./waterfall";

function span(spanId: string, parent: string, offsetMs: number, durationMs = 10): SpanItem {
  return {
    span_id: spanId,
    parent_span_id: parent,
    service: "api",
    name: spanId,
    kind: "INTERNAL",
    label: "code",
    start_ts: "2026-10-30T12:00:00Z",
    offset_ms: offsetMs,
    duration_ms: durationMs,
    self_ms: durationMs,
    status_code: "UNSET",
    status_message: "",
    http_method: "",
    http_route: "",
    http_status: 0,
    attributes: {},
  };
}

describe("waterfall helpers", () => {
  it("orders spans parent first, children by start, with depth; orphans start a root", () => {
    const rows = waterfallRows([
      span("db", "service", 10),
      span("root", "", 0),
      span("aws", "service", 60),
      span("service", "root", 5),
      span("orphan", "not-here", 70),
    ]);

    expect(rows.map((row) => `${row.span.span_id}:${String(row.depth)}`)).toEqual([
      "root:0",
      "service:1",
      "db:2",
      "aws:2",
      "orphan:0",
    ]);
  });

  it("hides the steps below a collapsed one, and knows which steps have children", () => {
    const rows = waterfallRows([span("root", "", 0), span("service", "root", 5), span("db", "service", 10)]);

    expect(rows.map((row) => row.hasChildren)).toEqual([true, true, false]);
    expect(visibleRows(rows, new Set(["service"])).map((row) => row.span.span_id)).toEqual(["root", "service"]);
    expect(visibleRows(rows, new Set(["root"])).map((row) => row.span.span_id)).toEqual(["root"]);
  });

  it("adds up own time by kind of step, the request's own time counting as your code", () => {
    const times = stepTimes([
      { ...span("root", "", 0, 100), label: "incoming_request", self_ms: 10 },
      { ...span("db", "root", 0, 30), label: "db" },
      { ...span("aws", "root", 0, 40), label: "external" },
      { ...span("billing", "root", 0, 20), label: "service_call" },
    ]);

    expect(times).toEqual({ code: 10, db: 30, external: 60, llm: 0 });
    expect(stepKindName("external")).toBe("External calls");
  });

  it("marks the time axis in round steps", () => {
    expect(axisTicks(885).map((tick) => tick.label)).toEqual(["0", "200 ms", "400 ms", "600 ms", "800 ms"]);
    expect(axisTicks(4200).map((tick) => tick.label)).toEqual(["0", "1.0 s", "2.0 s", "3.0 s", "4.0 s"]);
    expect(axisTicks(4200)[1]?.percent).toBeCloseTo(23.8, 1);
    expect(axisTicks(0)).toEqual([{ label: "0", percent: 0 }]);
  });

  it("places bars as percentages, never invisible or past the end", () => {
    expect(barPosition(span("a", "", 50, 25), 100)).toEqual({ left: 50, width: 25 });
    expect(barPosition(span("tiny", "", 0, 0), 100).width).toBeGreaterThan(0);
    const late = barPosition(span("late", "", 90, 50), 100);
    expect(late.left + late.width).toBeLessThanOrEqual(100);
  });

  it("names labels and durations for people", () => {
    expect(labelName("service_call")).toBe("Service call");
    expect(labelName("anything else")).toBe("Code");
    expect(formatDuration(4200)).toBe("4.2 s");
    expect(formatDuration(885)).toBe("885 ms");
    expect(formatDuration(0.25)).toBe("0.3 ms");
  });

  it("links a request to its waterfall in this project, and knows failed steps", () => {
    expect(traceLink("abc", "p1")).toBe("/requests/abc?project=p1");
    expect(spanFailed({ status_code: "ERROR", http_status: 200 })).toBe(true);
    expect(spanFailed({ status_code: "UNSET", http_status: 503 })).toBe(true);
    expect(spanFailed({ status_code: "OK", http_status: 404 })).toBe(false);
  });

  it("links to the trace's logs a minute either side", () => {
    const link = new URL(traceLogsLink("p1", "abc", "2026-10-30T12:00:00.000Z", 885), "http://x");

    expect(link.pathname).toBe("/logs");
    expect(link.searchParams.get("query")).toBe("trace:abc");
    expect(link.searchParams.get("start")).toBe("2026-10-30T11:59:00.000Z");
    expect(link.searchParams.get("end")).toBe("2026-10-30T12:01:00.885Z");
  });
});
