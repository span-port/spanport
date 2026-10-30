import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";

import { checkDataKey } from "../src/keyCheck.js";
import {
  type FakeServer,
  VALID_KEY,
  WRONG_KEY,
  captureStderr,
  startFakeSpanport,
  startRedirectServer,
} from "./helpers.js";

describe("checkDataKey", () => {
  let spanport: FakeServer;
  let stderr: () => string;

  beforeEach(async () => {
    spanport = await startFakeSpanport();
    stderr = captureStderr();
  });

  afterEach(async () => {
    mock.restoreAll();
    await spanport.stop();
  });

  it("accepts a valid key and sends it as a bearer token", async () => {
    assert.equal(await checkDataKey(spanport.url, VALID_KEY), true);

    const [request] = spanport.requests;
    assert.equal(request?.path, "/api/v1/api-keys/current");
    assert.equal(request.authorization, `Bearer ${VALID_KEY}`);
    assert.match(stderr(), /INFO spanport: data key \.\.\.a1b2 accepted/);
  });

  it("reports a rejected key loudly without printing it", async () => {
    assert.equal(await checkDataKey(spanport.url, WRONG_KEY), false);

    assert.match(stderr(), /ERROR spanport: data key \.\.\.wxyz was rejected/);
    assert.ok(!stderr().includes(WRONG_KEY));
  });

  it("warns, without throwing, when the server can't be reached", async () => {
    assert.equal(await checkDataKey("http://127.0.0.1:9", VALID_KEY), false);

    assert.match(stderr(), /WARNING spanport: could not reach/);
  });

  it("refuses redirects so the key never reaches another host", async () => {
    const redirect = await startRedirectServer(spanport.url);
    try {
      assert.equal(await checkDataKey(redirect.url, VALID_KEY), false);
    } finally {
      await redirect.stop();
    }

    assert.deepEqual(spanport.requests, []);
    assert.match(stderr(), /HTTP 302/);
  });

  it("refuses URLs that aren't http or https", async () => {
    assert.equal(await checkDataKey("file:///etc/passwd", VALID_KEY), false);

    assert.match(stderr(), /must start with http:\/\/ or https:\/\//);
  });
});
