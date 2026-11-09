import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApisPage } from "./ApisPage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };

function json(body: unknown): Response {
  return new Response(JSON.stringify(body));
}

const ENDPOINT = {
  service: "kosha-backend",
  http_method: "GET",
  route: "/api/environments/:id",
  requests: 1000,
  errors: 4,
  p50_ms: 180,
  p95_ms: 1900,
  p99_ms: 3400,
  avg_ms: 400,
  layers: { code_ms: 40, db_ms: 32, external_ms: 328, llm_ms: 0 },
  previous_p95_ms: 600,
};

function server() {
  const fetchMock = vi.fn((path: string) => {
    if (path.startsWith("/api/v1/projects")) {
      return Promise.resolve(json({ data: [PROJECT], next_cursor: null, has_more: false }));
    }
    if (path === "/api/v1/endpoints/detail") {
      return Promise.resolve(
        json({
          summary: ENDPOINT,
          bucket_seconds: 60,
          timeline: [{ at: "2026-11-03T04:34:00Z", requests: 40, errors: 4, p95_ms: 1900 }],
          statuses: [],
          steps: [],
          slowest: [],
        }),
      );
    }
    return Promise.resolve(
      json({
        totals: { requests: 1240, errors: 31, p95_ms: 1900, previous_p95_ms: 1100 },
        data: [ENDPOINT],
        slow_queries: [
          {
            statement: "SELECT * FROM variables WHERE config_id = $1",
            service: "kosha-backend",
            http_method: "GET",
            route: "/api/environments/:id",
            calls: 9000,
            calls_per_request: 9,
            avg_ms: 3,
            p95_ms: 8,
            total_ms: 27000,
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("APIs", () => {
  it("shows each API's speed, errors and where its time goes, linking to its requests", async () => {
    server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis?project=p1"]}>
          <ApisPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const table = within(await screen.findByRole("region", { name: "All APIs" }));
    const link = await table.findByRole("link", { name: /\/api\/environments\/:id/ });
    expect(link.getAttribute("href")).toBe(
      "/apis/detail?project=p1&range=1h&service=kosha-backend&method=GET&route=%2Fapi%2Fenvironments%2F%3Aid",
    );
    expect(screen.getByText("1,240")).toBeDefined();
    expect(screen.getByText("2.5%")).toBeDefined();
    expect(table.getByText("0.4%")).toBeDefined();
    expect(table.getByText("External calls 82%")).toBeDefined();
    expect(table.getByRole("img", { name: "Your code 10%, Database 8%, External calls 82%" })).toBeDefined();
  });

  it("follows the design: tabs, change vs before, warnings, latency chart and slow queries", async () => {
    server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis?project=p1"]}>
          <ApisPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("↑ 800 ms vs the period before")).toBeDefined();
    expect(screen.getByText("p95 up 3.2× vs the period before")).toBeDefined();
    expect(screen.getByRole("button", { name: "Deploys" })).toHaveProperty("disabled", true);
    expect(screen.getByText("kosha · backend · production")).toBeDefined();
    expect(await screen.findByRole("region", { name: "Latency over time" })).toBeDefined();
    const slow = within(screen.getByRole("region", { name: "Slow queries" }));
    expect(slow.getByText("SELECT * FROM variables WHERE config_id = $1")).toBeDefined();
    expect(slow.getByText("N+1 pattern")).toBeDefined();
  });

  it("opens an API's detail page from anywhere on its row", async () => {
    server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis?project=p1"]}>
          <Routes>
            <Route path="/apis" element={<ApisPage />} />
            <Route path="/apis/detail" element={<p>API detail page</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(await within(screen.getByRole("region", { name: "All APIs" })).findByText("0.4%"));

    expect(await screen.findByText("API detail page")).toBeDefined();
  });

  it("asks for the chosen range", async () => {
    const fetchMock = server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis?project=p1"]}>
          <ApisPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "7d" }));

    const bodies = fetchMock.mock.calls
      .filter(([path]) => path === "/api/v1/endpoints/summary")
      .map((call) => JSON.parse((call as unknown as [string, RequestInit])[1].body as string) as { start: string; end: string });
    const last = bodies.at(-1);
    const days = (Date.parse(last?.end ?? "") - Date.parse(last?.start ?? "")) / 86_400_000;
    expect(days).toBe(7);
  });
});
