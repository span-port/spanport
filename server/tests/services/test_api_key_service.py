from datetime import UTC, datetime

import pytest
from fakes import FakeApiKeyStore, FakeTenantStore

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.key_hashing import hash_api_key
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.services.api_key_service import ApiKeyService

pytestmark = pytest.mark.anyio


async def test_creates_a_data_key_stored_only_as_a_hash() -> None:
    keys = FakeApiKeyStore()
    service = ApiKeyService(FakeTenantStore(), keys)

    created = await service.create_data_key("acme", "northwind", "hr-portal", "production")

    assert created.raw_key.startswith("sp_ingest_")
    assert created.record.key_type == KeyType.INGEST
    assert created.record.last_four == created.raw_key[-4:]
    assert list(keys.records_by_hash) == [hash_api_key(created.raw_key)]


async def test_each_key_is_different_and_belongs_to_the_same_project() -> None:
    service = ApiKeyService(FakeTenantStore(), FakeApiKeyStore())

    first = await service.create_data_key("acme", "northwind", "hr-portal", "production")
    second = await service.create_data_key("acme", "northwind", "hr-portal", "production")

    assert first.raw_key != second.raw_key
    assert first.record.project_id == second.record.project_id


@pytest.mark.parametrize(
    "slugs",
    [
        ("Acme", "northwind", "hr-portal", "production"),
        ("acme", "north wind", "hr-portal", "production"),
        ("acme", "northwind", "-hr", "production"),
        ("acme", "northwind", "hr-portal", ""),
        ("acme", "northwind", "x" * 64, "production"),
    ],
    ids=["uppercase", "space", "leading-dash", "empty", "too-long"],
)
async def test_rejects_invalid_slugs(slugs: tuple[str, str, str, str]) -> None:
    service = ApiKeyService(FakeTenantStore(), FakeApiKeyStore())

    with pytest.raises(InvalidRequestError):
        await service.create_data_key(*slugs)


async def test_creation_log_never_contains_the_raw_key(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    service = ApiKeyService(FakeTenantStore(), FakeApiKeyStore())

    created = await service.create_data_key("acme", "northwind", "hr-portal", "production")

    assert f"key=...{created.raw_key[-4:]}" in caplog.text
    assert created.raw_key not in caplog.text


async def service_with_org() -> tuple[ApiKeyService, FakeApiKeyStore]:
    tenants = FakeTenantStore()
    keys = FakeApiKeyStore()
    await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    return ApiKeyService(tenants, keys), keys


async def test_creates_an_admin_key_that_expires_and_has_scopes() -> None:
    service, keys = await service_with_org()

    created = await service.create_admin_key("acme", (Scope.LOGS_READ,), expires_in_days=30)

    assert created.raw_key.startswith("sp_admin_")
    assert created.record.key_type == KeyType.ADMIN
    assert created.record.project_id is None
    assert created.record.scopes == (Scope.LOGS_READ,)
    assert created.record.expires_at is not None
    days_left = (created.record.expires_at - datetime.now(UTC)).days
    assert 29 <= days_left <= 30
    assert list(keys.records_by_hash) == [hash_api_key(created.raw_key)]


@pytest.mark.parametrize(
    ("scopes", "days", "message"),
    [
        ((), 30, "at least one scope"),
        ((Scope.LOGS_READ,), 0, "within 1 to 90 days"),
        ((Scope.LOGS_READ,), 91, "within 1 to 90 days"),
    ],
    ids=["no-scopes", "zero-days", "over-90-days"],
)
async def test_admin_keys_need_a_scope_and_an_expiry_within_90_days(
    scopes: tuple[Scope, ...], days: int, message: str
) -> None:
    service, _ = await service_with_org()

    with pytest.raises(InvalidRequestError, match=message):
        await service.create_admin_key("acme", scopes, expires_in_days=days)


async def test_admin_key_for_an_unknown_org_is_not_found() -> None:
    service, _ = await service_with_org()

    with pytest.raises(NotFoundError):
        await service.create_admin_key("nobody", (Scope.LOGS_READ,), expires_in_days=30)


async def test_lists_and_revokes_keys_by_id() -> None:
    service, _ = await service_with_org()
    data_key = await service.create_data_key("acme", "northwind", "hr-portal", "production")

    [listed] = [key for key in await service.list_keys("acme") if key.id == data_key.record.id]
    await service.revoke_key("acme", listed.id)

    [revoked] = await service.list_keys("acme")
    assert revoked.revoked_at is not None
    with pytest.raises(NotFoundError):
        await service.revoke_key("acme", listed.id)


async def test_cannot_revoke_a_key_of_another_org() -> None:
    service, _ = await service_with_org()
    other_org_key = await service.create_data_key("globex", "client", "app", "production")

    with pytest.raises(NotFoundError):
        await service.revoke_key("acme", other_org_key.record.id)
