import { describe, expect, it } from "vitest";

import { ApiError } from "../api/client";
import { stopsLiveTail } from "./liveTail";

function apiError(status: number): ApiError {
  return new ApiError(status, "code", "Title", "Detail", null);
}

describe("when a live tail stops", () => {
  it("stops on a 4xx that would fail again", () => {
    expect(stopsLiveTail(apiError(400))).toBe(true);
    expect(stopsLiveTail(apiError(401))).toBe(true);
    expect(stopsLiveTail(apiError(404))).toBe(true);
  });

  it("reconnects after a 429, a 5xx or a dropped connection", () => {
    expect(stopsLiveTail(apiError(429))).toBe(false);
    expect(stopsLiveTail(apiError(503))).toBe(false);
    expect(stopsLiveTail(new TypeError("network error"))).toBe(false);
  });
});
