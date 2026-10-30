// Log alerts: the server's limits on a rule, form defaults, messages and the page's tabs.

// Alerts are checked every minute, so the list refreshes about as often.
export const ALERTS_REFRESH_MS = 30_000;
export const DEFAULT_ALERT_THRESHOLD = 20;
export const DEFAULT_ALERT_WINDOW_MINUTES = 5;
export const MAX_ALERT_NAME_LENGTH = 100;
export const MAX_ALERT_THRESHOLD = 1_000_000;
export const MAX_ALERT_WINDOW_MINUTES = 60;
export const MAX_ALERT_EMAILS = 10;
// Addresses may be typed one per line or separated by commas, semicolons or spaces.
export const EMAIL_LIST_SEPARATOR = /[\s,;]+/;
export const EMAIL_LIST_JOINER = ", ";

export const ALERT_NAME_MESSAGE = "Give the alert a name.";
export const ALERT_THRESHOLD_MESSAGE = `Enter a whole number from 0 to ${MAX_ALERT_THRESHOLD.toLocaleString("en")}.`;
export const ALERT_WINDOW_MESSAGE = `Enter 1 to ${String(MAX_ALERT_WINDOW_MINUTES)} minutes.`;
export const ALERT_EMAILS_MESSAGE = `Add 1 to ${String(MAX_ALERT_EMAILS)} email addresses.`;
export const ALERT_EMAIL_INVALID_MESSAGE = "This isn't an email address:";
export const TEST_SENT_HINT = "Check the inbox (and spam) of each address.";

// Ready-made searches, so nobody needs the query syntax for the common alerts.
export const ALERT_SEARCH_PRESETS = [
  { label: "Errors", query: "level:ERROR" },
  { label: "Errors and warnings", query: "level:ERROR OR level:WARN" },
  { label: "Any log", query: "" },
] as const;
// The preview counts matching lines once typing has paused this long.
export const PREVIEW_DEBOUNCE_MS = 500;
export const MS_PER_MINUTE = 60_000;

export const ALERT_TABS = [
  { key: "alerts", label: "Now and history" },
  { key: "rules", label: "Rules" },
] as const;

// The Logs page opens Alerts with its search here, to start a rule from it.
export const URL_PARAM_ALERT_QUERY = "alert-query";
