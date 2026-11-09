import asyncio
import threading
import time

import pytest

from spanport_server.core import passwords
from spanport_server.core.constants import HASHING_THREAD_PREFIX, PASSWORD_HASH_THREADS
from spanport_server.core.passwords import hash_password, verify_password


def test_a_hash_checks_only_its_own_password() -> None:
    stored = hash_password("correct horse battery")

    assert stored.startswith("$argon2id$")
    assert "correct horse battery" not in stored
    assert verify_password(stored, "correct horse battery") is True
    assert verify_password(stored, "Correct horse battery") is False


def test_same_password_hashes_differently_each_time() -> None:
    assert hash_password("same password here") != hash_password("same password here")


def test_unknown_user_and_broken_hash_never_match() -> None:
    assert verify_password(None, "spanport-unknown-user") is False
    assert verify_password("not-a-hash", "anything") is False


@pytest.mark.anyio
async def test_hashing_runs_in_the_password_threads_not_the_event_loop() -> None:
    loop_thread = threading.current_thread().name
    threads: list[str] = []
    real_hash = passwords.hash_password

    def recording_hash(password: str) -> str:
        threads.append(threading.current_thread().name)
        return real_hash(password)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(passwords, "hash_password", recording_hash)
        stored = await passwords.hash_password_in_thread("correct horse battery")

    assert await passwords.verify_password_in_thread(stored, "correct horse battery") is True
    assert await passwords.verify_password_in_thread(None, "anything") is False
    assert threads[0].startswith(HASHING_THREAD_PREFIX)
    assert threads[0] != loop_thread


@pytest.mark.anyio
async def test_at_most_a_few_passwords_are_checked_at_once() -> None:
    running = 0
    most_at_once = 0
    counter_lock = threading.Lock()

    def slow_verify(password_hash: str | None, password: str) -> bool:
        nonlocal running, most_at_once
        with counter_lock:
            running += 1
            most_at_once = max(most_at_once, running)
        time.sleep(0.05)
        with counter_lock:
            running -= 1
        return False

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(passwords, "verify_password", slow_verify)
        await asyncio.gather(
            *(passwords.verify_password_in_thread(None, "guess") for _ in range(12))
        )

    assert most_at_once == PASSWORD_HASH_THREADS
