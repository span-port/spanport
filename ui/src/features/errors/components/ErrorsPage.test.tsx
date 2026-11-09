import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorsPage } from "./ErrorsPage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };
const TRACE = "0af7651916cd43dd8448eb211c80319c";
const BUCKET = { at: new Date(Date.now() - 10 * 60_000).toISOString(), requests: 400, client_errors: 3, server_errors: 5 };

function json(body: unknown): Response {
  return new Response(JSON.stringify(body));
}

function server() {
  const fetchMock = vi.fn((path: string) => {
    if (path.startsWith("/api/v1/projects")) {
      return Promise.resolve(json({ data: [PROJECT], next_cursor: null, has_more: false }));
    }
    if (path === "/api/v1/errors/window") {
      return Promise.resolve(
        json({
          total: 5,
          groups: [{ status: 503, service: "kosha-backend", http_method: "GET", route: "/api/users", requests: 5 }],
          requests: [
            {
              trace_id: TRACE,
              span_id: "b7ad6b7169203331",
              start_ts: BUCKET.at,
              service: "kosha-backend",
              http_method: "GET",
              route: "/api/users",
              http_status: 503,
              duration_ms: 1200,
              client_ip: "10.0.0.7",
              logged: "database timeout",
            },
          ],
        }),
      );
    }
    return Promise.resolve(
      json({
        bucket_seconds: 60,
        buckets: [BUCKET],
        totals: { requests: 400, client_errors: 3, server_errors: 5, worst_server: BUCKET },
        apis: [{ service: "kosha-backend", http_method: "GET", route: "/api/users", errors: 8 }],
      }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function bodiesOf(fetchMock: ReturnType<typeof server>, path: string) {
  return fetchMock.mock.calls
    .filter(([called]) => called === path)
    .map((call) => JSON.parse((call as unknown as [string, RequestInit])[1].body as string) as Record<string, string>);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HTTP errors", () => {
  it("shows the totals, and a chosen bar's requests with what they logged", async () => {
    const fetchMock = server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/errors?project=p1&show=5xx"]}>
          <ErrorsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("1.25% of requests; normally under 0.05%")).toBeDefined();
    expect(screen.getByRole("button", { name: "Grouped" })).toHaveProperty("disabled", true);

    await userEvent.click(within(screen.getByRole("region", { name: "Errors over time" })).getByRole("button"));

    const chosen = within(await screen.findByRole("region", { name: "Chosen moment" }));
    expect(await chosen.findByText("database timeout")).toBeDefined();
    expect(chosen.getByText("Service unavailable")).toBeDefined();
    expect(chosen.getByText("10.0.0.7")).toBeDefined();
    expect(chosen.getByRole("link", { name: "Open failed requests in Requests" }).getAttribute("href")).toBe(
      "/requests?project=p1&errors=1&range=15m",
    );
    expect(bodiesOf(fetchMock, "/api/v1/errors/window").at(-1)?.show).toBe("5xx");
  });

  it("narrows to one API", async () => {
    const fetchMock = server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/errors?project=p1"]}>
          <ErrorsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await screen.findByRole("option", { name: "GET /api/users" });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "API" }), "GET /api/users");

    const last = bodiesOf(fetchMock, "/api/v1/errors/summary").at(-1);
    expect([last?.service, last?.http_method, last?.route]).toEqual(["kosha-backend", "GET", "/api/users"]);
  });
});
