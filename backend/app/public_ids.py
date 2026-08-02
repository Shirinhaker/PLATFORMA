"""v1656 bilan mos, tashqi API uchun barqaror public ID generatorlari."""

import hashlib


def build_profile_public_id(kind: str, account_id: int) -> str:
    if kind not in {"user", "business"}:
        raise ValueError("Profil turi user yoki business bo'lishi kerak.")
    digest = hashlib.blake2s(
        f"{kind}:{account_id}".encode("utf-8"),
        digest_size=8,
        person=b"koprik",
    ).hexdigest()
    return f"{'u' if kind == 'user' else 'b'}_{digest}"


def build_listing_public_id(listing_id: int) -> str:
    digest = hashlib.blake2s(
        f"listing:{listing_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    return f"l_{digest}"


def build_content_public_id(kind: str, target_id: int) -> str:
    if kind not in {"product", "service"}:
        raise ValueError("Kontent turi product yoki service bo'lishi kerak.")
    digest = hashlib.blake2s(
        f"{kind}:{target_id}".encode("utf-8"),
        digest_size=8,
        key=b"koprik-content-v1",
    ).hexdigest()
    return f"{'p' if kind == 'product' else 's'}_{digest}"
