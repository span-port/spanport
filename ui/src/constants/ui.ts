// Time display, routes and text shown in several places.

export const UTC_ZONE = "UTC";
// en-CA formats parts in year-month-day order; times are assembled from parts anyway.
export const TIME_LOCALE = "en-CA";
// en-GB gives short month names such as "Oct".
export const MONTH_LOCALE = "en-GB";
export const MS_PER_SECOND = 1000;
export const NUMBER_LOCALE = "en-US";
export const GMT_LABEL = "GMT";
export const UTC_OFFSET_ZERO = "UTC+00:00";
export const UTC_LABEL = "UTC";
export const MS_PER_MINUTE = 60_000;
export const MS_PER_DAY = 86_400_000;
// The date picker always shows six weeks, Monday first.
export const DAYS_IN_GRID = 42;
export const DAYS_IN_WEEK = 7;
// "YYYY-MM-DD" is 10 characters; its "YYYY-MM" part is 7.
export const ISO_DAY_LENGTH = 10;
export const ISO_MONTH_LENGTH = 7;
// "HH:MM" of an "HH:MM:SS" time.
export const HOURS_MINUTES_LENGTH = 5;
export const WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] as const;
export const HOURS_IN_DAY = 24;
export const MINUTES_IN_HOUR = 60;
export const UTC_DEFAULT_LABEL = "UTC (default)";
export const BROWSER_ZONE_LABEL = "Browser local time";
// Zones offered besides UTC and the browser's own; the offset is added when shown.
export const TIME_ZONES = [
  { zone: "Asia/Kolkata", label: "India" },
  { zone: "Asia/Singapore", label: "Singapore" },
  { zone: "Asia/Dubai", label: "Dubai" },
  { zone: "Europe/London", label: "London" },
  { zone: "Europe/Berlin", label: "Berlin" },
  { zone: "America/New_York", label: "New York" },
  { zone: "America/Los_Angeles", label: "Los Angeles" },
  { zone: "Australia/Sydney", label: "Sydney" },
] as const;
export const VISIBILITY_EVENT = "visibilitychange";

export const ROOT_ELEMENT_ID = "root";
export const LOGS_ROUTE = "/logs";
export const PROJECTS_ROUTE = "/projects";
export const API_KEYS_ROUTE = "/api-keys";
export const ALERTS_ROUTE = "/alerts";
export const REQUESTS_ROUTE = "/requests";
// One trace's waterfall: /requests/{trace_id}?project=...
export const TRACE_ROUTE = "/requests/:traceId";
export const USERS_ROUTE = "/users";
// Open to anyone with an invite link: /accept-invite?token=...
export const ACCEPT_INVITE_ROUTE = "/accept-invite";
export const INVITE_TOKEN_PARAM = "token";
export const LOGIN_ROUTE = "/login";
export const SETUP_ROUTE = "/setup";
export const ANY_ROUTE = "*";

export const UNREACHABLE_SERVER_MESSAGE =
  "The Spanport server could not be reached. Check that it is running, then retry.";
export const EMPTY_VALUE = "Not set";
export const LATER_RELEASE_NOTE = "Coming in a later release";
export const MANAGERS_ONLY_NOTE =
  "Only owners and admins manage this. Ask one of them if you need a change here.";
export const JSON_INDENT = 2;
// Several copied log lines are NDJSON: one JSON object per line.
export const NDJSON_LINE_END = "\n";
