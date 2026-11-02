"""SDK constants. Code refers to these by name, never by inline value."""

DATA_KEY_PREFIX = "sp_ingest_"
DEFAULT_COLLECTOR_URL = "http://localhost:4318"
DEFAULT_SERVER_URL = "http://localhost:8000"
OTLP_LOGS_PATH = "/v1/logs"
OTLP_TRACES_PATH = "/v1/traces"

# Instrumentations switched on only when installed (they patch libraries the SDK doesn't depend
# on). Each pair is (module, instrumentor class); `pip install spanport[<name>]` installs one.
OPTIONAL_INSTRUMENTATIONS = (
    ("opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor"),
    ("opentelemetry.instrumentation.flask", "FlaskInstrumentor"),
    ("opentelemetry.instrumentation.django", "DjangoInstrumentor"),
    ("opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor"),
    ("opentelemetry.instrumentation.psycopg", "PsycopgInstrumentor"),
    ("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
    ("opentelemetry.instrumentation.requests", "RequestsInstrumentor"),
)
# Separates a decorated class's name from its method in span names, e.g. "UsersService.find".
SPAN_NAME_SEPARATOR = "."
# Instrumentation scope of the steps the SDK records itself (span() and @trace()).
SDK_SCOPE_NAME = "spanport"
CURRENT_API_KEY_PATH = "/api/v1/api-keys/current"
AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "
ALLOWED_URL_SCHEMES = ("http", "https")
KEY_CHECK_TIMEOUT_SECONDS = 5
KEY_CHECK_THREAD_NAME = "spanport-key-check"
VISIBLE_KEY_SUFFIX_LENGTH = 4

# The SDK's own messages go to stderr through this logger and are never exported.
SDK_LOGGER_NAME = "spanport"
SDK_LOG_FORMAT = "%(levelname)s spanport: %(message)s"
# Loggers on the export path. Exporting their records would send logs about sending logs.
EXPORT_PATH_LOGGER_PREFIXES = ("spanport", "opentelemetry", "urllib3", "requests")
