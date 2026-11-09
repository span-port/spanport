import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";

import { isLocalUrl, keyCheckUrl, warnPlainHttp } from "../src/endpoints.js";
import { captureStderr } from "./helpers.js";

describe("endpoints", () => {
  let stderr: () => string;

  beforeEach(() => {
    stderr = captureStderr();
  });

  afterEach(() => {
    mock.restoreAll();
  });

  it("knows this machine's addresses", () => {
    for (const url of ["http://localhost:4318", "http://127.0.0.1:4318", "http://[::1]:4318", "http://LOCALHOST"]) {
      assert.equal(isLocalUrl(url), true, url);
    }
    assert.equal(isLocalUrl("https://collector.acme.com"), false);
    assert.equal(isLocalUrl("not a url"), false);
  });

  it("always uses a given serverUrl", () => {
    assert.equal(keyCheckUrl("https://collector.acme.com", "https://spanport.acme.com"), "https://spanport.acme.com");
  });

  it("uses the default server only with a local collector", () => {
    assert.equal(keyCheckUrl("http://localhost:4318", undefined), "http://localhost:8000");
    assert.equal(stderr(), "");
  });

  it("skips the key check for a remote collector without serverUrl, and says why", () => {
    assert.equal(keyCheckUrl("https://collector.acme.com", undefined), undefined);
    assert.match(stderr(), /set serverUrl/);
  });

  it("warns once about plain http to another machine", () => {
    warnPlainHttp(["http://collector.acme.com:4318", "http://spanport.acme.com"]);

    assert.equal(stderr().split("\n").filter(Boolean).length, 1);
    assert.match(stderr(), /plain http to http:\/\/collector\.acme\.com:4318, http:\/\/spanport\.acme\.com/);
  });

  it("does not warn about https or local http", () => {
    warnPlainHttp(["https://collector.acme.com", "http://localhost:4318"]);

    assert.equal(stderr(), "");
  });
});
