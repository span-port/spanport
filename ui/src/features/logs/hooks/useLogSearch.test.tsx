import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RangeSelection } from "../../../lib/timeRange";
import { useLogCounts } from "./useLogSearch";

const FILTERS = { project_id: "p1", filters: [], combine: "and" as const, query: "" };
const LAST_FIVE_MINUTES: RangeSelection = { kind: "preset", key: "5m" };
const OPENED_AT = Date.parse("2026-10-30T03:30:00Z");

function countsServer() {
  const fetchMock = vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify({ total: 1, by_level: { ERROR: 1 } }))),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentEnd(fetchMock: ReturnType<typeof countsServer>, callIndex: number): string {
  const call = fetchMock.mock.calls[callIndex] as unknown as [string, RequestInit];
  return (JSON.parse(call[1].body as string) as { end: string }).end;
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useLogCounts", () => {
  it("counts a range that ends now while following live", async () => {
    const fetchMock = countsServer();

    renderHook(() => useLogCounts(FILTERS, LAST_FIVE_MINUTES, OPENED_AT, true), { wrapper });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce();
    });
    expect(Date.parse(sentEnd(fetchMock, 0))).toBeGreaterThan(OPENED_AT);
  });

  it("counts the range ending when the page was anchored when not following", async () => {
    const fetchMock = countsServer();

    renderHook(() => useLogCounts(FILTERS, LAST_FIVE_MINUTES, OPENED_AT, false), { wrapper });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce();
    });
    expect(sentEnd(fetchMock, 0)).toBe("2026-10-30T03:30:00.000Z");
  });
});
