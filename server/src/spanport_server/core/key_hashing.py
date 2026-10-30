"""How API keys, session ids and setup tokens are stored: a SHA-256 hash, never the raw value.

Keys also keep their last few characters for display.
"""

import hashlib

from spanport_server.core.constants import API_KEY_VISIBLE_SUFFIX_LENGTH


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key, session id or setup token for storage and lookup.

    These are long random values, so a plain SHA-256 is enough (unlike passwords).

    Args:
        raw_key: The full value as given to the user or browser.

    Returns:
        The SHA-256 hex digest (64 characters).
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


def visible_suffix(raw_key: str) -> str:
    """Return the last characters of a key, safe to show and log.

    Args:
        raw_key: The full key.

    Returns:
        The last API_KEY_VISIBLE_SUFFIX_LENGTH characters.
    """
    return raw_key[-API_KEY_VISIBLE_SUFFIX_LENGTH:]
