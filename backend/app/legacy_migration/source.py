from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3


REQUIRED_TABLES = (
    "users",
    "businesses",
    "item_groups",
    "items",
    "listings",
    "listing_media",
    "advertisements",
)


class SnapshotIntegrityError(RuntimeError):
    pass


class SnapshotExistsError(RuntimeError):
    pass


class LegacySchemaMismatch(RuntimeError):
    pass


class MediaManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class SnapshotInfo:
    path: Path
    database_sha256: str
    manifest_path: Path
    manifest_sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_snapshot(
    source_db: Path,
    output_dir: Path,
    media_roots: tuple[Path, ...],
) -> SnapshotInfo:
    source_path = source_db.resolve(strict=True)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "platforma.snapshot.db"
    manifest_path = output_dir / "media-manifest.json"
    if snapshot_path.exists() or manifest_path.exists():
        raise SnapshotExistsError("legacy_snapshot_output_exists")

    source_uri = f"{source_path.as_uri()}?mode=ro"
    source = sqlite3.connect(source_uri, uri=True)
    target = sqlite3.connect(snapshot_path)
    try:
        source.backup(target)
        quick = target.execute("PRAGMA quick_check").fetchone()[0]
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if quick != "ok" or integrity != "ok":
            raise SnapshotIntegrityError(
                "legacy_snapshot_integrity_failed"
            )
        target.commit()
    finally:
        target.close()
        source.close()

    manifest = build_media_manifest(media_roots)
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)

    return SnapshotInfo(
        path=snapshot_path,
        database_sha256=file_sha256(snapshot_path),
        manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


def build_media_manifest(
    media_roots: tuple[Path, ...],
) -> list[dict[str, int | str]]:
    entries: list[dict[str, int | str]] = []
    for index, configured_root in enumerate(media_roots):
        root = configured_root.resolve(strict=True)
        if not root.is_dir():
            raise MediaManifestError("legacy_media_root_not_directory")
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file():
                continue
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise MediaManifestError("legacy_media_path_outside_root")
            relative = resolved.relative_to(root).as_posix()
            entries.append(
                {
                    "reference": f"root_{index}/{relative}",
                    "sha256": file_sha256(resolved),
                    "size_bytes": resolved.stat().st_size,
                }
            )
    return sorted(entries, key=lambda item: str(item["reference"]))


def open_immutable(snapshot: Path) -> sqlite3.Connection:
    path = snapshot.resolve(strict=True)
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def inventory_source(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, int]]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing = sorted(set(REQUIRED_TABLES) - tables)
    if missing:
        raise LegacySchemaMismatch(
            "legacy_schema_missing_tables:" + ",".join(missing)
        )

    inventory: dict[str, dict[str, int]] = {}
    for table in REQUIRED_TABLES:
        counts: Counter[str] = Counter()
        counts["total"] = int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        )
        columns = _table_columns(connection, table)
        for dimension in _inventory_dimensions(table):
            if dimension not in columns:
                continue
            rows = connection.execute(
                f'SELECT "{dimension}", COUNT(*) '
                f'FROM "{table}" GROUP BY "{dimension}"'
            )
            for value, count in rows:
                label = str(value).strip() if value is not None else ""
                counts[label or "unknown"] += int(count)
        inventory[table] = dict(counts)
    return inventory


def _table_columns(
    connection: sqlite3.Connection,
    table: str,
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def _inventory_dimensions(table: str) -> tuple[str, ...]:
    dimensions = ["status"]
    if table in {"item_groups", "items"}:
        dimensions.append("kind")
    if table == "listing_media":
        dimensions.append("mtype")
    return tuple(dimensions)
