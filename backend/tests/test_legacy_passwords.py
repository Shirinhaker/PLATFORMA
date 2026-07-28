import pytest

from app.auth.security import verify_password_with_rehash
from app.legacy_migration.passwords import verify_legacy_pbkdf2


LEGACY_HASH = (
    "00112233445566778899aabbccddeeff$"
    "0ba712d93841d92cdc0a7a9149951429107b035040d07fd5bb3829bf79acd927"
)


def test_legacy_pbkdf2_is_accepted_and_rehashed_to_argon2():
    result = verify_password_with_rehash(
        LEGACY_HASH,
        "koprik-test-password",
    )

    assert result.valid is True
    assert result.replacement_hash
    assert result.replacement_hash.startswith("$argon2")


def test_wrong_legacy_password_is_rejected_without_replacement():
    result = verify_password_with_rehash(LEGACY_HASH, "wrong")

    assert result.valid is False
    assert result.replacement_hash is None


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "not-a-hash",
        "00$11",
        "g" * 32 + "$" + "0" * 64,
        "0" * 31 + "$" + "0" * 64,
        "0" * 32 + "$" + "0" * 63,
        "$argon2id$v=19$m=65536,t=3,p=4$invalid",
    ],
)
def test_malformed_legacy_values_return_false(encoded):
    assert verify_legacy_pbkdf2(encoded, "secret") is False
