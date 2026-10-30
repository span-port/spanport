import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LogItem } from "../types";
import { LogRow } from "./LogRow";

const STACK = "InvalidAccessKeyId: The AWS Access Key Id does not exist\n    at S3RestXmlProtocol.handleError";
const LOG: LogItem = {
  log_id: "l1",
  ts: "2026-10-30T03:32:45.230Z",
  service: "kosha-backend",
  level: "ERROR",
  message: STACK,
  trace_id: "",
  span_id: "",
  attributes: { "client.ip": "49.204.17.82" },
};

function renderExpanded() {
  const onFilter = vi.fn();
  const writeText = vi.fn<(text: string) => Promise<void>>(() => Promise.resolve());
  // jsdom has no clipboard; give the page one that records what was copied.
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LogRow log={LOG} timeZone="UTC" expanded onToggle={vi.fn()} onFilter={onFilter} />
    </QueryClientProvider>,
  );
  return { onFilter, writeText };
}

describe("LogRow", () => {
  it("shows the whole message with its line breaks and copies exactly that", async () => {
    const { writeText } = renderExpanded();

    expect(document.querySelector(".message-box-text")?.textContent).toBe(STACK);
    await userEvent.click(screen.getByRole("button", { name: "Copy message" }));

    expect(writeText).toHaveBeenCalledWith(STACK);
    expect(await screen.findByRole("button", { name: "Copy message" })).toHaveProperty(
      "textContent",
      "Copied",
    );
  });

  it("copies the whole record as JSON separately", async () => {
    const { writeText } = renderExpanded();

    await userEvent.click(screen.getByRole("button", { name: "Copy as JSON" }));

    const [copiedText] = writeText.mock.calls[0] ?? [""];
    expect(JSON.parse(copiedText)).toMatchObject({ log_id: "l1" });
  });

  it("turns a field into a filter or an exclusion; empty fields offer neither", async () => {
    const { onFilter } = renderExpanded();

    await userEvent.click(screen.getByRole("button", { name: "Show only client.ip = 49.204.17.82" }));
    await userEvent.click(screen.getByRole("button", { name: "Exclude service = kosha-backend" }));

    expect(onFilter.mock.calls).toEqual([
      [{ field: "client.ip", operator: "=", value: "49.204.17.82" }],
      [{ field: "service", operator: "!=", value: "kosha-backend" }],
    ]);
    expect(screen.queryByRole("button", { name: /trace_id/ })).toBeNull();
  });
});
