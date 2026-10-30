"""API key types and scopes, and the key data passed between layers."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    ADMIN_KEY_PREFIX,
    DATA_KEY_PREFIX,
    MAX_ADMIN_KEY_DAYS,
    MAX_KEY_NAME_LENGTH,
)
from spanport_server.core.ids import UuidV7


class KeyType(StrEnum):
    """Kinds of API key.

    Data keys (ingest) send telemetry for one project. Admin keys read and manage one
    organization through the API, limited by their scopes, and always expire.
    """

    INGEST = "ingest"
    ADMIN = "admin"


class Scope(StrEnum):
    """What an admin key may do."""

    LOGS_READ = "logs:read"
    PROJECTS_READ = "projects:read"


def key_prefix(key_type: KeyType) -> str:
    """Return the prefix every raw key of this type starts with."""
    match key_type:
        case KeyType.INGEST:
            return DATA_KEY_PREFIX
        case KeyType.ADMIN:
            return ADMIN_KEY_PREFIX


@dataclass(frozen=True)
class ApiKeyRecord:
    """A stored key, without its hash. Data keys have a project; admin keys have scopes."""

    id: UuidV7
    org_id: UuidV7
    project_id: UuidV7 | None
    key_type: KeyType
    last_four: str
    scopes: tuple[Scope, ...]
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    # Keys made with the CLI before names existed have none.
    name: str | None = None


class CurrentApiKeyResponse(BaseModel):
    """What the caller's own key is. Never includes the key or its hash."""

    key_type: KeyType
    last_four: str


@dataclass(frozen=True)
class CreatedKey:
    """A new key. `raw_key` is shown once and never stored."""

    raw_key: str
    record: ApiKeyRecord


class CreateKeyRequest(BaseModel):
    """A new key from the UI: a data key for one project, or an admin key with scopes."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_KEY_NAME_LENGTH)
    key_type: KeyType
    project_id: UuidV7 | None = None
    scopes: list[Scope] = Field(default_factory=list, max_length=len(Scope))
    expires_in_days: int = Field(default=MAX_ADMIN_KEY_DAYS, ge=1, le=MAX_ADMIN_KEY_DAYS)


class RenameKeyRequest(BaseModel):
    """A key's new name."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_KEY_NAME_LENGTH)


class ApiKeyItem(BaseModel):
    """A key as the UI lists it: never the key itself or its hash."""

    id: UuidV7
    name: str | None
    key_type: KeyType
    prefix: str
    last_four: str
    project_id: UuidV7 | None
    scopes: list[Scope]
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


def key_item(record: ApiKeyRecord) -> ApiKeyItem:
    """The listable view of a stored key."""
    return ApiKeyItem(
        id=record.id,
        name=record.name,
        key_type=record.key_type,
        prefix=key_prefix(record.key_type),
        last_four=record.last_four,
        project_id=record.project_id,
        scopes=list(record.scopes),
        created_at=record.created_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
    )


class ApiKeyListResponse(BaseModel):
    """A page of keys, newest first. Pass `next_cursor` back to get older ones."""

    data: list[ApiKeyItem]
    next_cursor: str | None
    has_more: bool


class CreatedKeyResponse(BaseModel):
    """A new key. `key` is the full secret, shown this once and never again."""

    key: str
    item: ApiKeyItem
