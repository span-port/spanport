"""SQLAlchemy tables. Importing this package registers every table on Base.metadata."""

from spanport_server.models.alert import AlertEvent, AlertRule
from spanport_server.models.api_key import ApiKey
from spanport_server.models.base import Base
from spanport_server.models.tenant import Client, Organization, Project
from spanport_server.models.user import (
    Invite,
    LoginFailure,
    ProjectMember,
    SetupToken,
    User,
    UserSession,
)

__all__ = [
    "AlertEvent",
    "AlertRule",
    "ApiKey",
    "Base",
    "Client",
    "Invite",
    "LoginFailure",
    "Organization",
    "Project",
    "ProjectMember",
    "SetupToken",
    "User",
    "UserSession",
]
