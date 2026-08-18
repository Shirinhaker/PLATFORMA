from __future__ import annotations

import hashlib
import sqlite3
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.legacy_migration.media.reading import sniff_media_type
from app.legacy_migration.model import MigrationRun
from app.legacy_migration.reconcile_parts.constants import StageResult
from app.legacy_migration.reconcile_parts.mapping import _find_mapping
from app.media.storage import (
    MAX_PROFILE_IMAGE_BYTES,
    PROFILE_IMAGE_TYPES,
    R2Storage,
)
from app.profiles.model import BusinessProfile, UserProfile

OWNER_CONFIG = {
    "user": (
        "users",
        "user_account",
        UserProfile,
        "avatar_object_key",
        "user_profile",
        "avatar",
    ),
    "business": (
        "businesses",
        "business_account",
        BusinessProfile,
        "logo_object_key",
        "business_profile",
        "logo",
    ),
}


def _source_owner_exists(
    source: sqlite3.Connection,
    table: str,
    legacy_id: int,
) -> bool:
    try:
        return bool(
            source.execute(
                f'SELECT 1 FROM "{table}" WHERE id=? LIMIT 1',
                (legacy_id,),
            ).fetchone()
        )
    except sqlite3.Error:
        return False


def _profile_image_rows(source: sqlite3.Connection):
    try:
        return source.execute(
            """
            SELECT owner_kind,owner_id,mime_type,content,updated_at
            FROM profile_images
            ORDER BY owner_kind,owner_id
            """
        ).fetchall()
    except sqlite3.Error:
        return []


def _normalized_content_type(value: object) -> str:
    content_type = str(value or "").strip().lower()
    return "image/jpeg" if content_type == "image/jpg" else content_type


async def migrate_profile_images(
    session: AsyncSession,
    source: sqlite3.Connection,
    storage: R2Storage,
    run: MigrationRun,
) -> StageResult:
    """v1656 `profile_images` BLOBlarini R2 profil rasmlariga ko'chir.

    v1656 avatar/logo URLi asl rasm emas: baytlar SQLite `profile_images`
    jadvalida. Oddiy MEDIA stage fayl/file_id manbalarini ko'chiradi va bu
    BLOB jadvalni ko'rmaydi. Shu V8 late-stage migratsiya user avatar va
    business logoni deterministik R2 kalitga yozadi va target profilga
    bog'laydi.

    Demo prune users/businesses qatorlarini snapshotdan oldin olib tashlaydi.
    `profile_images`da orphan demo BLOB qolgan bo'lsa source owner mavjud emas
    va u xavfsiz ravishda o'tkazib yuboriladi.
    """
    created = 0
    reused = 0

    for row in _profile_image_rows(source):
        owner_kind = str(row[0] or "").strip().lower()
        config = OWNER_CONFIG.get(owner_kind)
        if config is None:
            continue
        try:
            legacy_id = int(row[1])
        except (TypeError, ValueError):
            raise RuntimeError("profile_media_owner_id_invalid")

        source_table, mapping_type, model, field, entity_type, slot = config
        if not _source_owner_exists(source, source_table, legacy_id):
            # Demo prune'dan keyin qolgan orphan BLOB targetga ko'chmaydi.
            continue

        mapping = await _find_mapping(session, mapping_type, legacy_id)
        if mapping is None or mapping.target_id is None:
            raise RuntimeError(
                f"profile_media_owner_mapping_missing:{owner_kind}:{legacy_id}"
            )
        profile = await session.get(model, mapping.target_id)
        if profile is None:
            raise RuntimeError(f"profile_media_target_missing:{owner_kind}:{legacy_id}")

        content_type = _normalized_content_type(row[2])
        if content_type not in PROFILE_IMAGE_TYPES:
            raise RuntimeError(
                f"profile_media_content_type_invalid:{owner_kind}:{legacy_id}"
            )
        raw = bytes(row[3] or b"")
        if not raw or len(raw) > MAX_PROFILE_IMAGE_BYTES:
            raise RuntimeError(f"profile_media_size_invalid:{owner_kind}:{legacy_id}")
        sniffed = sniff_media_type(raw[:16])
        if sniffed != content_type:
            raise RuntimeError(
                f"profile_media_signature_mismatch:{owner_kind}:{legacy_id}"
            )

        digest = hashlib.sha256(raw).hexdigest()
        suffix = PROFILE_IMAGE_TYPES[content_type]
        expected_key = (
            f"migration/{run.id}/{entity_type}/{legacy_id}/{slot}/{digest}{suffix}"
        )
        current_key = str(getattr(profile, field, "") or "")
        if current_key == expected_key:
            try:
                verified = storage.verify_object(
                    current_key,
                    expected_size=len(raw),
                    expected_sha256=digest,
                    expected_content_type=content_type,
                )
            except Exception:
                verified = False
            if verified:
                reused += 1
                continue

        stored = storage.put_migration_object(
            stream=BytesIO(raw),
            run_id=run.id,
            entity_type=entity_type,
            legacy_id=legacy_id,
            slot=slot,
            sha256=digest,
            content_type=content_type,
            size_bytes=len(raw),
            suffix=suffix,
        )
        if not storage.verify_object(
            stored.object_key,
            expected_size=len(raw),
            expected_sha256=digest,
            expected_content_type=content_type,
        ):
            raise RuntimeError(
                f"profile_media_r2_verification_failed:{owner_kind}:{legacy_id}"
            )
        setattr(profile, field, stored.object_key)
        created += 1

    await session.flush()
    return StageResult(created=created, reused=reused)
