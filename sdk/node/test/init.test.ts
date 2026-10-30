import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";

import * as spanport from "../src/index.js";
import {
  type FakeServer,
  VALID_KEY,
  captureStderr,
  startFakeSpanport,
  waitFor,
} from "./helpers.js";

describe("init and shutdown", () => {
  let server: FakeServer;
  let stderr: () => string;

  beforeEach(async () => {
    server = await startFakeSpanport();
    stderr = captureStderr();
  });

  afterEach(async () => {
    await spanport.shutdown();
    mock.restoreAll();
    await server.stop();
  });

  it("sends console and stream logs to the collector with the data key", async () => {
    mock.method(console, "error", () => undefined);
    spanport.init({
      dataKey: VALID_KEY,
      service: "orders-api",
      collectorUrl: server.url,
      serverUrl: server.url,
    });
    await waitFor(() => stderr().includes("accepted"));

    console.error("Payment failed for order 1042");
    spanport.logStream().write('{"level":40,"msg":"from pino"}\n');
    await spanport.shutdown();

    const posts = server.requests.filter((request) => request.method === "POST");
    assert.ok(posts.length > 0);
    assert.ok(posts.every((post) => post.path === "/v1/logs"));
    assert.ok(posts.every((post) => post.authorization === `Bearer ${VALID_KEY}`));
    const sent = posts.map((post) => post.body).join("");
    assert.ok(sent.includes("Payment failed for order 1042"));
    assert.ok(sent.includes("from pino"));
    assert.ok(sent.includes("orders-api"));
  });

  it("leaves console untouched when captureConsole is false", () => {
    const originalLog = console.log;

    spanport.init({
      dataKey: VALID_KEY,
      service: "orders-api",
      collectorUrl: server.url,
      checkKey: false,
      captureConsole: false,
    });

    assert.equal(console.log, originalLog);
  });

  it("restores console on shutdown", async () => {
    const originalWarn = console.warn;
    spanport.init({ dataKey: VALID_KEY, service: "svc", collectorUrl: server.url, checkKey: false });
    assert.notEqual(console.warn, originalWarn);

    await spanport.shutdown();
    await spanport.shutdown();

    assert.equal(console.warn, originalWarn);
  });

  for (const [label, options, expected] of [
    ["empty key", { dataKey: "", service: "svc" }, /dataKey must be a data key/],
    ["admin key", { dataKey: "sp_admin_x", service: "svc" }, /dataKey must be a data key/],
    ["no service", { dataKey: VALID_KEY, service: "" }, /service must name this app/],
    [
      "bad collector URL",
      { dataKey: VALID_KEY, service: "svc", collectorUrl: "ftp://x" },
      /collectorUrl must start with http/,
    ],
  ] as const) {
    it(`reports ${label} and attaches nothing`, () => {
      const originalLog = console.log;

      spanport.init({ ...options, checkKey: false });

      assert.match(stderr(), expected);
      assert.equal(console.log, originalLog);
    });
  }

  it("ignores a second init", () => {
    spanport.init({ dataKey: VALID_KEY, service: "svc", collectorUrl: server.url, checkKey: false });

    spanport.init({ dataKey: VALID_KEY, service: "svc", collectorUrl: server.url, checkKey: false });

    assert.match(stderr(), /init\(\) was already called/);
  });

  it("drops stream lines written before init", async () => {
    spanport.logStream().write('{"msg":"too early"}\n');
    spanport.init({ dataKey: VALID_KEY, service: "svc", collectorUrl: server.url, checkKey: false });
    await spanport.shutdown();

    assert.ok(!server.requests.some((request) => request.body.includes("too early")));
  });
});
