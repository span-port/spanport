// Server endpoints and HTTP details the UI relies on.

export const AUTH_SETUP_PATH = "/api/v1/auth/setup";
export const AUTH_LOGIN_PATH = "/api/v1/auth/login";
export const AUTH_LOGOUT_PATH = "/api/v1/auth/logout";
export const AUTH_ME_PATH = "/api/v1/auth/me";
export const PROJECTS_PATH = "/api/v1/projects";
export const USERS_PATH = "/api/v1/users";
export const INVITES_PATH = "/api/v1/invites";
export const INSPECT_INVITE_PATH = "/api/v1/invites/inspect";
export const ACCEPT_INVITE_PATH = "/api/v1/invites/accept";
// PUT {USERS_PATH}/{id}{PROJECTS_SUFFIX} sets which projects a member or viewer sees.
export const PROJECTS_SUFFIX = "/projects";
// The server's maximum page size; one page holds the organization's people for now.
export const USERS_PAGE_SIZE = 500;
export const API_KEYS_PATH = "/api/v1/api-keys";
// POST {API_KEYS_PATH}/{id}{REVOKE_SUFFIX}
export const REVOKE_SUFFIX = "/revoke";
// POST {PROJECTS_PATH}/{id}{ARCHIVE_SUFFIX | RESTORE_SUFFIX}
export const ARCHIVE_SUFFIX = "/archive";
export const RESTORE_SUFFIX = "/restore";
// The server's maximum page size; one page holds every key for now.
export const KEYS_PAGE_SIZE = 500;
export const ALERT_RULES_PATH = "/api/v1/alert-rules";
export const ALERT_EVENTS_PATH = "/api/v1/alert-events";
// POST {ALERT_RULES_PATH}/{id}{TEST_SUFFIX}; POST {ALERT_EVENTS_PATH}/{id}{ACKNOWLEDGE_SUFFIX | RESOLVE_SUFFIX}
export const TEST_SUFFIX = "/test";
export const ACKNOWLEDGE_SUFFIX = "/acknowledge";
export const RESOLVE_SUFFIX = "/resolve";
// The server's maximum page size; one page holds a project's rules and recent alerts for now.
export const ALERTS_PAGE_SIZE = 500;
export const LOG_SEARCH_PATH = "/api/v1/logs/search";
export const LOG_COUNTS_PATH = "/api/v1/logs/counts";
export const LOG_TAIL_PATH = "/api/v1/logs/tail";
export const LOG_EXPORT_PATH = "/api/v1/logs/export";
export const TRACE_SEARCH_PATH = "/api/v1/traces/search";
// GET {TRACES_PATH}/{trace_id}?project_id=...
export const TRACES_PATH = "/api/v1/traces";
export const CONTENT_DISPOSITION_HEADER = "Content-Disposition";

// The server sets this cookie at sign-in; requests that change something echo it in the header.
export const CSRF_COOKIE = "__Host-sp_csrf";
export const CSRF_HEADER = "X-CSRF-Token";
// document.cookie reads "a=1; b=2".
export const COOKIE_SEPARATOR = "; ";
export const NAME_VALUE_SEPARATOR = "=";
export const JSON_CONTENT_TYPE = "application/json";
export const REQUEST_ID_HEADER = "X-Request-ID";
// Error code for answers that aren't problem+json, e.g. a proxy's 502 page.
export const UNKNOWN_ERROR_CODE = "unknown";

export const STATUS_UNAUTHORIZED = 401;
// 4xx answers mean the request itself is wrong, so retrying it won't help.
export const FIRST_CLIENT_ERROR_STATUS = 400;
export const FIRST_SERVER_ERROR_STATUS = 500;

// The server's maximum page size; one page holds every project for now.
export const PROJECTS_PAGE_SIZE = 500;
// Server data stays fresh this long, so moving around doesn't refetch everything.
export const QUERY_STALE_MS = 30_000;
// Failed reads retry this many times, except 4xx answers, which never retry.
export const MAX_QUERY_RETRIES = 3;

// TanStack Query cache keys.
export const CURRENT_USER_QUERY_KEY = "current-user";
export const PROJECTS_QUERY_KEY = "projects";
export const API_KEYS_QUERY_KEY = "api-keys";
export const LOG_SEARCH_QUERY_KEY = "log-search";
export const LOG_COUNTS_QUERY_KEY = "log-counts";
export const ALERT_RULES_QUERY_KEY = "alert-rules";
export const ALERT_EVENTS_QUERY_KEY = "alert-events";
export const ALERT_PREVIEW_QUERY_KEY = "alert-preview";
export const USERS_QUERY_KEY = "users";
export const TRACE_SEARCH_QUERY_KEY = "trace-search";
export const TRACE_QUERY_KEY = "trace";
export const INVITES_QUERY_KEY = "invites";
export const INVITE_DETAILS_QUERY_KEY = "invite-details";
