"""People who sign in to the UI, their sessions, and the first-time setup token.

Revision ID: 0003
"""

from typing import Any

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UUIDV7_DEFAULT = sqlalchemy.text("uuidv7()")


def id_and_created_at() -> list[sqlalchemy.Column[Any]]:
    """Columns every table starts with: a UUIDv7 primary key and a UTC creation time."""
    return [
        sqlalchemy.Column("id", sqlalchemy.Uuid(), primary_key=True, server_default=UUIDV7_DEFAULT),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
    ]


def optional_time(name: str) -> sqlalchemy.Column[Any]:
    """A nullable UTC timestamp column, e.g. when something was revoked."""
    return sqlalchemy.Column(name, sqlalchemy.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    """Create users, user_sessions and setup_tokens. Each foreign key has an index."""
    schema_operations.create_table(
        "users",
        *id_and_created_at(),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        # Stored lower case, so the unique index makes emails unique regardless of case.
        sqlalchemy.Column("email", sqlalchemy.String(), nullable=False, unique=True),
        sqlalchemy.Column("name", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("password_hash", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("role", sqlalchemy.String(), nullable=False),
        optional_time("disabled_at"),
        sqlalchemy.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')", name="ck_users_role"
        ),
        sqlalchemy.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
    )
    schema_operations.create_index("ix_users_org_id", "users", ["org_id"])
    # A session is a random id in an HttpOnly cookie; only its hash is stored.
    schema_operations.create_table(
        "user_sessions",
        *id_and_created_at(),
        sqlalchemy.Column(
            "user_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("users.id"), nullable=False
        ),
        sqlalchemy.Column("token_hash", sqlalchemy.String(), nullable=False, unique=True),
        sqlalchemy.Column("csrf_hash", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column(
            "last_seen_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
        optional_time("revoked_at"),
    )
    schema_operations.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    schema_operations.create_table(
        "setup_tokens",
        *id_and_created_at(),
        sqlalchemy.Column("token_hash", sqlalchemy.String(), nullable=False, unique=True),
        sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=False),
        optional_time("used_at"),
    )


def downgrade() -> None:
    """Drop the three tables; every user and session is lost."""
    schema_operations.drop_table("setup_tokens")
    schema_operations.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    schema_operations.drop_table("user_sessions")
    schema_operations.drop_index("ix_users_org_id", table_name="users")
    schema_operations.drop_table("users")
