import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { FilterChip } from "../types";
import { FilterBar } from "./FilterBar";

function renderFilterBar(filters: FilterChip[] = [], queryMode = false) {
  const handlers = {
    onAddFilter: vi.fn(),
    onRemoveFilter: vi.fn(),
    onRemoveLast: vi.fn(),
    onClearFilters: vi.fn(),
    onApplyQuery: vi.fn(),
    onSwitchToQuery: vi.fn(),
    onSwitchToChips: vi.fn(),
  };
  render(
    <FilterBar
      rows={[]}
      filters={filters}
      query=""
      queryMode={queryMode}
      matchCount={42}
      {...handlers}
    />,
  );
  return handlers;
}

const filterBox = () => screen.getByRole("combobox", { name: /Filter logs/ });

describe("FilterBar", () => {
  it("adds Message : text when plain text is typed and Enter pressed", async () => {
    const handlers = renderFilterBar();

    await userEvent.type(filterBox(), "  payment failed {Enter}");

    expect(handlers.onAddFilter).toHaveBeenCalledWith({
      field: "message",
      operator: ":",
      value: "payment failed",
    });
    expect(filterBox()).toHaveProperty("value", "");
  });

  it("builds a chip by picking a property, an operator and a value", async () => {
    const handlers = renderFilterBar();

    await userEvent.click(filterBox());
    await userEvent.click(screen.getByRole("option", { name: /^Service/ }));
    await userEvent.click(screen.getByRole("option", { name: /^Equals/ }));
    await userEvent.type(filterBox(), "api{Enter}");

    expect(handlers.onAddFilter).toHaveBeenCalledWith({ field: "service", operator: "=", value: "api" });
  });

  it("shows values of one property as one chip, leaves levels to the cards, and has no and/or", async () => {
    const handlers = renderFilterBar([
      { field: "service", operator: "=", value: "api" },
      { field: "level", operator: "=", value: "ERROR" },
      { field: "service", operator: "=", value: "worker" },
    ]);

    expect(screen.getByText("Service is one of")).toBeDefined();
    expect(screen.queryByText(/Level/)).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Join filters with" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Remove filter Service = worker" }));

    expect(handlers.onRemoveFilter).toHaveBeenCalledWith(2);
  });

  it("removes the last chip with Backspace", async () => {
    const handlers = renderFilterBar([{ field: "ip", operator: ":", value: "45.142." }]);

    await userEvent.type(filterBox(), "{Backspace}");

    expect(handlers.onRemoveLast).toHaveBeenCalledOnce();
  });

  it("keeps the query behind Show query, with the match count", async () => {
    renderFilterBar([{ field: "service", operator: "=", value: "api" }]);

    expect(screen.queryByText("service:api")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show query" }));

    expect(screen.getByText("service:api")).toBeDefined();
    expect(screen.getByText(/42 matching lines in range/)).toBeDefined();
  });

  it("has no quick filters, search-in or EC2 wording", () => {
    renderFilterBar();

    expect(screen.queryByText(/Quick filters/)).toBeNull();
    expect(screen.queryByText(/Search in/)).toBeNull();
    expect(screen.queryByText(/EC2/)).toBeNull();
  });

  it("runs a text query in query mode, with the count beside Back and no Show query", async () => {
    const handlers = renderFilterBar([], true);

    await userEvent.type(screen.getByRole("searchbox"), "level:ERROR timeout{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "← Back to filters" }));

    expect(handlers.onApplyQuery).toHaveBeenCalledWith("level:ERROR timeout");
    expect(handlers.onSwitchToChips).toHaveBeenCalledOnce();
    expect(screen.getByText("42 matching lines in range")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Show query" })).toBeNull();
  });
});
