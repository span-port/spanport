import { describe, expect, it } from "vitest";

import { fileNameFromDisposition } from "./download";

describe("fileNameFromDisposition", () => {
  it("reads the server's file name, or falls back", () => {
    expect(fileNameFromDisposition('attachment; filename="spanport-logs-a-b-c-20261030-1421.csv"', "x")).toBe(
      "spanport-logs-a-b-c-20261030-1421.csv",
    );
    expect(fileNameFromDisposition(null, "spanport-logs")).toBe("spanport-logs");
    expect(fileNameFromDisposition("attachment", "spanport-logs")).toBe("spanport-logs");
  });
});
