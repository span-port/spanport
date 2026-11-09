import { describe, expect, it } from "vitest";

import { brandLogo, luminance } from "./mapLogos";

describe("Service map logos", () => {
  it("finds the brand in a database, host or provider name", () => {
    expect(brandLogo("db", "postgresql · kosha")?.title).toBe("PostgreSQL");
    expect(brandLogo("external", "api.github.com")?.title).toBe("GitHub");
    expect(brandLogo("llm", "anthropic")?.title).toBe("Anthropic");
    expect(brandLogo("llm", "generativelanguage.googleapis.com")?.title).toBe("Google Gemini");
    expect(brandLogo("external", "maps.googleapis.com")?.title).toBe("Google");
  });

  it("leaves your services and unknown names to the drawn icons", () => {
    expect(brandLogo("service", "postgres-proxy")).toBeNull();
    expect(brandLogo("external", "iirm-envvariables.s3.ap-south-1.amazonaws.com")).toBeNull();
    expect(brandLogo("external", "promotion.example.com")).toBeNull();
  });

  it("draws dark brand colours in the text colour so they show on dark boxes", () => {
    expect(luminance("FFFFFF")).toBeCloseTo(1);
    expect(luminance("000000")).toBe(0);
    expect(brandLogo("external", "api.github.com")?.color).toBeNull();
    expect(brandLogo("db", "postgresql")?.color).toBe("#4169E1");
  });
});
