import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ServiceMapPage } from "./ServiceMapPage";

const PROJECT = { id: "p1", client: "kosha", project: "backend", environment: "production", archived: false };

function json(body: unknown): Response {
  return new Response(JSON.stringify(body));
}

function stats(calls: number, errors = 0, status = "ok") {
  return { calls, errors, p50_ms: 4, p95_ms: 9, status };
}

function server() {
  const fetchMock = vi.fn((path: string) => {
    if (path.startsWith("/api/v1/projects")) {
      return Promise.resolve(json({ data: [PROJECT], next_cursor: null, has_more: false }));
    }
    return Promise.resolve(
      json({
        range_seconds: 3600,
        nodes: [
          { id: "service:kosha-backend", kind: "service", name: "kosha-backend", ...stats(3600), calls_to: ["api.mailgun.net", "postgresql · kosha"], called_by: [] },
          { id: "db:postgresql · kosha", kind: "db", name: "postgresql · kosha", ...stats(36_000), calls_to: [], called_by: ["kosha-backend"] },
          { id: "external:api.mailgun.net", kind: "external", name: "api.mailgun.net", ...stats(100, 10, "bad"), calls_to: [], called_by: ["kosha-backend"] },
        ],
        edges: [
          { source: "service:kosha-backend", target: "db:postgresql · kosha", ...stats(36_000) },
          { source: "service:kosha-backend", target: "external:api.mailgun.net", ...stats(100, 10, "bad") },
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

describe("Service map", () => {
  it("draws what calls what, and shows a chosen box's details", async () => {
    server();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={["/apis/map?project=p1"]}>
          <ServiceMapPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const details = within(await screen.findByRole("complementary", { name: "Details" }));
    expect(details.getByRole("heading", { name: "kosha-backend" })).toBeDefined();
    expect(screen.getByText("10 queries/s · 4.0 ms")).toBeDefined();
    const database = screen.getByRole("button", { name: /postgresql · kosha/ });
    expect(database.querySelector("svg")?.getAttribute("data-brand")).toBe("PostgreSQL");
    expect(screen.getByRole("link", { name: "Service map" }).getAttribute("aria-current")).toBe("page");

    await userEvent.click(screen.getByRole("button", { name: /api\.mailgun\.net/ }));

    expect(details.getByText("Errors above normal")).toBeDefined();
    expect(details.getByText("10.00%")).toBeDefined();
    expect(details.getByRole("link", { name: "See the errors →" }).getAttribute("href")).toContain("/errors?project=p1");
  });
});
