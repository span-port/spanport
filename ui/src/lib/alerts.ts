// Pure helpers for log alerts: what a rule says in words, its settings, and email lists.
import { EMAIL_LIST_JOINER, EMAIL_LIST_SEPARATOR, TEST_SENT_HINT, URL_PARAM_ALERT_QUERY } from "../constants/alerts";
import { URL_PARAM_PROJECT } from "../constants/logs";
import { ALERTS_ROUTE } from "../constants/ui";
import { isManager } from "./roles";
import type { AlertEvent, AlertRule, AlertRuleSettings, AlertState } from "../features/alerts/api";
import type { CurrentUser } from "../features/auth";

/** The Alerts page, opened on a new rule for this project that starts from `query`. */
export function newAlertLink(projectId: string, query: string): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId, [URL_PARAM_ALERT_QUERY]: query });
  return `${ALERTS_ROUTE}?${params.toString()}`;
}

/** Just the settings of a rule, as the update call takes them (no id or dates). */
export function settingsOf(rule: AlertRule): AlertRuleSettings {
  return {
    name: rule.name,
    query: rule.query,
    threshold: rule.threshold,
    window_minutes: rule.window_minutes,
    email_recipients: rule.email_recipients,
    enabled: rule.enabled,
  };
}

/** e.g. "More than 20 lines matching level:ERROR in 5 min" ("1 line" when the threshold is 1). */
export function conditionText(rule: Pick<AlertRule, "threshold" | "query" | "window_minutes">): string {
  const search = rule.query ? `matching ${rule.query}` : "of any log";
  const lines = rule.threshold === 1 ? "line" : "lines";
  return `More than ${rule.threshold.toLocaleString("en")} ${lines} ${search} in ${String(rule.window_minutes)} min`;
}

/** e.g. 'Test email for "Too many errors" sent to a@x.com. Check the inbox (and spam).' */
export function testSentMessage(rule: Pick<AlertRule, "name" | "email_recipients">): string {
  return `Test email for "${rule.name}" sent to ${rule.email_recipients.join(EMAIL_LIST_JOINER)}. ${TEST_SENT_HINT}`;
}

/**
 * The rule's numbers in plain words, e.g. "Every minute, Spanport counts the matching lines of the
 * last 5 minutes. 21 or more sends a Firing email; back to 20 or fewer sends Resolved."
 */
export function thresholdExplained(threshold: number, windowMinutes: number): string {
  if (!Number.isInteger(threshold) || !Number.isInteger(windowMinutes) || threshold < 0 || windowMinutes < 1) {
    return "";
  }
  const minutes = windowMinutes === 1 ? "minute" : `${String(windowMinutes)} minutes`;
  if (threshold === 0) {
    const quiet = windowMinutes === 1 ? "a minute" : minutes;
    return `Every minute, Spanport looks at the last ${minutes}. Any matching line sends a Firing email; when none arrive for ${quiet}, it sends Resolved.`;
  }
  return `Every minute, Spanport counts the matching lines of the last ${minutes}. ${String(threshold + 1)} or more sends a Firing email; back to ${String(threshold)} or fewer sends Resolved.`;
}

/** e.g. "Right now: 37 lines in the last 5 minutes, so this alert would fire." */
export function previewText(matched: number, threshold: number, windowMinutes: number): string {
  const verdict = matched > threshold ? "would fire" : "would not fire";
  const lines = matched === 1 ? "line" : "lines";
  const minutes = windowMinutes === 1 ? "minute" : "minutes";
  return `Right now: ${matched.toLocaleString("en")} ${lines} in the last ${String(windowMinutes)} ${minutes}, so this alert ${verdict}.`;
}

/** Addresses typed one per line or separated by commas, semicolons or spaces, without repeats. */
export function parseEmailList(text: string): string[] {
  const addresses = text
    .split(EMAIL_LIST_SEPARATOR)
    .map((address) => address.trim().toLowerCase())
    .filter(Boolean);
  return [...new Set(addresses)];
}

/** Owners and admins add, change and delete rules. */
export function canManageAlertRules(role: CurrentUser["role"] | undefined): boolean {
  return isManager(role);
}

/** Everyone but viewers says "I'm on it" or resolves an alert. */
export function canRespondToAlerts(role: CurrentUser["role"] | undefined): boolean {
  return role !== undefined && role !== "viewer";
}

/** How a state reads on screen. */
export function stateLabel(state: AlertState): string {
  switch (state) {
    case "firing":
      return "Firing";
    case "acknowledged":
      return "Someone is on it";
    case "resolved":
      return "Resolved";
  }
}

/** Open alerts (firing first) to act on now, and the resolved ones as history. */
export function splitAlerts(events: AlertEvent[]): { open: AlertEvent[]; history: AlertEvent[] } {
  const open = events
    .filter((event) => event.state !== "resolved")
    .sort((first, second) => Number(second.state === "firing") - Number(first.state === "firing"));
  return { open, history: events.filter((event) => event.state === "resolved") };
}
