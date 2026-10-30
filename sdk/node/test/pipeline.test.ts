import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";

import { context, trace } from "@opentelemetry/api";
import { AsyncLocalStorageContextManager } from "@opentelemetry/context-async-hooks";
import { InMemoryLogRecordExporter } from "@opentelemetry/sdk-logs";
import { TracerProvider } from "@opentelemetry/sdk-trace";

import { buildLoggerProvider, toLogRecord } from "../src/pipeline.js";
import { consoleSeverity } from "../src/severity.js";

describe("pipeline", () => {
  const contextManager = new AsyncLocalStorageContextManager();

  before(() => {
    context.setGlobalContextManager(contextManager.enable());
  });

  after(() => {
    context.disable();
  });

  it("exports the entry with service, level, source and attributes", async () => {
    const exporter = new InMemoryLogRecordExporter();
    const provider = buildLoggerProvider("orders-api", exporter);

    provider.getLogger("test").emit(
      toLogRecord(
        { body: "Payment failed", severity: consoleSeverity("error"), attributes: { orderId: 7 } },
        "console",
      ),
    );
    await provider.forceFlush();

    const [record] = exporter.getFinishedLogRecords();
    assert.equal(record?.body, "Payment failed");
    assert.equal(record.severityText, "ERROR");
    assert.deepEqual(record.attributes, { orderId: 7, "log.source": "console" });
    assert.equal(record.resource.attributes["service.name"], "orders-api");
    await provider.shutdown();
  });

  it("attaches the active span's trace and span ids", async () => {
    const exporter = new InMemoryLogRecordExporter();
    const provider = buildLoggerProvider("orders-api", exporter);
    const tracer = new TracerProvider().getTracer("test");

    const spanContext = tracer.startActiveSpan("POST /payments", (span) => {
      provider
        .getLogger("test")
        .emit(
          toLogRecord(
            { body: "card declined", severity: consoleSeverity("error"), attributes: {} },
            "console",
          ),
        );
      span.end();
      return span.spanContext();
    });
    await provider.forceFlush();

    const [record] = exporter.getFinishedLogRecords();
    assert.equal(record?.spanContext?.traceId, spanContext.traceId);
    assert.equal(record.spanContext.spanId, spanContext.spanId);
    assert.ok(trace.isSpanContextValid(spanContext));
    await provider.shutdown();
  });
});
