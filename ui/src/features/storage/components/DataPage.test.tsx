import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataPage } from "./DataPage";

const usage = (rows: number, bytes: number) => ({
  rows,
  estimated_bytes: bytes,
  oldest: rows ? "2026-11-01T00:00:00Z" : null,
  newest: rows ? "2026-11-03T00:00:00Z" : null,
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Data", () => {
  it("shows what each project stores and that Redis isn't used yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              logs_retention_days: 7,
              spans_retention_days: 30,
              totals: { logs: usage(12_400, 3 * 1024 * 1024), spans: usage(900, 1024 * 1024) },
              projects: [
                {
                  project_id: "p1",
                  client: "kosha",
                  project: "backend",
                  environment: "production",
                  logs: usage(12_400, 3 * 1024 * 1024),
                  spans: usage(900, 1024 * 1024),
                },
              ],
              redis_in_use: false,
            }),
          ),
        ),
      ),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <DataPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Logs · kept 7 days")).toBeDefined();
    expect(screen.getAllByText("12,400")).toHaveLength(2);
    expect(screen.getByText("4.0 MB")).toBeDefined();
    expect(screen.getByText(/Not used yet/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Integrations" })).toHaveProperty("disabled", true);
  });
});
