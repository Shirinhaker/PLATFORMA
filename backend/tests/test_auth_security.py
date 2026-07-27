import re

from app.accounts.model import AccountType
from app.auth.security import (
    decrypt_outbox_secret,
    derive_csrf,
    derive_otp,
    encrypt_outbox_secret,
    generate_login,
    generate_password,
    hash_password,
    new_url_token,
    sha256_token,
    verify_password,
)


def test_password_is_argon2_hashed_and_verifiable():
    encoded = hash_password("Yaxshi-Parol-42")
    assert encoded.startswith("$argon2")
    assert verify_password(encoded, "Yaxshi-Parol-42") is True
    assert verify_password(encoded, "xato") is False
    assert "Yaxshi-Parol-42" not in encoded


def test_otp_is_stable_six_digits_per_challenge_version():
    first = derive_otp(41, 1, "test-secret")
    assert re.fullmatch(r"\d{6}", first)
    assert first == derive_otp(41, 1, "test-secret")
    assert first != derive_otp(41, 2, "test-secret")


def test_login_prefixes_make_account_type_visible_to_support_only():
    assert generate_login(AccountType.USER).startswith("u_")
    assert generate_login(AccountType.BUSINESS).startswith("b_")


def test_random_password_and_url_token_are_not_reused():
    assert generate_password() != generate_password()
    assert new_url_token() != new_url_token()


def test_tokens_are_hashed_and_csrf_is_bound_to_the_session():
    assert sha256_token("session-a") == (
        "fa57a52dbf08190218529730a3e99db6946c6c29220fb6e0551e21598b0b05db"
    )
    assert derive_csrf("session-a", "csrf-secret") != derive_csrf(
        "session-b",
        "csrf-secret",
    )


def test_outbox_credentials_are_encrypted_at_rest():
    key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    ciphertext = encrypt_outbox_secret(
        {"login": "u_test", "password": "secret"},
        key,
    )
    assert "u_test" not in ciphertext
    assert "secret" not in ciphertext
    assert decrypt_outbox_secret(ciphertext, key) == {
        "login": "u_test",
        "password": "secret",
    }
