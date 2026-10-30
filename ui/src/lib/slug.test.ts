import { describe, expect, it } from "vitest";

import { toSlug } from "./slug";

describe("toSlug", () => {
  it("makes the slug the server accepts", () => {
    expect(toSlug("Tracking API")).toBe("tracking-api");
    expect(toSlug("  Globex  Logistics (EU) ")).toBe("globex-logistics-eu");
    expect(toSlug("already-a-slug")).toBe("already-a-slug");
  });

  it("is empty when there are no letters or digits", () => {
    expect(toSlug("!!! ")).toBe("");
  });

  it("stays within 63 characters without a trailing dash", () => {
    const slug = toSlug(`${"a".repeat(62)} b`);

    expect(slug.length).toBeLessThanOrEqual(63);
    expect(slug.endsWith("-")).toBe(false);
  });
});
