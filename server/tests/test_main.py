import pytest

from spanport_server.core.config import DatabaseSettings, Settings, load_settings
from spanport_server.repositories.clickhouse.database import read_limits

REQUIRED_ENV = {
    "SPANPORT_LOG_LEVEL": "INFO",
    "SPANPORT_SERVER_HOST": "127.0.0.1",
    "SPANPORT_SERVER_PORT": "8000",
    "SPANPORT_POSTGRES_HOST": "localhost",
    "SPANPORT_POSTGRES_PORT": "5433",
    "SPANPORT_POSTGRES_USER": "spanport",
    "SPANPORT_POSTGRES_PASSWORD": "secret-postgres-password",
    "SPANPORT_POSTGRES_DB": "spanport",
    "SPANPORT_CLICKHOUSE_HOST": "localhost",
    "SPANPORT_CLICKHOUSE_PORT": "8123",
    "SPANPORT_CLICKHOUSE_USER": "spanport",
    "SPANPORT_CLICKHOUSE_PASSWORD": "secret-clickhouse-password",
    "SPANPORT_CLICKHOUSE_DB": "spanport",
}


@pytest.fixture
def full_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.delenv("SPANPORT_SERVER_RELOAD", raising=False)
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_loads_settings_from_environment(full_env: pytest.MonkeyPatch) -> None:
    settings = load_settings(Settings)

    assert settings.server_port == 8000
    assert settings.server_reload is False
    assert settings.postgres_password.get_secret_value() == "secret-postgres-password"
    assert "secret-postgres-password" not in repr(settings)


def test_database_settings_need_no_server_or_log_settings(full_env: pytest.MonkeyPatch) -> None:
    full_env.delenv("SPANPORT_LOG_LEVEL")
    full_env.delenv("SPANPORT_SERVER_HOST")
    full_env.delenv("SPANPORT_SERVER_PORT")

    settings = load_settings(DatabaseSettings)

    assert settings.log_level == "INFO"
    assert settings.postgres_db == "spanport"


def test_missing_settings_stop_startup_naming_each_variable(full_env: pytest.MonkeyPatch) -> None:
    full_env.delenv("SPANPORT_SERVER_HOST")
    full_env.delenv("SPANPORT_CLICKHOUSE_DB")

    with pytest.raises(SystemExit) as stopped:
        load_settings(Settings)

    message = str(stopped.value.code)
    assert "SPANPORT_SERVER_HOST" in message
    assert "SPANPORT_CLICKHOUSE_DB" in message


def test_invalid_setting_is_named_without_echoing_its_value(full_env: pytest.MonkeyPatch) -> None:
    full_env.setenv("SPANPORT_SERVER_PORT", "99999")

    with pytest.raises(SystemExit) as stopped:
        load_settings(Settings)

    message = str(stopped.value.code)
    assert "SPANPORT_SERVER_PORT" in message
    assert "99999" not in message


@pytest.mark.parametrize("variable", ["SPANPORT_POSTGRES_PASSWORD", "SPANPORT_CLICKHOUSE_PASSWORD"])
def test_refuses_to_start_with_the_placeholder_password(
    full_env: pytest.MonkeyPatch, variable: str
) -> None:
    full_env.setenv(variable, "change-me")

    with pytest.raises(SystemExit) as stopped:
        load_settings(DatabaseSettings)

    message = str(stopped.value.code)
    assert variable in message
    assert "placeholder password" in message


def test_read_limits_default_to_30_seconds_and_2_gib(full_env: pytest.MonkeyPatch) -> None:
    settings = load_settings(DatabaseSettings)

    assert read_limits(settings) == {
        "max_execution_time": 30,
        "max_memory_usage": 2 * 1024 * 1024 * 1024,
    }


def test_read_limits_come_from_the_environment(full_env: pytest.MonkeyPatch) -> None:
    full_env.setenv("SPANPORT_CLICKHOUSE_MAX_EXECUTION_SECONDS", "5")
    full_env.setenv("SPANPORT_CLICKHOUSE_MAX_MEMORY_BYTES", str(512 * 1024 * 1024))

    settings = load_settings(DatabaseSettings)

    assert read_limits(settings) == {
        "max_execution_time": 5,
        "max_memory_usage": 512 * 1024 * 1024,
    }


def test_a_read_limit_of_zero_would_mean_none_so_it_is_refused(
    full_env: pytest.MonkeyPatch,
) -> None:
    full_env.setenv("SPANPORT_CLICKHOUSE_MAX_EXECUTION_SECONDS", "0")

    with pytest.raises(SystemExit):
        load_settings(DatabaseSettings)
