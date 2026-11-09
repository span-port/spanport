// Pure helpers for log alerts: what a rule says in words, its settings, and email lists.
import {
  EMAIL_LIST_JOINER,
  EMAIL_LIST_SEPARATOR,
  MS_PER_MINUTE,
  TEST_SENT_HINT,
  URL_PARAM_ALERT_QUERY,
} from "../constants/alerts";
import {
  MODE_QUERY,
  RANGE_ABSOLUTE,
  URL_PARAM_END,
  URL_PARAM_MODE,
  URL_PARAM_PROJECT,
  URL_PARAM_QUERY,
  URL_PARAM_RANGE,
  URL_PARAM_START,
} from "../constants/logs";
import { ALERTS_ROUTE, LOGS_ROUTE } from "../constants/ui";
import { isManager } from "./roles";
import type { AlertEvent, AlertRule, AlertRuleSettings, AlertState } from "../features/alerts/api";
import type { CurrentUser } from "../features/auth";

/** The Alerts page, opened on a new rule for this project that starts from `query`. */
export function newAlertLink(projectId: string, query: string): string {
  const params = new URLSearchParams({ [URL_PARAM_PROJECT]: projectId, [URL_PARAM_ALERT_QUERY]: query });
  return `${ALERTS_ROUTE}?${params.toString()}`;
}

/** The Logs page with the rule's search over the window that fired the alert and as long again after it. */
export function alertLogsLink(
  projectId: string,
  event: Pick<AlertEvent, "query" | "fired_at" | "window_minutes">,
): string {
  const firedMs = Date.parse(event.fired_at);
  const windowMs = event.window_minutes * MS_PER_MINUTE;
  const params = new URLSearchParams({
    [URL_PARAM_PROJECT]: projectId,
    [URL_PARAM_RANGE]: RANGE_ABSOLUTE,
    [URL_PARAM_START]: new Date(firedMs - windowMs).toISOString(),
    [URL_PARAM_END]: new Date(firedMs + windowMs).toISOString(),
    [URL_PARAM_QUERY]: event.query,
    [URL_PARAM_MODE]: MODE_QUERY,
  });
  return `${LOGS_ROUTE}?${params.toString()}`;
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
 * The rule's numbers in plain words, e.g. "Every 10 seconds, Spanport counts the matching lines of
 * the last 5 minutes. 21 or more sends a Firing email; back to 20 or fewer sends Resolved."
 */
export function thresholdExplained(threshold: number, windowMinutes: number, checkSeconds: number): string {
  if (!Number.isInteger(threshold) || !Number.isInteger(windowMinutes) || threshold < 0 || windowMinutes < 1) {
    return "";
  }
  const every = `Every ${String(checkSeconds)} seconds`;
  const minutes = windowMinutes === 1 ? "minute" : `${String(windowMinutes)} minutes`;
  if (threshold === 0) {
    const quiet = windowMinutes === 1 ? "a minute" : minutes;
    return `${every}, Spanport looks at the last ${minutes}. Any matching line sends a Firing email; when none arrive for ${quiet}, it sends Back to normal.`;
  }
  return `${every}, Spanport counts the matching lines of the last ${minutes}. ${String(threshold + 1)} or more sends a Firing email; back to ${String(threshold)} or fewer sends Back to normal.`;
}

/** e.g. "with 4 lines in 1 min": what the check counted when the alert fired. */
export function firedWith(event: Pick<AlertEvent, "matched_count" | "window_minutes">): string {
  const lines = event.matched_count === 1 ? "line" : "lines";
  return `with ${event.matched_count.toLocaleString("en")} ${lines} in ${String(event.window_minutes)} min`;
}

/**
 * Who closed an alert, e.g. "Resolved by Priya". Alerts closed before alerts waited for a person
 * have nobody, e.g. "Closed automatically: back to 1 or fewer matching lines in 1 min".
 */
export function howItEnded(event: Pick<AlertEvent, "resolved_by" | "threshold" | "window_minutes">): string {
  if (event.resolved_by !== null) return `Resolved by ${event.resolved_by}`;
  return `Closed automatically: back to ${allowedLines(event.threshold)} in ${String(event.window_minutes)} min`;
}

/** e.g. "Back to normal at 03:32 (1 or fewer matching lines in 1 min); still needs a person to resolve it". */
export function backToNormalText(
  event: Pick<AlertEvent, "threshold" | "window_minutes">,
  recoveredAt: string,
): string {
  return `Back to normal at ${recoveredAt} (${allowedLines(event.threshold)} in ${String(event.window_minutes)} min); still needs a person to resolve it`;
}

/** "no matching lines" or "20 or fewer matching lines": what the rule allows. */
function allowedLines(threshold: number): string {
  return threshold === 0 ? "no matching lines" : `${threshold.toLocaleString("en")} or fewer matching lines`;
}

/** e.g. "after 2 min", "after under a minute": how long an alert stayed open. */
export function openFor(firedAt: string, resolvedAt: string): string {
  const minutes = Math.round((Date.parse(resolvedAt) - Date.parse(firedAt)) / MS_PER_MINUTE);
  return minutes < 1 ? "after under a minute" : `after ${String(minutes)} min`;
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

/** The form's message for a window outside 1 to `maxMinutes` (the server's limit). */
export function windowMessage(maxMinutes: number): string {
  return `Enter 1 to ${String(maxMinutes)} minutes.`;
}

/** The form's message for too few or too many addresses (the server allows up to `maxEmails`). */
export function emailsMessage(maxEmails: number): string {
  return `Add 1 to ${String(maxEmails)} email addresses.`;
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
