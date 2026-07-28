# Koprik Phase 3C Content Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BUILD v1656 monolitidagi akkauntlar, bizneslar, mahsulotlar, xizmatlar, e’lonlar, reklamalar va media fayllarni idempotent migrator orqali PostgreSQL/R2 ga xavfsiz ko‘chirish hamda yangi katalog, qidiruv va reklama API/UI qismlarini ishga tushirish.

**Architecture:** Yangi SQLAlchemy modellar va Alembic migratsiyasi kontentni `accounts`/`business_profiles` bilan bog‘laydi, `legacy_migration` CLI esa immutable SQLite snapshotni ketma-ket stage’larda o‘qib, `legacy_id_map` orqali takrorlanmaydigan import bajaradi. Public API faqat allowlist qilingan faol kontentni chiqaradi; React frontend katalog/qidiruv/reklamani shu API’dan oladi, `E’lonlar` esa `listings_enabled=false` bo‘lganda yopiq qoladi.

**Tech Stack:** Python 3.12, FastAPI 0.139, SQLAlchemy asyncio 2.x, PostgreSQL, Alembic, Redis, boto3/Cloudflare R2, Pydantic v2, React 19, TypeScript 5.8, Vite 7, Vitest 3, pytest.

## Global Constraints

- `static/index.html`, legacy BUILD `v1656`, ishlab turgan monolit va production bazaga staging gate’lari o‘tmaguncha tegilmaydi.
- Migratsiya manbasi faqat immutable SQLite backup bo‘ladi; live `platforma.db` bevosita o‘qilmaydi.
- Stage tartibi: `snapshot -> inventory -> accounts -> businesses -> catalog -> listings -> advertisements -> media -> verify`.
- Bir xil snapshot ikkinchi marta ishlatilganda yangi target yozuvlar soni `0` bo‘lishi shart.
- `E’lon` va `Reklama` alohida model, API va frontend holati bo‘lib qoladi.
- `price_text` qiymati aynan ko‘chiriladi; migrator narxni taxminiy son qiymatiga aylantirmaydi.
- Egasi aniqlanmagan, lekin public uchun boshqa majburiy maydonlari to‘liq mahsulot/xizmat `owner_state=unlinked` bilan ko‘rinadi; buyurtma va chat capability’lari `false` bo‘ladi.
- Majburiy public ma’lumoti yetishmagan yozuv `review_state=review_required` bilan ko‘chadi va public API’dan yashiriladi.
- Bloklangan, o‘chirilgan, muddati tugagan va nofaol yozuvlar statusi bilan ko‘chadi; faqat faol `ready` yozuvlar public bo‘ladi.
- Takrorlangan login, telefon yoki Telegram ID avtomatik birlashtirilmaydi; unresolved identity conflict production gate’ini bloklaydi.
- Eski PBKDF2 parol xeshi birinchi muvaffaqiyatli kirishda Argon2id’ga yangilanadi; sessionlar ko‘chirilmaydi.
- `staff.pass_plain` Phase 3C target sxemasi, logi, reporti va artifactlariga kirmaydi; xodimlar moduli Phase 3C scope’idan tashqarida qoladi.
- Media R2 ga checksum bilan ko‘chadi; `missing`/`invalid` media standart tasvirga tushadi, `failed > 0` production gate’ini bloklaydi.
- Public API parol xeshi, telefon, Telegram ID, session, to‘lov ma’lumoti, STIR, private koordinata, R2 object key yoki legacy ID qaytarmaydi.
- Production ko‘chirish vaqtida sayt “Texnik ishlar olib borilmoqda” sahifasiga o‘tadi; rollback ma’lumot o‘chirishga tayanmaydi.
- Har task failing test, eng kichik passing implementation, to‘liq focused test va alohida commit bilan tugaydi.

---

## File Map

### PostgreSQL domain

- `backend/app/catalog/model.py` — `CatalogGroup` va `CatalogItem`.
- `backend/app/listings/model.py` — `Listing` va `ListingMedia`.
- `backend/app/advertisements/model.py` — `Advertisement`.
- `backend/app/legacy_migration/model.py` — run, ID mapping, issue va media migration holatlari.
- `backend/migrations/versions/0003_phase3c_content.py` — barcha Phase 3C jadvallari, indekslari va constraintlari.

### Migrator

- `backend/app/legacy_migration/source.py` — backup, integrity, fingerprint, immutable SQLite reader va inventory.
- `backend/app/legacy_migration/passwords.py` — legacy PBKDF2 formatini aniqlash.
- `backend/app/legacy_migration/reconcile.py` — akkaunt/biznes deterministic mappingi va conflictlar.
- `backend/app/legacy_migration/catalog_stage.py` — guruh, mahsulot va xizmat importi.
- `backend/app/legacy_migration/listing_stage.py` — e’lon va e’lon media metadata importi.
- `backend/app/legacy_migration/advertisement_stage.py` — reklama snapshot, schedule va target importi.
- `backend/app/legacy_migration/media_stage.py` — local/Telegram media adapterlari va R2 upload.
- `backend/app/legacy_migration/report.py` — PII’siz JSON/Markdown hisobot.
- `backend/app/legacy_migration/verify.py` — data/media/security/functional gate’lari.
- `backend/app/legacy_migration/runner.py` — idempotent stage orchestration.
- `backend/app/legacy_migration/cli.py` — `koprik-migrate-legacy` CLI.

### Public backend

- `backend/app/catalog/schemas.py`, `repository.py`, `service.py`, `router.py` — public katalog.
- `backend/app/advertisements/schemas.py`, `repository.py`, `router.py` — public banner tanlash.
- `backend/app/listings/router.py` — feature flag o‘chiq paytdagi yopiq route contracti.
- `backend/app/public_discovery/*` — qidiruvni `product | service` bilan kengaytirish.

### Frontend

- `frontend/src/api/types.ts`, `client.ts` — typed katalog va reklama API.
- `frontend/src/legacy/public/CatalogItemCard.tsx` — mahsulot/xizmat kartasi.
- `frontend/src/legacy/public/PublicSearchResults.tsx` — profile va kontent natijalari.
- `frontend/src/legacy/public/HomeAdvertisements.tsx` — responsive bannerlar.
- `frontend/src/legacy/public/CatalogScreen.tsx`, `CategoryScreen.tsx` — real katalog.
- `frontend/public/maintenance.html` — production cutover oynasi.

### Verification and operations

- `scripts/verify_phase3c.py` — repository contract verifier.
- `tests/test_phase3c_content_migration_contract.py` — cross-layer contract.
- `docs/deploy-phase3c-staging.md` — staging execution va approval gate.
- `docs/deploy-phase3c-production.md` — maintenance, cutover va rollback.

---

## Task 1: Define Phase 3C SQLAlchemy Models

**Files:**

- Create: `backend/app/catalog/__init__.py`
- Create: `backend/app/catalog/model.py`
- Create: `backend/app/listings/__init__.py`
- Create: `backend/app/listings/model.py`
- Create: `backend/app/advertisements/__init__.py`
- Create: `backend/app/advertisements/model.py`
- Create: `backend/app/legacy_migration/__init__.py`
- Create: `backend/app/legacy_migration/model.py`
- Create: `backend/tests/test_phase3c_models.py`

**Interfaces:**

- Produces: `CatalogGroup`, `CatalogItem`, `Listing`, `ListingMedia`, `Advertisement`, `MigrationRun`, `LegacyIdMap`, `MigrationIssue`, `MediaMigration`.
- Produces enums: `OwnerState`, `ReviewState`, `MigrationEnvironment`, `MigrationStage`, `MigrationStatus`, `MediaMigrationState`.
- All imported content rows carry `migration_run_id`; rollback/public isolation depends on it.

- [ ] **Step 1: Write model-contract tests**

```python
from sqlalchemy import UniqueConstraint

from app.catalog.model import CatalogItem
from app.legacy_migration.model import LegacyIdMap, MediaMigration


def test_catalog_item_keeps_text_price_and_owner_state():
    columns = CatalogItem.__table__.c
    assert columns.price_text.type.length == 120
    assert columns.business_account_id.nullable is True
    assert columns.owner_state.nullable is False
    assert columns.review_state.nullable is False
    assert columns.migration_run_id.nullable is False


def test_legacy_mapping_is_unique_per_entity_and_legacy_id():
    constraints = {
        tuple(constraint.columns.keys())
        for constraint in LegacyIdMap.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("entity_type", "legacy_id") in constraints


def test_media_mapping_distinguishes_desktop_mobile_and_listing_positions():
    constraints = {
        tuple(constraint.columns.keys())
        for constraint in MediaMigration.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("entity_type", "legacy_id", "slot") in constraints
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `cd backend && pytest tests/test_phase3c_models.py -q`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.catalog'`.

- [ ] **Step 3: Add focused models**

Use string-backed enums with `values_callable` and validation, following `backend/app/accounts/model.py`. The core signatures must be:

```python
class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[int]
    business_account_id: Mapped[int | None]
    catalog_group_id: Mapped[int | None]
    owner_name_snapshot: Mapped[str]
    name: Mapped[str]
    price_text: Mapped[str]
    note: Mapped[str]
    kind: Mapped[str]
    queue_enabled: Mapped[bool]
    image_object_key: Mapped[str]
    status: Mapped[str]
    owner_state: Mapped[OwnerState]
    review_state: Mapped[ReviewState]
    migration_run_id: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class LegacyIdMap(Base):
    __tablename__ = "legacy_id_map"
    __table_args__ = (
        UniqueConstraint("entity_type", "legacy_id", name="uq_legacy_id_map"),
    )

    id: Mapped[int]
    entity_type: Mapped[str]
    legacy_id: Mapped[int]
    target_id: Mapped[int | None]
    source_row_hash: Mapped[str]
    mapping_status: Mapped[str]
    review_reason: Mapped[str]
    last_run_id: Mapped[int]
```

`CatalogGroup.kind` and `CatalogItem.kind` accept only `product | service`; `ListingMedia.media_type` accepts only `photo | video`; `Advertisement.placement` defaults to `home`. `Advertisement.price` and historical counters remain integers. JSON fields use SQLAlchemy `JSON`, not serialized text.

- [ ] **Step 4: Run model tests**

Run: `cd backend && pytest tests/test_phase3c_models.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog backend/app/listings backend/app/advertisements \
  backend/app/legacy_migration backend/tests/test_phase3c_models.py
git commit -m "feat: define Phase 3C content models"
```

## Task 2: Create the Alembic Schema

**Files:**

- Create: `backend/migrations/versions/0003_phase3c_content.py`
- Modify: `backend/migrations/env.py`
- Create: `backend/tests/test_phase3c_migration.py`

**Interfaces:**

- Consumes: all Task 1 models.
- Produces: PostgreSQL revision `0003_phase3c_content`, down revision `0002_auth_profiles`.
- Produces database constraints used by every import stage.

- [ ] **Step 1: Write migration-source tests**

```python
from pathlib import Path


MIGRATION = Path("migrations/versions/0003_phase3c_content.py")


def test_phase3c_migration_declares_all_tables_and_parent():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0003_phase3c_content"' in source
    assert 'down_revision = "0002_auth_profiles"' in source
    for table in (
        "migration_runs",
        "legacy_id_map",
        "migration_issues",
        "media_migration",
        "catalog_groups",
        "catalog_items",
        "listings",
        "listing_media",
        "advertisements",
    ):
        assert f'op.create_table(\\n        "{table}"' in source


def test_phase3c_migration_has_idempotency_and_public_indexes():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "uq_legacy_id_map" in source
    assert "uq_media_migration_source_slot" in source
    assert "ix_catalog_items_public" in source
    assert "ix_advertisements_public_schedule" in source
```

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_phase3c_migration.py -q`  
Expected: FAIL because `0003_phase3c_content.py` does not exist.

- [ ] **Step 3: Write upgrade and exact reverse-order downgrade**

The revision creates migration control tables first, then catalog, listings and advertisements. Foreign keys to `accounts.id` use `ondelete="SET NULL"` so an imported public snapshot is not destroyed if an account is administratively removed; content-to-group/listing foreign keys use `ondelete="SET NULL"` or `CASCADE` according to ownership.

Required partial public indexes:

```python
op.create_index(
    "ix_catalog_items_public",
    "catalog_items",
    ["kind", "status", "review_state", "created_at", "id"],
)
op.create_index(
    "ix_advertisements_public_schedule",
    "advertisements",
    ["placement", "status", "start_at", "end_at", "id"],
)
```

Update `backend/migrations/env.py` with imports for the four new model modules so `Base.metadata` is complete.

- [ ] **Step 4: Verify migration source and real upgrade**

Run:

```bash
cd backend
pytest tests/test_phase3c_migration.py -q
KOPRIK_DATABASE_URL="$KOPRIK_TEST_DATABASE_URL" alembic upgrade head
KOPRIK_DATABASE_URL="$KOPRIK_TEST_DATABASE_URL" alembic current
```

Expected: tests PASS and Alembic current revision is `0003_phase3c_content`.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations backend/tests/test_phase3c_migration.py
git commit -m "feat: add Phase 3C database migration"
```

## Task 3: Support Legacy PBKDF2 Passwords with One-Time Rehash

**Files:**

- Create: `backend/app/legacy_migration/passwords.py`
- Modify: `backend/app/auth/security.py`
- Modify: `backend/app/auth/service.py`
- Create: `backend/tests/test_legacy_passwords.py`
- Modify: `backend/tests/test_auth_service.py`

**Interfaces:**

- Produces: `verify_legacy_pbkdf2(encoded: str, raw: str) -> bool`.
- Produces: `PasswordVerification(valid: bool, replacement_hash: str | None)`.
- Produces: `verify_password_with_rehash(encoded: str, raw: str) -> PasswordVerification`.
- Existing `verify_password(encoded, raw) -> bool` remains backward-compatible.

- [ ] **Step 1: Write the legacy-format test**

```python
from app.auth.security import verify_password_with_rehash


def test_legacy_pbkdf2_is_accepted_and_rehashed_to_argon2():
    encoded = (
        "00112233445566778899aabbccddeeff$"
        "0ba712d93841d92cdc0a7a9149951429107b035040d07fd5bb3829bf79acd927"
    )
    result = verify_password_with_rehash(encoded, "koprik-test-password")
    assert result.valid is True
    assert result.replacement_hash
    assert result.replacement_hash.startswith("$argon2")


def test_wrong_legacy_password_is_rejected_without_replacement():
    result = verify_password_with_rehash(
        "00112233445566778899aabbccddeeff$"
        "0ba712d93841d92cdc0a7a9149951429107b035040d07fd5bb3829bf79acd927",
        "wrong",
    )
    assert result.valid is False
    assert result.replacement_hash is None
```

The encoded fixture is generated once with the monolith algorithm:

```python
hashlib.pbkdf2_hmac(
    "sha256",
    b"koprik-test-password",
    bytes.fromhex("00112233445566778899aabbccddeeff"),
    200_000,
).hex()
```

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_passwords.py -q`  
Expected: FAIL because `verify_password_with_rehash` is missing.

- [ ] **Step 3: Implement constant-time legacy verification**

```python
@dataclass(frozen=True)
class PasswordVerification:
    valid: bool
    replacement_hash: str | None = None


def verify_password_with_rehash(encoded: str, raw: str) -> PasswordVerification:
    if verify_current_argon2(encoded, raw):
        return PasswordVerification(True)
    if verify_legacy_pbkdf2(encoded, raw):
        return PasswordVerification(True, hash_password(raw))
    return PasswordVerification(False)
```

`verify_legacy_pbkdf2` accepts exactly `32 hex salt + "$" + 64 hex digest`, uses 200,000 SHA-256 iterations and `hmac.compare_digest`. Malformed values return `False` without raising or logging the hash.

- [ ] **Step 4: Upgrade the hash inside the existing login transaction**

In `AuthService.start_login`, replace the direct boolean check with:

```python
password_check = (
    verify_password_with_rehash(account.password_hash, password)
    if account is not None and account.status == "active"
    else PasswordVerification(False)
)
if not password_check.valid:
    raise INVALID_CREDENTIALS
if password_check.replacement_hash:
    account.password_hash = password_check.replacement_hash
```

The same transaction that creates the login challenge commits the replacement hash. Add a service test proving the first login replaces the legacy value and the second login uses Argon2.

- [ ] **Step 5: Run focused and auth tests**

Run: `cd backend && pytest tests/test_legacy_passwords.py tests/test_auth_security.py tests/test_auth_service.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/legacy_migration/passwords.py backend/app/auth/security.py \
  backend/app/auth/service.py backend/tests/test_legacy_passwords.py \
  backend/tests/test_auth_service.py
git commit -m "feat: upgrade legacy passwords on login"
```

## Task 4: Build Immutable Snapshot and Inventory

**Files:**

- Create: `backend/app/legacy_migration/source.py`
- Create: `backend/tests/test_legacy_source.py`

**Interfaces:**

- Produces: `SnapshotInfo(path: Path, database_sha256: str, manifest_path: Path, manifest_sha256: str)`.
- Produces: `create_snapshot(source_db: Path, output_dir: Path, media_roots: tuple[Path, ...]) -> SnapshotInfo`.
- Produces: `open_immutable(snapshot: Path) -> sqlite3.Connection`.
- Produces: `inventory_source(connection: sqlite3.Connection) -> dict[str, dict[str, int]]`.

- [ ] **Step 1: Write snapshot tests with a real SQLite fixture**

```python
def test_snapshot_is_consistent_read_only_and_fingerprinted(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    result = create_snapshot(source, tmp_path / "snapshot", ())

    assert result.path.exists()
    assert len(result.database_sha256) == 64
    assert len(result.manifest_sha256) == 64
    connection = open_immutable(result.path)
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO users(login) VALUES ('blocked')")


def test_inventory_counts_entities_and_statuses(tmp_path):
    source = build_legacy_fixture(tmp_path / "platforma.db")
    result = create_snapshot(source, tmp_path / "snapshot", ())
    inventory = inventory_source(open_immutable(result.path))
    assert inventory["items"]["total"] == 2
    assert inventory["items"]["product"] == 1
    assert inventory["items"]["service"] == 1
    assert inventory["advertisements"]["active"] == 1
```

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_source.py -q`  
Expected: FAIL because `app.legacy_migration.source` does not exist.

- [ ] **Step 3: Implement backup and immutable open**

Use `sqlite3.Connection.backup()`; never `shutil.copy()` a live WAL database. After backup, run both checks:

```python
quick = target.execute("PRAGMA quick_check").fetchone()[0]
integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
if quick != "ok" or integrity != "ok":
    raise SnapshotIntegrityError("legacy_snapshot_integrity_failed")
```

Open the result with `sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)`. Generate a sorted JSON media manifest containing only normalized relative reference, byte size and SHA-256; do not include tokens, absolute deployment paths or media bytes.

- [ ] **Step 4: Implement inventory for exact source tables**

Inventory `users`, `businesses`, `item_groups`, `items`, `listings`, `listing_media`, and `advertisements`. Count item `kind`, all available `status` values and media `mtype`. Missing required tables raise `LegacySchemaMismatch`; optional late-added columns are discovered through `PRAGMA table_info`.

- [ ] **Step 5: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_source.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/legacy_migration/source.py backend/tests/test_legacy_source.py
git commit -m "feat: snapshot and inventory legacy data"
```

## Task 5: Reconcile Accounts and Business Profiles

**Files:**

- Create: `backend/app/legacy_migration/reconcile.py`
- Create: `backend/tests/test_legacy_reconcile.py`

**Interfaces:**

- Consumes: immutable `sqlite3.Connection`, `AsyncSession`, `MigrationRun`.
- Produces: `reconcile_accounts(...) -> StageResult`.
- Produces: `reconcile_businesses(...) -> StageResult`.
- Produces `StageResult(created: int, reused: int, updated: int, quarantined: int, issues: int)`.
- Creates `LegacyIdMap` entity types `user_account` and `business_account`.

- [ ] **Step 1: Write deterministic-mapping tests**

```python
@pytest.mark.asyncio
async def test_existing_exact_login_and_type_are_reused(db_session, legacy_source, run):
    existing = await seed_account(
        db_session,
        account_type="business",
        login="turon",
        telegram_user_id=9001,
    )
    result = await reconcile_accounts(db_session, legacy_source, run)
    mapping = await get_mapping(db_session, "user_account", 7)
    assert mapping.target_id == existing.id
    assert result.reused == 1
    assert result.created == 0


@pytest.mark.asyncio
async def test_duplicate_telegram_id_is_not_merged(db_session, conflicting_source, run):
    result = await reconcile_accounts(db_session, conflicting_source, run)
    issues = await list_issue_codes(db_session, run.id)
    assert result.quarantined == 2
    assert issues.count("identity.telegram_duplicate") == 2
    assert await count_mapped_targets(db_session, "user_account") == 0
```

Add tests for exact login/type, exact Telegram/type, mismatched account type, duplicate login, duplicate phone/Telegram detection, missing business owner and a second identical run creating zero accounts.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_reconcile.py -q`  
Expected: FAIL because `reconcile_accounts` is missing.

- [ ] **Step 3: Implement source-row hashing and mapping lookup**

```python
def source_row_hash(entity_type: str, row: Mapping[str, object]) -> str:
    payload = {
        "entity_type": entity_type,
        "row": {key: row[key] for key in sorted(row)},
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        .encode("utf-8")
    ).hexdigest()
```

Before creating anything, lock/read `LegacyIdMap(entity_type, legacy_id)`. An unchanged hash reuses the target; a changed source row updates only fields allowlisted for that stage and stores the new hash.

- [ ] **Step 4: Apply exact identity precedence**

For `users`:

1. Existing `legacy_id_map`.
2. Exact normalized `login` plus exact `AccountType`.
3. Exact non-null `tg_id` plus exact `AccountType`.
4. Otherwise create a new account if no conflict exists.

Never map by similar name or approximate phone. `users.role == "business"` produces a business account and later receives a `BusinessProfile`; ordinary users receive `UserProfile`. Preserve `pass_hash` unchanged because Task 3 handles one-time rehash. Set account status from the source status when available, otherwise `active`.

- [ ] **Step 5: Reconcile businesses through owner mapping**

Map `businesses.user_id -> LegacyIdMap("user_account", user_id)`. Populate `BusinessProfile` with `name`, `phone`, `descr`, `username`, `yon`, `tur`, `address`, coordinates, parsed `work_hours`, payment/admin fields and crop values. If owner mapping is ambiguous, create `identity.business_owner_unresolved` and no fake account/profile.

- [ ] **Step 6: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_reconcile.py -q`  
Expected: PASS with the second-run assertion `created == 0`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/legacy_migration/reconcile.py \
  backend/tests/test_legacy_reconcile.py
git commit -m "feat: reconcile legacy owners"
```

## Task 6: Import Catalog Groups, Products, and Services

**Files:**

- Create: `backend/app/legacy_migration/catalog_stage.py`
- Create: `backend/tests/test_legacy_catalog_stage.py`

**Interfaces:**

- Produces: `import_catalog(session, source, run) -> StageResult`.
- Creates mappings `catalog_group` and `catalog_item`.
- Consumes `business_account` mappings from Task 5.

- [ ] **Step 1: Write catalog behavior tests**

```python
@pytest.mark.asyncio
async def test_catalog_keeps_price_kind_status_and_owner(db_session, source, run):
    await import_catalog(db_session, source, run)
    item = await db_session.scalar(select(CatalogItem).where(CatalogItem.name == "Mebel"))
    assert item.price_text == "1 500 000 so'mdan"
    assert item.kind == "product"
    assert item.owner_state is OwnerState.LINKED
    assert item.business_account_id is not None
    assert item.review_state is ReviewState.READY


@pytest.mark.asyncio
async def test_unlinked_owner_item_is_visible_but_has_no_owner_id(
    db_session, source_without_owner_mapping, run
):
    await import_catalog(db_session, source_without_owner_mapping, run)
    item = await db_session.scalar(select(CatalogItem))
    assert item.owner_state is OwnerState.UNLINKED
    assert item.business_account_id is None
    assert item.review_state is ReviewState.READY


@pytest.mark.asyncio
async def test_missing_required_name_is_quarantined(db_session, source_blank_name, run):
    await import_catalog(db_session, source_blank_name, run)
    item = await db_session.scalar(select(CatalogItem))
    assert item.review_state is ReviewState.REVIEW_REQUIRED
    assert await issue_exists(db_session, run.id, "catalog.required.name")
```

Also cover group mapping, `queue_enabled`, inactive status, exact source `created_at`, missing photo reference, source-row update and zero duplicates on rerun.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_catalog_stage.py -q`  
Expected: FAIL because `import_catalog` is missing.

- [ ] **Step 3: Implement group-before-item import**

```python
async def import_catalog(
    session: AsyncSession,
    source: sqlite3.Connection,
    run: MigrationRun,
) -> StageResult:
    await import_catalog_groups(session, source, run)
    return await import_catalog_items(session, source, run)
```

Validate `kind in {"product", "service"}`. Unknown kind is preserved as an issue and `review_required`, not silently changed to `product`. Convert Unix seconds to timezone-aware UTC. Save `photo_file` only as a `MediaMigration` pending reference fingerprint/slot `primary`; do not write the legacy reference into `image_object_key`.

- [ ] **Step 4: Implement review and owner rules**

`name.strip()` and valid kind are required for public visibility. Missing owner alone does not cause review quarantine: use `owner_name_snapshot` from the source business and `owner_state=unlinked`. Missing safe public name/kind creates a `catalog.required.*` issue and hides the row.

- [ ] **Step 5: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_catalog_stage.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/legacy_migration/catalog_stage.py \
  backend/tests/test_legacy_catalog_stage.py
git commit -m "feat: import legacy catalog"
```

## Task 7: Import Listings Without Enabling the Feature

**Files:**

- Create: `backend/app/legacy_migration/listing_stage.py`
- Create: `backend/tests/test_legacy_listing_stage.py`

**Interfaces:**

- Produces: `import_listings(session, source, run) -> StageResult`.
- Creates mappings `listing` and `listing_media`.
- Listing public availability remains controlled by `Settings.listings_enabled`.

- [ ] **Step 1: Write listing import tests**

```python
@pytest.mark.asyncio
async def test_listing_and_media_metadata_are_distinct_from_ads(db_session, source, run):
    result = await import_listings(db_session, source, run)
    listing = await db_session.scalar(select(Listing))
    media = (await db_session.scalars(select(ListingMedia))).all()
    assert result.created == 2
    assert listing.price_text == "Kelishiladi"
    assert listing.visibility == "all"
    assert [item.position for item in media] == [0]
    assert media[0].object_key == ""
    assert media[0].migration_state == "pending"
    assert await db_session.scalar(select(func.count()).select_from(Advertisement)) == 0
```

Add cases for user owner, optional business owner, unresolved owner, inactive/deleted status, missing title/category, photo/video positions and idempotent rerun.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_listing_stage.py -q`  
Expected: FAIL because `import_listings` is missing.

- [ ] **Step 3: Import listing metadata and media slots**

Map `listings.user_id` through `user_account` and optional `business_id` through `business_account`. Keep exact `price`, `visibility`, coordinates, status and timestamps. Required `title` and `cat` failures create `listing.required.title` or `listing.required.category` and set `review_required`.

For each `listing_media` row create:

```python
ListingMedia(
    listing_id=target_listing.id,
    media_type=normalize_media_type(row["mtype"]),
    object_key="",
    position=int(row["pos"] or 0),
    migration_state="pending",
    migration_run_id=run.id,
)
```

Create corresponding `MediaMigration(entity_type="listing_media", legacy_id=row["id"], slot="primary")`. Store only a SHA-256 fingerprint of `tg_file_id` in migration control data; the raw Telegram file ID stays in memory/source snapshot and never enters reports.

- [ ] **Step 4: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_listing_stage.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/legacy_migration/listing_stage.py \
  backend/tests/test_legacy_listing_stage.py
git commit -m "feat: import legacy listings"
```

## Task 8: Import Advertisement Snapshots Separately

**Files:**

- Create: `backend/app/legacy_migration/advertisement_stage.py`
- Create: `backend/tests/test_legacy_advertisement_stage.py`

**Interfaces:**

- Produces: `import_advertisements(session, source, run) -> StageResult`.
- Creates mapping `advertisement`.
- Creates media slots `desktop` and `mobile`.

- [ ] **Step 1: Write advertisement fidelity tests**

```python
@pytest.mark.asyncio
async def test_ad_snapshot_is_not_repriced_or_turned_into_business(db_session, source, run):
    await import_advertisements(db_session, source, run)
    ad = await db_session.scalar(select(Advertisement))
    assert ad.title == "Turon Savdo"
    assert ad.owner_business_account_id is None
    assert ad.price == 350_000
    assert ad.district_count == 7
    assert ad.hours_per_day == 1
    assert ad.district_hour_rate == 50_000
    assert ad.billable_district_hours == 7
    assert ad.targets_json == [{"region": "Surxondaryo", "district": "Qumqo‘rg‘on"}]
    assert await count_business_profiles(db_session, "Turon Savdo") == 0
```

Add assertions for desktop/mobile file slots, crop values, daily time window, start/end, duration, status, views/clicks, malformed `targets_json`, owner mapping and idempotent rerun.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_advertisement_stage.py -q`  
Expected: FAIL because `import_advertisements` is missing.

- [ ] **Step 3: Import exact schedule and historical price snapshot**

Never call a pricing calculator. Parse `targets_json` only when it is a JSON list of allowlisted region/district objects; malformed JSON produces `advertisement.targets_invalid` and `review_required`. Keep `title`/`caption` as the owner snapshot even with no mapped business.

Create `MediaMigration` rows:

```python
for slot, reference in (
    ("desktop", row["image_file"]),
    ("mobile", row["mobile_image_file"]),
):
    if reference:
        await ensure_media_mapping(
            session,
            run=run,
            entity_type="advertisement",
            legacy_id=row["id"],
            slot=slot,
            source_reference=reference,
        )
```

- [ ] **Step 4: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_advertisement_stage.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/legacy_migration/advertisement_stage.py \
  backend/tests/test_legacy_advertisement_stage.py
git commit -m "feat: import legacy advertisements"
```

## Task 9: Copy Media to R2 with Checksum Verification

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/media/storage.py`
- Create: `backend/app/legacy_migration/media_stage.py`
- Create: `backend/tests/test_legacy_media_stage.py`
- Modify: `backend/tests/test_media_storage.py`

**Interfaces:**

- Produces: `ResolvedMedia(stream: BinaryIO, content_type: str, size_bytes: int, sha256: str)`.
- Produces adapters `LocalMediaResolver` and `TelegramMediaResolver`.
- Produces: `R2Storage.put_migration_object(...) -> StoredObject`.
- Produces: `R2Storage.verify_object(...) -> bool`.
- Produces: `migrate_media(session, source, storage, settings, run) -> StageResult`.

- [ ] **Step 1: Write media-state tests**

```python
@pytest.mark.asyncio
async def test_valid_media_is_uploaded_and_verified(db_session, fake_storage, source, run):
    result = await migrate_media(db_session, source, fake_storage, test_settings, run)
    media = await db_session.scalar(select(MediaMigration))
    assert result.created == 1
    assert media.state is MediaMigrationState.COPIED
    assert len(media.sha256) == 64
    assert media.size_bytes == len(PNG_BYTES)
    assert media.destination_object_key.startswith(f"migration/{run.id}/")
    assert fake_storage.verified == [media.destination_object_key]


@pytest.mark.asyncio
async def test_missing_media_keeps_content_and_marks_missing(
    db_session, missing_source, fake_storage, run
):
    await migrate_media(db_session, missing_source, fake_storage, test_settings, run)
    media = await db_session.scalar(select(MediaMigration))
    item = await db_session.scalar(select(CatalogItem))
    assert media.state is MediaMigrationState.MISSING
    assert item.image_object_key == ""


@pytest.mark.asyncio
async def test_path_escape_is_invalid_not_read(tmp_path, db_session, run):
    resolver = LocalMediaResolver((tmp_path / "uploads",))
    result = await resolver.resolve("../../etc/passwd")
    assert result.code == "media.path_outside_roots"
```

Add tests for JPEG/PNG/WebP/GIF/MP4/WebM magic bytes, oversized media, Telegram 404, checksum mismatch, desktop/mobile assignment, retry count and safe error codes.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_media_stage.py tests/test_media_storage.py -q`  
Expected: FAIL because migration upload methods are missing.

- [ ] **Step 3: Add safe settings**

```python
legacy_media_roots: str = ""
legacy_media_max_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
legacy_snapshot_root: str = ""
listings_enabled: bool = False
phase3c_public_enabled: bool = False
```

Production validation rejects an empty `legacy_snapshot_root` only for the migrator CLI, not for normal API startup. Never store the Telegram token or R2 secret in a report.

- [ ] **Step 4: Implement byte sniffing and streaming**

Read at most the configured limit into `tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)`, updating SHA-256 incrementally. Validate content signatures:

```python
def sniff_media_type(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header[:4] in {b"GIF8"}:
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    return None
```

Local resolution canonicalizes paths and requires `resolved_path.is_relative_to(allowed_root)`. Telegram resolution calls `getFile`, then streams the returned file path through `httpx.AsyncClient.stream`; raw `file_id` and bot token never enter logs.

- [ ] **Step 5: Upload and verify**

Use R2 key `migration/{run_id}/{entity_type}/{legacy_id}/{slot}/{sha256}{suffix}`. Call `upload_fileobj`, then `head_object`; compare `ContentLength`, stored `sha256` metadata and content type before marking `copied`. `missing` and `invalid` are terminal non-blocking states; transport/R2/checksum errors are `failed` and block the gate.

- [ ] **Step 6: Assign verified keys**

Only after verification update the target field:

- catalog `primary -> CatalogItem.image_object_key`;
- listing media `primary -> ListingMedia.object_key`;
- advertisement `desktop -> desktop_image_object_key`;
- advertisement `mobile -> mobile_image_object_key`.

- [ ] **Step 7: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_media_stage.py tests/test_media_storage.py tests/test_config.py -q`  
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/app/media/storage.py \
  backend/app/legacy_migration/media_stage.py \
  backend/tests/test_legacy_media_stage.py backend/tests/test_media_storage.py
git commit -m "feat: migrate legacy media to R2"
```

## Task 10: Orchestrate Stages, Reports, and Verification Gates

**Files:**

- Create: `backend/app/legacy_migration/report.py`
- Create: `backend/app/legacy_migration/verify.py`
- Create: `backend/app/legacy_migration/runner.py`
- Create: `backend/app/legacy_migration/cli.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/test_legacy_migration_runner.py`
- Create: `backend/tests/test_legacy_migration_report.py`
- Create: `backend/tests/test_legacy_migration_verify.py`

**Interfaces:**

- Produces: `MigrationRunner.run(snapshot, environment, until_stage=None) -> MigrationRun`.
- Produces CLI `koprik-migrate-legacy snapshot|run|verify|report`.
- Produces `VerificationReport(passed: bool, gates: list[GateResult])`.
- Produces JSON and Markdown reports containing safe codes/counts only.

- [ ] **Step 1: Write orchestration tests**

```python
@pytest.mark.asyncio
async def test_runner_executes_stages_in_fixed_order_and_resumes(db_session, fixture):
    runner = build_runner(db_session, fixture)
    first = await runner.run(fixture.snapshot, "staging", until_stage="catalog")
    assert first.stage == "catalog"
    second = await runner.run(fixture.snapshot, "staging")
    assert second.counters_json["catalog"]["created"] == 0
    assert second.stage == "verify"


@pytest.mark.asyncio
async def test_production_requires_explicit_confirmation_and_maintenance():
    runner = build_runner(environment="production")
    with pytest.raises(ProductionGateError, match="production_confirmation_required"):
        await runner.run(snapshot, "production")
```

Add tests for fingerprint mismatch, failed prerequisite stage, failed media, unresolved identity conflicts, source/target count mismatch, report redaction and successful idempotency gate.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_legacy_migration_runner.py tests/test_legacy_migration_report.py tests/test_legacy_migration_verify.py -q`  
Expected: FAIL because runner/report/verifier modules are missing.

- [ ] **Step 3: Implement fixed stage registry**

```python
STAGES: tuple[StageDefinition, ...] = (
    StageDefinition("inventory", inventory_stage),
    StageDefinition("accounts", reconcile_accounts),
    StageDefinition("businesses", reconcile_businesses),
    StageDefinition("catalog", import_catalog),
    StageDefinition("listings", import_listings),
    StageDefinition("advertisements", import_advertisements),
    StageDefinition("media", migrate_media),
    StageDefinition("verify", verify_migration),
)
```

Each stage runs in its own PostgreSQL transaction. Successful stage counters commit; an unexpected exception rolls back the stage, records a safe stage-level error code in a fresh transaction and marks the run `failed`.

- [ ] **Step 4: Implement production guard**

Production execution requires all of:

```python
ProductionApproval(
    typed_environment="production",
    typed_snapshot_sha256=snapshot.database_sha256,
    maintenance_enabled=True,
    approved_staging_run_id=staging_run_id,
)
```

The approved staging run must use the same schema version and have all gates passed. The CLI never infers production approval from environment variables alone.

- [ ] **Step 5: Implement exact gates**

`verify_migration` fails when:

- any required source row lacks one `legacy_id_map`;
- catalog kind counts differ;
- listing/ad counts are mixed or differ;
- foreign keys are broken;
- identity conflict count is non-zero;
- `MediaMigration.state == failed` count is non-zero;
- `copied + missing + invalid != source_media_reference_count`;
- copied R2 size/checksum verification fails;
- a second dry idempotency pass reports created rows;
- report/public schema leak scans find forbidden field names.

- [ ] **Step 6: Implement redacted reports**

Allow only run ID, fingerprints, timestamps, stage, entity type, legacy numeric ID, safe issue code, counters and gate result. Reject keys matching:

```python
FORBIDDEN_REPORT_KEYS = {
    "name", "phone", "login", "telegram_user_id", "tg_id",
    "password", "pass_hash", "pass_plain", "token",
    "source_reference", "object_url",
}
```

- [ ] **Step 7: Register CLI**

Add to `backend/pyproject.toml`:

```toml
[project.scripts]
koprik-worker = "app.outbox.worker:main"
koprik-migrate-legacy = "app.legacy_migration.cli:main"
```

CLI examples:

```bash
koprik-migrate-legacy snapshot \
  --source /data/platforma.db \
  --output /data/migration/2026-07-29
koprik-migrate-legacy run \
  --snapshot /data/migration/2026-07-29/platforma.snapshot.db \
  --environment staging
koprik-migrate-legacy verify --run-id 42
koprik-migrate-legacy report --run-id 42 --format markdown
```

- [ ] **Step 8: Run focused tests**

Run: `cd backend && pytest tests/test_legacy_migration_runner.py tests/test_legacy_migration_report.py tests/test_legacy_migration_verify.py -q`  
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/legacy_migration backend/pyproject.toml \
  backend/tests/test_legacy_migration_runner.py \
  backend/tests/test_legacy_migration_report.py \
  backend/tests/test_legacy_migration_verify.py
git commit -m "feat: orchestrate Phase 3C migration"
```

## Task 11: Publish Safe Catalog APIs

**Files:**

- Create: `backend/app/catalog/schemas.py`
- Create: `backend/app/catalog/repository.py`
- Create: `backend/app/catalog/service.py`
- Create: `backend/app/catalog/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_public_catalog_schemas.py`
- Create: `backend/tests/test_public_catalog_repository.py`
- Create: `backend/tests/test_public_catalog_router.py`

**Interfaces:**

- Produces: `GET /api/v1/public/catalog/items`.
- Produces: `GET /api/v1/public/catalog/items/{public_id}`.
- Produces `PublicCatalogItem` with capability flags and no private columns.
- Uses `build_content_public_id(kind: str, target_id: int) -> str`.

- [ ] **Step 1: Write schema and HTTP tests**

```python
def test_unlinked_catalog_card_disables_owner_actions():
    item = PublicCatalogItem(
        kind="product",
        public_id="p_abc",
        name="Mebel",
        price_text="Kelishiladi",
        owner_state="unlinked",
        owner_label="Egasi hali akkauntini bog‘lamagan",
        can_order=False,
        can_chat=False,
    )
    assert "business_account_id" not in item.model_dump()
    assert "image_object_key" not in item.model_dump()


def test_catalog_route_is_public_and_filters_product(client):
    response = client.get(
        "/api/v1/public/catalog/items",
        params={"kind": "product", "district": "Qumqo‘rg‘on", "page": 1},
    )
    assert response.status_code == 200
    assert all(item["kind"] == "product" for item in response.json()["items"])
```

Repository tests prove inactive, deleted and `review_required` rows are excluded; unlinked ready rows remain; ordering and pagination are deterministic; filters cover kind, direction, activity type, region, district, mahalla and `q`.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_public_catalog_schemas.py tests/test_public_catalog_repository.py tests/test_public_catalog_router.py -q`  
Expected: FAIL because catalog public modules are missing.

- [ ] **Step 3: Implement allowlisted query projection**

Select only public columns and safe owner/profile fields. Build IDs with keyed BLAKE2s, using distinct prefixes `p_` and `s_`; never expose target ID or legacy ID. Media URL generation consumes an object key internally and returns a short-lived/public-safe URL; the key is absent from the response model.

Required response fields:

```python
class PublicCatalogItem(BaseModel):
    kind: Literal["product", "service"]
    public_id: str
    name: str
    price_text: str
    note: str
    owner_state: Literal["linked", "unlinked"]
    owner_public_id: str
    owner_name: str
    owner_label: str
    direction: str
    activity_type: str
    region: str
    district: str
    mahalla: str
    image_url: str
    can_order: bool
    can_chat: bool
```

- [ ] **Step 4: Add cache with PostgreSQL fallback**

Follow `PublicDiscoveryService`: canonical JSON key, 30-second TTL, single-flight task, Redis read/write failure fallback. Use cache prefix `public:catalog:v1:`. Gate the router with `phase3c_public_enabled`; disabled staging returns `404 feature_not_available`.

- [ ] **Step 5: Register service and router**

Construct `CatalogService` in FastAPI lifespan using `database.session`, Redis, R2 URL provider and settings. Store it in `app.state.catalog_service`; include the router without auth dependencies.

- [ ] **Step 6: Run focused and backend tests**

Run:

```bash
cd backend
pytest tests/test_public_catalog_schemas.py tests/test_public_catalog_repository.py \
  tests/test_public_catalog_router.py -q
pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/catalog backend/app/main.py \
  backend/tests/test_public_catalog_schemas.py \
  backend/tests/test_public_catalog_repository.py \
  backend/tests/test_public_catalog_router.py
git commit -m "feat: expose public catalog"
```

## Task 12: Publish Advertisement Selection and Keep Listings Closed

**Files:**

- Create: `backend/app/advertisements/schemas.py`
- Create: `backend/app/advertisements/repository.py`
- Create: `backend/app/advertisements/router.py`
- Create: `backend/app/listings/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_public_advertisements.py`
- Create: `backend/tests/test_listings_feature_flag.py`

**Interfaces:**

- Produces: `GET /api/v1/public/advertisements`.
- Produces: `GET /api/v1/public/listings` returning `404 feature_not_available` while disabled.
- Produces: `select_active_advertisements(now, placement, location)`.

- [ ] **Step 1: Write schedule/target tests**

```python
@pytest.mark.asyncio
async def test_ad_must_match_date_time_status_placement_and_location(db_session):
    items = await select_active_advertisements(
        db_session,
        now=datetime(2026, 7, 29, 18, 30, tzinfo=UTC),
        placement="home",
        region="Surxondaryo",
        district="Qumqo‘rg‘on",
    )
    assert [item.title for item in items] == [
        "Tuman banneri", "Viloyat banneri", "Respublika banneri"
    ]


def test_listings_remain_closed(client):
    response = client.get("/api/v1/public/listings")
    assert response.status_code == 404
    assert response.json()["code"] == "feature_not_available"
```

Cover all-day ads, overnight daily ranges, start/end boundaries, expired/blocked ads, district/region/republic target precedence, stable ordering and desktop/mobile URL fields.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_public_advertisements.py tests/test_listings_feature_flag.py -q`  
Expected: FAIL because routers/repository are missing.

- [ ] **Step 3: Implement ad selection without repricing**

Filter `status == "active"`, `review_state == "ready"`, `placement`, inclusive `start_at <= now < end_at`, daily window and target match. Sort target specificity `district -> region -> republic`, then schedule start and ID. Return title, caption, linked owner public ID when available, desktop/mobile media URLs and crop values; do not return price/statistics/internal target JSON.

- [ ] **Step 4: Add explicit listings flag route**

```python
@router.get("/listings")
async def list_public_listings(request: Request):
    if not request.app.state.settings.listings_enabled:
        raise ApiError(
            404,
            "feature_not_available",
            "E’lonlar hozircha ochilmagan.",
        )
    return await request.app.state.listing_service.list_public()
```

Do not construct or call `listing_service` while the flag is false. No frontend link is added in this task.

- [ ] **Step 5: Run focused and backend tests**

Run:

```bash
cd backend
pytest tests/test_public_advertisements.py tests/test_listings_feature_flag.py -q
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/advertisements backend/app/listings/router.py \
  backend/app/main.py backend/tests/test_public_advertisements.py \
  backend/tests/test_listings_feature_flag.py
git commit -m "feat: serve ads and gate listings"
```

## Task 13: Extend Unified Public Search with Products and Services

**Files:**

- Modify: `backend/app/public_discovery/schemas.py`
- Modify: `backend/app/public_discovery/repository.py`
- Modify: `backend/app/public_discovery/service.py`
- Modify: `backend/tests/test_public_discovery_schemas.py`
- Modify: `backend/tests/test_public_discovery_repository.py`
- Modify: `backend/tests/test_public_discovery_service.py`
- Modify: `backend/tests/test_public_discovery_router.py`

**Interfaces:**

- Extends `PublicResultKind` and `PublicResultType` with `PRODUCT` and `SERVICE`.
- Preserves current `all | user | business` request behavior and existing profile card fields.
- Bumps cache prefix from `public:search:v1:` to `public:search:v2:`.

- [ ] **Step 1: Write backward-compatibility and content tests**

```python
def test_all_search_keeps_profiles_and_adds_content():
    params = PublicSearchParams(q="mebel", result_type="all")
    data, _ = build_public_search_statements(params)
    sql = compile_sql(data)
    assert "user_profiles" in sql
    assert "business_profiles" in sql
    assert "catalog_items" in sql


def test_product_search_excludes_profile_tables():
    data, _ = build_public_search_statements(
        PublicSearchParams(q="mebel", result_type="product")
    )
    sql = compile_sql(data)
    assert "catalog_items" in sql
    assert "user_profiles" not in sql
    assert "business_profiles" not in sql
    assert "review_required" in sql
```

Router tests prove old profile response fields remain unchanged and content cards add only `price_text`, `owner_state`, `owner_label`, `can_order`, `can_chat`.

- [ ] **Step 2: Confirm RED**

Run: `cd backend && pytest tests/test_public_discovery_schemas.py tests/test_public_discovery_repository.py tests/test_public_discovery_service.py tests/test_public_discovery_router.py -q`  
Expected: FAIL because `product` and `service` are rejected.

- [ ] **Step 3: Add a union-compatible content projection**

Keep one normalized union projection with empty literals for fields not used by a kind. Content query requires active status, ready review state and enabled Phase 3C public flag. Product/service cards use the same opaque ID and media URL rules as Task 11. Unlinked cards expose the warning/capabilities but no owner account ID.

- [ ] **Step 4: Preserve caching and fallback**

Change `_CACHE_PREFIX = "public:search:v2:"` to avoid stale v1 profile-only payloads. Keep canonical params, 30-second TTL, single-flight and Redis failure fallback unchanged.

- [ ] **Step 5: Run focused and backend tests**

Run:

```bash
cd backend
pytest tests/test_public_discovery_schemas.py tests/test_public_discovery_repository.py \
  tests/test_public_discovery_service.py tests/test_public_discovery_router.py -q
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/public_discovery backend/tests/test_public_discovery_*.py
git commit -m "feat: search products and services"
```

## Task 14: Connect the Typed Frontend to Catalog and Advertisements

**Files:**

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`
- Create: `frontend/src/legacy/public/CatalogItemCard.tsx`
- Create: `frontend/src/legacy/public/CatalogItemCard.test.tsx`
- Create: `frontend/src/legacy/public/HomeAdvertisements.tsx`
- Create: `frontend/src/legacy/public/HomeAdvertisements.test.tsx`
- Modify: `frontend/src/legacy/public/PublicSearchResults.tsx`
- Modify: `frontend/src/legacy/public/CatalogScreen.tsx`
- Modify: `frontend/src/legacy/public/CatalogScreen.test.tsx`
- Modify: `frontend/src/legacy/public/CategoryScreen.tsx`
- Modify: `frontend/src/legacy/public/CategoryScreen.test.tsx`
- Modify: `frontend/src/legacy/public/HomeScreen.tsx`
- Modify: `frontend/src/legacy/public/HomeScreen.test.tsx`
- Modify: `frontend/src/legacy/public/legacy-public.css`
- Create: `frontend/public/maintenance.html`

**Interfaces:**

- Produces client methods `getCatalogItems`, `getCatalogItem`, `getAdvertisements`.
- Extends `searchPublic` result kinds with `product | service`.
- Keeps `E’lonlar` navigation absent.

- [ ] **Step 1: Write typed-client tests**

```typescript
it("serializes catalog filters without auth or CSRF", async () => {
  await api.getCatalogItems({
    kind: "service",
    district: "Qumqo‘rg‘on",
    page: 2,
    page_size: 20,
  });
  expect(fetcher).toHaveBeenCalledWith(
    expect.stringContaining(
      "/api/v1/public/catalog/items?kind=service&district=Qumqo%E2%80%98rg%E2%80%98on&page=2&page_size=20",
    ),
    expect.objectContaining({
      method: "GET",
      headers: { Accept: "application/json" },
    }),
  );
});
```

Add tests for advertisement location/placement parameters and the absence of `X-CSRF-Token`.

- [ ] **Step 2: Write component tests**

```typescript
it("shows the unlinked-owner warning and disables actions", () => {
  render(<CatalogItemCard item={unlinkedItem} />);
  expect(screen.getByText("Egasi hali akkauntini bog‘lamagan")).toBeVisible();
  expect(screen.getByRole("button", { name: "Buyurtma berish" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Chat" })).toBeDisabled();
});

it("uses the mobile banner source on a narrow screen", async () => {
  setViewportWidth(390);
  render(<HomeAdvertisements api={api} location={location} />);
  expect(await screen.findByRole("img", { name: "Turon Savdo" }))
    .toHaveAttribute("src", "/media/mobile.webp");
});
```

Cover loading, empty, retry, pagination, product/service label, linked owner navigation, missing-media standard image, responsive banner and public data rendering when session bootstrap fails.

- [ ] **Step 3: Confirm RED**

Run:

```bash
cd frontend
npm test -- src/api/client.test.ts \
  src/legacy/public/CatalogItemCard.test.tsx \
  src/legacy/public/HomeAdvertisements.test.tsx \
  src/legacy/public/CatalogScreen.test.tsx \
  src/legacy/public/CategoryScreen.test.tsx \
  src/legacy/public/HomeScreen.test.tsx
```

Expected: FAIL because types, methods and components are missing.

- [ ] **Step 4: Add exact TypeScript contracts**

```typescript
export type PublicCatalogItem = {
  kind: "product" | "service";
  public_id: string;
  name: string;
  price_text: string;
  note: string;
  owner_state: "linked" | "unlinked";
  owner_public_id: string;
  owner_name: string;
  owner_label: string;
  direction: string;
  activity_type: string;
  region: string;
  district: string;
  mahalla: string;
  image_url: string;
  can_order: boolean;
  can_chat: boolean;
};
```

Mirror backend pagination and ad response names exactly. Optional query values are omitted; parameter order is fixed and tested.

- [ ] **Step 5: Render real catalog/search/ad data**

`CatalogScreen` and `CategoryScreen` load from `getCatalogItems`; local direction/activity data remains only for navigation/filter labels. `PublicSearchResults` renders all four result kinds. `HomeScreen` renders `HomeAdvertisements` but never renders an `E’lonlar` link or calls `/public/listings`.

Use `/assets/catalog-placeholder.svg` or the existing checked-in safe standard image for missing media. Do not embed legacy Telegram/R2 references.

- [ ] **Step 6: Add maintenance page**

`frontend/public/maintenance.html` is self-contained, responsive, contains “Texnik ishlar olib borilmoqda”, and has no API calls. It is deployed as `/maintenance.html`; routing to it is an operations step in Task 15.

- [ ] **Step 7: Run frontend tests and production build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all Vitest suites PASS and Vite build exits `0`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src frontend/public/maintenance.html
git commit -m "feat: render migrated catalog and ads"
```

## Task 15: Add Contract Verification, Staging, Cutover, and Rollback

**Files:**

- Create: `scripts/verify_phase3c.py`
- Create: `tests/test_phase3c_content_migration_contract.py`
- Create: `docs/deploy-phase3c-staging.md`
- Create: `docs/deploy-phase3c-production.md`
- Modify only if required: `.github/workflows/phase1-ci.yml`

**Interfaces:**

- Produces command `python scripts/verify_phase3c.py`.
- Produces a staging approval record with run ID, snapshot SHA-256 and gate results.
- Produces a production checklist that does not delete the monolith or legacy media.

- [ ] **Step 1: Write cross-layer contract tests**

```python
def test_phase3c_contract_keeps_legacy_and_separates_listing_from_ad():
    assert 'BUILD = "v1656"' in Path("static/index.html").read_text(encoding="utf-8")
    listing = Path("backend/app/listings/model.py").read_text(encoding="utf-8")
    ad = Path("backend/app/advertisements/model.py").read_text(encoding="utf-8")
    assert '__tablename__ = "listings"' in listing
    assert '__tablename__ = "advertisements"' in ad
    assert "price_text" in listing
    assert "daily_start" in ad


def test_public_contract_never_exposes_private_identifiers():
    public_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path("backend/app/catalog/schemas.py"),
            Path("backend/app/advertisements/schemas.py"),
            Path("backend/app/public_discovery/schemas.py"),
            Path("frontend/src/api/types.ts"),
        )
    )
    for forbidden in (
        "password_hash", "telegram_user_id", "business_account_id",
        "image_object_key", "desktop_image_object_key", "legacy_id",
    ):
        assert forbidden not in public_sources
```

Add checks for migration revision, fixed stage order, false listing flag default, v2 search cache, frontend/backend field-name parity, report forbidden keys, maintenance page and unchanged legacy line-count contract.

- [ ] **Step 2: Confirm RED**

Run: `pytest tests/test_phase3c_content_migration_contract.py -q`  
Expected: FAIL until the verifier/runbooks exist and every Phase 3C file is present.

- [ ] **Step 3: Implement repository verifier**

`scripts/verify_phase3c.py` runs static contract checks without production credentials. It exits non-zero on a missing model/migration, public private-field leak, stage-order drift, listing flag enabled by default, absent maintenance page or legacy BUILD/line-count change.

- [ ] **Step 4: Write staging runbook**

The exact sequence in `docs/deploy-phase3c-staging.md`:

1. Deploy PostgreSQL revision `0003_phase3c_content`.
2. Create immutable snapshot and record SHA-256.
3. Run migration through `verify`.
4. Run the same snapshot again and require `created=0`.
5. Inspect JSON/Markdown report for counts and safe issue codes.
6. Resolve all identity conflicts.
7. Require media `failed=0` and reconciliation equality.
8. Enable `KOPRIK_PHASE3C_PUBLIC_ENABLED=true` on staging only.
9. Smoke-test health, readiness, profiles, products, services, location filters, owner warning, disabled actions, ads and closed listings.
10. Test Redis-off PostgreSQL fallback.
11. Test phone, tablet and desktop frontend.
12. Record approved staging run ID and snapshot fingerprint.

- [ ] **Step 5: Write production and rollback runbook**

The exact sequence in `docs/deploy-phase3c-production.md`:

1. Confirm approved staging run and maintenance window.
2. Route users to `/maintenance.html`.
3. Stop all monolith writes and verify no write worker remains.
4. Take the final SQLite backup/media manifest and fingerprints.
5. Run production migration with typed environment, snapshot hash, maintenance flag and approved staging run ID.
6. Require every verification gate PASS.
7. Run API/frontend smoke tests while maintenance remains active.
8. Switch routing to the new frontend/backend.
9. Remove maintenance routing.
10. Require every user to log in once; do not require re-registration.

Rollback on any failed gate:

1. Route back to `/maintenance.html`.
2. Disable `KOPRIK_PHASE3C_PUBLIC_ENABLED`.
3. Restore routing to the unchanged monolith.
4. Re-enable monolith writes.
5. Keep PostgreSQL run rows isolated by `migration_run_id`.
6. Do not delete SQLite, R2 objects or partial target rows.
7. Correct the issue and rerun idempotently.

- [ ] **Step 6: Run the complete fresh verification matrix**

Run:

```bash
python scripts/verify_phase1.py
python scripts/verify_phase2.py
python scripts/verify_phase3a.py
python scripts/verify_phase3b.py
python scripts/verify_phase3c.py
cd backend && pytest -q
cd ../frontend && npm test && npm run build
cd .. && pytest tests/test_phase3c_content_migration_contract.py -q
```

Expected: every command exits `0`; backend/frontend test counts and build output are copied verbatim into the commit/PR handoff.

- [ ] **Step 7: Run redaction and incomplete-work scans**

Run:

```bash
rg -n 'NotImplementedError|pass_plain|telegram_bot_token|r2_secret_access_key' \
  backend/app/legacy_migration docs/deploy-phase3c-*.md scripts/verify_phase3c.py
```

Expected: no unfinished implementation stubs or secret values. The only allowed `pass_plain` matches are explicit negative assertions proving it is absent from target/report output.

- [ ] **Step 8: Commit**

```bash
git add scripts/verify_phase3c.py tests/test_phase3c_content_migration_contract.py \
  docs/deploy-phase3c-staging.md docs/deploy-phase3c-production.md \
  .github/workflows/phase1-ci.yml
git commit -m "docs: add Phase 3C rollout gates"
```

- [ ] **Step 9: Prepare the review handoff**

Push `codex/phase3c-content-migration` and open a draft PR to `main` only after all implementation tasks are complete. The PR body includes exact test/build outputs, staging run ID, source snapshot SHA-256, entity/media counts, unresolved issue count, legacy BUILD/line-count statement, maintenance steps and rollback evidence. Production migration is not performed by merging the PR.

---

## Implementation Completion Gate

Phase 3C implementation is ready for staging only when all conditions are true:

1. Revision `0003_phase3c_content` upgrades cleanly.
2. Immutable snapshot passes both SQLite integrity checks.
3. Account/business mapping is deterministic and identity conflicts are resolved.
4. Catalog, listings and advertisements reconcile independently.
5. Second identical run creates zero rows.
6. Media has `failed=0`; copied checksums match; missing/invalid items render the standard image.
7. Public schemas pass the private-field denylist.
8. Unlinked catalog items show the warning and disable order/chat.
9. Listings remain `404 feature_not_available`.
10. Redis failure falls back to PostgreSQL.
11. All backend/frontend/contract/verifier commands pass.
12. `static/index.html` remains BUILD v1656 with its recorded line-count contract.
13. Staging report and rollback drill are reviewed before a production maintenance window is scheduled.
