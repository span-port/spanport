"""IDs. Every id Spanport creates is a UUIDv7: time-ordered, so new rows sort last.

Python, Postgres and ClickHouse have one UUID type for all versions; `UuidV7` names the ids we
create so the code says which version they are.
"""

import uuid

UuidV7 = uuid.UUID


def new_id() -> UuidV7:
    """Return a new UUIDv7."""
    return uuid.uuid7()
