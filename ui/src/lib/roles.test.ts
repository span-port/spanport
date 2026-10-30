import { describe, expect, it } from "vitest";

import { isManager } from "./roles";

describe("isManager", () => {
  it("is true only for owners and admins", () => {
    expect(isManager("owner")).toBe(true);
    expect(isManager("admin")).toBe(true);
    expect(isManager("member")).toBe(false);
    expect(isManager("viewer")).toBe(false);
    expect(isManager(undefined)).toBe(false);
  });
});
