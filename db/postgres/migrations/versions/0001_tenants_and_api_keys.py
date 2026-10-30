"""Organizations, clients, projects and API keys.

Revision ID: 0001
"""

from typing import Any

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Postgres 18's built-in UUIDv7 generator. Postgres has one `uuid` column type for every version,
# so this default is what makes ids v7 even for rows inserted outside the app.
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


def upgrade() -> None:
    """Create the tenant tables and api_keys. Each foreign key is covered by an index."""
    schema_operations.create_table(
        "organizations",
        *id_and_created_at(),
        sqlalchemy.Column("slug", sqlalchemy.String(), nullable=False, unique=True),
    )
    # The unique (org_id, slug) index also serves the org_id foreign key.
    schema_operations.create_table(
        "clients",
        *id_and_created_at(),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        sqlalchemy.Column("slug", sqlalchemy.String(), nullable=False),
        sqlalchemy.UniqueConstraint("org_id", "slug"),
    )
    # The unique (client_id, slug, environment) index also serves the client_id foreign key.
    schema_operations.create_table(
        "projects",
        *id_and_created_at(),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        sqlalchemy.Column(
            "client_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("clients.id"), nullable=False
        ),
        sqlalchemy.Column("slug", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("environment", sqlalchemy.String(), nullable=False),
        sqlalchemy.UniqueConstraint("client_id", "slug", "environment"),
    )
    schema_operations.create_index("ix_projects_org_id", "projects", ["org_id"])
    schema_operations.create_table(
        "api_keys",
        *id_and_created_at(),
        sqlalchemy.Column(
            "org_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("organizations.id"), nullable=False
        ),
        sqlalchemy.Column(
            "project_id", sqlalchemy.Uuid(), sqlalchemy.ForeignKey("projects.id"), nullable=False
        ),
        sqlalchemy.Column("key_type", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("key_hash", sqlalchemy.String(), nullable=False, unique=True),
        sqlalchemy.Column("last_four", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("revoked_at", sqlalchemy.DateTime(timezone=True), nullable=True),
        sqlalchemy.CheckConstraint("key_type IN ('ingest')", name="ck_api_keys_key_type"),
        sqlalchemy.CheckConstraint("length(key_hash) = 64", name="ck_api_keys_key_hash_length"),
    )
    schema_operations.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    schema_operations.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])


def downgrade() -> None:
    """Drop the tables in reverse order of their foreign keys."""
    schema_operations.drop_table("api_keys")
    schema_operations.drop_table("projects")
    schema_operations.drop_table("clients")
    schema_operations.drop_table("organizations")
