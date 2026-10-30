import { describe, expect, it } from "vitest";

import { passwordStrength, strengthFill, strengthMessage } from "./passwordStrength";

describe("password strength", () => {
  it("needs 12 characters and three kinds of character to be strong", () => {
    expect(passwordStrength("")).toBe("empty");
    expect(passwordStrength("Short1!")).toBe("weak");
    expect(passwordStrength("alllowercaseletters")).toBe("weak");
    expect(passwordStrength("Mixed case 2026")).toBe("strong");
  });

  it("fills the meter one step for length and one per kind", () => {
    expect(strengthFill("")).toBe(0);
    expect(strengthFill("abc")).toBeCloseTo(0.2);
    expect(strengthFill("Abcdefghijk1!")).toBe(1);
  });

  it("says what to do", () => {
    expect(strengthMessage("empty")).toBe("At least 12 characters");
    expect(strengthMessage("strong")).toBe("Strong password");
  });
});
