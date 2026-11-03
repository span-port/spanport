import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApisPage } from "./ApisPage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };

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
        totals: { requests: 1240, errors: 31, p95_ms: 1900 },
        data: [
          {
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

    const link = await screen.findByRole("link", { name: /\/api\/environments\/:id/ });
    expect(link.getAttribute("href")).toBe(
      "/requests?project=p1&service=kosha-backend&route=%2Fapi%2Fenvironments%2F%3Aid",
    );
    expect(screen.getByText("1,240")).toBeDefined();
    expect(screen.getByText("2.5%")).toBeDefined();
    expect(screen.getByText("0.4%")).toBeDefined();
    expect(screen.getByText("External calls 82%")).toBeDefined();
    expect(screen.getByRole("img", { name: "Your code 10%, Database 8%, External calls 82%" })).toBeDefined();
  });

  it("opens an API's requests from anywhere on its row", async () => {
    server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis?project=p1"]}>
          <Routes>
            <Route path="/apis" element={<ApisPage />} />
            <Route path="/requests" element={<p>Requests page</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByText("0.4%"));

    expect(await screen.findByText("Requests page")).toBeDefined();
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
