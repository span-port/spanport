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
MAX_INGEST_DECOMPRESSED_BYTES = 10 * 1024 * 1024
# Most log records or spans in one request. The collector sends at most 1,000; a larger request
# is refused before any row is built, so a tiny body of empty records can't make millions.
MAX_INGEST_RECORDS = 5_000
# Where records sit in the protobuf: request field 1 (resource_logs / resource_spans), then field
# 2 (scope_logs / scope_spans), then field 2 (log_records / spans). The same for logs and traces.
OTLP_RECORD_FIELD_PATH = (1, 2, 2)
INVALID_OTLP_DETAIL = "The body is not a valid OTLP request."
# Protobuf wire format: a field key is (field number << 3) | wire type; a varint carries 7 bits
# per byte, the high bit saying another byte follows; fixed fields are 8 or 4 bytes.
PROTOBUF_FIELD_NUMBER_SHIFT = 3
PROTOBUF_WIRE_TYPE_MASK = 0b111
VARINT_PAYLOAD_MASK = 0x7F
VARINT_CONTINUE_BIT = 0x80
VARINT_BITS_PER_BYTE = 7
MAX_VARINT_SHIFT = 63
PROTOBUF_FIXED64_BYTES = 8
PROTOBUF_FIXED32_BYTES = 4
TOO_MANY_RECORDS_DETAIL = "A request may hold at most {limit:,} records. Send smaller batches."
# Rows per ClickHouse insert; a larger request is written in several inserts.
CLICKHOUSE_INSERT_CHUNK_ROWS = 1_000
STORAGE_REFUSED_DETAIL = "Storage refused a value in this batch. Check the records' fields."
# Longest values kept from a record; longer ones are cut so one record can't fail a batch.
MAX_LEVEL_TEXT_LENGTH = 32
MAX_SERVICE_NAME_LENGTH = 200
MAX_SPAN_NAME_LENGTH = 1_000
MAX_ATTRIBUTE_KEY_LENGTH = 256
MAX_URL_PATH_LENGTH = 2_048
# The logs table stores severity_number as UInt8; HTTP status codes have three digits.
MAX_SEVERITY_NUMBER = 255
MAX_HTTP_STATUS_DIGITS = 3
# A span longer than this is stored with this duration (a wrong clock, not a real request).
MAX_SPAN_DURATION = timedelta(hours=24)
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
# A database call names its database system: the current OpenTelemetry name, then the older one.
DB_SYSTEM_ATTRIBUTES = ("db.system.name", "db.system")
# HTTP attributes: the current OpenTelemetry names first, then the older ones still sent by
# many libraries.
HTTP_METHOD_ATTRIBUTES = ("http.request.method", "http.method")
HTTP_ROUTE_ATTRIBUTES = ("http.route",)
# Without a route (no framework instrumentation), the request's path stands in for it, with
# id-like parts replaced so requests to the same endpoint group together.
URL_PATH_ATTRIBUTES = ("url.path", "http.target")
URL_QUERY_SEPARATOR = "?"
URL_PATH_SEPARATOR = "/"
ROUTE_ID_PLACEHOLDER = ":id"
# A number, a UUID, 16+ hex characters (e.g. a Mongo ObjectId), or a 20+ character token
# with a digit in it.
ID_SEGMENT_PATTERN = (
    r"^(\d+"
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|[0-9a-fA-F]{16,}"
    r"|(?=[A-Za-z_-]*\d)[A-Za-z0-9_-]{20,})$"
)
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
# "Slower than" on the Requests screen: at most a day.
MAX_MIN_DURATION_MS = 24 * 60 * 60 * 1000
# trace_id is 32 hex characters, span_id 16 (W3C trace context).
TRACE_ID_PATTERN = r"^[0-9a-f]{32}$"
SPAN_ID_PATTERN = r"^[0-9a-f]{16}$"
CURSOR_SPAN_KEY = "span_id"
NO_TRACE_DETAIL = "No trace with this id in this project in the last 30 days."
INVALID_REQUEST_TRACE_DETAIL = "A trace id is 32 hexadecimal characters."
TRACE_RANGE_DETAIL = "start must be within the last 30 days; older traces are gone."
RANGE_ORDER_DETAIL = "end must be after start."

# API monitoring (the APIs screen): per endpoint, speed, errors and where the time goes.
ENDPOINT_SUMMARY_PATH = "/api/v1/endpoints/summary"
# The busiest endpoints are listed; has_more says when there are others.
MAX_ENDPOINTS = 200
# A request's steps start after it does; they are looked for this far past the range's end.
LAYER_SPAN_SLACK = timedelta(hours=1)
ENDPOINT_DETAIL_PATH = "/api/v1/endpoints/detail"
MAX_HTTP_METHOD_LENGTH = 16
# The detail page's chart has about this many points; an interval is never under a minute.
TIMELINE_POINTS = 60
MIN_BUCKET_SECONDS = 60
MAX_ENDPOINT_STEPS = 25
SLOWEST_REQUESTS = 10
# The APIs page's "Slow queries": the database queries with the most total time.
MAX_SLOW_QUERIES = 10
MAX_STATEMENT_LENGTH = 500
# A query's text: the current OpenTelemetry name, then the older one.
DB_QUERY_TEXT_ATTRIBUTES = ("db.query.text", "db.statement")
# Step kinds as the UI names them (database and LLM keep their category's name).
STEP_KIND_EXTERNAL = "external"
STEP_KIND_CODE = "code"
QUANTILE_TYPICAL = 0.5
QUANTILE_SLOW = 0.95
QUANTILE_SLOWEST = 0.99
# How a client span reads in the waterfall: another of your services answered it, or not.
SPAN_LABEL_SERVICE_CALL = "service_call"
SPAN_LABEL_EXTERNAL = "external"
# A request failed when its span status is ERROR or it answered 5xx.
SPAN_STATUS_ERROR = "ERROR"
FIRST_SERVER_ERROR_STATUS = 500

# HTTP errors over time (the Errors screen): 4xx and 5xx answers of incoming requests.
ERROR_SUMMARY_PATH = "/api/v1/errors/summary"
ERROR_WINDOW_PATH = "/api/v1/errors/window"
FIRST_CLIENT_ERROR_STATUS = 400
# One past the last HTTP status code.
END_HTTP_STATUS = 600
# A chosen bar lists its newest failing requests and its (status, API) groups.
ERROR_WINDOW_REQUESTS = 20
MAX_ERROR_GROUPS = 50
# The caller's address: the current OpenTelemetry name, then the older ones.
CLIENT_ADDRESS_ATTRIBUTES = ("client.address", "http.client_ip", "net.peer.ip")
# "What the code logged" for a failing request: its most severe log line, cut to this length.
MAX_LOGGED_LENGTH = 300
ROUTE_REQUIRES_SERVICE_DETAIL = "service: needed when route is given."

# The service map (APIs -> Service map): what calls what, from stored spans.
SERVICE_MAP_PATH = "/api/v1/service-map"
MAX_MAP_EDGES = 200
# A caller's span starts before the request it makes; it is looked for this far before the range.
CALLER_SPAN_SLACK = timedelta(minutes=5)
# A box or line is red above this share of failed calls, orange at this many times the slow-5%
# time of the period before.
MAP_ERROR_SHARE = 0.01
MAP_SLOWER_TIMES = 2
# Node ids: "<kind>:<name>"; your services are kind "service".
MAP_KIND_SERVICE = "service"
MAP_ID_SEPARATOR = ":"
# What a database, an outgoing call and an LLM call are called on the map: the first attribute
# with a value (current OpenTelemetry names first), else the span name.
DB_NAMESPACE_ATTRIBUTES = ("db.namespace", "db.name")
DB_NAME_SEPARATOR = " · "
UNNAMED_DATABASE = "database"
PEER_HOST_ATTRIBUTES = ("server.address", "net.peer.name", "http.host")
PEER_URL_ATTRIBUTES = ("url.full", "http.url")
LLM_PROVIDER_ATTRIBUTES = ("gen_ai.provider.name", "gen_ai.system")

# Sign-in: first-time setup, email and password, server-side sessions
AUTH_SETUP_PATH = "/api/v1/auth/setup"
AUTH_LOGIN_PATH = "/api/v1/auth/login"
AUTH_LOGOUT_PATH = "/api/v1/auth/logout"
AUTH_ME_PATH = "/api/v1/auth/me"
SETUP_TOKEN_LIFETIME = timedelta(hours=1)
# Signed-in users are signed out after this long without a request.
SESSION_IDLE_TIMEOUT = timedelta(hours=8)
# However active, a session ends this long after sign-in (SPANPORT_SESSION_MAX_HOURS).
DEFAULT_SESSION_MAX_HOURS = 168
MAX_SESSION_MAX_HOURS = 30 * 24
SESSION_TOKEN_BYTES = 32
# Argon2 runs in its own threads, at most this many at once, so a flood of sign-ins can neither
# block the event loop nor take every core.
PASSWORD_HASH_THREADS = 4
HASHING_THREAD_PREFIX = "password-hash"
# Postgres advisory lock keys. Setup takes one lock for the whole server; sign-in takes one
# per email, as (namespace, hashtext(email hash)).
SETUP_ADVISORY_LOCK = 7301
LOGIN_ADVISORY_LOCK_NAMESPACE = 7302
# Postgres's name for the unique constraint on users.email (migration 0003).
USERS_EMAIL_UNIQUE = "users_email_key"
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
# One plain address: no separators, quotes, brackets or control characters, so a value like
# "a@x.com,b@y.com" or "Name <a@x.com>" can never turn into several recipients.
EMAIL_PATTERN = (
    r'^[^\s@,;:<>()\[\]"\\\x00-\x1f\x7f]+@[^\s@,;:<>()\[\]"\\\x00-\x1f\x7f]+'
    r'\.[^\s@,;:<>()\[\]"\\\x00-\x1f\x7f]+$'
)
# Rule names and other one-line text: no control characters (CR/LF would break email headers).
SINGLE_LINE_PATTERN = r"^[^\x00-\x1f\x7f]*$"
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
# Defaults and allowed ranges of SPANPORT_LOGIN_FAILURE_LIMIT / _WINDOW_MINUTES.
DEFAULT_LOGIN_FAILURE_LIMIT = 5
MAX_LOGIN_FAILURE_LIMIT = 100
DEFAULT_LOGIN_FAILURE_WINDOW_MINUTES = 15
MAX_LOGIN_FAILURE_WINDOW_MINUTES = 24 * 60
TOO_MANY_LOGINS_DETAIL = "Too many wrong passwords for this email. Try again in {minutes} min."
RETRY_AFTER_HEADER = "Retry-After"
# The client went away before the request was read (nginx's code for it; never seen by anyone).
CLIENT_CLOSED_REQUEST_STATUS = 499
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
# For an email with an account in another organization: says nothing about that account.
NOT_INVITABLE_DETAIL = "This email can't be invited."
ROLE_CHANGED_DETAIL = "This user's role changed meanwhile. Reload the page and try again."
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
# Setup -> Data -> Storage: how much each project keeps in ClickHouse.
STORAGE_PATH = "/api/v1/storage"
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
# Spreadsheets run a cell starting with these as a formula (also after leading spaces); such
# cells get a leading quote.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "|", "\t", "\r", "\n")
CSV_LEADING_SPACE = " "
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
# Real cursors are about 110 characters; anything far longer was made up.
MAX_CURSOR_LENGTH = 256
# A range may end a little ahead (logs can be stamped up to MAX_FUTURE_LOG_SKEW ahead), never
# arbitrarily far in the future.
MAX_RANGE_END_SKEW = timedelta(hours=1)
RANGE_END_DETAIL = "end: must be at most 1 hour from now."
RANGE_OUT_OF_BOUNDS_DETAIL = "start, end: the date is out of range."
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
ALERT_SETTINGS_PATH = "/api/v1/alert-settings"
ALERT_EVENTS_PATH = "/api/v1/alert-events"
ACKNOWLEDGE_ALERT_EVENT_PATH = "/api/v1/alert-events/{event_id}/acknowledge"
RESOLVE_ALERT_EVENT_PATH = "/api/v1/alert-events/{event_id}/resolve"
ASSIGN_ALERT_EVENT_PATH = "/api/v1/alert-events/{event_id}/assign"
# People an alert of a project can be assigned to (members can't list users otherwise).
ALERT_ASSIGNEES_PATH = "/api/v1/alert-assignees"
MAX_RESOLUTION_NOTE_LENGTH = 2000
DEFAULT_ALERTS_LIMIT = 100
MAX_ALERTS_LIMIT = 500
MAX_ALERT_BODY_BYTES = 16 * 1024
MAX_ALERT_NAME_LENGTH = 100
MAX_ALERT_THRESHOLD = 1_000_000
# Defaults and allowed ranges of the SPANPORT_ALERT_* settings. The ceilings also bound the
# request schema, so a body is size-checked before the server's own limit is applied.
DEFAULT_ALERT_MAX_WINDOW_MINUTES = 60
ALERT_WINDOW_CEILING_MINUTES = 24 * 60
DEFAULT_ALERT_MAX_EMAILS = 10
ALERT_EMAILS_CEILING = 100
DEFAULT_ALERT_MAX_RULES_PER_PROJECT = 50
ALERT_RULES_CEILING = 1000
# Each server checks due rules this often; rules are claimed with SKIP LOCKED, so replicas
# never check the same rule twice.
DEFAULT_ALERT_CHECK_SECONDS = 10
MAX_ALERT_CHECK_SECONDS = 300
# A checked rule is due again this much before the next round, so a round that wakes a little
# early (clock drift) still checks it instead of skipping one. The interval must stay above it.
MIN_ALERT_CHECK_SECONDS = 5
ALERT_CHECK_EARLY = timedelta(seconds=2)
# Each check also counts this far before the rule's window: lines reach storage a few seconds
# after their timestamp (SDK and collector batching), so a late line is still counted.
ALERT_CHECK_OVERLAP = timedelta(seconds=15)
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
NO_ASSIGNEE_DETAIL = (
    "user_id: no active owner, admin or member of your organization who can see this project."
)
EMAIL_NOT_SET_UP_DETAIL = (
    "Email isn't set up on this server. Set SPANPORT_SMTP_HOST and SPANPORT_SMTP_FROM."
)
ALERT_WINDOW_LIMIT_DETAIL = "window_minutes: this server allows 1 to {limit} minutes."
ALERT_EMAILS_LIMIT_DETAIL = "email_recipients: this server allows 1 to {limit} addresses."
ALERT_RULES_LIMIT_DETAIL = "This project already has {limit} alert rules, the most allowed."

# ClickHouse: reply only after the rows are written to disk.
LOGS_TABLE = "logs"
CLICKHOUSE_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}
# Reads are limited per query (SPANPORT_CLICKHOUSE_MAX_EXECUTION_SECONDS / _MAX_MEMORY_BYTES, set
# on the client); writes lift those limits (0 means none), since their size is already bounded.
CLICKHOUSE_MAX_EXECUTION_SETTING = "max_execution_time"
CLICKHOUSE_MAX_MEMORY_SETTING = "max_memory_usage"
CLICKHOUSE_WRITE_SETTINGS = {CLICKHOUSE_MAX_EXECUTION_SETTING: 0, CLICKHOUSE_MAX_MEMORY_SETTING: 0}
DEFAULT_CLICKHOUSE_MAX_EXECUTION_SECONDS = 30
MAX_CLICKHOUSE_MAX_EXECUTION_SECONDS = 3_600
DEFAULT_CLICKHOUSE_MAX_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
MIN_CLICKHOUSE_MAX_MEMORY_BYTES = 64 * 1024 * 1024
# ClickHouse error codes for a query stopped by those limits: TIMEOUT_EXCEEDED, TOO_SLOW
# (expected to run past the time limit) and MEMORY_LIMIT_EXCEEDED.
CLICKHOUSE_LIMIT_ERROR_CODES = frozenset({159, 160, 241})
QUERY_TOO_EXPENSIVE_DETAIL = (
    "This query needs more time or memory than the server allows. "
    "Narrow the time range or add filters."
)
# The password .env.example ships with; the server refuses to start with it.
PLACEHOLDER_PASSWORD = "change-me"  # noqa: S105 - the known placeholder, refused at start-up
ENV_EXAMPLE_PLACEHOLDER_DETAIL = "replace the placeholder password from .env.example"
# Data and admin keys are their prefix plus secrets.token_urlsafe(API_KEY_RANDOM_BYTES): 43
# characters of A-Z, a-z, 0-9, "_" and "-". Anything else is refused without a database lookup.
API_KEY_BODY_PATTERN = r"^[A-Za-z0-9_-]{43}$"

# API docs (/docs, /redoc, /openapi.json) are served only with SPANPORT_API_DOCS=true.
API_DOCS_PATH = "/docs"
API_REDOC_PATH = "/redoc"
OPENAPI_PATH = "/openapi.json"

# Rate limits on /api/v1 (in-process token buckets; health and OTLP ingest are never limited).
# Signed-in people and admin keys are limited per caller; routes open without signing in are
# limited per client address. Defaults and allowed ranges of the SPANPORT_RATE_LIMIT_* settings.
API_PATH_PREFIX = "/api/v1/"
AUTHORIZATION_HEADER = "Authorization"
RATE_LIMIT_WINDOW_SECONDS = 60
SECONDS_PER_HOUR = 60 * 60
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
DEFAULT_RATE_LIMIT_PER_MINUTE = 300
DEFAULT_RATE_LIMIT_EXPENSIVE_PER_MINUTE = 120
DEFAULT_RATE_LIMIT_PUBLIC_PER_MINUTE = 20
MAX_RATE_LIMIT_PER_MINUTE = 100_000
# A limiter remembers at most this many callers; the least recently seen is forgotten first.
RATE_LIMIT_MAX_BUCKETS = 100_000
# Routes that run large ClickHouse queries share a lower limit per caller.
EXPENSIVE_PATHS = frozenset(
    {
        LOG_SEARCH_PATH,
        LOG_COUNTS_PATH,
        LOG_EXPORT_PATH,
        ENDPOINT_SUMMARY_PATH,
        ENDPOINT_DETAIL_PATH,
        ERROR_SUMMARY_PATH,
        ERROR_WINDOW_PATH,
        SERVICE_MAP_PATH,
        TRACE_SEARCH_PATH,
    }
)
# Open without signing in, so limited per client address.
PUBLIC_PATHS = frozenset(
    {AUTH_SETUP_PATH, AUTH_LOGIN_PATH, INSPECT_INVITE_PATH, ACCEPT_INVITE_PATH}
)
# nginx (the UI container) sends the browser's address in this header.
REAL_IP_HEADER = "X-Real-IP"
UNKNOWN_CLIENT_ADDRESS = "unknown"
# Limiter keys: who is counted, and for what.
USER_RATE_KEY = "user:{user_id}"
API_KEY_RATE_KEY = "key:{key_id}"
ADDRESS_RATE_KEY = "address:{address}"
EXPENSIVE_RATE_KEY = "expensive:{caller}"
ALERT_TEST_RULE_RATE_KEY = "alert-test-rule:{rule_id}"
ALERT_TEST_USER_RATE_KEY = "alert-test-user:{user_id}"
ALERT_EMAIL_ORG_RATE_KEY = "alert-email:{org_id}"
TAIL_SLOT_KEY = "tail:{org_id}:{caller}"
EXPORT_SLOT_KEY = "export:{org_id}:{caller}"
RATE_LIMITED_DETAIL = "Too many requests. Try again in {seconds} s."
# Testing an alert rule sends real email: once a minute per rule, and a daily cap per person.
ALERT_TEST_RULE_INTERVAL_SECONDS = 60
DEFAULT_ALERT_TESTS_PER_DAY = 20
MAX_ALERT_TESTS_PER_DAY = 10_000
ALERT_TEST_RULE_DETAIL = "This rule was tested less than a minute ago. Try again in {seconds} s."
ALERT_TESTS_PER_DAY_DETAIL = "You sent {limit} test emails in the last day, the most allowed."
# Alert emails per organization per hour (SPANPORT_ALERT_MAX_EMAILS_PER_HOUR); over it, emails
# are skipped and the alert itself is still recorded.
DEFAULT_ALERT_MAX_EMAILS_PER_HOUR = 100
MAX_ALERT_EMAILS_PER_HOUR = 100_000
ALERT_EMAIL_CAP_DETAIL = (
    "This organization sent {limit} alert emails in the last hour, the most allowed. "
    "The email was not sent."
)
# Live tail: the caller's access is checked again this often; a stream lasts at most
# SPANPORT_TAIL_MAX_MINUTES (the UI reconnects); a caller runs at most a few at once.
TAIL_RECHECK_SECONDS = 60
DEFAULT_TAIL_MAX_MINUTES = 60
MAX_TAIL_MAX_MINUTES = 24 * 60
DEFAULT_MAX_TAILS_PER_CALLER = 3
DEFAULT_MAX_EXPORTS_PER_CALLER = 1
MAX_STREAMS_PER_CALLER = 100
# A slot whose stream was torn down without cleanup frees itself after its longest run plus this.
STREAM_SLOT_MARGIN_SECONDS = 60
# An export that has not finished in this time no longer holds its slot.
EXPORT_SLOT_SECONDS = 15 * 60
STREAM_SLOT_RETRY_SECONDS = 15
TOO_MANY_TAILS_DETAIL = "You have {limit} live tails open, the most allowed. Close one first."
TOO_MANY_EXPORTS_DETAIL = "You have {limit} exports running, the most allowed. Wait for one."
