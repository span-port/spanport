import pytest

from spanport_server.core.config import DatabaseSettings, Settings, load_settings

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
