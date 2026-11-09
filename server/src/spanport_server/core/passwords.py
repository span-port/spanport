"""Password hashing with Argon2id (argon2-cffi's defaults follow RFC 9106).

Argon2 is deliberately slow, so request handlers use the `_in_thread` versions: they run in a
small pool of their own, keeping the event loop free and capping how many cores sign-ins use.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from spanport_server.core.constants import (
    HASHING_THREAD_PREFIX,
    PASSWORD_HASH_THREADS,
    UNKNOWN_USER_PASSWORD,
)

_hasher = PasswordHasher()
# Compared against when the email is unknown, so a wrong email takes as long as a wrong password.
_UNKNOWN_USER_HASH = _hasher.hash(UNKNOWN_USER_PASSWORD)
# Extra sign-ins wait in this pool's queue instead of each taking a thread of their own.
_hashing_pool = ThreadPoolExecutor(
    max_workers=PASSWORD_HASH_THREADS, thread_name_prefix=HASHING_THREAD_PREFIX
)


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


async def hash_password_in_thread(password: str) -> str:
    """hash_password, run in the password pool so the event loop keeps serving requests."""
    return await asyncio.get_running_loop().run_in_executor(_hashing_pool, hash_password, password)


async def verify_password_in_thread(password_hash: str | None, password: str) -> bool:
    """verify_password, run in the password pool so the event loop keeps serving requests."""
    return await asyncio.get_running_loop().run_in_executor(
        _hashing_pool, verify_password, password_hash, password
    )
