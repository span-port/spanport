import { describe, expect, it } from "vitest";

import type { LogItem } from "../features/logs/types";
import { enterChoice, filterSuggestions, stagePrefix } from "./filterSuggestions";

function log(service: string, ip: string): LogItem {
  return {
    log_id: `${service}-${ip}`,
    ts: "2026-10-29T07:00:00Z",
    service,
    level: "INFO",
    message: "ok",
    trace_id: "",
    span_id: "",
    attributes: { "client.ip": ip },
  };
}

describe("filter suggestions", () => {
  it("offers properties, and typed text as a message search", () => {
    const { title, items } = filterSuggestions({ step: "property" }, "le", []);

    expect(title).toBe("Properties");
    expect(items.map((item) => item.label)).toEqual(["Level", 'Message contains "le"']);
  });

  it("offers only the operators a property supports", () => {
    const { items } = filterSuggestions({ step: "operator", field: "level" }, "", []);

    expect(items.map((item) => item.detail)).toEqual(["=", "!="]);
  });

  it("suggests values seen on screen, most frequent first, after the typed value", () => {
    const rows = [log("api", "1.1.1.1"), log("worker", "2.2.2.2"), log("api", "3.3.3.3")];

    const services = filterSuggestions({ step: "value", field: "service", operator: "=" }, "", rows);
    const ips = filterSuggestions({ step: "value", field: "ip", operator: ":" }, "2.2", rows);

    expect(services.items.map((item) => item.label)).toEqual(["api", "worker"]);
    expect(ips.items.map((item) => item.label)).toEqual(['Use "2.2"', "2.2.2.2"]);
  });

  it("always offers the main levels", () => {
    const { items } = filterSuggestions({ step: "value", field: "level", operator: "=" }, "", []);

    expect(items.map((item) => item.label)).toEqual(["ERROR", "WARN", "INFO", "DEBUG"]);
  });

  it("turns Enter into a message search or a finished chip", () => {
    expect(enterChoice({ step: "property" }, "  timeout ")).toEqual({
      action: "chip",
      chip: { field: "message", operator: ":", value: "timeout" },
    });
    expect(enterChoice({ step: "value", field: "level", operator: "!=" }, "DEBUG")).toEqual({
      action: "chip",
      chip: { field: "level", operator: "!=", value: "DEBUG" },
    });
    expect(enterChoice({ step: "operator", field: "level" }, "x")).toBeNull();
    expect(enterChoice({ step: "property" }, "  ")).toBeNull();
  });

  it("shows what is being built", () => {
    expect(stagePrefix({ step: "value", field: "ip", operator: ":" })).toBe("Client IP :");
  });
});
