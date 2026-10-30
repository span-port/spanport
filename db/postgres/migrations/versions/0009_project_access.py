"""Per-project access: members and viewers can be limited to some projects.

Revision ID: 0009
"""

import sqlalchemy
from alembic import op as schema_operations
from sqlalchemy.dialects import postgresql

# Alembic reads these four names; they must keep exactly these names.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add users.all_projects (true for everyone already there), project_members, and the
    access an invite will grant. Deleting a project or user removes their membership rows.
    """
    schema_operations.add_column(
        "users",
        sqlalchemy.Column(
            "all_projects", sqlalchemy.Boolean(), nullable=False, server_default=sqlalchemy.true()
        ),
    )
    schema_operations.add_column(
        "invites",
        sqlalchemy.Column(
            "all_projects", sqlalchemy.Boolean(), nullable=False, server_default=sqlalchemy.true()
        ),
    )
    schema_operations.add_column(
        "invites",
        sqlalchemy.Column(
            "project_ids",
            postgresql.ARRAY(sqlalchemy.Uuid()),
            nullable=False,
            server_default="{}",
        ),
    )
    schema_operations.create_table(
        "project_members",
        sqlalchemy.Column(
            "id", sqlalchemy.Uuid(), primary_key=True, server_default=sqlalchemy.text("uuidv7()")
        ),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        sqlalchemy.Column(
            "project_id",
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sqlalchemy.Column(
            "user_id",
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sqlalchemy.UniqueConstraint("project_id", "user_id"),
    )
    schema_operations.create_index("ix_project_members_org_id", "project_members", ["org_id"])
    schema_operations.create_index(
        "ix_project_members_project_id", "project_members", ["project_id"]
    )
    schema_operations.create_index("ix_project_members_user_id", "project_members", ["user_id"])


def downgrade() -> None:
    """Drop the limits: everyone sees every project of their org again."""
    schema_operations.drop_table("project_members")
    schema_operations.drop_column("invites", "project_ids")
    schema_operations.drop_column("invites", "all_projects")
    schema_operations.drop_column("users", "all_projects")
