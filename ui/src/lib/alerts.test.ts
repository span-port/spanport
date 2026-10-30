import { describe, expect, it } from "vitest";

import type { AlertEvent, AlertRule } from "../features/alerts/api";
import {
  conditionText,
  newAlertLink,
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
    acknowledged_at: null,
    acknowledged_by: null,
    resolved_at: null,
    resolved_by: null,
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

  it("spells out the threshold, including 0 for any line", () => {
    expect(thresholdExplained(20, 5)).toBe(
      "Every minute, Spanport counts the matching lines of the last 5 minutes. 21 or more sends a Firing email; back to 20 or fewer sends Resolved.",
    );
    expect(thresholdExplained(0, 1)).toBe(
      "Every minute, Spanport looks at the last minute. Any matching line sends a Firing email; when none arrive for a minute, it sends Resolved.",
    );
    expect(thresholdExplained(Number.NaN, 5)).toBe("");
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
