import assert from "node:assert/strict";
import { afterEach, describe, it, mock } from "node:test";

import { captureConsole } from "../src/consoleCapture.js";

describe("captureConsole", () => {
  afterEach(() => {
    mock.restoreAll();
  });

  it("passes the formatted call on and still prints it as before", () => {
    const printed = mock.method(console, "error", () => undefined);
    const passedOn: string[] = [];
    const restore = captureConsole((method, message) => passedOn.push(`${method}: ${message}`));

    console.error("order %d failed", 1042);
    restore();

    assert.deepEqual(passedOn, ["error: order 1042 failed"]);
    assert.equal(printed.mock.callCount(), 1);
    assert.deepEqual(printed.mock.calls[0]?.arguments, ["order %d failed", 1042]);
  });

  it("puts the original methods back", () => {
    const originalLog = console.log;
    const restore = captureConsole(() => undefined);
    assert.notEqual(console.log, originalLog);

    restore();

    assert.equal(console.log, originalLog);
  });

  it("keeps the console working if passing on fails", () => {
    mock.method(console, "warn", () => undefined);
    const restore = captureConsole(() => {
      throw new Error("exporter broke");
    });

    try {
      assert.doesNotThrow(() => {
        console.warn("still works");
      });
    } finally {
      restore();
    }
  });

  it("doesn't loop when the receiver itself logs to the console", () => {
    mock.method(console, "info", () => undefined);
    let calls = 0;
    const restore = captureConsole(() => {
      calls += 1;
      console.info("logged while passing on");
    });

    console.info("hello");
    restore();

    assert.equal(calls, 1);
  });
});
