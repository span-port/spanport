import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Role } from "../../auth/api";
import { useLogExport } from "../hooks/useLogExport";
import type { LogFilterRequest } from "../types";
import { ExportMenu } from "./ExportMenu";

const REQUEST: LogFilterRequest = {
  project_id: "p1",
  filters: [{ field: "level", operator: "=", value: "ERROR" }],
  combine: "and",
  query: "",
  start: "2026-10-30T11:00:00.000Z",
  end: "2026-10-30T12:00:00.000Z",
};

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

/** The menu with a real useLogExport, as LogStream wires it. */
function renderMenu(matchCount: number, role: Role) {
  const exporter = renderHook(() => useLogExport(REQUEST, matchCount, role), { wrapper }).result;
  render(<ExportMenu rows={[]} matchCount={matchCount} exporter={exporter.current} />, { wrapper });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ExportMenu", () => {
  it("downloads exactly the current search under the server's file name", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response("ts,level\n", {
          headers: { "Content-Disposition": 'attachment; filename="spanport-logs-x.csv"' },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    // jsdom has no object URLs; only these two are replaced, the rest of URL stays real.
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: () => "blob:file" });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderMenu(42, "member");

    await userEvent.click(screen.getByRole("button", { name: /Export/ }));
    expect(screen.getByRole("menuitem", { name: /Download CSV/ }).textContent).toContain("42 lines");
    await userEvent.click(screen.getByRole("menuitem", { name: /Download CSV/ }));

    await vi.waitFor(() => {
      expect(click).toHaveBeenCalledOnce();
    });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/v1/logs/export");
    expect(JSON.parse(init.body as string)).toEqual({ ...REQUEST, format: "csv" });
  });

  it("tells viewers they can't download", async () => {
    renderMenu(42, "viewer");

    await userEvent.click(screen.getByRole("button", { name: /Export/ }));

    const download = screen.getByRole("menuitem", { name: /Download JSON lines/ });
    expect(download).toHaveProperty("disabled", true);
    expect(download.textContent).toContain("Viewers can't download logs");
  });

  it("asks to narrow a search over the 100,000-line limit", async () => {
    renderMenu(100_001, "owner");

    await userEvent.click(screen.getByRole("button", { name: /Export/ }));

    expect(screen.getByRole("menuitem", { name: /Download CSV/ }).textContent).toContain("narrow the range");
  });
});
