"""Login failures: wrong passwords per email, for the sign-in rate limit.

Revision ID: 0008
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create login_failures; rows older than the 15-minute window are deleted as new ones come."""
    schema_operations.create_table(
        "login_failures",
        sqlalchemy.Column(
            "id", sqlalchemy.Uuid(), primary_key=True, server_default=sqlalchemy.text("uuidv7()")
        ),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
        sqlalchemy.Column("email_hash", sqlalchemy.String(), nullable=False),
    )
    schema_operations.create_index(
        "ix_login_failures_email_hash", "login_failures", ["email_hash", "created_at"]
    )
    schema_operations.create_index("ix_login_failures_created_at", "login_failures", ["created_at"])


def downgrade() -> None:
    """Drop login_failures; every email's failure count starts again from zero."""
    schema_operations.drop_table("login_failures")
