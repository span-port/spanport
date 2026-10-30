"""A name on each API key, so people can tell keys apart in the UI.

Revision ID: 0004
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add api_keys.name. Keys made before this have no name."""
    schema_operations.add_column(
        "api_keys", sqlalchemy.Column("name", sqlalchemy.String(), nullable=True)
    )


def downgrade() -> None:
    """Drop the names; the keys themselves keep working."""
    schema_operations.drop_column("api_keys", "name")
