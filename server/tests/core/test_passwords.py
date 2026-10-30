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
