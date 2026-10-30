import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequestsPage } from "./RequestsPage";
import { TracePage } from "./TracePage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };
const TRACE = "0af7651916cd43dd8448eb211c80319c";

function span(spanId: string, parent: string, label: string, offsetMs: number, durationMs: number, selfMs: number) {
  return {
    span_id: spanId,
    parent_span_id: parent,
    service: "kosha-backend",
    name: spanId,
    kind: "INTERNAL",
    label,
    start_ts: "2026-10-30T12:00:00Z",
    offset_ms: offsetMs,
    duration_ms: durationMs,
    self_ms: selfMs,
    status_code: "UNSET",
    status_message: "",
    http_method: "",
    http_route: "",
    http_status: 0,
    attributes: { "db.system": "postgresql" },
  };
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body));
}

function server() {
  const fetchMock = vi.fn((path: string) => {
    if (path.startsWith("/api/v1/projects")) {
      return Promise.resolve(json({ data: [PROJECT], next_cursor: null, has_more: false }));
    }
    if (path === "/api/v1/traces/search") {
      return Promise.resolve(
        json({
          data: [
            {
              trace_id: TRACE,
              span_id: "b7ad6b7169203331",
              service: "kosha-backend",
              name: "GET",
              http_method: "GET",
              http_route: "/api/environments/:id",
              http_status: 500,
              error: true,
              start_ts: "2026-10-30T12:00:00Z",
              duration_ms: 885,
            },
          ],
          next_cursor: null,
          has_more: false,
        }),
      );
    }
    return Promise.resolve(
      json({
        trace_id: TRACE,
        start_ts: "2026-10-30T12:00:00Z",
        duration_ms: 885,
        truncated: false,
        spans: [
          span("GET /api/environments/:id", "", "incoming_request", 0, 885, 15),
          span("VariablesService.list", "GET /api/environments/:id", "code", 5, 870, 38),
          span("SELECT variables", "VariablesService.list", "db", 10, 42, 42),
          span("AWS Secrets Manager", "VariablesService.list", "external", 60, 790, 790),
        ],
      }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(url: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/requests/:traceId" element={<TracePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Requests", () => {
  it("lists requests with their status and duration, and filters to errors", async () => {
    const fetchMock = server();
    renderAt("/requests?project=p1");

    const link = await screen.findByRole("link", { name: /\/api\/environments\/:id/ });
    expect(link.getAttribute("href")).toBe(`/requests/${TRACE}?project=p1`);
    expect(screen.getByText("885 ms")).toBeDefined();
    await userEvent.click(screen.getByRole("checkbox", { name: "Errors only" }));

    const bodies = fetchMock.mock.calls
      .filter(([path]) => path === "/api/v1/traces/search")
      .map((call) => JSON.parse((call as unknown as [string, RequestInit])[1].body as string) as { errors_only: boolean });
    expect(bodies.at(-1)?.errors_only).toBe(true);
  });

  it("shows a request as a nested waterfall with own times and a link to its logs", async () => {
    server();
    renderAt(`/requests/${TRACE}?project=p1`);

    const external = await screen.findByRole("button", { name: /AWS Secrets Manager/ });
    expect(external.textContent).toContain("External");
    expect(screen.getByRole("button", { name: /SELECT variables/ }).textContent).toContain("Database");
    expect(screen.getByRole("link", { name: "See logs" }).getAttribute("href")).toContain(`query=trace%3A${TRACE}`);

    await userEvent.click(screen.getByRole("button", { name: /SELECT variables/ }));
    expect(screen.getByText("db.system")).toBeDefined();
  });
});
