import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ManagersOnly } from "./ManagersOnly";

describe("ManagersOnly", () => {
  it("shows the screen to owners and admins", () => {
    render(
      <ManagersOnly role="admin" title="Users">
        <p>Invite someone</p>
      </ManagersOnly>,
    );

    expect(screen.getByText("Invite someone")).toBeDefined();
  });

  it("shows members and viewers a note instead of forms the server would refuse", () => {
    render(
      <ManagersOnly role="viewer" title="Users">
        <p>Invite someone</p>
      </ManagersOnly>,
    );

    expect(screen.queryByText("Invite someone")).toBeNull();
    expect(screen.getByRole("heading", { name: "Users" })).toBeDefined();
    expect(screen.getByText(/Only owners and admins manage this/)).toBeDefined();
  });
});
