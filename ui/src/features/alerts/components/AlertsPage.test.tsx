import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AlertEvent } from "../api";
import { AlertsPage } from "./AlertsPage";

const PROJECT = { id: "p1", client: "globex", project: "tracking-api", environment: "production", archived: false };
const FIRING: AlertEvent = {
  id: "e1",
  rule_id: "r1",
  rule_name: "Too many errors",
  query: "level:ERROR",
  threshold: 20,
  window_minutes: 5,
  state: "firing",
  matched_count: 42,
  fired_at: "2026-10-30T12:00:00Z",
  recovered_at: null,
  assignee_id: null,
  assigned_to: null,
  acknowledged_at: null,
  acknowledged_by: null,
  resolved_at: null,
  resolved_by: null,
  resolution_note: null,
};
const PRIYA = { id: "u2", name: "Priya", email: "priya@x.com" };

// A server configured below the defaults, so the form shows it follows the server.
const SERVER_LIMITS = { check_seconds: 10, max_emails: 3, max_window_minutes: 30, max_rules_per_project: 50 };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const page = (data: unknown[]) => json({ data, next_cursor: null, has_more: false });

/** A fake server for a signed-in person with `role`; returns the fetch mock to inspect calls. */
function server(role: string, events: AlertEvent[] = []) {
  const fetchMock = vi.fn((path: string, init: RequestInit) => {
    if (path.startsWith("/api/v1/auth/me")) {
      return Promise.resolve(json({ id: "u1", name: "Sam", email: "sam@x.com", role, organization: "acme" }));
    }
    if (path.startsWith("/api/v1/projects")) return Promise.resolve(page([PROJECT]));
    if (path === "/api/v1/logs/counts") return Promise.resolve(json({ total: 37, by_level: { ERROR: 37 } }));
    if (path === "/api/v1/alert-settings") return Promise.resolve(json(SERVER_LIMITS));
    if (path.startsWith("/api/v1/alert-assignees")) return Promise.resolve(page([PRIYA]));
    if (path.startsWith("/api/v1/alert-events") && init.method !== "POST") return Promise.resolve(page(events));
    if (init.method === "POST" && path === "/api/v1/alert-rules") return Promise.resolve(json({}, 201));
    if (init.method === "POST") return Promise.resolve(new Response(null, { status: 204 }));
    return Promise.resolve(page([]));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <AlertsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function callTo(fetchMock: ReturnType<typeof server>, method: string, path: string) {
  return fetchMock.mock.calls.find(([url, init]) => url === path && init.method === method);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Alerts", () => {
  it("starts a rule from the Logs search and refuses a mistyped email until it is fixed", async () => {
    const fetchMock = server("owner");
    renderAt("/alerts?alert-query=level%3AERROR");

    expect(await screen.findByDisplayValue("level:ERROR")).toBeDefined();
    expect((await screen.findByRole("status")).textContent).toBe(
      "Right now: 37 lines in the last 5 minutes, so this alert would fire.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Errors and warnings" }));
    expect(screen.getByLabelText("Search")).toHaveProperty("value", "level:ERROR OR level:WARN");
    await userEvent.click(screen.getByRole("button", { name: "Errors" }));
    await userEvent.type(screen.getByLabelText("Name"), "Too many errors");
    const emails = await screen.findByLabelText(/^Email \(up to 3,/);
    expect(screen.getByLabelText("Minutes")).toHaveProperty("max", "30");
    await userEvent.type(emails, "oncall@yourco.com, oncall@yourco");
    await userEvent.click(screen.getByRole("button", { name: "Save rule" }));

    expect(screen.getByRole("alert").textContent).toContain("oncall@yourco");
    expect(callTo(fetchMock, "POST", "/api/v1/alert-rules")).toBeUndefined();

    await userEvent.type(emails, ".com");
    await userEvent.click(screen.getByRole("button", { name: "Save rule" }));

    const call = callTo(fetchMock, "POST", "/api/v1/alert-rules");
    expect(JSON.parse(call?.[1].body as string)).toEqual({
      project_id: "p1",
      name: "Too many errors",
      query: "level:ERROR",
      threshold: 20,
      window_minutes: 5,
      email_recipients: ["oncall@yourco.com"],
      enabled: true,
    });
  });

  it("lets a member say they're on a firing alert, without managing rules", async () => {
    const fetchMock = server("member", [FIRING]);
    renderAt("/alerts");

    await userEvent.click(await screen.findByRole("button", { name: "I'm on it" }));

    expect(screen.getByRole("button", { name: "Now and history (1 firing)" })).toBeDefined();
    expect(callTo(fetchMock, "POST", "/api/v1/alert-events/e1/acknowledge")).toBeDefined();
    expect(screen.queryByRole("button", { name: "New alert rule" })).toBeNull();
  });

  it("assigns an alert to someone and resolves it with a note", async () => {
    const fetchMock = server("member", [{ ...FIRING, recovered_at: "2026-10-30T12:02:00Z" }]);
    renderAt("/alerts");

    expect(await screen.findByText(/still needs a person to resolve it/)).toBeDefined();
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Assign Too many errors to" }), "u2");
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await userEvent.type(screen.getByLabelText(/What did you find/), "Expired AWS key, rotated it.");
    await userEvent.click(screen.getByRole("button", { name: "Mark resolved" }));

    const assign = callTo(fetchMock, "POST", "/api/v1/alert-events/e1/assign");
    const resolve = callTo(fetchMock, "POST", "/api/v1/alert-events/e1/resolve");
    expect(JSON.parse(assign?.[1].body as string)).toEqual({ user_id: "u2" });
    expect(JSON.parse(resolve?.[1].body as string)).toEqual({ note: "Expired AWS key, rotated it." });
  });

  it("shows a closed alert's note and who resolved it in the history", async () => {
    server("member", [
      { ...FIRING, state: "resolved", resolved_at: "2026-10-30T12:20:00Z", resolved_by: "Priya", resolution_note: "Rotated the key." },
    ]);
    renderAt("/alerts");

    expect(await screen.findByText("Resolved by Priya")).toBeDefined();
    expect(screen.getByText("Rotated the key.")).toBeDefined();
  });

  it("shows a viewer the alert but no actions", async () => {
    server("viewer", [FIRING]);
    renderAt("/alerts");

    expect(await screen.findByText("Too many errors")).toBeDefined();
    expect(screen.queryByRole("button", { name: "I'm on it" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Resolve" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: /Assign/ })).toBeNull();
  });
});
