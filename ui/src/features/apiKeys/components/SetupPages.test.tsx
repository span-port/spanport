import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectsPage } from "../../projects";
import { ApiKeysPage } from "./ApiKeysPage";

const PROJECT = {
  id: "p1",
  client: "globex",
  project: "tracking-api",
  environment: "production",
  archived: false,
};
const RAW_KEY = "sp_ingest_the-whole-secret-a1b2";
const LISTED_KEY = {
  id: "k1",
  name: "tracking-prod",
  key_type: "ingest",
  prefix: "sp_ingest_",
  last_four: "a1b2",
  project_id: "p1",
  scopes: [],
  created_at: "2026-10-29T07:00:00Z",
  expires_at: null,
  revoked_at: null,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

type Route = (path: string, init: RequestInit) => Response | undefined;

/** A fake server: `route` answers first; projects and keys lists have defaults. */
function server(route: Route = () => undefined) {
  const fetchMock = vi.fn((path: string, init: RequestInit) =>
    Promise.resolve(
      route(path, init) ??
        (path.startsWith("/api/v1/projects")
          ? json({ data: [PROJECT], next_cursor: null, has_more: false })
          : json({ data: [LISTED_KEY], next_cursor: null, has_more: false })),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function bodyOf(fetchMock: ReturnType<typeof server>, method: string, path: string): unknown {
  const call = fetchMock.mock.calls.find(([url, init]) => url === path && init.method === method);
  return call ? JSON.parse(call[1].body as string) : undefined;
}

function renderPage(page: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Clients and projects", () => {
  it("adds a project with its names turned into slugs, then lists it under its client", async () => {
    const fetchMock = server((path, init) =>
      init.method === "POST" ? json(PROJECT, 201) : undefined,
    );
    renderPage(<ProjectsPage />);

    await userEvent.type(screen.getByLabelText("Client"), "Globex");
    await userEvent.type(screen.getByLabelText("Project"), "Tracking API");
    await userEvent.click(screen.getByRole("radio", { name: "Staging" }));
    const preview = screen.getByText("You are adding").parentElement;
    expect(preview?.textContent).toContain("globex/tracking-api/staging");
    await userEvent.click(screen.getByRole("button", { name: "Add project" }));

    expect(await screen.findByRole("status")).toBeDefined();
    expect(bodyOf(fetchMock, "POST", "/api/v1/projects")).toEqual({
      client: "globex",
      project: "tracking-api",
      environment: "staging",
    });
    expect(screen.getByRole("region", { name: "Client globex" })).toBeDefined();
  });
});

describe("Project changes", () => {
  it("adds a new environment, warns about look-alikes and selects it", async () => {
    const fetchMock = server((_path, init) =>
      init.method === "POST" ? json({ ...PROJECT, environment: "qa" }, 201) : undefined,
    );
    renderPage(<ProjectsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "+ Environment" }));
    await userEvent.type(screen.getByLabelText("New environment"), "Prod");
    expect(screen.getByText(/You already have/).textContent).toContain("production");
    await userEvent.clear(screen.getByLabelText("New environment"));
    await userEvent.type(screen.getByLabelText("New environment"), "QA{Enter}");
    await userEvent.type(screen.getByLabelText("Client"), "Globex");
    await userEvent.type(screen.getByLabelText("Project"), "Tracking API");
    await userEvent.click(screen.getByRole("button", { name: "Add project" }));

    expect(screen.getByRole("radio", { name: "qa" })).toHaveProperty("checked", true);
    await screen.findByRole("status");
    expect(bodyOf(fetchMock, "POST", "/api/v1/projects")).toMatchObject({ environment: "qa" });
  });

  it("renames a project and archives it on the second click", async () => {
    const fetchMock = server((_path, init) =>
      init.method === "POST" || init.method === "PATCH" ? json(PROJECT) : undefined,
    );
    renderPage(<ProjectsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
    const nameBox = screen.getByLabelText("Project name");
    await userEvent.clear(nameBox);
    await userEvent.type(nameBox, "Tracking API v2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await userEvent.click(await screen.findByRole("button", { name: "Archive" }));
    const archiveCalls = () => fetchMock.mock.calls.filter(([url]) => url.endsWith("/archive"));
    expect(archiveCalls()).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Click again to archive" }));

    expect(bodyOf(fetchMock, "PATCH", "/api/v1/projects/p1")).toEqual({
      project: "tracking-api-v2",
      environment: "production",
    });
    expect(archiveCalls()).toHaveLength(1);
  });
});

describe("Deleting a project", () => {
  it("is offered only when archived and needs the name typed", async () => {
    const archived = { ...PROJECT, archived: true };
    const fetchMock = server((path, init) => {
      if (init.method === "DELETE") return new Response(null, { status: 204 });
      return path.startsWith("/api/v1/projects")
        ? json({ data: [archived], next_cursor: null, has_more: false })
        : undefined;
    });
    renderPage(<ProjectsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const deleteForever = screen.getByRole("button", { name: "Delete forever" });
    expect(deleteForever).toHaveProperty("disabled", true);
    await userEvent.type(screen.getByLabelText("Type the project name to confirm"), "tracking-ap");
    expect(deleteForever).toHaveProperty("disabled", true);
    await userEvent.type(screen.getByLabelText("Type the project name to confirm"), "i");
    await userEvent.click(deleteForever);

    const deletes = fetchMock.mock.calls.filter(([, init]) => init.method === "DELETE");
    expect(deletes.map(([url]) => url)).toEqual(["/api/v1/projects/p1"]);
  });
});

describe("API keys", () => {
  it("renames a key in place", async () => {
    const fetchMock = server((_path, init) =>
      init.method === "PATCH" ? json({ ...LISTED_KEY, name: "renamed" }) : undefined,
    );
    renderPage(<ApiKeysPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
    const nameBox = screen.getByLabelText("Key name");
    await userEvent.clear(nameBox);
    await userEvent.type(nameBox, "renamed{Enter}");

    expect(bodyOf(fetchMock, "PATCH", "/api/v1/api-keys/k1")).toEqual({ name: "renamed" });
  });

  it("creates a data key and shows the whole key only in the created panel", async () => {
    const fetchMock = server((path, init) =>
      path === "/api/v1/api-keys" && init.method === "POST"
        ? json({ key: RAW_KEY, item: LISTED_KEY }, 201)
        : undefined,
    );
    renderPage(<ApiKeysPage />);

    expect(await screen.findByText("sp_ingest_…a1b2")).toBeDefined();
    expect(screen.queryByText(RAW_KEY)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Create key" }));
    const form = screen.getByRole("form", { name: "Create key" });
    await userEvent.type(within(form).getByLabelText("Name"), "tracking-prod");
    await userEvent.selectOptions(within(form).getByLabelText("Project"), "p1");
    await userEvent.click(within(form).getByRole("button", { name: "Create key" }));

    expect(await screen.findByText(RAW_KEY)).toBeDefined();
    expect(bodyOf(fetchMock, "POST", "/api/v1/api-keys")).toEqual({
      name: "tracking-prod",
      key_type: "ingest",
      project_id: "p1",
    });
    // Not copied yet: leaving the tab keeps it, so it can't be lost.
    await userEvent.click(screen.getByRole("button", { name: /^Admin keys/ }));
    expect(screen.queryByText(RAW_KEY)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /^Data keys/ }));
    expect(screen.getByText(RAW_KEY)).toBeDefined();
    // Copied: leaving the tab closes it for good.
    await userEvent.click(screen.getByRole("button", { name: "Copy key" }));
    await userEvent.click(screen.getByRole("button", { name: /^Admin keys/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Data keys/ }));
    expect(screen.queryByText(RAW_KEY)).toBeNull();
  });

  it("deletes only revoked keys, on the second click", async () => {
    const revoked = { ...LISTED_KEY, revoked_at: "2026-10-29T08:00:00Z" };
    const fetchMock = server((path, init) => {
      if (init.method === "DELETE") return new Response(null, { status: 204 });
      return path.startsWith("/api/v1/api-keys")
        ? json({ data: [revoked], next_cursor: null, has_more: false })
        : undefined;
    });
    renderPage(<ApiKeysPage />);

    expect(screen.queryByRole("button", { name: "Revoke" })).toBeNull();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByRole("button", { name: "Click again to delete" }));

    const deletes = fetchMock.mock.calls.filter(([, init]) => init.method === "DELETE");
    expect(deletes.map(([url]) => url)).toEqual(["/api/v1/api-keys/k1"]);
  });

  it("asks for a project before creating a data key", async () => {
    const fetchMock = server();
    renderPage(<ApiKeysPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Create key" }));
    const form = screen.getByRole("form", { name: "Create key" });
    await userEvent.type(within(form).getByLabelText("Name"), "x");
    await userEvent.click(within(form).getByRole("button", { name: "Create key" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Choose the project");
    expect(bodyOf(fetchMock, "POST", "/api/v1/api-keys")).toBeUndefined();
  });

  it("revokes only on the second click", async () => {
    const fetchMock = server((_path, init) =>
      init.method === "POST" ? new Response(null, { status: 204 }) : undefined,
    );
    renderPage(<ApiKeysPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Revoke" }));
    const revokeCalls = () => fetchMock.mock.calls.filter(([url]) => url.endsWith("/revoke"));
    expect(revokeCalls()).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Click again to revoke" }));

    expect(revokeCalls().map(([url]) => url)).toEqual(["/api/v1/api-keys/k1/revoke"]);
  });

  it("shows LLM and browser keys as coming later", async () => {
    server();
    renderPage(<ApiKeysPage />);

    expect(await screen.findByRole("button", { name: "LLM keys" })).toHaveProperty("disabled", true);
  });
});
