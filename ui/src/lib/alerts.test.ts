import { describe, expect, it } from "vitest";

import type { AlertEvent, AlertRule } from "../features/alerts/api";
import {
  alertLogsLink,
  backToNormalText,
  conditionText,
  firedWith,
  howItEnded,
  newAlertLink,
  openFor,
  parseEmailList,
  previewText,
  settingsOf,
  splitAlerts,
  testSentMessage,
  thresholdExplained,
} from "./alerts";

const rule: AlertRule = {
  id: "r1",
  project_id: "p1",
  created_at: "2026-10-30T12:00:00Z",
  name: "Too many errors",
  query: "level:ERROR",
  threshold: 20,
  window_minutes: 5,
  email_recipients: ["oncall@example.com"],
  enabled: true,
};

function alertIn(state: AlertEvent["state"], id: string): AlertEvent {
  return {
    id,
    rule_id: "r1",
    rule_name: "Too many errors",
    query: "level:ERROR",
    threshold: 20,
    window_minutes: 5,
    state,
    matched_count: 21,
    fired_at: "2026-10-30T12:00:00Z",
    recovered_at: null,
    assignee_id: null,
    assigned_to: null,
    acknowledged_at: null,
    acknowledged_by: null,
    resolved_at: null,
    resolved_by: null,
    resolution_note: null,
  };
}

describe("alerts helpers", () => {
  it("says what a rule watches, or any log when it has no search", () => {
    expect(conditionText(rule)).toBe("More than 20 lines matching level:ERROR in 5 min");
    expect(conditionText({ ...rule, query: "", threshold: 0 })).toBe("More than 0 lines of any log in 5 min");
    expect(conditionText({ ...rule, threshold: 1, window_minutes: 1 })).toBe(
      "More than 1 line matching level:ERROR in 1 min",
    );
  });

  it("names the rule and addresses a test email went to", () => {
    expect(testSentMessage(rule)).toBe(
      'Test email for "Too many errors" sent to oncall@example.com. Check the inbox (and spam) of each address.',
    );
  });

  it("spells out the threshold at the server's check interval, including 0 for any line", () => {
    expect(thresholdExplained(20, 5, 10)).toBe(
      "Every 10 seconds, Spanport counts the matching lines of the last 5 minutes. 21 or more sends a Firing email; back to 20 or fewer sends Back to normal.",
    );
    expect(thresholdExplained(0, 1, 30)).toBe(
      "Every 30 seconds, Spanport looks at the last minute. Any matching line sends a Firing email; when none arrive for a minute, it sends Back to normal.",
    );
    expect(thresholdExplained(Number.NaN, 5, 10)).toBe("");
  });

  it("links an alert to the rule's logs around the time it fired", () => {
    const link = new URL(alertLogsLink("p1", { ...alertIn("firing", "a"), window_minutes: 5 }), "http://x");

    expect(link.pathname).toBe("/logs");
    expect(link.searchParams.get("query")).toBe("level:ERROR");
    expect(link.searchParams.get("start")).toBe("2026-10-30T11:55:00.000Z");
    expect(link.searchParams.get("end")).toBe("2026-10-30T12:05:00.000Z");
  });

  it("says what a closed alert fired with, how long it lasted and how it ended", () => {
    const resolved = { ...alertIn("resolved", "a"), threshold: 1, window_minutes: 1, matched_count: 4 };

    expect(firedWith(resolved)).toBe("with 4 lines in 1 min");
    expect(howItEnded({ ...resolved, resolved_by: "Priya" })).toBe("Resolved by Priya");
    // Alerts closed before alerts waited for a person have nobody.
    expect(howItEnded(resolved)).toBe("Closed automatically: back to 1 or fewer matching lines in 1 min");
    expect(howItEnded({ ...resolved, threshold: 0 })).toBe("Closed automatically: back to no matching lines in 1 min");
    expect(backToNormalText(resolved, "3 Nov 03:32")).toBe(
      "Back to normal at 3 Nov 03:32 (1 or fewer matching lines in 1 min); still needs a person to resolve it",
    );
    expect(openFor("2026-11-02T19:27:00Z", "2026-11-02T19:29:10Z")).toBe("after 2 min");
    expect(openFor("2026-11-02T19:27:00Z", "2026-11-02T19:27:20Z")).toBe("after under a minute");
  });

  it("says whether the rule would fire now, firing only above the threshold", () => {
    expect(previewText(20, 20, 5)).toBe("Right now: 20 lines in the last 5 minutes, so this alert would not fire.");
    expect(previewText(1, 0, 1)).toBe("Right now: 1 line in the last 1 minute, so this alert would fire.");
  });

  it("links to a new rule for the project, starting from the Logs search", () => {
    expect(newAlertLink("p1", "level:ERROR")).toBe("/alerts?project=p1&alert-query=level%3AERROR");
  });

  it("keeps only the settings the server accepts", () => {
    expect(Object.keys(settingsOf(rule)).sort()).toEqual([
      "email_recipients",
      "enabled",
      "name",
      "query",
      "threshold",
      "window_minutes",
    ]);
  });

  it("reads emails split any common way, lower case and without repeats", () => {
    expect(parseEmailList(" A@x.com, b@x.com;\nb@x.com  c@x.com\n")).toEqual(["a@x.com", "b@x.com", "c@x.com"]);
    expect(parseEmailList("  ")).toEqual([]);
  });

  it("puts firing alerts first and resolved ones in history", () => {
    const { open, history } = splitAlerts([
      alertIn("acknowledged", "a"),
      alertIn("resolved", "b"),
      alertIn("firing", "c"),
    ]);

    expect(open.map((event) => event.id)).toEqual(["c", "a"]);
    expect(history.map((event) => event.id)).toEqual(["b"]);
  });
});
