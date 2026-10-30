from datetime import UTC, datetime, timedelta

import pytest
from fakes import SAMPLE_ADMIN_KEY, SAMPLE_DATA_KEY, FakeApiKeyStore

from spanport_server.core.errors import InvalidKeyError, MissingScopeError
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.services.api_key_auth_service import ApiKeyAuthService

pytestmark = pytest.mark.anyio


async def test_accepts_a_known_data_key() -> None:
    store = FakeApiKeyStore()
    stored = store.add_key(SAMPLE_DATA_KEY)

    record = await ApiKeyAuthService(store).authenticate(SAMPLE_DATA_KEY, KeyType.INGEST)

    assert record == stored


@pytest.mark.parametrize(
    "raw_key",
    [None, "", "sp_admin_looks-like-a-key", "sp_ingest_never-created"],
    ids=["missing", "empty", "wrong-prefix", "unknown"],
)
async def test_rejects_keys_that_are_not_valid_data_keys(raw_key: str | None) -> None:
    store = FakeApiKeyStore()
    store.add_key(SAMPLE_DATA_KEY)

    with pytest.raises(InvalidKeyError):
        await ApiKeyAuthService(store).authenticate(raw_key, KeyType.INGEST)


async def test_rejects_a_revoked_key() -> None:
    store = FakeApiKeyStore()
    store.add_key(SAMPLE_DATA_KEY, revoked_at=datetime(2026, 10, 1, tzinfo=UTC))

    with pytest.raises(InvalidKeyError):
        await ApiKeyAuthService(store).authenticate(SAMPLE_DATA_KEY, KeyType.INGEST)


async def test_accepts_an_admin_key_with_the_needed_scope() -> None:
    store = FakeApiKeyStore()
    stored = store.add_key(
        SAMPLE_ADMIN_KEY,
        KeyType.ADMIN,
        scopes=(Scope.LOGS_READ,),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    record = await ApiKeyAuthService(store).authenticate(
        SAMPLE_ADMIN_KEY, KeyType.ADMIN, required_scope=Scope.LOGS_READ
    )

    assert record == stored


async def test_rejects_an_expired_key() -> None:
    store = FakeApiKeyStore()
    store.add_key(
        SAMPLE_ADMIN_KEY,
        KeyType.ADMIN,
        scopes=(Scope.LOGS_READ,),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(InvalidKeyError):
        await ApiKeyAuthService(store).authenticate(SAMPLE_ADMIN_KEY, KeyType.ADMIN)


async def test_valid_key_without_the_scope_gets_a_scope_error() -> None:
    store = FakeApiKeyStore()
    store.add_key(SAMPLE_ADMIN_KEY, KeyType.ADMIN, expires_at=datetime.now(UTC) + timedelta(1))

    with pytest.raises(MissingScopeError):
        await ApiKeyAuthService(store).authenticate(
            SAMPLE_ADMIN_KEY, KeyType.ADMIN, required_scope=Scope.LOGS_READ
        )


async def test_data_key_is_not_an_admin_key() -> None:
    store = FakeApiKeyStore()
    store.add_key(SAMPLE_DATA_KEY)

    with pytest.raises(InvalidKeyError):
        await ApiKeyAuthService(store).authenticate(SAMPLE_DATA_KEY, KeyType.ADMIN)


async def test_rejection_log_shows_only_the_last_four_characters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(InvalidKeyError):
        await ApiKeyAuthService(FakeApiKeyStore()).authenticate(SAMPLE_DATA_KEY, KeyType.INGEST)

    assert "...a1b2" in caplog.text
    assert SAMPLE_DATA_KEY not in caplog.text
