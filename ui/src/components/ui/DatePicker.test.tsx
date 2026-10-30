import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DatePicker } from "./DatePicker";
import { TimeSelect } from "./TimeSelect";

describe("DatePicker", () => {
  it("opens a month grid, offers only allowed days and picks one", async () => {
    const onChange = vi.fn();
    render(
      <DatePicker
        label="Start date"
        value="2026-10-30"
        onChange={onChange}
        min="2026-10-23"
        max="2026-10-30"
        today="2026-10-30"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Start date: 30 Oct 2026" }));
    expect(screen.getByText("October 2026")).toBeDefined();
    expect(screen.getByRole("button", { name: "31 Oct 2026" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "22 Oct 2026" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "30 Oct 2026" })).toHaveProperty(
      "ariaPressed",
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "25 Oct 2026" }));

    expect(onChange).toHaveBeenCalledWith("2026-10-25");
    expect(screen.queryByText("October 2026")).toBeNull();
  });

  it("moves between months", async () => {
    render(
      <DatePicker label="End date" value="2026-10-30" onChange={vi.fn()} min="" max="9999" today="" />,
    );

    await userEvent.click(screen.getByRole("button", { name: /^End date/ }));
    await userEvent.click(screen.getByRole("button", { name: "Next month" }));

    expect(screen.getByText("November 2026")).toBeDefined();
  });
});

describe("TimeSelect", () => {
  it("changes the hour and keeps the minute", async () => {
    const onChange = vi.fn();
    render(<TimeSelect label="Start time" value="08:15" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Start time hour"), "14");

    expect(onChange).toHaveBeenCalledWith("14:15");
  });
});
