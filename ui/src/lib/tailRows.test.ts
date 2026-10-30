import { describe, expect, it } from "vitest";

import type { LogItem } from "../features/logs/types";
import { mergeTailRows } from "./tailRows";

function log(id: string): LogItem {
  return {
    log_id: id,
    ts: "2026-10-29T07:00:00Z",
    service: "api",
    level: "INFO",
    message: id,
    trace_id: "",
    span_id: "",
    attributes: {},
  };
}

describe("merging tailed rows", () => {
  it("puts new rows on top, newest first", () => {
    const merged = mergeTailRows([log("b"), log("a")], [log("c"), log("d")], 10);

    expect(merged.map((row) => row.log_id)).toEqual(["d", "c", "b", "a"]);
  });

  it("skips rows already shown, as after a reconnect", () => {
    const merged = mergeTailRows([log("b"), log("a")], [log("a"), log("b"), log("c")], 10);

    expect(merged.map((row) => row.log_id)).toEqual(["c", "b", "a"]);
  });

  it("keeps only the newest rows", () => {
    const merged = mergeTailRows([log("b"), log("a")], [log("c")], 2);

    expect(merged.map((row) => row.log_id)).toEqual(["c", "b"]);
  });
});
