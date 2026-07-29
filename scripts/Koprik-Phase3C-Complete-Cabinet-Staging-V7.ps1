param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackupDir = "C:\Users\55555555\Downloads\koprik-phase3c-backup"
$Archive = Join-Path $BackupDir "koprik-phase3c-source-final.tar.gz"
$ExpectedArchiveSha256 = "a1d7e6e1d287a0f7b8fb9bd0b43bb0bc88418538b5e98b1d570e5f9be1e291ff"
$ExpectedSchema = "0006_phase3c_complete_cabinet_v1"
$ExpectedAlembicHead = "0005_profile_cabinet_parity"
$RemoteRoot = "/tmp/koprik-phase3c-v7-input"
$RemoteArchive = "$RemoteRoot/koprik-phase3c-source-final.tar.gz"
$SshTarget = "koprik-api-staging"

Write-Host "SCRIPT_VERSION=7"
Write-Host "MIGRATION_MODE=COMPLETE_REAL_CABINETS"
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
    $InputPath = Join-Path $TempRoot "koprik-v7-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v7-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v7-$Token.err"
    $Utf8NoBom = New-Object Text.UTF8Encoding($false)

    try {
        [IO.File]::WriteAllText($InputPath, $Script, $Utf8NoBom)
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
    throw "BACKUP_ARCHIVE_NOT_FOUND"
}
$ActualArchiveSha256 = (
    Get-FileHash -LiteralPath $Archive -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($ActualArchiveSha256 -ne $ExpectedArchiveSha256) {
    throw "LOCAL_ARCHIVE_SHA256_MISMATCH"
}
Write-Host "LOCAL_ARCHIVE_SHA256_OK"

$PreflightScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V7_ERROR=%s\n' "$1" >&2
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
test "$DEPLOYED_SCHEMA" = "0006_phase3c_complete_cabinet_v1" \
  || fail "complete_cabinet_code_not_deployed"
command -v koprik-migrate-legacy >/dev/null \
  || fail "migration_cli_not_installed"

ALEMBIC_CURRENT="$(python -m alembic current)"
printf '%s\n' "$ALEMBIC_CURRENT"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "0005_profile_cabinet_parity" \
  || fail "unexpected_alembic_head"

python - <<'PY'
from app.legacy_migration.profile_parity_v7 import (
    BUSINESS_MODULE_TABLES,
    EXPLICIT_DEMO_FLAGS,
)
assert "staff" in BUSINESS_MODULE_TABLES
assert "documents" in BUSINESS_MODULE_TABLES
assert "warehouse_items" in BUSINESS_MODULE_TABLES
assert "education_students" in BUSINESS_MODULE_TABLES
assert "medical_appointments" in BUSINESS_MODULE_TABLES
assert "is_demo" in EXPLICIT_DEMO_FLAGS
print("COMPLETE_CABINET_CODE_GUARD_OK")
PY

printf 'STAGING_V7_GUARD_OK SCHEMA=%s BACKEND=%s\n' \
  "$DEPLOYED_SCHEMA" "$BACKEND_DIR"
'@

$PreflightOutput = Invoke-RemoteBash `
    -Script $PreflightScript `
    -FailureCode "STAGING_V7_PREFLIGHT_FAILED"
$PreflightText = $PreflightOutput -join "`n"
if ($PreflightText -notmatch "STAGING_V7_GUARD_OK") {
    throw "STAGING_V7_GUARD_CONFIRMATION_MISSING"
}
if ($PreflightText -notmatch [Regex]::Escape("SCHEMA=$ExpectedSchema")) {
    throw "STAGING_V7_SCHEMA_CONFIRMATION_MISMATCH"
}

if (-not $Execute.IsPresent) {
    Write-Host "DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0"
    Write-Host "V7 code, staging environment and Alembic head are ready."
    exit 0
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
  printf 'PHASE3C_V7_ERROR=%s\n' "$1" >&2
  exit 1
}

test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "environment_is_not_staging"
case "${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_be_disabled"
    ;;
esac

ARCHIVE="/tmp/koprik-phase3c-v7-input/koprik-phase3c-source-final.tar.gz"
EXPECTED_ARCHIVE_SHA256="a1d7e6e1d287a0f7b8fb9bd0b43bb0bc88418538b5e98b1d570e5f9be1e291ff"
EXPECTED_SCHEMA="0006_phase3c_complete_cabinet_v1"
EXPECTED_ALEMBIC_HEAD="0005_profile_cabinet_parity"
WORK="/tmp/koprik-phase3c-v7-$(date +%Y%m%d-%H%M%S)"

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
  || fail "complete_cabinet_code_not_deployed"

python -m alembic upgrade head
ALEMBIC_CURRENT="$(python -m alembic current)"
printf '%s\n' "$ALEMBIC_CURRENT"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "$EXPECTED_ALEMBIC_HEAD" \
  || fail "unexpected_alembic_head"

mkdir -p "$WORK"
tar -xzf "$ARCHIVE" -C "$WORK"
SOURCE="$WORK/migration/phase3c-source/platforma.source.db"
MEDIA="$WORK/uploads"
SNAPSHOT_DIR="$WORK/snapshot"
SNAPSHOT_DB="$SNAPSHOT_DIR/platforma.snapshot.db"
MANIFEST="$SNAPSHOT_DIR/media-manifest.json"

test -f "$SOURCE" || fail "source_database_not_found_after_extract"
test -d "$MEDIA" || fail "media_directory_not_found_after_extract"

koprik-migrate-legacy snapshot \
  --source "$SOURCE" \
  --output "$SNAPSHOT_DIR" \
  --media-root "$MEDIA" \
  | tee "$WORK/snapshot-result.json"

test -f "$SNAPSHOT_DB" || fail "snapshot_database_not_created"
test -f "$MANIFEST" || fail "media_manifest_not_created"
export KOPRIK_LEGACY_MEDIA_ROOTS="$MEDIA"

koprik-migrate-legacy run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  | tee "$WORK/run-1.json"

RUN_ID="$(python - "$WORK/run-1.json" <<'PY'
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
koprik-migrate-legacy verify --run-id "$RUN_ID" \
  | tee "$WORK/verify-1.json"

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
  | tee "$WORK/verify-2.json"
koprik-migrate-legacy report --run-id "$RUN_ID" --format json \
  > "$WORK/final-report.json"

python - "$WORK/final-report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
assert report["schema_version"] == "0006_phase3c_complete_cabinet_v1"
assert report["environment"] == "staging"
assert report["status"] == "completed"
assert report["stage"] == "verify"
assert report["verification"]["passed"] is True
failed = [
    gate["code"]
    for gate in report["verification"]["gates"]
    if not gate["passed"]
]
assert failed == [], failed
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
for stage in ("accounts", "businesses"):
    counters = report["counters"].get(stage) or {}
    assert int(counters.get("quarantined", -1)) == 0
print(
    "COMPLETE_CABINET_REPORT_OK "
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
            user_payloads = (
                await session.scalars(
                    select(UserProfile).where(UserProfile.has_business.is_(True))
                )
            ).all()
            business_payloads = (
                await session.scalars(select(BusinessProfile))
            ).all()
            assert links >= 20, links
            assert linked_users >= 20, linked_users
            assert all(isinstance(row.cabinet_payload, dict) for row in user_payloads)
            assert all(isinstance(row.cabinet_payload, dict) for row in business_payloads)
            print(
                "CABINET_LINKS_OK "
                f"LINKS={links} LINKED_USERS={linked_users} "
                f"BUSINESSES={len(business_payloads)}"
            )
    finally:
        await database.stop()

asyncio.run(main())
PY

printf 'PHASE3C_V7_STAGING_COMPLETE RUN_ID=%s WORK=%s\n' "$RUN_ID" "$WORK"
'@

Invoke-RemoteBash `
    -Script $ExecuteScript `
    -FailureCode "STAGING_V7_MIGRATION_FAILED" | Out-Null

Write-Host "Phase 3C V7 complete-cabinet staging migration finished."
Write-Host "Production migration was not started."
