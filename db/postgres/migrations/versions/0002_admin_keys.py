"""Admin keys: organization-wide, scoped and always expiring.

Revision ID: 0002
"""

import sqlalchemy
from alembic import op as schema_operations
from sqlalchemy.dialects import postgresql

# Alembic reads these four names; they must keep exactly these names.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLE = "api_keys"


def upgrade() -> None:
    """Let api_keys hold admin keys: optional project, scopes, expiry, and checks per key type."""
    schema_operations.alter_column(TABLE, "project_id", nullable=True)
    schema_operations.add_column(
        TABLE,
        sqlalchemy.Column(
            "scopes",
            postgresql.ARRAY(sqlalchemy.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    schema_operations.add_column(
        TABLE, sqlalchemy.Column("expires_at", sqlalchemy.DateTime(timezone=True), nullable=True)
    )
    schema_operations.drop_constraint("ck_api_keys_key_type", TABLE, type_="check")
    schema_operations.create_check_constraint(
        "ck_api_keys_key_type", TABLE, "key_type IN ('ingest', 'admin')"
    )
    # Data keys belong to a project; admin keys to the whole organization.
    schema_operations.create_check_constraint(
        "ck_api_keys_project_by_type",
        TABLE,
        "(key_type = 'ingest' AND project_id IS NOT NULL) "
        "OR (key_type = 'admin' AND project_id IS NULL)",
    )
    # Admin keys must expire within 90 days of creation.
    schema_operations.create_check_constraint(
        "ck_api_keys_admin_expiry",
        TABLE,
        "key_type <> 'admin' OR "
        "(expires_at IS NOT NULL AND expires_at <= created_at + interval '90 days')",
    )


def downgrade() -> None:
    """Delete admin keys (the old schema can't hold them) and restore the data-key-only table."""
    schema_operations.drop_constraint("ck_api_keys_admin_expiry", TABLE, type_="check")
    schema_operations.drop_constraint("ck_api_keys_project_by_type", TABLE, type_="check")
    schema_operations.execute(sqlalchemy.text("DELETE FROM api_keys WHERE key_type = 'admin'"))
    schema_operations.drop_constraint("ck_api_keys_key_type", TABLE, type_="check")
    schema_operations.create_check_constraint(
        "ck_api_keys_key_type", TABLE, "key_type IN ('ingest')"
    )
    schema_operations.drop_column(TABLE, "expires_at")
    schema_operations.drop_column(TABLE, "scopes")
    schema_operations.alter_column(TABLE, "project_id", nullable=False)
