"""Who created each API key, so removing or demoting a person revokes the admin keys they made.

Revision ID: 0011
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add api_keys.created_by (indexed; deleting the user leaves the key without a creator).

    Existing keys, and keys made with the CLI, have no creator.
    """
    schema_operations.add_column(
        "api_keys",
        sqlalchemy.Column(
            "created_by",
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey(
                "users.id", name="fk_api_keys_created_by_users", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    schema_operations.create_index("ix_api_keys_created_by", "api_keys", ["created_by"])


def downgrade() -> None:
    """Drop api_keys.created_by; keys keep working, only who made them is forgotten."""
    schema_operations.drop_index("ix_api_keys_created_by", table_name="api_keys")
    schema_operations.drop_column("api_keys", "created_by")
