import { describe, expect, it } from "vitest";

import { readCookie } from "./cookies";

describe("readCookie", () => {
  it("finds a cookie by its exact name", () => {
    const header = "__Host-sp_csrf=abc%3D; other=1; __Host-sp_csrf_old=x";

    expect(readCookie("__Host-sp_csrf", header)).toBe("abc=");
    expect(readCookie("other", header)).toBe("1");
    expect(readCookie("missing", header)).toBeNull();
    expect(readCookie("__Host-sp_csrf", "")).toBeNull();
  });
});
