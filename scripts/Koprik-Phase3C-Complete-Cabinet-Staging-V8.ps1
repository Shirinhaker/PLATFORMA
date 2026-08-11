param(
    [Parameter(Mandatory = $true)]
    [string]$Archive,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedArchiveSha256,
    [Parameter(Mandatory = $true)]
    [string]$SshTarget,
    [switch]$Execute,
    [switch]$BackupConfirmed,
    [ValidateRange(1, 1000)]
    [int]$NormalizationBatchSize = 100
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedSchema = "0008_phase3c_taxi_v1"
$ExpectedInitialHead = "0005_profile_cabinet_parity"
$ExpectedFinalHead = "0041_taxi_driver_domain"
$RemoteRoot = "/tmp/koprik-phase3c-v8-input"
$RemoteArchive = "$RemoteRoot/koprik-phase3c-source-final.tar.gz"

Write-Host "SCRIPT_VERSION=8"
Write-Host "MIGRATION_MODE=FRESH_CURRENT_TYPED_CABINETS"
Write-Host ("EXECUTE={0}" -f $Execute.IsPresent)

function Invoke-RemoteBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,
        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    $Token = [Guid]::NewGuid().ToString("N")
    $TempRoot = [IO.Path]::GetTempPath()
    $InputPath = Join-Path $TempRoot "koprik-v8-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v8-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v8-$Token.err"
    $Utf8NoBom = New-Object Text.UTF8Encoding($false)

    try {
        # Windows nusxasida bu fayl CRLF bilan olinadi va here-string ham
        # CRLF saqlaydi. Masofaviy bash uchun `pipefail\r` — mavjud bo'lmagan
        # parametr, ya'ni skript hech qachon ishlamaydi. LF ga keltiriladi.
        $UnixScript = $Script -replace "`r`n", "`n" -replace "`r", "`n"
        [IO.File]::WriteAllText($InputPath, $UnixScript, $Utf8NoBom)
        $Process = Start-Process `
            -FilePath "ssh.exe" `
            -ArgumentList @($SshTarget, "bash -s") `
            -RedirectStandardInput $InputPath `
            -RedirectStandardOutput $OutputPath `
            -RedirectStandardError $ErrorPath `
            -NoNewWindow `
            -Wait `
            -PassThru

        $Output = if (Test-Path -LiteralPath $OutputPath) {
            Get-Content -LiteralPath $OutputPath
        } else {
            @()
        }
        $Errors = if (Test-Path -LiteralPath $ErrorPath) {
            Get-Content -LiteralPath $ErrorPath
        } else {
            @()
        }
        $Output | ForEach-Object { Write-Host $_ }
        $Errors | ForEach-Object { Write-Error $_ -ErrorAction Continue }
        if ($Process.ExitCode -ne 0) {
            throw $FailureCode
        }
        return ,$Output
    }
    finally {
        Remove-Item -LiteralPath $InputPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $ErrorPath -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    throw "SOURCE_ARCHIVE_NOT_FOUND"
}
$ActualArchiveSha256 = (
    Get-FileHash -LiteralPath $Archive -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($ActualArchiveSha256 -ne $ExpectedArchiveSha256.ToLowerInvariant()) {
    throw "LOCAL_ARCHIVE_SHA256_MISMATCH"
}
Write-Host "LOCAL_ARCHIVE_SHA256_OK"

$PreflightScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V8_ERROR=%s\n' "$1" >&2
  exit 1
}

test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "environment_is_not_staging"
case "${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_be_disabled"
    ;;
esac

find_backend_dir() {
  for candidate in "$PWD" "$PWD/backend" /app /app/backend; do
    if test -f "$candidate/alembic.ini" \
      && test -f "$candidate/pyproject.toml" \
      && test -d "$candidate/app/legacy_migration"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

BACKEND_DIR="$(find_backend_dir)" || fail "backend_directory_not_found"
cd "$BACKEND_DIR"

DEPLOYED_SCHEMA="$(python - <<'PY'
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
print(MIGRATION_SCHEMA_VERSION)
PY
)"
test "$DEPLOYED_SCHEMA" = "0008_phase3c_taxi_v1" \
  || fail "current_complete_cabinet_code_not_deployed"
command -v koprik-migrate-legacy >/dev/null \
  || fail "migration_cli_not_installed"
command -v koprik-migrate-late-domains >/dev/null \
  || fail "late_domain_cli_not_installed"
python -c 'import app.cabinet_records.cli' \
  || fail "cabinet_normalization_cli_not_installed"

ALEMBIC_CURRENT="$(python -m alembic current)"
ALEMBIC_HEADS="$(python -m alembic heads)"
printf '%s\n' "$ALEMBIC_CURRENT"
printf '%s\n' "$ALEMBIC_HEADS"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "0005_profile_cabinet_parity" \
  || fail "fresh_migration_database_must_start_at_0005"
printf '%s' "$ALEMBIC_HEADS" | grep -q "0041_taxi_driver_domain" \
  || fail "current_alembic_head_not_deployed"

python - <<'PY'
from app.legacy_migration.profile_parity_v7 import (
    BUSINESS_MODULE_TABLES,
    EXPLICIT_DEMO_FLAGS,
    import_late_typed_domains,
)
assert "staff" in BUSINESS_MODULE_TABLES
assert "documents" in BUSINESS_MODULE_TABLES
assert "warehouse_items" in BUSINESS_MODULE_TABLES
assert "education_students" in BUSINESS_MODULE_TABLES
assert "medical_appointments" in BUSINESS_MODULE_TABLES
assert "is_demo" in EXPLICIT_DEMO_FLAGS
assert callable(import_late_typed_domains)
print("CURRENT_TYPED_CABINET_CODE_GUARD_OK")
PY

printf 'STAGING_V8_GUARD_OK SCHEMA=%s INITIAL_HEAD=%s FINAL_HEAD=%s BACKEND=%s\n' \
  "$DEPLOYED_SCHEMA" "0005_profile_cabinet_parity" \
  "0041_taxi_driver_domain" "$BACKEND_DIR"
'@

$PreflightOutput = Invoke-RemoteBash `
    -Script $PreflightScript `
    -FailureCode "STAGING_V8_PREFLIGHT_FAILED"
$PreflightText = $PreflightOutput -join "`n"
if ($PreflightText -notmatch "STAGING_V8_GUARD_OK") {
    throw "STAGING_V8_GUARD_CONFIRMATION_MISSING"
}
if ($PreflightText -notmatch [Regex]::Escape("SCHEMA=$ExpectedSchema")) {
    throw "STAGING_V8_SCHEMA_CONFIRMATION_MISMATCH"
}
if ($PreflightText -notmatch [Regex]::Escape("INITIAL_HEAD=$ExpectedInitialHead")) {
    throw "STAGING_V8_INITIAL_HEAD_CONFIRMATION_MISMATCH"
}
if ($PreflightText -notmatch [Regex]::Escape("FINAL_HEAD=$ExpectedFinalHead")) {
    throw "STAGING_V8_FINAL_HEAD_CONFIRMATION_MISMATCH"
}

if (-not $Execute.IsPresent) {
    Write-Host "DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0"
    exit 0
}
if (-not $BackupConfirmed.IsPresent) {
    throw "STAGING_BACKUP_CONFIRMATION_REQUIRED"
}

& ssh.exe $SshTarget "mkdir -p $RemoteRoot"
if ($LASTEXITCODE -ne 0) {
    throw "REMOTE_INPUT_DIRECTORY_FAILED"
}
& scp.exe -- $Archive "${SshTarget}:$RemoteArchive"
if ($LASTEXITCODE -ne 0) {
    throw "ARCHIVE_UPLOAD_FAILED"
}

$ExecuteScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V8_ERROR=%s\n' "$1" >&2
  exit 1
}

test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "environment_is_not_staging"
case "${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_be_disabled"
    ;;
esac

ARCHIVE="/tmp/koprik-phase3c-v8-input/koprik-phase3c-source-final.tar.gz"
EXPECTED_ARCHIVE_SHA256="__EXPECTED_ARCHIVE_SHA256__"
EXPECTED_SCHEMA="0008_phase3c_taxi_v1"
EXPECTED_INITIAL_HEAD="0005_profile_cabinet_parity"
EXPECTED_FINAL_HEAD="0041_taxi_driver_domain"
NORMALIZATION_BATCH_SIZE="__NORMALIZATION_BATCH_SIZE__"
WORK="/tmp/koprik-phase3c-v8-$(date +%Y%m%d-%H%M%S)"

test -f "$ARCHIVE" || fail "archive_not_found"
ACTUAL_ARCHIVE_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
test "$ACTUAL_ARCHIVE_SHA256" = "$EXPECTED_ARCHIVE_SHA256" \
  || fail "archive_sha256_mismatch"

find_backend_dir() {
  for candidate in "$PWD" "$PWD/backend" /app /app/backend; do
    if test -f "$candidate/alembic.ini" \
      && test -f "$candidate/pyproject.toml" \
      && test -d "$candidate/app/legacy_migration"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

BACKEND_DIR="$(find_backend_dir)" || fail "backend_directory_not_found"
cd "$BACKEND_DIR"

DEPLOYED_SCHEMA="$(python - <<'PY'
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
print(MIGRATION_SCHEMA_VERSION)
PY
)"
test "$DEPLOYED_SCHEMA" = "$EXPECTED_SCHEMA" \
  || fail "current_complete_cabinet_code_not_deployed"

ALEMBIC_CURRENT="$(python -m alembic current)"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "$EXPECTED_INITIAL_HEAD" \
  || fail "fresh_migration_database_must_start_at_0005"

mkdir -p "$WORK"
tar -xzf "$ARCHIVE" -C "$WORK"
SOURCE="$WORK/migration/phase3c-source/platforma.source.db"
MEDIA="$WORK/uploads"
SNAPSHOT_DIR="$WORK/snapshot"
SNAPSHOT_DB="$SNAPSHOT_DIR/platforma.snapshot.db"
MANIFEST="$SNAPSHOT_DIR/media-manifest.json"

test -f "$SOURCE" || fail "source_database_not_found_after_extract"
test -d "$MEDIA" || fail "media_directory_not_found_after_extract"

# v1616 demo yozuvlari migratsiya doirasidan chiqariladi (egasining qarori).
# Tozalash arxivdan chiqarilgan **vaqtinchalik nusxada** bajariladi — jonli
# v1656 bazasiga tegilmaydi. Snapshot shundan keyin olinadi, shuning uchun
# barmoq izi va barcha gate sanoqlari o'z-o'zidan mos bo'ladi.
python -m app.legacy_migration.demo_prune "$SOURCE"

koprik-migrate-legacy snapshot \
  --source "$SOURCE" \
  --output "$SNAPSHOT_DIR" \
  --media-root "$MEDIA" \
  | tee "$WORK/snapshot-result.json"

test -f "$SNAPSHOT_DB" || fail "snapshot_database_not_created"
test -f "$MANIFEST" || fail "media_manifest_not_created"
export KOPRIK_LEGACY_MEDIA_ROOTS="$MEDIA"

# Bazaviy import 0005 sxemasida bajariladi, lekin uni bajaradigan kod bugungi
# modellarga tayanadi. SQLAlchemy INSERT'ga mapperdagi **barcha** ustunlarni
# nomlaydi, shuning uchun 0005 da hali mavjud bo'lmagan har bir ustun importni
# yiqitadi. Ular vaqtincha qo'shilib, rasmiy Alembic zanjiri boshlanishidan
# oldin yana olib tashlanadi — zanjir o'zi to'ldiradi:
#   - `public_id` (0010) — `_backfill_public_ids` barcha qatorlarga
#     `blake2s(kind:account_id)` dan deterministik qiymat yozadi, ya'ni
#     bu yerda tashlab ketilgani bilan aynan o'sha qiymat qaytadi;
#   - `specialist_rating_*` (0032) — nol qiymatdan boshlanadi.
python - <<'PY'
import asyncio
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import Database

async def main():
    database = Database(Settings().database_url)
    await database.start()
    try:
        async with database.session() as session:
            async with session.begin():
                await session.execute(text(
                    "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS "
                    "specialist_rating_sum INTEGER NOT NULL DEFAULT 0"
                ))
                await session.execute(text(
                    "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS "
                    "specialist_rating_count INTEGER NOT NULL DEFAULT 0"
                ))
                await session.execute(text(
                    "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS "
                    "public_id VARCHAR(18)"
                ))
                await session.execute(text(
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS "
                    "public_id VARCHAR(18)"
                ))
    finally:
        await database.stop()

asyncio.run(main())
PY

koprik-migrate-legacy run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  --until-stage businesses \
  | tee "$WORK/run-1-base.json"

RUN_ID="$(python - "$WORK/run-1-base.json" <<'PY'
import json
import sys
for line in reversed(open(sys.argv[1], encoding="utf-8").read().splitlines()):
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        continue
    if "run_id" in payload:
        print(int(payload["run_id"]))
        break
else:
    raise SystemExit("run_id_not_found")
PY
)"
test -n "$RUN_ID" || fail "run_id_missing"

python - <<'PY'
import asyncio
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import Database

async def main():
    database = Database(Settings().database_url)
    await database.start()
    try:
        async with database.session() as session:
            async with session.begin():
                await session.execute(text(
                    "ALTER TABLE user_profiles "
                    "DROP COLUMN specialist_rating_count"
                ))
                await session.execute(text(
                    "ALTER TABLE user_profiles "
                    "DROP COLUMN specialist_rating_sum"
                ))
                # `public_id` ni 0010 qayta yaratadi va deterministik
                # to'ldiradi — bu yerda tashlanishi ma'lumot yo'qotmaydi.
                await session.execute(text(
                    "ALTER TABLE user_profiles DROP COLUMN public_id"
                ))
                await session.execute(text(
                    "ALTER TABLE business_profiles DROP COLUMN public_id"
                ))
    finally:
        await database.stop()

asyncio.run(main())
PY

python -m alembic upgrade head
ALEMBIC_CURRENT="$(python -m alembic current)"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "$EXPECTED_FINAL_HEAD" \
  || fail "final_alembic_head_mismatch"

koprik-migrate-legacy run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  | tee "$WORK/run-1-complete.json"
RUN_ID_COMPLETE="$(python - "$WORK/run-1-complete.json" <<'PY'
import json
import sys
for line in reversed(open(sys.argv[1], encoding="utf-8").read().splitlines()):
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        continue
    if "run_id" in payload:
        print(int(payload["run_id"]))
        break
else:
    raise SystemExit("run_id_not_found")
PY
)"
test "$RUN_ID_COMPLETE" = "$RUN_ID" \
  || fail "schema_upgrade_resume_created_new_migration"
koprik-migrate-legacy verify --run-id "$RUN_ID" \
  | tee "$WORK/verify-complete.json"

koprik-migrate-late-domains \
  --snapshot "$SNAPSHOT_DB" \
  --run-id "$RUN_ID" \
  --environment staging \
  | tee "$WORK/late-domains.json"

koprik-migrate-legacy run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  | tee "$WORK/run-2.json"
RUN_ID_2="$(python - "$WORK/run-2.json" <<'PY'
import json
import sys
for line in reversed(open(sys.argv[1], encoding="utf-8").read().splitlines()):
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        continue
    if "run_id" in payload:
        print(int(payload["run_id"]))
        break
else:
    raise SystemExit("run_id_not_found")
PY
)"
test "$RUN_ID_2" = "$RUN_ID" || fail "second_run_created_new_migration"

koprik-migrate-legacy verify --run-id "$RUN_ID" \
  | tee "$WORK/verify-final.json"
koprik-migrate-legacy report --run-id "$RUN_ID" --format json \
  > "$WORK/final-report.json"

python -m app.cabinet_records.cli \
  --execute --batch-size "$NORMALIZATION_BATCH_SIZE" \
  | tee "$WORK/cabinet-normalization.json"
python -m app.cabinet_records.cli --verify-only \
  | tee "$WORK/cabinet-normalization-verify.json"

python - "$WORK/final-report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
assert report["schema_version"] == "0008_phase3c_taxi_v1"
assert report["environment"] == "staging"
assert report["status"] == "completed"
assert report["stage"] == "verify"
assert report["verification"]["passed"] is True
assert [
    gate["code"]
    for gate in report["verification"]["gates"]
    if not gate["passed"]
] == []
required = {
    "mapping_coverage",
    "identity_conflicts",
    "cabinet_demo_rows",
    "cabinet_sensitive_fields",
    "idempotency",
    "public_schema_leak",
}
actual = {gate["code"] for gate in report["verification"]["gates"]}
assert required <= actual, sorted(required - actual)
assert int(report["counters"].get("idempotency_created", -1)) == 0
late = report["counters"].get("late_typed_domains") or {}
assert int(late.get("quarantined", -1)) == 0
for stage in ("accounts", "businesses"):
    counters = report["counters"].get(stage) or {}
    assert int(counters.get("quarantined", -1)) == 0
print(
    "CURRENT_TYPED_CABINET_REPORT_OK "
    f"RUN_ID={report['run_id']} IDEMPOTENCY_CREATED=0"
)
PY

python - <<'PY'
import asyncio
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import Database
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile

async def main():
    database = Database(Settings().database_url)
    await database.start()
    try:
        async with database.session() as session:
            links = int(await session.scalar(select(func.count(ProfileLink.user_account_id))) or 0)
            linked_users = int(
                await session.scalar(
                    select(func.count(UserProfile.account_id)).where(
                        UserProfile.has_business.is_(True)
                    )
                ) or 0
            )
            businesses = int(
                await session.scalar(select(func.count(BusinessProfile.account_id))) or 0
            )
            # Ilgari bu yerda `>= 20` turardi — o'sha raqam demo yozuvlar
            # ham ko'chirilgan davrga moslangan edi. Demo chiqarilgach
            # (`demo_prune`) real biznes 3 ta, ya'ni chegara ma'nosini
            # yo'qotadi. O'rniga aniq moslik tekshiriladi: har bir biznes
            # egasiga bog'langan bo'lishi shart. Bu kuchliroq shart —
            # `>= 20` bir nechta bog'lanmagan biznesni sezmasdan o'tkazardi.
            assert businesses > 0, businesses
            assert links == businesses, (links, businesses)
            assert 0 < linked_users <= businesses, (linked_users, businesses)
            print(
                "CABINET_LINKS_OK "
                f"LINKS={links} LINKED_USERS={linked_users} "
                f"BUSINESSES={businesses}"
            )
    finally:
        await database.stop()

asyncio.run(main())
PY

printf 'PHASE3C_V8_STAGING_COMPLETE RUN_ID=%s WORK=%s\n' "$RUN_ID" "$WORK"
'@

$ExecuteScript = $ExecuteScript.Replace(
    "__EXPECTED_ARCHIVE_SHA256__",
    $ExpectedArchiveSha256.ToLowerInvariant()
).Replace(
    "__NORMALIZATION_BATCH_SIZE__",
    $NormalizationBatchSize.ToString()
)

Invoke-RemoteBash `
    -Script $ExecuteScript `
    -FailureCode "STAGING_V8_MIGRATION_FAILED" | Out-Null

Write-Host "Phase 3C V8 fresh staging data migration finished."
Write-Host "Production migration was not started."
