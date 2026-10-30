"""Log alerts: everyone signed in sees a project's rules and alerts; owners and admins manage
rules; owners, admins and members acknowledge and resolve alerts.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from spanport_server.core.constants import (
    ACKNOWLEDGE_ALERT_EVENT_PATH,
    ALERT_EVENTS_PATH,
    ALERT_RULE_PATH,
    ALERT_RULES_PATH,
    DEFAULT_ALERTS_LIMIT,
    MAX_ALERT_BODY_BYTES,
    MAX_ALERTS_LIMIT,
    RESOLVE_ALERT_EVENT_PATH,
    TEST_ALERT_RULE_PATH,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import (
    get_alert_event_service,
    get_alert_rule_service,
    require_manager,
    require_responder,
    require_signed_in,
)
from spanport_server.schemas.alert import (
    AlertEventListResponse,
    AlertRuleItem,
    AlertRuleListResponse,
    CreateAlertRuleRequest,
    UpdateAlertRuleRequest,
)
from spanport_server.schemas.auth import Caller
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.alert_rule_service import AlertRuleService

router = APIRouter()

Limit = Annotated[int, Query(ge=1, le=MAX_ALERTS_LIMIT)]


@router.get(ALERT_RULES_PATH)
async def list_rules(
    project_id: Annotated[UuidV7, Query()],
    caller: Annotated[Caller, Depends(require_signed_in)],
    rule_service: Annotated[AlertRuleService, Depends(get_alert_rule_service)],
    limit: Limit = DEFAULT_ALERTS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> AlertRuleListResponse:
    """One page of a project's alert rules.

    Raises:
        NotSignedInError (401), NotFoundError: project (404), InvalidRequestError: cursor (400).
    """
    return await rule_service.list_rules(caller, project_id, cursor, limit)


@router.post(ALERT_RULES_PATH, status_code=HTTPStatus.CREATED)
async def create_rule(
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    rule_service: Annotated[AlertRuleService, Depends(get_alert_rule_service)],
    content_type: Annotated[str, Header()] = "",
) -> AlertRuleItem:
    """Add an alert rule to a project.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError: project (404),
        InvalidRequestError: bad field or query, or email not set up (400).
    """
    body = await parse_json_body(
        request, content_type, CreateAlertRuleRequest, MAX_ALERT_BODY_BYTES
    )
    return await rule_service.create_rule(caller, body)


@router.patch(ALERT_RULE_PATH)
async def update_rule(
    rule_id: UuidV7,
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    rule_service: Annotated[AlertRuleService, Depends(get_alert_rule_service)],
    content_type: Annotated[str, Header()] = "",
) -> AlertRuleItem:
    """Change an alert rule (every setting is sent; the project stays the same).

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        InvalidRequestError (400).
    """
    body = await parse_json_body(
        request, content_type, UpdateAlertRuleRequest, MAX_ALERT_BODY_BYTES
    )
    return await rule_service.update_rule(caller, rule_id, body)


@router.delete(ALERT_RULE_PATH, status_code=HTTPStatus.NO_CONTENT)
async def delete_rule(
    rule_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    rule_service: Annotated[AlertRuleService, Depends(get_alert_rule_service)],
) -> None:
    """Delete an alert rule and its alert history.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    await rule_service.delete_rule(caller, rule_id)


@router.post(TEST_ALERT_RULE_PATH, status_code=HTTPStatus.NO_CONTENT)
async def send_test(
    rule_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    rule_service: Annotated[AlertRuleService, Depends(get_alert_rule_service)],
) -> None:
    """Email a test message to the rule's recipients.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        DeliveryError: email not set up or refused (502).
    """
    await rule_service.send_test(caller, rule_id)


@router.get(ALERT_EVENTS_PATH)
async def list_events(
    project_id: Annotated[UuidV7, Query()],
    caller: Annotated[Caller, Depends(require_signed_in)],
    event_service: Annotated[AlertEventService, Depends(get_alert_event_service)],
    limit: Limit = DEFAULT_ALERTS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> AlertEventListResponse:
    """One page of a project's alerts, newest first.

    Raises:
        NotSignedInError (401), NotFoundError: project (404), InvalidRequestError: cursor (400).
    """
    return await event_service.list_events(caller, project_id, cursor, limit)


@router.post(ACKNOWLEDGE_ALERT_EVENT_PATH, status_code=HTTPStatus.NO_CONTENT)
async def acknowledge_event(
    event_id: UuidV7,
    caller: Annotated[Caller, Depends(require_responder)],
    event_service: Annotated[AlertEventService, Depends(get_alert_event_service)],
) -> None:
    """Say "I'm on it" for a firing alert.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    await event_service.acknowledge(caller, event_id)


@router.post(RESOLVE_ALERT_EVENT_PATH, status_code=HTTPStatus.NO_CONTENT)
async def resolve_event(
    event_id: UuidV7,
    caller: Annotated[Caller, Depends(require_responder)],
    event_service: Annotated[AlertEventService, Depends(get_alert_event_service)],
) -> None:
    """Resolve an open alert by hand.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    await event_service.resolve(caller, event_id)
