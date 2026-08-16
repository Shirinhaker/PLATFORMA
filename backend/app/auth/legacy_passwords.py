"""Eski v1656 parol xeshlarini tekshirish.

Bu **migratsiya kodi emas**, garchi ilgari `legacy_migration/` da turgan
bo'lsa ham. v1656 dan ko'chib kelgan foydalanuvchilarning paroli bazada
o'sha eski PBKDF2 shaklida qoladi va ular parolni o'zgartirmaguncha shu
yerda tekshiriladi — ya'ni bu doimiy ish-vaqti ehtiyoji.

`app/auth/security.py` login paytida shu funksiyani chaqiradi: yangi
format mos kelmasa, eskisiga tushadi.
"""

import hashlib
import hmac
import re

_LEGACY_PBKDF2 = re.compile(r"(?P<salt>[0-9a-fA-F]{32})\$(?P<digest>[0-9a-fA-F]{64})")


def verify_legacy_pbkdf2(encoded: str, raw: str) -> bool:
    match = _LEGACY_PBKDF2.fullmatch(encoded)
    if match is None:
        return False

    try:
        salt = bytes.fromhex(match.group("salt"))
        expected = bytes.fromhex(match.group("digest"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            raw.encode("utf-8"),
            salt,
            200_000,
        )
    except (UnicodeEncodeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)
