import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiJson } from "./client";

function respondWith(status: number, body: string, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn(() => Promise.resolve(new Response(body, { status, headers })));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentRequest(fetchMock: ReturnType<typeof respondWith>): RequestInit {
  const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  return init;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("API client", () => {
  it("sends a POST with its JSON body and the CSRF token from the cookie", async () => {
    // jsdom's page is plain http, where browsers refuse __Host- cookies, so stub the cookie jar.
    vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-sp_csrf=csrf-from-cookie");
    const fetchMock = respondWith(200, '{"total": 3}');

    const body = await apiJson<{ total: number }>("/api/v1/logs/counts", {
      method: "POST",
      body: { project_id: "p" },
    });

    expect(body.total).toBe(3);
    const init = sentRequest(fetchMock);
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toEqual({
      "X-CSRF-Token": "csrf-from-cookie",
      "Content-Type": "application/json",
    });
    expect(init.body).toBe('{"project_id":"p"}');
  });

  it("sends no CSRF header and no key on a GET", async () => {
    const fetchMock = respondWith(200, "{}");

    await apiJson("/api/v1/auth/me");

    expect(sentRequest(fetchMock).headers).toEqual({});
  });

  it("turns a problem+json answer into an ApiError with its code and request id", async () => {
    respondWith(
      400,
      JSON.stringify({
        type: "about:blank",
        title: "Invalid request",
        status: 400,
        detail: "The query has an unclosed bracket.",
        code: "invalid_request",
        request_id: "01a1-req",
      }),
    );

    const failure = apiJson("/api/v1/logs/search");

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 400,
      code: "invalid_request",
      detail: "The query has an unclosed bracket.",
      requestId: "01a1-req",
    });
  });

  it("keeps the status for an answer that is not problem+json", async () => {
    respondWith(502, "<html>Bad Gateway</html>", { "X-Request-ID": "proxy-1" });

    await expect(apiJson("/api/v1/projects")).rejects.toMatchObject({
      status: 502,
      code: "unknown",
      requestId: "proxy-1",
    });
  });
});
