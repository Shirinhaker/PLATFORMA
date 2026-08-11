param(
    [Parameter(Mandatory = $true)]
    [string]$SshTarget,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 1000000000)]
    [int]$ApprovedStagingRunId,
    [Parameter(Mandatory = $true)]
    [string]$SnapshotPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedSnapshotSha256,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedManifestSha256,
    [switch]$Execute,
    [switch]$BackupConfirmed,
    [switch]$MaintenanceConfirmed,
    [switch]$SourceWritesStoppedConfirmed
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedSchema = "0008_phase3c_taxi_v1"
$ExpectedHead = "0041_taxi_driver_domain"

Write-Host "SCRIPT_VERSION=8"
Write-Host "MIGRATION_MODE=PROMOTE_VERIFIED_V8_CANDIDATE"
Write-Host ("EXECUTE={0}" -f $Execute.IsPresent)
Write-Host ("APPROVED_STAGING_RUN_ID={0}" -f $ApprovedStagingRunId)

if ($SnapshotPath -notmatch '^/tmp/koprik-phase3c-v8-[0-9]{8}-[0-9]{6}/snapshot/platforma\.snapshot\.db$') {
    throw "PRODUCTION_V8_SNAPSHOT_PATH_NOT_FROM_STAGING_WORKDIR"
}
if ($ExpectedSnapshotSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw "PRODUCTION_V8_SNAPSHOT_SHA256_INVALID"
}
if ($ExpectedManifestSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw "PRODUCTION_V8_MANIFEST_SHA256_INVALID"
}

function Invoke-RemoteBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,
        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    $Token = [Guid]::NewGuid().ToString("N")
    $TempRoot = [IO.Path]::GetTempPath()
    $InputPath = Join-Path $TempRoot "koprik-v8-production-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v8-production-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v8-production-$Token.err"
    $Utf8NoBom = New-Object Text.UTF8Encoding($false)

    try {
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

$PreflightScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V8_PRODUCTION_ERROR=%s\n' "$1" >&2
  exit 1
}

# Candidate hali ommaga ochilmagan staging servis bo'lishi shart. Production
# yozuvi shu candidate DB ichida yaratiladi; trafik keyin alohida ochiladi.
test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "candidate_environment_must_remain_staging_before_cutover"
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

SNAPSHOT="__SNAPSHOT_PATH__"
MANIFEST="$(dirname "$SNAPSHOT")/media-manifest.json"
EXPECTED_SNAPSHOT_SHA256="__EXPECTED_SNAPSHOT_SHA256__"
EXPECTED_MANIFEST_SHA256="__EXPECTED_MANIFEST_SHA256__"
APPROVED_STAGING_RUN_ID="__APPROVED_STAGING_RUN_ID__"
EXPECTED_SCHEMA="0008_phase3c_taxi_v1"
EXPECTED_HEAD="0041_taxi_driver_domain"

test -f "$SNAPSHOT" || fail "approved_snapshot_not_found"
test -f "$MANIFEST" || fail "approved_manifest_not_found"
test "$(sha256sum "$SNAPSHOT" | awk '{print $1}')" = "$EXPECTED_SNAPSHOT_SHA256" \
  || fail "approved_snapshot_sha256_mismatch"
test "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA256" \
  || fail "approved_manifest_sha256_mismatch"

DEPLOYED_SCHEMA="$(python - <<'PY'
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
print(MIGRATION_SCHEMA_VERSION)
PY
)"
test "$DEPLOYED_SCHEMA" = "$EXPECTED_SCHEMA" \
  || fail "current_complete_cabinet_code_not_deployed"
ALEMBIC_CURRENT="$(python -m alembic current)"
printf '%s' "$ALEMBIC_CURRENT" | grep -q "$EXPECTED_HEAD" \
  || fail "candidate_database_not_at_current_head"

python - "$APPROVED_STAGING_RUN_ID" "$EXPECTED_SNAPSHOT_SHA256" "$EXPECTED_MANIFEST_SHA256" <<'PY'
import asyncio
import sys
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.model import (
    MediaMigration,
    MediaMigrationState,
    MigrationEnvironment,
    MigrationRun,
    MigrationStage,
    MigrationStatus,
)
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
from app.profiles.model import BusinessProfile, ProfileLink, UserProfile

run_id = int(sys.argv[1])
expected_snapshot = sys.argv[2]
expected_manifest = sys.argv[3]

async def main():
    database = Database(Settings().database_url)
    await database.start()
    try:
        async with database.session() as session:
            run = await session.get(MigrationRun, run_id)
            assert run is not None, "approved_staging_run_not_found"
            assert run.environment is MigrationEnvironment.STAGING, run.environment
            assert run.status is MigrationStatus.COMPLETED, run.status
            assert run.stage is MigrationStage.VERIFY, run.stage
            assert run.schema_version == MIGRATION_SCHEMA_VERSION, run.schema_version
            assert run.source_database_sha256 == expected_snapshot
            assert run.media_manifest_sha256 == expected_manifest
            verify = run.counters_json.get("verify") or {}
            assert verify.get("passed") is True, "approved_staging_verification_failed"
            assert [g.get("code") for g in verify.get("gates", []) if not g.get("passed")] == []
            assert int(run.counters_json.get("idempotency_created", -1)) == 0
            for stage in ("accounts", "businesses"):
                counters = run.counters_json.get(stage) or {}
                assert int(counters.get("quarantined", -1)) == 0, (stage, counters)
            late = run.counters_json.get("late_typed_domains") or {}
            assert int(late.get("quarantined", -1)) == 0, late

            states = {
                state: int(count)
                for state, count in (
                    await session.execute(
                        select(MediaMigration.state, func.count(MediaMigration.id))
                        .where(MediaMigration.migration_run_id == run.id)
                        .group_by(MediaMigration.state)
                    )
                ).all()
            }
            copied = states.get(MediaMigrationState.COPIED, 0)
            pending = states.get(MediaMigrationState.PENDING, 0)
            missing = states.get(MediaMigrationState.MISSING, 0)
            invalid = states.get(MediaMigrationState.INVALID, 0)
            failed = states.get(MediaMigrationState.FAILED, 0)
            assert pending == 0, ("media_pending", pending)
            assert missing == 0, ("media_missing", missing)
            assert invalid == 0, ("media_invalid", invalid)
            assert failed == 0, ("media_failed", failed)
            media_gate = next(
                (g for g in verify.get("gates", []) if g.get("code") == "media_terminal_count"),
                None,
            )
            assert media_gate is not None, "media_terminal_gate_missing"
            assert copied == int(media_gate.get("expected", -1)), (copied, media_gate)

            businesses = int(
                await session.scalar(select(func.count(BusinessProfile.account_id))) or 0
            )
            links = int(
                await session.scalar(select(func.count(ProfileLink.user_account_id))) or 0
            )
            linked_users = int(
                await session.scalar(
                    select(func.count(UserProfile.account_id)).where(
                        UserProfile.has_business.is_(True)
                    )
                ) or 0
            )
            assert businesses > 0, businesses
            assert links == businesses, (links, businesses)
            assert 0 < linked_users <= businesses, (linked_users, businesses)
            print(
                "PRODUCTION_V8_PROMOTION_GUARD_OK "
                f"STAGING_RUN_ID={run.id} MEDIA_COPIED={copied} "
                f"BUSINESSES={businesses} LINKS={links}"
            )
    finally:
        await database.stop()

asyncio.run(main())
PY
'@

$PreflightScript = $PreflightScript.Replace(
    "__SNAPSHOT_PATH__",
    $SnapshotPath
).Replace(
    "__EXPECTED_SNAPSHOT_SHA256__",
    $ExpectedSnapshotSha256.ToLowerInvariant()
).Replace(
    "__EXPECTED_MANIFEST_SHA256__",
    $ExpectedManifestSha256.ToLowerInvariant()
).Replace(
    "__APPROVED_STAGING_RUN_ID__",
    $ApprovedStagingRunId.ToString()
)

$PreflightOutput = Invoke-RemoteBash `
    -Script $PreflightScript `
    -FailureCode "PRODUCTION_V8_PREFLIGHT_FAILED"
if (($PreflightOutput -join "`n") -notmatch "PRODUCTION_V8_PROMOTION_GUARD_OK") {
    throw "PRODUCTION_V8_GUARD_CONFIRMATION_MISSING"
}

if (-not $Execute.IsPresent) {
    Write-Host "DRY_RUN_COMPLETE DATABASE_WRITES=0 TRAFFIC_CHANGES=0"
    exit 0
}
if (-not $BackupConfirmed.IsPresent) {
    throw "PRODUCTION_V8_BACKUP_CONFIRMATION_REQUIRED"
}
if (-not $MaintenanceConfirmed.IsPresent) {
    throw "PRODUCTION_V8_MAINTENANCE_CONFIRMATION_REQUIRED"
}
if (-not $SourceWritesStoppedConfirmed.IsPresent) {
    throw "PRODUCTION_V8_SOURCE_WRITES_STOPPED_CONFIRMATION_REQUIRED"
}

$ExecuteScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V8_PRODUCTION_ERROR=%s\n' "$1" >&2
  exit 1
}

test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "candidate_environment_changed_before_promotion"
case "${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_remain_disabled"
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

SNAPSHOT="__SNAPSHOT_PATH__"
MANIFEST="$(dirname "$SNAPSHOT")/media-manifest.json"
EXPECTED_SNAPSHOT_SHA256="__EXPECTED_SNAPSHOT_SHA256__"
EXPECTED_MANIFEST_SHA256="__EXPECTED_MANIFEST_SHA256__"
APPROVED_STAGING_RUN_ID="__APPROVED_STAGING_RUN_ID__"
WORK="$(dirname "$(dirname "$SNAPSHOT")")"

test -f "$SNAPSHOT" || fail "approved_snapshot_not_found"
test -f "$MANIFEST" || fail "approved_manifest_not_found"
test "$(sha256sum "$SNAPSHOT" | awk '{print $1}')" = "$EXPECTED_SNAPSHOT_SHA256" \
  || fail "approved_snapshot_sha256_changed"
test "$(sha256sum "$MANIFEST" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA256" \
  || fail "approved_manifest_sha256_changed"

koprik-migrate-legacy run \
  --snapshot "$SNAPSHOT" \
  --environment production \
  --confirm-environment production \
  --confirm-snapshot-sha256 "$EXPECTED_SNAPSHOT_SHA256" \
  --maintenance-enabled \
  --approved-staging-run-id "$APPROVED_STAGING_RUN_ID" \
  | tee "$WORK/production-run.json"

PRODUCTION_RUN_ID="$(python - "$WORK/production-run.json" <<'PY'
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
    raise SystemExit("production_run_id_not_found")
PY
)"
test -n "$PRODUCTION_RUN_ID" || fail "production_run_id_missing"

koprik-migrate-legacy verify --run-id "$PRODUCTION_RUN_ID" \
  | tee "$WORK/production-verify.json"
koprik-migrate-legacy report --run-id "$PRODUCTION_RUN_ID" --format json \
  > "$WORK/production-report.json"

python - "$WORK/production-report.json" "$APPROVED_STAGING_RUN_ID" "$EXPECTED_SNAPSHOT_SHA256" "$EXPECTED_MANIFEST_SHA256" <<'PY'
import asyncio
import json
import sys
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import Database
from app.legacy_migration.model import MediaMigration, MediaMigrationState, MigrationRun

report_path = sys.argv[1]
approved_staging_run_id = int(sys.argv[2])
expected_snapshot = sys.argv[3]
expected_manifest = sys.argv[4]

with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)

assert report["schema_version"] == "0008_phase3c_taxi_v1", report["schema_version"]
assert report["environment"] == "production", report["environment"]
assert report["status"] == "completed", report["status"]
assert report["stage"] == "verify", report["stage"]
assert report["verification"]["passed"] is True
assert [
    gate["code"]
    for gate in report["verification"]["gates"]
    if not gate["passed"]
] == []
for stage in ("accounts", "businesses"):
    counters = report["counters"].get(stage) or {}
    assert int(counters.get("quarantined", -1)) == 0, (stage, counters)
created_stages = (
    "accounts",
    "businesses",
    "catalog",
    "listings",
    "advertisements",
    "media",
)
created = {
    stage: int((report["counters"].get(stage) or {}).get("created", 0))
    for stage in created_stages
}
assert sum(created.values()) == 0, created

async def main():
    database = Database(Settings().database_url)
    await database.start()
    try:
        async with database.session() as session:
            run = await session.get(MigrationRun, int(report["run_id"]))
            assert run is not None
            assert run.approved_staging_run_id == approved_staging_run_id
            assert run.source_database_sha256 == expected_snapshot
            assert run.media_manifest_sha256 == expected_manifest
            states = {
                state: int(count)
                for state, count in (
                    await session.execute(
                        select(MediaMigration.state, func.count(MediaMigration.id))
                        .where(MediaMigration.migration_run_id == run.id)
                        .group_by(MediaMigration.state)
                    )
                ).all()
            }
            assert states.get(MediaMigrationState.PENDING, 0) == 0, states
            assert states.get(MediaMigrationState.MISSING, 0) == 0, states
            assert states.get(MediaMigrationState.INVALID, 0) == 0, states
            assert states.get(MediaMigrationState.FAILED, 0) == 0, states
            print(
                "PRODUCTION_V8_REPORT_OK "
                f"RUN_ID={run.id} APPROVED_STAGING_RUN_ID={approved_staging_run_id} "
                f"CREATED=0 MEDIA_COPIED={states.get(MediaMigrationState.COPIED, 0)}"
            )
    finally:
        await database.stop()

asyncio.run(main())
PY

printf 'PHASE3C_V8_PRODUCTION_PROMOTION_COMPLETE RUN_ID=%s STAGING_RUN_ID=%s WORK=%s\n' \
  "$PRODUCTION_RUN_ID" "$APPROVED_STAGING_RUN_ID" "$WORK"
printf 'TRAFFIC_NOT_CHANGED=1\n'
printf 'NEXT_STEP=manual_smoke_then_explicit_route_cutover\n'
'@

$ExecuteScript = $ExecuteScript.Replace(
    "__SNAPSHOT_PATH__",
    $SnapshotPath
).Replace(
    "__EXPECTED_SNAPSHOT_SHA256__",
    $ExpectedSnapshotSha256.ToLowerInvariant()
).Replace(
    "__EXPECTED_MANIFEST_SHA256__",
    $ExpectedManifestSha256.ToLowerInvariant()
).Replace(
    "__APPROVED_STAGING_RUN_ID__",
    $ApprovedStagingRunId.ToString()
)

Invoke-RemoteBash `
    -Script $ExecuteScript `
    -FailureCode "PRODUCTION_V8_PROMOTION_FAILED" | Out-Null

Write-Host "Phase 3C V8 production data promotion finished."
Write-Host "Traffic was NOT switched and public Phase 3C was NOT enabled."
