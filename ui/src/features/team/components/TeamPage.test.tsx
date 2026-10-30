import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AcceptInvitePage } from "../../auth";
import { TeamPage } from "./TeamPage";

const OWNER = { id: "u1", name: "Sam", email: "sam@x.com", role: "owner", organization: "acme" };
const ALL = { all_projects: true, project_ids: [] };
const ADMIN = {
  id: "u2",
  name: "Ravi",
  email: "ravi@x.com",
  role: "admin",
  created_at: "2026-10-30T12:00:00Z",
  ...ALL,
};
const VIEWER = { ...ADMIN, id: "u3", name: "Asha", email: "asha@x.com", role: "viewer" };
const PENDING = {
  id: "i1",
  email: "nitsh@x.com",
  role: "member",
  invited_by: "Sam",
  created_at: "2026-10-30T12:00:00Z",
  expires_at: "2026-11-06T12:00:00Z",
  ...ALL,
};
const PROJECTS = [
  { id: "p1", client: "northwind", project: "hr", environment: "production", archived: false },
  { id: "p2", client: "globex", project: "tracking", environment: "staging", archived: false },
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const page = (data: unknown[]) => json({ data, next_cursor: null, has_more: false });

/** A fake server; `answer` handles a call first, then the defaults. */
function server(answer: (path: string, init: RequestInit) => Response | undefined = () => undefined) {
  const fetchMock = vi.fn((path: string, init: RequestInit) => {
    const answered = answer(path, init);
    if (answered) return Promise.resolve(answered);
    if (path.startsWith("/api/v1/auth/me")) return Promise.resolve(json(OWNER));
    if (path.startsWith("/api/v1/projects")) return Promise.resolve(page(PROJECTS));
    if (init.method === "PUT") return Promise.resolve(json({ ...VIEWER, all_projects: false, project_ids: ["p1"] }));
    if (path.startsWith("/api/v1/users")) {
      return Promise.resolve(page([{ ...OWNER, created_at: ADMIN.created_at, ...ALL }, ADMIN, VIEWER]));
    }
    if (path.startsWith("/api/v1/invites") && init.method !== "POST") return Promise.resolve(page([PENDING]));
    return Promise.resolve(new Response(null, { status: 204 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(url: string, element: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const callTo = (fetchMock: ReturnType<typeof server>, method: string, path: string) =>
  fetchMock.mock.calls.find(([url, init]) => url === path && init.method === method);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Users", () => {
  it("creates an invite link to send, and a mistyped invite can be cancelled", async () => {
    const fetchMock = server((path, init) =>
      path === "/api/v1/invites" && init.method === "POST"
        ? json({ token: "tok/1", item: { ...PENDING, email: "new@x.com" } }, 201)
        : undefined,
    );
    renderAt("/users", <TeamPage />);

    await userEvent.type(screen.getByLabelText("Email"), "New@X.com");
    await userEvent.click(screen.getByRole("radio", { name: /^Viewer/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Only these projects" }));
    await userEvent.click(screen.getByRole("button", { name: "Create invite link" }));
    expect(screen.getByRole("alert").textContent).toContain("Pick at least one project");
    await userEvent.click(await screen.findByRole("checkbox", { name: "globex · tracking · staging" }));
    await userEvent.click(screen.getByRole("button", { name: "Create invite link" }));

    expect(JSON.parse(callTo(fetchMock, "POST", "/api/v1/invites")?.[1].body as string)).toEqual({
      email: "new@x.com",
      role: "viewer",
      all_projects: false,
      project_ids: ["p2"],
    });
    expect((await screen.findByText(/accept-invite\?token=tok%2F1$/)).textContent).toContain(window.location.origin);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel invite" }));
    await userEvent.click(screen.getByRole("button", { name: "Click again to cancel" }));
    expect(callTo(fetchMock, "DELETE", "/api/v1/invites/i1")).toBeDefined();
  });

  it("lets an owner change someone's role but not their own", async () => {
    const fetchMock = server();
    renderAt("/users", <TeamPage />);

    await userEvent.selectOptions(await screen.findByLabelText("Role of ravi@x.com"), "member");

    expect(JSON.parse(callTo(fetchMock, "PATCH", "/api/v1/users/u2")?.[1].body as string)).toEqual({
      role: "member",
    });
    expect(screen.queryByLabelText("Role of sam@x.com")).toBeNull();
  });

  it("limits a viewer to some projects; admins have no project editor", async () => {
    const fetchMock = server();
    renderAt("/users", <TeamPage />);

    // Only the viewer has the button: the owner is you and Ravi is an admin.
    await userEvent.click(await screen.findByRole("button", { name: "Edit projects" }));
    const editor = within(screen.getByRole("group", { name: "Projects asha@x.com can see" }));
    await userEvent.click(editor.getByRole("radio", { name: "Only these projects" }));
    await userEvent.click(editor.getByRole("checkbox", { name: "northwind · hr · production" }));
    await userEvent.click(editor.getByRole("button", { name: "Save" }));

    expect(JSON.parse(callTo(fetchMock, "PUT", "/api/v1/users/u3/projects")?.[1].body as string)).toEqual({
      all_projects: false,
      project_ids: ["p1"],
    });
  });
});

describe("Accept invite", () => {
  it("shows who the invite is for, and creates the account only on Accept", async () => {
    const fetchMock = server((path) => {
      if (path === "/api/v1/invites/inspect") {
        return json({ email: "new@x.com", role: "viewer", organization: "acme", invited_by: "Sam" });
      }
      if (path === "/api/v1/invites/accept") return json({ ...OWNER, email: "new@x.com", role: "viewer" }, 201);
      return undefined;
    });
    renderAt("/accept-invite?token=tok", <AcceptInvitePage />);

    expect(await screen.findByText("Join acme on Spanport")).toBeDefined();
    expect(callTo(fetchMock, "POST", "/api/v1/invites/accept")).toBeUndefined();
    await userEvent.type(screen.getByLabelText("Your name"), "New Person");
    await userEvent.type(screen.getByLabelText("Password"), "a long enough passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Accept and join" }));

    expect(JSON.parse(callTo(fetchMock, "POST", "/api/v1/invites/accept")?.[1].body as string)).toEqual({
      token: "tok",
      name: "New Person",
      password: "a long enough passphrase",
    });
  });

  it("says when the link is incomplete", () => {
    server();
    renderAt("/accept-invite", <AcceptInvitePage />);

    expect(screen.getByRole("alert").textContent).toContain("full invite link");
  });
});
