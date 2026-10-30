import { describe, expect, it } from "vitest";

import {
  formatLogTime,
  formatTableTime,
  utcToZonedInputs,
  zonedInputsToUtc,
  zoneOffsetLabel,
} from "./formatTime";

describe("time display", () => {
  it("shows the same moment in UTC and in another zone, to the millisecond", () => {
    const loggedAt = "2026-10-29T07:00:01.123456Z";

    expect(formatLogTime(loggedAt, "UTC")).toBe("2026-10-29 07:00:01.123");
    expect(formatLogTime(loggedAt, "Asia/Kolkata")).toBe("2026-10-29 12:30:01.123");
    expect(formatTableTime(loggedAt, "Asia/Kolkata")).toBe("29 Oct 12:30:01.123");
  });

  it("names the zone's offset, following daylight saving", () => {
    expect(zoneOffsetLabel("UTC", new Date("2026-10-29T00:00:00Z"))).toBe("UTC+00:00");
    expect(zoneOffsetLabel("Asia/Kolkata", new Date("2026-10-29T00:00:00Z"))).toBe("UTC+05:30");
    expect(zoneOffsetLabel("America/New_York", new Date("2026-07-01T00:00:00Z"))).toBe("UTC-04:00");
    expect(zoneOffsetLabel("America/New_York", new Date("2026-12-01T00:00:00Z"))).toBe("UTC-05:00");
  });
});

describe("typed times", () => {
  it("reads typed times in the chosen zone", () => {
    expect(zonedInputsToUtc("2026-10-29", "12:30", "Asia/Kolkata")).toBe(Date.parse("2026-10-29T07:00:00Z"));
    expect(zonedInputsToUtc("2026-10-29", "07:00:05", "UTC")).toBe(Date.parse("2026-10-29T07:00:05Z"));
  });

  it("follows daylight saving on both sides of the change", () => {
    expect(zonedInputsToUtc("2026-07-01", "09:00", "America/New_York")).toBe(Date.parse("2026-07-01T13:00:00Z"));
    expect(zonedInputsToUtc("2026-12-01", "09:00", "America/New_York")).toBe(Date.parse("2026-12-01T14:00:00Z"));
  });

  it("is NaN for incomplete input and round-trips complete input", () => {
    const moment = Date.parse("2026-10-29T07:00:05Z");

    expect(zonedInputsToUtc("", "12:30", "UTC")).toBeNaN();
    expect(utcToZonedInputs(moment, "Asia/Kolkata")).toEqual({ date: "2026-10-29", time: "12:30:05" });
    const { date, time } = utcToZonedInputs(moment, "Australia/Sydney");
    expect(zonedInputsToUtc(date, time, "Australia/Sydney")).toBe(moment);
  });
});
