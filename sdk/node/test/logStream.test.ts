import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { trace } from "@opentelemetry/api";

import { createLogStream, parseLogLine } from "../src/logStream.js";
import { type LogEntry } from "../src/pipeline.js";

const TRACE_ID = "0af7651916cd43dd8448eb211c80319c";
const SPAN_ID = "b7ad6b7169203331";

describe("parseLogLine", () => {
  it("reads a pino line: msg, numeric level, time, trace ids, other fields as attributes", () => {
    const entry = parseLogLine(
      JSON.stringify({
        level: 50,
        time: 1793008800000,
        msg: "Payment failed",
        orderId: 1042,
        user: { id: "u-42" },
        trace_id: TRACE_ID,
        span_id: SPAN_ID,
      }),
    );

    assert.equal(entry.body, "Payment failed");
    assert.equal(entry.severity.text, "ERROR");
    assert.equal(entry.timestamp?.toISOString(), "2026-10-26T10:00:00.000Z");
    assert.deepEqual(entry.attributes, { orderId: 1042, user: '{"id":"u-42"}' });
    const spanContext = entry.context && trace.getSpanContext(entry.context);
    assert.equal(spanContext?.traceId, TRACE_ID);
    assert.equal(spanContext.spanId, SPAN_ID);
  });

  it("reads a winston JSON line: message, level name, ISO timestamp", () => {
    const entry = parseLogLine(
      JSON.stringify({ level: "warn", message: "Disk 91% full", timestamp: "2026-10-26T10:00:00Z" }),
    );

    assert.equal(entry.body, "Disk 91% full");
    assert.equal(entry.severity.text, "WARN");
    assert.equal(entry.timestamp?.toISOString(), "2026-10-26T10:00:00.000Z");
    assert.deepEqual(entry.attributes, {});
  });

  it("keeps a line that isn't JSON as an INFO message", () => {
    const entry = parseLogLine("plain text line");

    assert.equal(entry.body, "plain text line");
    assert.equal(entry.severity.text, "INFO");
  });

  it("ignores trace ids that aren't valid", () => {
    const entry = parseLogLine(JSON.stringify({ msg: "x", trace_id: "not-hex", span_id: "1" }));

    assert.equal(entry.context, undefined);
  });
});

describe("createLogStream", () => {
  it("joins lines split across writes and skips blank lines", async () => {
    const entries: LogEntry[] = [];
    const stream = createLogStream((entry) => entries.push(entry));

    stream.write('{"msg":"first"}\n{"msg":"sec');
    stream.write('ond"}\n\n');
    await new Promise<void>((resolve) => stream.end(resolve));

    assert.deepEqual(
      entries.map((entry) => entry.body),
      ["first", "second"],
    );
  });
});
