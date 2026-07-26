import base64
import hashlib
import hmac
import json
import secrets

from cryptography.exceptions import InvalidKey
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from app.accounts.model import AccountType


try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerifyMismatchError
except ModuleNotFoundError:
    _PASSWORDS = None
else:
    _PASSWORDS = PasswordHasher()


def _new_argon2id() -> Argon2id:
    return Argon2id(
        salt=secrets.token_bytes(16),
        length=32,
        iterations=3,
        lanes=4,
        memory_cost=65_536,
    )


def hash_password(raw: str) -> str:
    if _PASSWORDS is not None:
        return _PASSWORDS.hash(raw)
    return _new_argon2id().derive_phc_encoded(raw.encode("utf-8"))


def verify_password(encoded: str, raw: str) -> bool:
    if _PASSWORDS is not None:
        try:
            return _PASSWORDS.verify(encoded, raw)
        except (InvalidHashError, VerifyMismatchError):
            return False

    try:
        Argon2id.verify_phc_encoded(raw.encode("utf-8"), encoded)
    except (InvalidKey, ValueError):
        return False
    return True


def sha256_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_url_token() -> str:
    return secrets.token_urlsafe(32)


def _hmac_bytes(value: str, secret: str) -> bytes:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def derive_otp(challenge_id: int, version: int, secret: str) -> str:
    number = int.from_bytes(
        _hmac_bytes(f"otp:{challenge_id}:{version}", secret)[:8],
        "big",
    ) % 1_000_000
    return f"{number:06d}"


def derive_csrf(session_token: str, secret: str) -> str:
    return base64.urlsafe_b64encode(
        _hmac_bytes(f"csrf:{session_token}", secret)
    ).decode("ascii").rstrip("=")


def encrypt_outbox_secret(payload: dict[str, str], key: str) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return Fernet(key.encode("ascii")).encrypt(raw).decode("ascii")


def decrypt_outbox_secret(ciphertext: str, key: str) -> dict[str, str]:
    raw = Fernet(key.encode("ascii")).decrypt(ciphertext.encode("ascii"))
    value = json.loads(raw.decode("utf-8"))
    return {str(name): str(item) for name, item in value.items()}


def generate_login(account_type: AccountType) -> str:
    prefix = "u" if account_type is AccountType.USER else "b"
    return f"{prefix}_{secrets.token_hex(5)}"


def generate_password() -> str:
    return secrets.token_urlsafe(12)
