// Errors screen: HTTP errors over time (4xx and 5xx answers of incoming requests).

// The screen's tabs, as in the UI canvas; grouped errors (by exception) come later.
export const ERROR_TABS = [
  { key: "time", label: "HTTP errors", ready: true },
  { key: "grouped", label: "Grouped", ready: false },
] as const;

export const ERROR_SHOW_CHOICES = [
  { key: "all", label: "4xx and 5xx" },
  { key: "5xx", label: "5xx only" },
  { key: "4xx", label: "4xx only" },
] as const;
export type ErrorShow = (typeof ERROR_SHOW_CHOICES)[number]["key"];
export const DEFAULT_ERROR_SHOW: ErrorShow = "all";

// URL params: what to show and which API ("service method route", one value per param).
export const URL_PARAM_SHOW = "show";
export const ALL_APIS = "";

// HTTP status groups: 4xx starts here, 5xx at FIRST_SERVER_ERROR.
export const FIRST_CLIENT_ERROR = 400;
export const FIRST_SERVER_ERROR = 500;
// Server errors above this share of requests are worth a look.
export const NORMAL_SERVER_ERROR_SHARE = 0.0005;
export const NORMAL_SERVER_ERROR_NOTE = "normally under 0.05%";
export const SECONDS_PER_MINUTE = 60;
// A chosen bar lists this many of its newest failing requests (the server's limit).
export const ERROR_WINDOW_REQUESTS = 20;
// "Open error logs" searches for this.
export const ERROR_LOGS_QUERY = "level:ERROR";

// What common status codes mean, in words.
export const STATUS_MEANINGS: Readonly<Record<number, string>> = {
  400: "Bad request",
  401: "Not signed in (wrong or missing credentials)",
  403: "Not allowed",
  404: "Not found",
  405: "Method not allowed",
  409: "Conflict with the current state",
  413: "Request too large",
  422: "Request could not be processed",
  429: "Too many requests (rate limited)",
  500: "Server error (code crashed)",
  502: "Bad answer from another service",
  503: "Service unavailable",
  504: "Timed out waiting for another service",
};

export const ERRORS_DESCRIPTION =
  "4xx (the request was wrong, for example 401 or 404) and 5xx (your server failed, for example 500 or 503) over time. Select a bar to see the exact requests from that moment.";
export const NO_ERRORS_NOTE = "No 4xx or 5xx answers in this range.";
export const SELECT_A_BAR_NOTE = "Select a bar to see the requests from that time.";
