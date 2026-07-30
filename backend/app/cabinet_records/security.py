from __future__ import annotations

from collections.abc import Mapping


SENSITIVE_NAMES = {
    "password",
    "password_hash",
    "pass_hash",
    "pass_plain",
    "biz_pass_hash",
    "token",
    "token_hash",
    "start_token",
    "start_token_hash",
    "secret",
    "private_key",
    "csrf_token",
    "otp",
    "otp_hash",
    "code_hash",
}
SENSITIVE_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
)


class SensitiveCabinetFieldError(ValueError):
    pass


def assert_payload_safe(value: object, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = key.casefold()
            current = (*path, key)
            if normalized in SENSITIVE_NAMES or normalized.endswith(SENSITIVE_SUFFIXES):
                raise SensitiveCabinetFieldError(
                    "cabinet_normalization_sensitive_field:" + "/".join(current)
                )
            assert_payload_safe(child, path=current)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_payload_safe(child, path=(*path, str(index)))
