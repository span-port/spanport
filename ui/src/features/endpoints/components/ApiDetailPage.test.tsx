import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiDetailPage } from "./ApiDetailPage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };
const ROUTE = "/api/environments/:environmentId/components/:configId/variables";
const TRACE = "0af7651916cd43dd8448eb211c80319c";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body));
}

function server() {
  const fetchMock = vi.fn((path: string) => {
    if (path.startsWith("/api/v1/projects")) {
      return Promise.resolve(json({ data: [PROJECT], next_cursor: null, has_more: false }));
    }
    return Promise.resolve(
      json({
        summary: {
          service: "kosha-backend",
          http_method: "GET",
          route: ROUTE,
          requests: 40,
          errors: 4,
          p50_ms: 180,
          p95_ms: 620,
          p99_ms: 900,
          avg_ms: 200,
          layers: { code_ms: 80, db_ms: 20, external_ms: 100, llm_ms: 0 },
        },
        bucket_seconds: 60,
        timeline: [{ at: "2026-11-03T04:34:00Z", requests: 40, errors: 4, p95_ms: 620 }],
        statuses: [
          { status: 304, requests: 36 },
          { status: 500, requests: 4 },
        ],
        steps: [
          { kind: "db", name: "pg.query:SELECT kosha", calls: 120, calls_per_request: 3, avg_ms: 4, p95_ms: 9, total_ms: 480 },
        ],
        slowest: [
          { trace_id: TRACE, span_id: "b7ad6b7169203331", start_ts: "2026-11-03T04:34:10Z", duration_ms: 885, http_status: 500, error: true },
        ],
      }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API detail", () => {
  it("shows one API's numbers, steps, status codes and slowest requests", async () => {
    const fetchMock = server();
    const query = new URLSearchParams({ project: "p1", service: "kosha-backend", method: "GET", route: ROUTE });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={[`/apis/detail?${query.toString()}`]}>
          <ApiDetailPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("10%")).toBeDefined();
    expect(screen.getByText("620 ms")).toBeDefined();
    expect(screen.getByText("pg.query:SELECT kosha")).toBeDefined();
    expect(screen.getByText("3.0")).toBeDefined();
    expect(screen.getByText("5xx")).toBeDefined();
    expect(screen.getByRole("link", { name: /3 Nov/ }).getAttribute("href")).toBe(`/requests/${TRACE}?project=p1`);
    expect(screen.getByRole("link", { name: "See its requests" }).getAttribute("href")).toContain("/requests?project=p1");
    expect(screen.getByRole("link", { name: "← APIs" }).getAttribute("href")).toBe("/apis?project=p1&range=1h");
    const body = fetchMock.mock.calls
      .filter(([path]) => path === "/api/v1/endpoints/detail")
      .map((call) => JSON.parse((call as unknown as [string, RequestInit])[1].body as string) as { route: string })
      .at(-1);
    expect(body?.route).toBe(ROUTE);
  });
});
