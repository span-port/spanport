// Log alerts: form defaults and fixed limits, messages and the page's tabs.

// The server's own settings (SPANPORT_ALERT_*) come from GET /api/v1/alert-settings; these
// match its defaults and are used until that answers.
export const DEFAULT_ALERT_LIMITS = {
  check_seconds: 10,
  max_emails: 10,
  max_window_minutes: 60,
  max_rules_per_project: 50,
} as const;
export const MS_PER_SECOND = 1000;
export const DEFAULT_ALERT_THRESHOLD = 20;
export const DEFAULT_ALERT_WINDOW_MINUTES = 5;
export const MAX_ALERT_NAME_LENGTH = 100;
export const MAX_ALERT_THRESHOLD = 1_000_000;
// Addresses may be typed one per line or separated by commas, semicolons or spaces.
export const EMAIL_LIST_SEPARATOR = /[\s,;]+/;
export const EMAIL_LIST_JOINER = ", ";

export const ALERT_NAME_MESSAGE = "Give the alert a name.";
export const ALERT_THRESHOLD_MESSAGE = `Enter a whole number from 0 to ${MAX_ALERT_THRESHOLD.toLocaleString("en")}.`;
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
