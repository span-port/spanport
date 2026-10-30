import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { consoleSeverity, pinoSeverity, winstonSeverity } from "../src/severity.js";

describe("severity mapping", () => {
  it("maps console methods", () => {
    assert.deepEqual(
      (["debug", "log", "info", "warn", "error"] as const).map((m) => consoleSeverity(m).text),
      ["DEBUG", "INFO", "INFO", "WARN", "ERROR"],
    );
  });

  it("maps pino numbers, including custom levels in between", () => {
    assert.deepEqual(
      [10, 20, 30, 35, 40, 50, 60, 70].map((level) => pinoSeverity(level).text),
      ["TRACE", "DEBUG", "INFO", "INFO", "WARN", "ERROR", "FATAL", "FATAL"],
    );
  });

  it("maps winston names, case-insensitively, unknown as INFO", () => {
    assert.deepEqual(
      ["error", "WARN", "info", "http", "verbose", "debug", "silly", "crit", "custom"].map(
        (level) => winstonSeverity(level).text,
      ),
      ["ERROR", "WARN", "INFO", "INFO", "DEBUG", "DEBUG", "TRACE", "FATAL", "INFO"],
    );
  });
});
