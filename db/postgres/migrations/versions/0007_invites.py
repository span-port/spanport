"""Invites: owners and admins invite people; the account exists only once they accept.

Revision ID: 0007
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

UUIDV7_DEFAULT = sqlalchemy.text("uuidv7()")


def upgrade() -> None:
    """Create invites. Each foreign key has an index; only the token's hash is stored."""
    schema_operations.create_table(
        "invites",
        sqlalchemy.Column("id", sqlalchemy.Uuid(), primary_key=True, server_default=UUIDV7_DEFAULT),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        sqlalchemy.Column("email", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("role", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("token_hash", sqlalchemy.String(), nullable=False, unique=True),
        sqlalchemy.Column(
            "invited_by",
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=False),
        sqlalchemy.Column("accepted_at", sqlalchemy.DateTime(timezone=True), nullable=True),
        sqlalchemy.Column("cancelled_at", sqlalchemy.DateTime(timezone=True), nullable=True),
        sqlalchemy.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')", name="ck_invites_role"
        ),
        sqlalchemy.CheckConstraint("email = lower(email)", name="ck_invites_email_lower"),
    )
    schema_operations.create_index("ix_invites_org_id", "invites", ["org_id"])
    schema_operations.create_index("ix_invites_invited_by", "invites", ["invited_by"])


def downgrade() -> None:
    """Drop invites; pending invites are lost, accepted ones already became users."""
    schema_operations.drop_table("invites")
