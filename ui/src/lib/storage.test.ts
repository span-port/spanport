import { describe, expect, it } from "vitest";

import { formatBytes, sharePercent } from "./storage";

describe("storage helpers", () => {
  it("writes sizes in 1024 steps, one decimal under 10", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(3_500)).toBe("3.4 KB");
    expect(formatBytes(12 * 1024 * 1024)).toBe("12 MB");
    expect(formatBytes(1.25 * 1024 ** 3)).toBe("1.3 GB");
  });

  it("gives each project's share of everything stored", () => {
    expect(sharePercent(25, 100)).toBe(25);
    expect(sharePercent(0, 0)).toBe(0);
  });
});
