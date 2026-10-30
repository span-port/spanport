"""Server-wide constants. Code refers to these by name, never by inline value."""

from datetime import timedelta
from pathlib import Path
from typing import Final

SERVICE_NAME = "spanport-server"
ENV_PREFIX = "SPANPORT_"
DEFAULT_LOG_LEVEL: Final = "INFO"
APP_IMPORT_PATH = "spanport_server.main:app"
HEALTH_PATH = "/health"
HEALTH_STATUS_OK = "ok"
# The CLI logs to stderr so stdout carries only its output.
CLI_LOG_STREAM = "ext://sys.stderr"

# Migrations. The Docker image keeps the repo layout under /app.
REPO_ROOT = Path(__file__).resolve().parents[4]
ALEMBIC_CONFIG_PATH = REPO_ROOT / "db" / "postgres" / "alembic.ini"
CLICKHOUSE_MIGRATIONS_DIR = REPO_ROOT / "db" / "clickhouse" / "migrations"
CLICKHOUSE_UP_FILE = "up.sql"
CLICKHOUSE_DOWN_FILE = "down.sql"
ALEMBIC_LATEST_REVISION = "head"
ALEMBIC_PREVIOUS_REVISION = "-1"
POSTGRES_DRIVER = "postgresql+asyncpg"

# API keys
DATA_KEY_PREFIX = "sp_ingest_"
ADMIN_KEY_PREFIX = "sp_admin_"
# Admin keys must expire; the database enforces the same limit.
MAX_ADMIN_KEY_DAYS = 90
API_KEY_RANDOM_BYTES = 32
API_KEY_VISIBLE_SUFFIX_LENGTH = 4
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
BEARER_PREFIX = "Bearer "
# The key that made the request; SDKs call it once at start-up to check their data key.
CURRENT_API_KEY_PATH = "/api/v1/api-keys/current"
INVALID_KEY_DETAIL = "Missing or invalid API key."
# Keys and projects are managed from the UI by owners and admins.
API_KEYS_PATH = "/api/v1/api-keys"
REVOKE_API_KEY_PATH = "/api/v1/api-keys/{key_id}/revoke"
DEFAULT_KEYS_LIMIT = 100
MAX_KEYS_LIMIT = 500
MAX_KEY_NAME_LENGTH = 100
MANAGER_ROLES = frozenset({"owner", "admin"})
NOT_A_MANAGER_DETAIL = "Only owners and admins can manage projects and keys."
PROJECT_EXISTS_DETAIL = "This client already has a project with this name in this environment."
KEY_PROJECT_DETAIL = "A data key needs a project_id from your organization."
ADMIN_KEY_PROJECT_DETAIL = "An admin key covers the whole organization; leave project_id out."
ADMIN_KEY_SCOPES_DETAIL = "An admin key needs at least one scope."
NO_ACTIVE_KEY_DETAIL = "No active key with this id in your organization."
NO_KEY_DETAIL = "No key with this id in your organization."
API_KEY_PATH = "/api/v1/api-keys/{key_id}"
PROJECT_PATH = "/api/v1/projects/{project_id}"
ARCHIVE_PROJECT_PATH = "/api/v1/projects/{project_id}/archive"
RESTORE_PROJECT_PATH = "/api/v1/projects/{project_id}/restore"
NO_PROJECT_DETAIL = "No project with this id in your organization."
ARCHIVED_PROJECT_DETAIL = "This project is archived. Restore it before creating keys for it."
ACTIVE_PROJECT_DELETE_DETAIL = "Archive the project before deleting it."
NO_REVOKED_KEY_DETAIL = (
    "No revoked key with this id in your organization. Revoke a key before deleting it."
)

# OTLP log ingest
OTLP_LOGS_PATH = "/v1/logs"
PROTOBUF_CONTENT_TYPE = "application/x-protobuf"
PROBLEM_CONTENT_TYPE = "application/problem+json"
# RFC 9457: "about:blank" means the HTTP status title says it all; `code` gives the detail.
PROBLEM_TYPE_DEFAULT = "about:blank"
REQUEST_ID_HEADER = "X-Request-ID"
GZIP_ENCODING = "gzip"
MAX_INGEST_BODY_BYTES = 10 * 1024 * 1024
MAX_INGEST_DECOMPRESSED_BYTES = 50 * 1024 * 1024
SERVICE_NAME_ATTRIBUTE = "service.name"
UNKNOWN_SERVICE_NAME = "unknown_service"
NANOS_PER_SECOND = 1_000_000_000
# OTLP severity numbers run 1 to 24, four per level: 1-4 TRACE, 5-8 DEBUG, ... 21-24 FATAL.
LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL")
SEVERITY_NUMBERS_PER_LEVEL = 4
UNSPECIFIED_LOG_LEVEL = "UNSPECIFIED"
# Logs are kept 7 days; older ones are dropped at ingest instead of written and deleted.
LOG_RETENTION = timedelta(days=7)
# A log stamped further ahead than this has a wrong clock; it gets the time it was received.
MAX_FUTURE_LOG_SKEW = timedelta(hours=1)

# OTLP trace ingest (spans). Same checks and limits as logs.
OTLP_TRACES_PATH = "/v1/traces"
SPANS_TABLE = "spans"
# Spans are kept 30 days (TRD); older ones are dropped at ingest like old logs.
SPAN_RETENTION = timedelta(days=30)
# What a span was, decided at ingest (TRD "Span classification", first match wins). Whether a
# client call reached another of your services or an outside API is decided when reading a trace.
SPAN_CATEGORY_LLM = "llm"
SPAN_CATEGORY_DB = "db"
SPAN_CATEGORY_CLIENT = "client"
SPAN_CATEGORY_INCOMING = "incoming_request"
SPAN_CATEGORY_CODE = "code"
GEN_AI_ATTRIBUTE_PREFIX = "gen_ai."
DB_SYSTEM_ATTRIBUTE = "db.system"
# HTTP attributes: the current OpenTelemetry names first, then the older ones still sent by
# many libraries.
HTTP_METHOD_ATTRIBUTES = ("http.request.method", "http.method")
HTTP_ROUTE_ATTRIBUTES = ("http.route",)
HTTP_STATUS_ATTRIBUTES = ("http.response.status_code", "http.status_code")
# OTLP enum names arrive as e.g. "SPAN_KIND_SERVER" / "STATUS_CODE_ERROR"; stored without prefix.
SPAN_KIND_PREFIX = "SPAN_KIND_"
STATUS_CODE_PREFIX = "STATUS_CODE_"
SPAN_KIND_UNSPECIFIED = "UNSPECIFIED"
SPAN_STATUS_UNSET = "UNSET"
OUTGOING_SPAN_KINDS = frozenset({"CLIENT", "PRODUCER"})
INCOMING_SPAN_KINDS = frozenset({"SERVER", "CONSUMER"})
NANOS_PER_MICROSECOND = 1_000
NANOS_PER_MILLISECOND = 1_000_000

# Trace search and detail (the Requests screen). Read with the logs:read permission for now.
TRACE_SEARCH_PATH = "/api/v1/traces/search"
TRACE_PATH = "/api/v1/traces/{trace_id}"
DEFAULT_TRACE_SEARCH_LIMIT = 100
MAX_TRACE_SEARCH_LIMIT = 500
# A trace with more spans than this shows the first ones (by start time) and says it was cut.
MAX_TRACE_SPANS = 2_000
MAX_ROUTE_FILTER_LENGTH = 200
# trace_id is 32 hex characters, span_id 16 (W3C trace context).
TRACE_ID_PATTERN = r"^[0-9a-f]{32}$"
SPAN_ID_PATTERN = r"^[0-9a-f]{16}$"
CURSOR_SPAN_KEY = "span_id"
NO_TRACE_DETAIL = "No trace with this id in this project in the last 30 days."
INVALID_REQUEST_TRACE_DETAIL = "A trace id is 32 hexadecimal characters."
TRACE_RANGE_DETAIL = "start must be within the last 30 days; older traces are gone."
# How a client span reads in the waterfall: another of your services answered it, or not.
SPAN_LABEL_SERVICE_CALL = "service_call"
SPAN_LABEL_EXTERNAL = "external"
# A request failed when its span status is ERROR or it answered 5xx.
SPAN_STATUS_ERROR = "ERROR"
FIRST_SERVER_ERROR_STATUS = 500

# Sign-in: first-time setup, email and password, server-side sessions
AUTH_SETUP_PATH = "/api/v1/auth/setup"
AUTH_LOGIN_PATH = "/api/v1/auth/login"
AUTH_LOGOUT_PATH = "/api/v1/auth/logout"
AUTH_ME_PATH = "/api/v1/auth/me"
SETUP_TOKEN_LIFETIME = timedelta(hours=1)
# Signed-in users are signed out after this long without a request.
SESSION_IDLE_TIMEOUT = timedelta(hours=8)
SESSION_TOKEN_BYTES = 32
# __Host- makes browsers require Secure, Path=/ and no Domain, so subdomains can't overwrite them.
SESSION_COOKIE = "__Host-sp_session"
CSRF_COOKIE = "__Host-sp_csrf"
CSRF_HEADER = "X-CSRF-Token"
COOKIE_PATH = "/"
SESSION_COOKIE_SAME_SITE: Final = "lax"
CSRF_COOKIE_SAME_SITE: Final = "strict"
# Methods that change nothing, so they need no CSRF token.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Checked when an email is unknown, so timing doesn't reveal which emails exist.
UNKNOWN_USER_PASSWORD = "spanport-unknown-user"  # noqa: S105 - a decoy, not a credential
MIN_PASSWORD_LENGTH = 12
# Long enough for any passphrase, short enough that hashing can't be used to waste CPU.
MAX_PASSWORD_LENGTH = 256
MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 254
MAX_ORG_NAME_LENGTH = 63
MAX_AUTH_BODY_BYTES = 8 * 1024
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
# An organization name becomes its slug: lower case, every other run of characters one "-".
SLUG_SEPARATOR_PATTERN = r"[^a-z0-9]+"
SLUG_SEPARATOR = "-"
USER_ROLES = ("owner", "admin", "member", "viewer")
INVALID_LOGIN_DETAIL = "The email or password is wrong."
NOT_SIGNED_IN_DETAIL = "Sign in to continue."
CSRF_DETAIL = "The request is missing its CSRF token. Reload the page and try again."
INVALID_SETUP_DETAIL = (
    "This setup token is wrong, already used or expired. Restart the server to print a new one."
)
SETUP_DONE_DETAIL = "Spanport is already set up. Sign in instead."
WEAK_PASSWORD_DETAIL = f"Use a password of at least {MIN_PASSWORD_LENGTH} characters."
UNKNOWN_USER_DETAIL = "No user has this email."
ORG_NAME_DETAIL = "organization: use letters or digits in the name."
# Sign-in rate limit, per email: this many wrong passwords within the window locks that email
# until the oldest of them is older than the window. A successful sign-in clears the count.
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
TOO_MANY_LOGINS_DETAIL = "Too many wrong passwords for this email. Try again in {minutes} min."
RETRY_AFTER_HEADER = "Retry-After"
SECONDS_PER_MINUTE = 60

# Users and invites: owners and admins invite people, change roles and remove users.
USERS_PATH = "/api/v1/users"
USER_PATH = "/api/v1/users/{user_id}"
INVITES_PATH = "/api/v1/invites"
INVITE_PATH = "/api/v1/invites/{invite_id}"
# Open to anyone holding the invite link: see who it is for, then accept it.
INSPECT_INVITE_PATH = "/api/v1/invites/inspect"
ACCEPT_INVITE_PATH = "/api/v1/invites/accept"
INVITE_LIFETIME = timedelta(days=7)
DEFAULT_USERS_LIMIT = 100
MAX_USERS_LIMIT = 500
INVALID_INVITE_DETAIL = (
    "This invite link is wrong, already used, cancelled or expired. Ask for a new one."
)
ACCOUNT_EXISTS_DETAIL = "This email already has a Spanport account."
LAST_OWNER_DETAIL = "The organization needs an owner. Make someone else an owner first."
OWNER_ONLY_DETAIL = "Only owners can make someone an owner or change an owner."
SELF_CHANGE_DETAIL = (
    "You can't change your own role or remove yourself. Ask another owner or admin."
)
NO_USER_DETAIL = "No user with this id in your organization."
NO_INVITE_DETAIL = "No pending invite with this id in your organization."
# Members and viewers may be limited to some projects; owners and admins always see all.
USER_PROJECTS_PATH = "/api/v1/users/{user_id}/projects"
FULL_ACCESS_ROLES = frozenset({"owner", "admin"})
PICK_PROJECTS_DETAIL = "Pick at least one project, or give access to all projects."
UNKNOWN_PROJECTS_DETAIL = "Some of these projects aren't in your organization."
FULL_ACCESS_ROLE_DETAIL = "Owners and admins always see every project."

# Projects API
PROJECTS_PATH = "/api/v1/projects"
DEFAULT_PROJECTS_LIMIT = 100
MAX_PROJECTS_LIMIT = 500

# Log search API
LOG_SEARCH_PATH = "/api/v1/logs/search"
LOG_COUNTS_PATH = "/api/v1/logs/counts"
LOG_TAIL_PATH = "/api/v1/logs/tail"
# Export: the current search as a file, streamed. Larger exports (emailed links) come later.
LOG_EXPORT_PATH = "/api/v1/logs/export"
MAX_EXPORT_LINES = 100_000
EXPORT_BATCH_SIZE = 5_000
EXPORT_FILE_PREFIX = "spanport-logs"
EXPORT_TIME_FORMAT = "%Y%m%d-%H%M"
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"
NDJSON_CONTENT_TYPE = "application/x-ndjson"
CONTENT_DISPOSITION_HEADER = "Content-Disposition"
CSV_COLUMNS = ("ts", "level", "service", "message", "trace_id", "span_id", "client_ip", "user_id")
# Spreadsheets run a cell starting with these as a formula; such cells get a leading quote.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CSV_FORMULA_GUARD = "'"
VIEWER_EXPORT_DETAIL = "Viewers can't export logs. Ask an owner, admin or member."
TOO_MANY_TO_EXPORT_DETAIL = (
    "This search matches {count:,} lines; an export holds at most {limit:,}. "
    "Narrow the time range or add filters."
)
# Live tail: look at the last 30 s every 2 s, so logs that arrive a few seconds late still show.
TAIL_POLL_SECONDS = 2
TAIL_WINDOW = timedelta(seconds=30)
TAIL_BATCH_LIMIT = 500
# Keeps idle proxies from closing the stream.
TAIL_HEARTBEAT_SECONDS = 15
SSE_CONTENT_TYPE = "text/event-stream"
SSE_LOGS_EVENT = "logs"
SSE_HEARTBEAT = ": heartbeat\n\n"
# Sent the moment a stream opens: proxies (Vite's dev proxy, some nginx setups) hold the
# response headers until the first body byte, so without it the UI waits on "Connecting".
SSE_OPENED = ": connected\n\n"
# Streams must not be buffered by proxies (nginx honours this header).
STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
JSON_CONTENT_TYPE = "application/json"
# Pydantic messages read "<general reason>, <detail>"; the detail can quote the input.
VALIDATION_DETAIL_SEPARATOR = ", "
MAX_SEARCH_BODY_BYTES = 64 * 1024
DEFAULT_SEARCH_LIMIT = 100
MAX_SEARCH_LIMIT = 500
MAX_FILTER_CHIPS = 20
MAX_FILTER_VALUE_LENGTH = 500
MAX_QUERY_LENGTH = 2000
# Brackets deeper than this are refused, so a crafted query can't exhaust the stack.
MAX_QUERY_NESTING = 20
# A field in a chip or a "field:value" term: letters, digits, "_", "." and "-".
FIELD_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.\-]{0,99}$"
# Fields that are real columns of the logs table; any other field is an attribute key.
LOG_COLUMN_FIELDS = ("level", "service", "message", "trace_id", "span_id")
# Short names the query language accepts, e.g. ip:45.142.* means attributes['client.ip'].
LOG_FIELD_ALIASES = {"ip": "client.ip", "user": "user.id", "trace": "trace_id", "span": "span_id"}
STORAGE_UNAVAILABLE_DETAIL = "Log storage is unavailable. Retry later."
INVALID_CURSOR_DETAIL = "The cursor is not valid. Start again without it."
# Keys inside the opaque paging cursor (base64url JSON).
CURSOR_TIME_KEY = "ts"
CURSOR_ID_KEY = "log_id"
LOG_LEVEL_COLUMN = "level"
LOG_MESSAGE_COLUMN = "message"
# ClickHouse's token index only accepts plain alphanumeric words; other text is a substring search.
SEARCH_WORD_PATTERN = r"^[A-Za-z0-9]+$"
# Characters with a meaning in ILIKE, escaped so they match literally.
LIKE_SPECIAL_CHARACTERS_PATTERN = r"([\\%_])"
# "*" in a value matches anything.
QUERY_WILDCARD = "*"
QUERY_WORD_BREAKS = '()"'
QUERY_PHRASE_QUOTE = '"'
QUERY_FIELD_SEPARATOR = ":"
QUERY_EXCLUDE_PREFIX = "-"
QUERY_KEYWORD_AND = "AND"
QUERY_KEYWORD_OR = "OR"
QUERY_KEYWORD_NOT = "NOT"

# Log alerts
ALERT_RULES_PATH = "/api/v1/alert-rules"
ALERT_RULE_PATH = "/api/v1/alert-rules/{rule_id}"
TEST_ALERT_RULE_PATH = "/api/v1/alert-rules/{rule_id}/test"
ALERT_EVENTS_PATH = "/api/v1/alert-events"
ACKNOWLEDGE_ALERT_EVENT_PATH = "/api/v1/alert-events/{event_id}/acknowledge"
RESOLVE_ALERT_EVENT_PATH = "/api/v1/alert-events/{event_id}/resolve"
DEFAULT_ALERTS_LIMIT = 100
MAX_ALERTS_LIMIT = 500
MAX_ALERT_BODY_BYTES = 16 * 1024
MAX_ALERT_NAME_LENGTH = 100
MAX_ALERT_THRESHOLD = 1_000_000
MAX_ALERT_WINDOW_MINUTES = 60
MAX_ALERT_EMAILS = 10
# Each server checks due rules this often; rules are claimed with SKIP LOCKED, so replicas
# never check the same rule twice.
ALERT_CHECK_INTERVAL = timedelta(minutes=1)
ALERT_CHECK_BATCH = 100
NOTIFY_TIMEOUT_SECONDS = 10
DEFAULT_SMTP_PORT = 587
# Port 465 speaks TLS from the first byte (SMTPS); other ports start plain and may STARTTLS.
SMTPS_PORT = 465
SMTP_DISCONNECTED_DETAIL = (
    "The mail server closed the connection. Check SPANPORT_SMTP_PORT: use 587 with "
    "SPANPORT_SMTP_STARTTLS=true, or 465 (SSL)."
)
SMTP_LOGIN_DETAIL = (
    "The mail server refused the username or password (SPANPORT_SMTP_USERNAME and "
    "SPANPORT_SMTP_PASSWORD). Gmail and Outlook need an app password, not your normal one."
)
SMTP_RECIPIENTS_DETAIL = "The mail server refused one or more recipient addresses."
SMTP_SENDER_DETAIL = "The mail server refused the sender address (SPANPORT_SMTP_FROM)."
SMTP_UNREACHABLE_DETAIL = (
    "The mail server can't be reached. Check SPANPORT_SMTP_HOST and SPANPORT_SMTP_PORT."
)
SMTP_OTHER_DETAIL = "Email could not be sent: {reason}."
ALERT_EMAIL_SUBJECT_PREFIX = "[Spanport]"
# Alert emails: an HTML template (with a plain-text part for clients that show only text).
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
ALERT_EMAIL_TEMPLATE = "alert_email.html"
ALERT_EMAIL_ROW_TEMPLATE = "alert_email_row.html"
EMAIL_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"
EMAIL_TEXT_FONT = "inherit"
EMAIL_CODE_FONT = "Consolas,Menlo,monospace"
ALERT_EMAIL_BUTTON_TEMPLATE = "alert_email_button.html"
# Buttons in alert emails link into the UI at SPANPORT_UI_URL (optional; no buttons without it).
# These routes and URL params must match ui/src/constants (ui.ts and logs.ts).
UI_URL_SCHEMES = ("http://", "https://")
UI_ALERTS_ROUTE = "/alerts"
UI_LOGS_ROUTE = "/logs"
UI_PARAM_PROJECT = "project"
UI_PARAM_RANGE = "range"
UI_RANGE_ABSOLUTE = "absolute"
UI_PARAM_START = "start"
UI_PARAM_END = "end"
UI_PARAM_QUERY = "query"
UI_PARAM_MODE = "mode"
UI_MODE_QUERY = "query"
UI_URL_DETAIL = "ui_url must start with http:// or https://"
EMAIL_BUTTON_TEXT_COLOR = "#ffffff"
EMAIL_SECONDARY_BUTTON_COLOR = "#12161c"
EMAIL_FIRING_COLOR = "#e5484d"
EMAIL_RESOLVED_COLOR = "#30a46c"
EMAIL_TEST_COLOR = "#12a594"
# Roles that may acknowledge and resolve alerts; viewers only look.
RESPONDER_ROLES = frozenset({"owner", "admin", "member"})
NOT_A_RESPONDER_DETAIL = "Viewers can't acknowledge or resolve alerts."
NO_ALERT_RULE_DETAIL = "No alert rule with this id in your organization."
NO_OPEN_ALERT_DETAIL = "No open alert with this id in your organization."
EMAIL_NOT_SET_UP_DETAIL = (
    "Email isn't set up on this server. Set SPANPORT_SMTP_HOST and SPANPORT_SMTP_FROM."
)

# ClickHouse: reply only after the rows are written to disk.
LOGS_TABLE = "logs"
CLICKHOUSE_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}
