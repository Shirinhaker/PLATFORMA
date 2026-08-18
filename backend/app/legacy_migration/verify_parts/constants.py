"""Tekshiruv natijasi va kirish ma'lumoti shakllari."""

from __future__ import annotations

from dataclasses import dataclass

EXPLICIT_DEMO_FLAGS = (
    "is_demo",
    "demo",
    "is_test",
    "test_mode",
    "demo_mode",
)

SENSITIVE_CABINET_KEYS = {
    "pass_hash",
    "pass_plain",
    "password",
    "password_hash",
    "biz_pass_hash",
    "token",
    "token_hash",
    "start_token",
    "start_token_hash",
    "code_hash",
    "otp",
    "otp_hash",
    "secret",
    "private_key",
}

SENSITIVE_CABINET_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
    "pass_hash",
    "password_hash",
    "token_hash",
    "code_hash",
)


@dataclass(frozen=True)
class GateResult:
    code: str
    passed: bool
    actual: object
    expected: object


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    gates: list[GateResult]


@dataclass(frozen=True)
class VerificationInput:
    source_rows: int
    mapped_rows: int
    source_catalog_kinds: dict[str, int]
    target_catalog_kinds: dict[str, int]
    source_listings: int
    target_listings: int
    source_advertisements: int
    target_advertisements: int
    broken_foreign_keys: int
    identity_conflicts: int
    source_media_references: int
    media_copied: int
    media_missing: int
    media_invalid: int
    media_failed: int
    copied_media_unverified: int
    idempotency_created: int
    forbidden_public_fields: tuple[str, ...]
    cabinet_demo_rows: int = 0
    cabinet_sensitive_fields: int = 0
    source_stories: int = 0
    target_stories: int = 0
    source_story_views: int = 0
    target_story_views: int = 0
    source_story_reports: int = 0
    target_story_reports: int = 0
