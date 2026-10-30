import { describe, expect, it } from "vitest";

import { environmentChoices, environmentLabel, similarEnvironment } from "./environments";

describe("environments", () => {
  it("offers the standard ones, then used ones, then added ones, each once", () => {
    expect(environmentChoices(["qa", "production"], ["uat", "qa"])).toEqual([
      "production",
      "staging",
      "development",
      "qa",
      "uat",
    ]);
  });

  it("flags names that look like an existing environment", () => {
    const existing = ["production", "staging", "qa"];

    expect(similarEnvironment("prod", existing)).toBe("production");
    expect(similarEnvironment("stag", existing)).toBe("staging");
    expect(similarEnvironment("qa-eu", existing)).toBe("qa");
    expect(similarEnvironment("production", existing)).toBeNull();
    expect(similarEnvironment("uat", existing)).toBeNull();
    expect(similarEnvironment("", existing)).toBeNull();
  });

  it("labels standard environments and shows others as they are", () => {
    expect(environmentLabel("staging")).toBe("Staging");
    expect(environmentLabel("qa")).toBe("qa");
  });
});
