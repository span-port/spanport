"""Setup -> Data -> Storage: how much each project keeps. Owners and admins only."""

from typing import Annotated

from fastapi import APIRouter, Depends

from spanport_server.core.constants import STORAGE_PATH
from spanport_server.dependencies import get_storage_service, require_manager
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.storage import StorageResponse
from spanport_server.services.storage_service import StorageService

router = APIRouter()


@router.get(STORAGE_PATH)
async def storage_summary(
    caller: Annotated[Caller, Depends(require_manager)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> StorageResponse:
    """The organization's stored logs and traces per project, with totals and retention.

    Raises:
        NotSignedInError (401), NotAllowedError (403), StorageUnavailableError (503).
    """
    return await storage_service.summary(caller)
