import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";
import { SetupPage } from "./SetupPage";

const PASSWORD = "a long Passphrase 1";
const OWNER = { id: "u1", name: "Nitish", email: "owner@example.com", role: "owner", organization: "acme" };

function problem(status: number, code: string, detail: string): Response {
  return new Response(JSON.stringify({ title: "Error", detail, code }), { status });
}

/** The JSON body sent to the path ending in `pathEnd`. */
function sentBody(fetchMock: ReturnType<typeof serverAnswers>, pathEnd: string): unknown {
  const call = fetchMock.mock.calls.find(([path]) => path.endsWith(pathEnd)) as unknown as [
    string,
    RequestInit,
  ];
  return JSON.parse(call[1].body as string);
}

/** Answers /auth/me with 401 and every other call with `answer`. */
function serverAnswers(answer: () => Response) {
  const fetchMock = vi.fn((path: string) =>
    Promise.resolve(path.endsWith("/me") ? problem(401, "not_signed_in", "Sign in.") : answer()),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string, page: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={page} />
          <Route path="/logs" element={<p>Logs screen</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Sign in", () => {
  it("opens the logs after a successful sign-in", async () => {
    const fetchMock = serverAnswers(() => new Response(JSON.stringify(OWNER), { status: 200 }));
    renderAt("/login", <LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("Password"), `${PASSWORD}{Enter}`);

    expect(await screen.findByText("Logs screen")).toBeDefined();
    expect(sentBody(fetchMock, "/login")).toEqual({ email: "owner@example.com", password: PASSWORD });
  });

  it("shows the server's message for a wrong password", async () => {
    serverAnswers(() => problem(401, "invalid_login", "The email or password is wrong."));
    renderAt("/login", <LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong{Enter}");

    expect((await screen.findByRole("alert")).textContent).toContain("The email or password is wrong.");
  });

  it("says when to try again after too many wrong passwords", async () => {
    serverAnswers(() =>
      problem(429, "rate_limited", "Too many wrong passwords for this email. Try again in 10 min."),
    );
    renderAt("/login", <LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong{Enter}");

    expect((await screen.findByRole("alert")).textContent).toContain("Try again in 10 min.");
  });

  it("checks the email before calling the server", async () => {
    const fetchMock = serverAnswers(() => new Response("{}"));
    renderAt("/login", <LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.type(screen.getByLabelText("Password"), "x{Enter}");

    expect((await screen.findByRole("alert")).textContent).toBe("Enter a valid email address.");
    expect(fetchMock.mock.calls.every(([path]) => path.endsWith("/me"))).toBe(true);
  });

  it("shows Google sign-in as coming later", () => {
    serverAnswers(() => new Response("{}"));
    renderAt("/login", <LoginPage />);

    expect(screen.getByRole("button", { name: "Continue with Google" })).toHaveProperty("disabled", true);
  });
});

describe("Set up", () => {
  async function fillSetup(token: string, password: string) {
    if (token) await userEvent.type(screen.getByLabelText("Setup token"), token);
    await userEvent.type(screen.getByLabelText("Your name"), "Nitish");
    await userEvent.type(screen.getByLabelText("Email"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("Password"), password);
    await userEvent.type(screen.getByLabelText("Organization name"), "acme{Enter}");
  }

  it("sends the pasted token with the form and opens the logs", async () => {
    const fetchMock = serverAnswers(() => new Response(JSON.stringify(OWNER), { status: 201 }));
    renderAt("/setup", <SetupPage />);

    await fillSetup("  token-from-log ", PASSWORD);

    expect(await screen.findByText("Logs screen")).toBeDefined();
    expect(sentBody(fetchMock, "/setup")).toMatchObject({ token: "token-from-log", organization: "acme" });
  });

  it("asks for the token before calling the server", async () => {
    const fetchMock = serverAnswers(() => new Response("{}"));
    renderAt("/setup", <SetupPage />);

    await fillSetup("", PASSWORD);

    expect((await screen.findByRole("alert")).textContent).toBe("Paste the setup token from the server's log.");
    expect(fetchMock.mock.calls.every(([path]) => path.endsWith("/me"))).toBe(true);
  });

  it("refuses a short password and rates it on the meter", async () => {
    serverAnswers(() => new Response("{}"));
    renderAt("/setup", <SetupPage />);

    await fillSetup("token-from-log", "short");

    expect((await screen.findByRole("alert")).textContent).toBe("Use at least 12 characters.");
    expect(screen.getByText(/mix of letters, numbers and symbols/)).toBeDefined();
  });

  it("explains a used or expired token", async () => {
    serverAnswers(() => problem(410, "setup_link_invalid", "This setup token is wrong, already used or expired."));
    renderAt("/setup", <SetupPage />);

    await fillSetup("old-token", PASSWORD);

    expect((await screen.findByRole("alert")).textContent).toContain("already used or expired");
  });
});
