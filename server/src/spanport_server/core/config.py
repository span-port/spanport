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
    DEFAULT_ALERT_MAX_RULES_PER_PROJECT,
    DEFAULT_ALERT_MAX_WINDOW_MINUTES,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOGIN_FAILURE_LIMIT,
    DEFAULT_LOGIN_FAILURE_WINDOW_MINUTES,
    DEFAULT_SMTP_PORT,
    ENV_PREFIX,
    MAX_ALERT_CHECK_SECONDS,
    MAX_LOGIN_FAILURE_LIMIT,
    MAX_LOGIN_FAILURE_WINDOW_MINUTES,
    MIN_ALERT_CHECK_SECONDS,
    UI_URL_DETAIL,
    UI_URL_SCHEMES,
)

LogLevelSetting = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Port = Annotated[int, Field(ge=1, le=65535)]


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
