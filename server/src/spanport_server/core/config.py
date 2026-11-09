"""Typed settings read once from SPANPORT_ environment variables."""

import sys
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from spanport_server.core.constants import (
    ALERT_EMAILS_CEILING,
    ALERT_RULES_CEILING,
    ALERT_WINDOW_CEILING_MINUTES,
    DEFAULT_ALERT_CHECK_SECONDS,
    DEFAULT_ALERT_MAX_EMAILS,
    DEFAULT_ALERT_MAX_EMAILS_PER_HOUR,
    DEFAULT_ALERT_MAX_RULES_PER_PROJECT,
    DEFAULT_ALERT_MAX_WINDOW_MINUTES,
    DEFAULT_ALERT_TESTS_PER_DAY,
    DEFAULT_CLICKHOUSE_MAX_EXECUTION_SECONDS,
    DEFAULT_CLICKHOUSE_MAX_MEMORY_BYTES,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOGIN_FAILURE_LIMIT,
    DEFAULT_LOGIN_FAILURE_WINDOW_MINUTES,
    DEFAULT_MAX_EXPORTS_PER_CALLER,
    DEFAULT_MAX_TAILS_PER_CALLER,
    DEFAULT_RATE_LIMIT_EXPENSIVE_PER_MINUTE,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DEFAULT_RATE_LIMIT_PUBLIC_PER_MINUTE,
    DEFAULT_SESSION_MAX_HOURS,
    DEFAULT_SMTP_PORT,
    DEFAULT_TAIL_MAX_MINUTES,
    ENV_EXAMPLE_PLACEHOLDER_DETAIL,
    ENV_PREFIX,
    MAX_ALERT_CHECK_SECONDS,
    MAX_ALERT_EMAILS_PER_HOUR,
    MAX_ALERT_TESTS_PER_DAY,
    MAX_CLICKHOUSE_MAX_EXECUTION_SECONDS,
    MAX_LOGIN_FAILURE_LIMIT,
    MAX_LOGIN_FAILURE_WINDOW_MINUTES,
    MAX_RATE_LIMIT_PER_MINUTE,
    MAX_SESSION_MAX_HOURS,
    MAX_STREAMS_PER_CALLER,
    MAX_TAIL_MAX_MINUTES,
    MIN_ALERT_CHECK_SECONDS,
    MIN_CLICKHOUSE_MAX_MEMORY_BYTES,
    PLACEHOLDER_PASSWORD,
    UI_URL_DETAIL,
    UI_URL_SCHEMES,
)

LogLevelSetting = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Port = Annotated[int, Field(ge=1, le=65535)]


class ApiDocsSettings(BaseSettings):
    """Read when the app is built, before the other settings: whether /docs, /redoc and
    /openapi.json are served (off by default, so a public server doesn't list its API).
    """

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    api_docs: bool = False


class DatabaseSettings(BaseSettings):
    """What migrations, the CLI and repositories need: the two databases and a log level."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    log_level: LogLevelSetting = DEFAULT_LOG_LEVEL

    postgres_host: str
    postgres_port: Port
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str

    clickhouse_host: str
    clickhouse_port: Port
    clickhouse_user: str
    clickhouse_password: SecretStr
    clickhouse_db: str
    # Limits on each read query; a query over them is stopped and the caller told to narrow it.
    clickhouse_max_execution_seconds: int = Field(
        DEFAULT_CLICKHOUSE_MAX_EXECUTION_SECONDS, ge=1, le=MAX_CLICKHOUSE_MAX_EXECUTION_SECONDS
    )
    clickhouse_max_memory_bytes: int = Field(
        DEFAULT_CLICKHOUSE_MAX_MEMORY_BYTES, ge=MIN_CLICKHOUSE_MAX_MEMORY_BYTES
    )

    @field_validator("postgres_password", "clickhouse_password")
    @classmethod
    def check_not_placeholder(cls, password: SecretStr) -> SecretStr:
        """Refuse the placeholder password from .env.example, so no install runs with it."""
        if password.get_secret_value() == PLACEHOLDER_PASSWORD:
            raise ValueError(ENV_EXAMPLE_PLACEHOLDER_DETAIL)
        return password


class Settings(DatabaseSettings):
    """Everything the API server needs: the database settings, where to listen and the
    optional mail server for alert emails.
    """

    server_host: str
    server_port: Port
    server_reload: bool = False

    smtp_host: str | None = None
    smtp_port: Port = DEFAULT_SMTP_PORT
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    # Where people open the UI, e.g. https://spanport.acme.com. Used only for links in alert
    # emails; without it, emails have no buttons.
    ui_url: str | None = None

    # Log alerts: how often rules are checked and what a rule may hold.
    alert_check_seconds: int = Field(
        DEFAULT_ALERT_CHECK_SECONDS, ge=MIN_ALERT_CHECK_SECONDS, le=MAX_ALERT_CHECK_SECONDS
    )
    alert_max_emails: int = Field(DEFAULT_ALERT_MAX_EMAILS, ge=1, le=ALERT_EMAILS_CEILING)
    alert_max_window_minutes: int = Field(
        DEFAULT_ALERT_MAX_WINDOW_MINUTES, ge=1, le=ALERT_WINDOW_CEILING_MINUTES
    )
    alert_max_rules_per_project: int = Field(
        DEFAULT_ALERT_MAX_RULES_PER_PROJECT, ge=1, le=ALERT_RULES_CEILING
    )

    # Sign-in rate limit per email: this many wrong passwords within the window locks it.
    login_failure_limit: int = Field(DEFAULT_LOGIN_FAILURE_LIMIT, ge=1, le=MAX_LOGIN_FAILURE_LIMIT)
    login_failure_window_minutes: int = Field(
        DEFAULT_LOGIN_FAILURE_WINDOW_MINUTES, ge=1, le=MAX_LOGIN_FAILURE_WINDOW_MINUTES
    )
    # However active, a session ends this many hours after sign-in.
    session_max_hours: int = Field(DEFAULT_SESSION_MAX_HOURS, ge=1, le=MAX_SESSION_MAX_HOURS)

    # Requests per minute on /api/v1: per signed-in person or admin key, a lower limit on the
    # routes that run large queries, and per client address on the routes open without signing in.
    rate_limit_per_minute: int = Field(
        DEFAULT_RATE_LIMIT_PER_MINUTE, ge=1, le=MAX_RATE_LIMIT_PER_MINUTE
    )
    rate_limit_expensive_per_minute: int = Field(
        DEFAULT_RATE_LIMIT_EXPENSIVE_PER_MINUTE, ge=1, le=MAX_RATE_LIMIT_PER_MINUTE
    )
    rate_limit_public_per_minute: int = Field(
        DEFAULT_RATE_LIMIT_PUBLIC_PER_MINUTE, ge=1, le=MAX_RATE_LIMIT_PER_MINUTE
    )
    # Test emails of alert rules per person per day (and always at most one a minute per rule).
    rate_limit_alert_tests_per_day: int = Field(
        DEFAULT_ALERT_TESTS_PER_DAY, ge=1, le=MAX_ALERT_TESTS_PER_DAY
    )
    # Live tails and exports one caller may run at once.
    rate_limit_concurrent_tails: int = Field(
        DEFAULT_MAX_TAILS_PER_CALLER, ge=1, le=MAX_STREAMS_PER_CALLER
    )
    rate_limit_concurrent_exports: int = Field(
        DEFAULT_MAX_EXPORTS_PER_CALLER, ge=1, le=MAX_STREAMS_PER_CALLER
    )
    # A live tail ends after this long; the UI opens a new one.
    tail_max_minutes: int = Field(DEFAULT_TAIL_MAX_MINUTES, ge=1, le=MAX_TAIL_MAX_MINUTES)
    # Alert emails per organization per hour; over it, emails are skipped (alerts still open).
    alert_max_emails_per_hour: int = Field(
        DEFAULT_ALERT_MAX_EMAILS_PER_HOUR, ge=1, le=MAX_ALERT_EMAILS_PER_HOUR
    )

    @model_validator(mode="after")
    def check_smtp_from(self) -> Settings:
        """Alert emails need a sender address once a mail server is set."""
        if self.smtp_host and not self.smtp_from:
            raise ValueError("smtp_from is required when smtp_host is set")
        return self

    @field_validator("ui_url")
    @classmethod
    def check_ui_url(cls, ui_url: str | None) -> str | None:
        """Only web addresses, so an email link can never be javascript: or similar."""
        if not ui_url:
            return None
        if not ui_url.startswith(UI_URL_SCHEMES):
            raise ValueError(UI_URL_DETAIL)
        return ui_url.rstrip("/")


def load_settings[SettingsType: BaseSettings](settings_class: type[SettingsType]) -> SettingsType:
    """Read settings from the environment, or stop start-up with a clear message.

    The message names each bad variable and the problem, never its value.

    Args:
        settings_class: DatabaseSettings for migrations and the CLI, Settings for the server.

    Returns:
        The validated settings.

    Raises:
        SystemExit: A variable is missing or invalid.
    """
    try:
        return settings_class()
    except ValidationError as validation_error:
        # Errors from a whole-settings check (e.g. SMTP from address) name no single variable.
        problems = [
            f"{ENV_PREFIX}{str(error['loc'][0]).upper()}: {error['msg']}"
            if error["loc"]
            else error["msg"]
            for error in validation_error.errors()
        ]
        sys.exit("invalid configuration: " + "; ".join(problems))
