"""API keys: the SDKs' start-up check, and listing, creating and revoking keys from the UI.

Managing keys needs a signed-in owner or admin (with the CSRF header on POST); admin keys can't
manage keys.
"""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from spanport_server.core.constants import (
    API_KEY_PATH,
    API_KEYS_PATH,
    CURRENT_API_KEY_PATH,
    DEFAULT_KEYS_LIMIT,
    MAX_AUTH_BODY_BYTES,
    MAX_KEYS_LIMIT,
    REVOKE_API_KEY_PATH,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_api_key_service, require_data_key, require_manager
from spanport_server.schemas.api_key import (
    ApiKeyItem,
    ApiKeyListResponse,
    ApiKeyRecord,
    CreatedKeyResponse,
    CreateKeyRequest,
    CurrentApiKeyResponse,
    RenameKeyRequest,
    key_item,
)
from spanport_server.schemas.auth import Caller
from spanport_server.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(CURRENT_API_KEY_PATH)
async def get_current_api_key(
    key: Annotated[ApiKeyRecord, Depends(require_data_key)],
) -> CurrentApiKeyResponse:
    """Confirm the caller's data key is valid and say which key it is.

    The key check itself happens in `require_data_key`; an invalid key never reaches this body.

    Returns:
        The key's type and last four characters.

    Raises:
        InvalidKeyError: The key is missing, unknown, revoked or not a data key (401).
    """
    logger.info("data key check ok key=...%s project=%s", key.last_four, key.project_id)
    return CurrentApiKeyResponse(key_type=key.key_type, last_four=key.last_four)


@router.get(API_KEYS_PATH)
async def list_keys(
    caller: Annotated[Caller, Depends(require_manager)],
    key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    limit: Annotated[int, Query(ge=1, le=MAX_KEYS_LIMIT)] = DEFAULT_KEYS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> ApiKeyListResponse:
    """One page of the organization's keys, newest first. Never includes a key or its hash.

    Raises:
        NotSignedInError (401), NotAllowedError (403), InvalidRequestError: bad limit or cursor.
    """
    return await key_service.list_page(caller, cursor, limit)


@router.post(API_KEYS_PATH, status_code=HTTPStatus.CREATED)
async def create_key(
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    content_type: Annotated[str, Header()] = "",
) -> CreatedKeyResponse:
    """Create a data key for a project or an admin key for the organization.

    Returns:
        The full key, shown this once, and its listable details (201).

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError: the project
        isn't in the organization (404), InvalidRequestError: bad fields (400).
    """
    body = await parse_json_body(request, content_type, CreateKeyRequest, MAX_AUTH_BODY_BYTES)
    created = await key_service.create_key(caller, body)
    return CreatedKeyResponse(key=created.raw_key, item=key_item(created.record))


@router.patch(API_KEY_PATH)
async def rename_key(
    key_id: UuidV7,
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    content_type: Annotated[str, Header()] = "",
) -> ApiKeyItem:
    """Give a key a new name; the key itself doesn't change.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        InvalidRequestError: empty or too long name (400).
    """
    body = await parse_json_body(request, content_type, RenameKeyRequest, MAX_AUTH_BODY_BYTES)
    return key_item(await key_service.rename_key(caller, key_id, body.name))


@router.delete(API_KEY_PATH, status_code=HTTPStatus.NO_CONTENT)
async def delete_key(
    key_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> None:
    """Remove a revoked key from the list for good.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError: no revoked key
        with this id (404).
    """
    await key_service.delete_key(caller, key_id)


@router.post(REVOKE_API_KEY_PATH, status_code=HTTPStatus.NO_CONTENT)
async def revoke_key(
    key_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> None:
    """Revoke a key; it stops working on its next request.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError: no active key
        with this id in the organization (404).
    """
    await key_service.revoke_in_org(caller.org_id, key_id, caller.label)
