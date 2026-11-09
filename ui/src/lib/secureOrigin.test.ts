import { describe, expect, it } from "vitest";

import { needsHttps } from "./secureOrigin";

describe("needsHttps", () => {
  it("asks for https on plain http to another host", () => {
    expect(needsHttps("http:", "spanport.acme.com")).toBe(true);
    expect(needsHttps("http:", "10.0.0.5")).toBe(true);
  });

  it("is fine over https", () => {
    expect(needsHttps("https:", "spanport.acme.com")).toBe(false);
  });

  it("is fine over http on this machine", () => {
    expect(needsHttps("http:", "localhost")).toBe(false);
    expect(needsHttps("http:", "LOCALHOST")).toBe(false);
    expect(needsHttps("http:", "127.0.0.1")).toBe(false);
    expect(needsHttps("http:", "[::1]")).toBe(false);
  });
});
