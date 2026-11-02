import assert from "node:assert/strict";
import http from "node:http";
import { type AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, it } from "node:test";

import { SpanKind, SpanStatusCode } from "@opentelemetry/api";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";
import { InMemorySpanExporter, type ReadableSpan } from "@opentelemetry/sdk-trace";

import { trace, withSpan } from "../src/spans.js";
import { type ActiveTracing, startTracing } from "../src/tracing.js";

const OWN_HOSTS = { collectorUrl: "http://127.0.0.1:4318", serverUrl: "http://127.0.0.1:8000" };
const NOTHING_INSTALLED = (): undefined => undefined;

describe("tracing", () => {
  let exporter: InMemorySpanExporter;
  let tracing: ActiveTracing;

  async function finished(): Promise<ReadableSpan[]> {
    await tracing.provider.forceFlush();
    return exporter.getFinishedSpans();
  }

  beforeEach(() => {
    exporter = new InMemorySpanExporter();
    tracing = startTracing("orders-api", exporter, OWN_HOSTS, NOTHING_INSTALLED);
  });

  afterEach(async () => {
    await tracing.stop();
  });

  it("nests withSpan steps under the current one, sync and async", async () => {
    await withSpan("handle request", async () => {
      withSpan("validate", () => 1);
      await withSpan("load user", () => Promise.resolve("user"));
    });

    const spans = await finished();
    const byName = new Map(spans.map((span) => [span.name, span]));
    const root = byName.get("handle request");
    assert.ok(root);
    for (const child of ["validate", "load user"]) {
      assert.equal(byName.get(child)?.parentSpanContext?.spanId, root.spanContext().spanId);
    }
    assert.equal(root.resource.attributes["service.name"], "orders-api");
  });

  it("marks a failed step and rethrows the same error", async () => {
    const boom = new Error("payment declined");

    await assert.rejects(withSpan("charge card", () => Promise.reject(boom)), boom);
    assert.throws(() => withSpan("parse", () => { throw new TypeError("bad"); }), TypeError);

    const spans = await finished();
    assert.ok(spans.every((span) => span.status.code === SpanStatusCode.ERROR));
    assert.equal(spans.find((span) => span.name === "charge card")?.status.message, "payment declined");
  });

  it("times every method of a decorated class as ClassName.method", async () => {
    class VariablesService {
      constructor(private readonly prefix: string) {}

      list(): string[] {
        return [`${this.prefix}-a`];
      }

      async find(id: string): Promise<string> {
        return Promise.resolve(`${this.prefix}-${id}`);
      }
    }
    trace()(VariablesService);
    const service = new VariablesService("var");

    assert.deepEqual(service.list(), ["var-a"]);
    assert.equal(await service.find("7"), "var-7");
    assert.equal(service.find.name, "find");

    const names = (await finished()).map((span) => span.name).sort();
    assert.deepEqual(names, ["VariablesService.find", "VariablesService.list"]);
  });

  it("keeps framework metadata on decorated methods (NestJS routes)", () => {
    const store = new Map<unknown, Map<unknown, unknown>>();
    const reflect = Reflect as unknown as Record<string, unknown>;
    reflect.defineMetadata = (key: unknown, value: unknown, target: object) => {
      store.set(target, (store.get(target) ?? new Map()).set(key, value));
    };
    reflect.getMetadata = (key: unknown, target: object) => store.get(target)?.get(key);
    reflect.getMetadataKeys = (target: object) => [...(store.get(target)?.keys() ?? [])];
    try {
      class UsersController {
        find(): string {
          return "user";
        }
      }
      // The method as a value (frameworks attach metadata to the function itself).
      const methodOf = (owner: object): object =>
        Object.getOwnPropertyDescriptor(owner, "find")?.value as object;
      (reflect.defineMetadata as (k: string, v: string, t: object) => void)(
        "path",
        "/users",
        methodOf(UsersController.prototype),
      );

      trace()(UsersController);

      assert.equal(store.get(methodOf(UsersController.prototype))?.get("path"), "/users");
    } finally {
      delete reflect.defineMetadata;
      delete reflect.getMetadata;
      delete reflect.getMetadataKeys;
    }
  });

  it("times incoming requests and outgoing calls, but never the SDK's own", async () => {
    const server = http.createServer((_request, response) => response.end("ok"));
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = (server.address() as AddressInfo).port;
    const get = (path: string) =>
      new Promise<void>((resolve) => {
        http.get({ host: "127.0.0.1", port, path }, (response) => response.resume().on("end", resolve));
      });

    await get("/orders/42");
    const appKinds = (await finished()).map((span) => span.kind);
    await tracing.stop();
    // The same server now playing Spanport's collector: calls to it are the SDK's own.
    exporter = new InMemorySpanExporter();
    tracing = startTracing(
      "orders-api",
      exporter,
      { ...OWN_HOSTS, collectorUrl: `http://127.0.0.1:${String(port)}` },
      NOTHING_INSTALLED,
    );
    await get("/v1/traces");
    server.close();
    const ownKinds = (await finished()).map((span) => span.kind);

    assert.ok(appKinds.includes(SpanKind.SERVER));
    assert.ok(appKinds.includes(SpanKind.CLIENT));
    assert.ok(!ownKinds.includes(SpanKind.CLIENT));
  });

  it("sends traceparent on outgoing calls, so another service joins the same trace", async () => {
    let received: string | undefined;
    const server = http.createServer((request, response) => {
      received = request.headers.traceparent as string | undefined;
      response.end("ok");
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = (server.address() as AddressInfo).port;

    await withSpan("checkout", () =>
      new Promise<void>((resolve) => {
        http.get({ host: "127.0.0.1", port, path: "/billing" }, (response) => response.resume().on("end", resolve));
      }),
    );
    server.close();

    const checkout = (await finished()).find((span) => span.name === "checkout");
    assert.ok(checkout);
    assert.match(received ?? "", new RegExp(`^00-${checkout.spanContext().traceId}-[0-9a-f]{16}-01$`));
  });

  it("switches on optional instrumentations the app has installed, and only those", async () => {
    await tracing.stop();

    tracing = startTracing("orders-api", exporter, OWN_HOSTS, (name) =>
      name === "@opentelemetry/instrumentation-express" ? { ExpressInstrumentation: HttpInstrumentation } : undefined,
    );

    assert.deepEqual(tracing.optional, ["@opentelemetry/instrumentation-express"]);
  });
});
