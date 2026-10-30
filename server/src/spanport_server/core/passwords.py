"""Password hashing with Argon2id (argon2-cffi's defaults follow RFC 9106)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from spanport_server.core.constants import UNKNOWN_USER_PASSWORD

_hasher = PasswordHasher()
# Compared against when the email is unknown, so a wrong email takes as long as a wrong password.
_UNKNOWN_USER_HASH = _hasher.hash(UNKNOWN_USER_PASSWORD)


def hash_password(password: str) -> str:
    """Hash a password for storage.

    Returns:
        An encoded Argon2id hash that includes its own salt and parameters.
    """
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Check a password against its stored hash, in about the same time whether or not it matches.

    Args:
        password_hash: The stored hash, or None when no user has the email given.
        password: The password typed.

    Returns:
        True only when a stored hash exists and the password matches it.
    """
    try:
        _hasher.verify(password_hash or _UNKNOWN_USER_HASH, password)
    except VerificationError, InvalidHashError:
        return False
    return password_hash is not None
