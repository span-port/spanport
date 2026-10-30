import { describe, expect, it } from "vitest";

import { parseRequestLine, statusTone } from "./requestLine";

describe("request lines", () => {
  it("splits method, path, status, duration and the rest, and templates ids in the path", () => {
    const line = parseRequestLine(
      "GET /api/environments/d3bf2bc2-7474-4c41-98df-05f70c256824/components/8b633dc6-237f-464d-9658-dc3a33f5faa0/variables 500 402ms user=nitish@divami.com",
    );

    expect(line).toEqual({
      method: "GET",
      path: "/api/environments/d3bf2bc2-7474-4c41-98df-05f70c256824/components/8b633dc6-237f-464d-9658-dc3a33f5faa0/variables",
      template: "/api/environments/:id/components/:id/variables",
      status: 500,
      durationMs: 402,
      rest: "user=nitish@divami.com",
    });
  });

  it("templates numeric ids and keeps query strings and plain words", () => {
    expect(parseRequestLine("POST /orders/1042?retry=1 201 12.5ms")?.template).toBe(
      "/orders/:id?retry=1",
    );
    expect(parseRequestLine("GET /api/notifications 304 9ms")?.template).toBe("/api/notifications");
  });

  it("leaves other messages alone", () => {
    expect(parseRequestLine("[ExceptionsHandler] InvalidAccessKeyId: bad key")).toBeNull();
    expect(parseRequestLine("GET is a verb")).toBeNull();
  });

  it("colors statuses by class", () => {
    expect([200, 304, 404, 503].map(statusTone)).toEqual([
      "ok",
      "redirect",
      "client-error",
      "server-error",
    ]);
  });
});
