param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "SCRIPT_VERSION=6"
Write-Host "MIGRATION_MODE=SHARED_LOGIN_CABINETS"
Write-Host ("EXECUTE={0}" -f $Execute.IsPresent)

$BackupDir = "C:\Users\55555555\Downloads\koprik-phase3c-backup"
$Archive = Join-Path $BackupDir "koprik-phase3c-source-final.tar.gz"
$ExpectedArchiveSha256 = "a1d7e6e1d287a0f7b8fb9bd0b43bb0bc88418538b5e98b1d570e5f9be1e291ff"
$RemoteArchive = "/tmp/koprik-phase3c-input/koprik-phase3c-source-final.tar.gz"
$ExpectedV5Schema = "0003_phase3c_dual_accounts_v4"
$ExpectedV6Schema = "0004_phase3c_shared_login_v1"
$ExpectedAlembicHead = "0004_shared_login_cabinets"
$ExpectedV5RunId = 4
$SshTarget = "koprik-api-staging"

function Invoke-RemoteBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,
        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    $Token = [Guid]::NewGuid().ToString("N")
    $TempRoot = [IO.Path]::GetTempPath()
    $InputPath = Join-Path $TempRoot "koprik-v6-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v6-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v6-$Token.err"
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

        foreach ($Line in $Output) {
            Write-Host $Line
        }
        foreach ($Line in $Errors) {
            Write-Error $Line -ErrorAction Continue
        }

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
  printf 'PHASE3C_V6_ERROR=%s\n' "$1" >&2
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

EXPECTED_V5_SCHEMA="0003_phase3c_dual_accounts_v4"
EXPECTED_V6_SCHEMA="0004_phase3c_shared_login_v1"

DEPLOYED_V6_SCHEMA="$(
  python - <<'PY'
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
print(MIGRATION_SCHEMA_VERSION)
PY
)"
test "$DEPLOYED_V6_SCHEMA" = "$EXPECTED_V6_SCHEMA" \
  || fail "v6_code_not_deployed"
command -v koprik-migrate-legacy-v6 >/dev/null \
  || fail "v6_cli_not_installed"
command -v koprik-migrate-legacy >/dev/null \
  || fail "base_cli_not_installed"

REPORT="$(mktemp)"
trap 'rm -f "$REPORT"' EXIT
koprik-migrate-legacy report --run-id 4 --format json > "$REPORT"
python - "$REPORT" "$EXPECTED_V5_SCHEMA" <<'PY'
import json
import sys

path, expected_schema = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    report = json.load(handle)

assert int(report.get("run_id") or 0) == 4
assert report.get("schema_version") == expected_schema
assert report.get("environment") == "staging"
assert report.get("stage") == "verify"
assert report.get("status") == "failed"
issues = report.get("issues") or []
assert sum(
    issue.get("issue_code") == "identity.account_type_mismatch"
    for issue in issues
) == 20
assert sum(
    issue.get("issue_code") == "identity.business_owner_unresolved"
    for issue in issues
) == 20
print("V5_RUN_4_GUARD_OK")
PY

printf 'STAGING_V6_GUARD_OK SCHEMA=%s BACKEND=%s\n' \
  "$DEPLOYED_V6_SCHEMA" "$BACKEND_DIR"
'@

$PreflightOutput = Invoke-RemoteBash `
    -Script $PreflightScript `
    -FailureCode "STAGING_V6_PREFLIGHT_FAILED"
$PreflightText = $PreflightOutput -join "`n"
if ($PreflightText -notmatch "STAGING_V6_GUARD_OK") {
    throw "STAGING_V6_GUARD_CONFIRMATION_MISSING"
}
if ($PreflightText -notmatch [Regex]::Escape("SCHEMA=$ExpectedV6Schema")) {
    throw "STAGING_V6_SCHEMA_CONFIRMATION_MISMATCH"
}

if (-not $Execute.IsPresent) {
    Write-Host "DRY_RUN_COMPLETE DATABASE_WRITES=0 FILE_UPLOADS=0"
    Write-Host "Run again with -Execute only after PR #18 is merged and api-staging deploy is healthy."
    exit 0
}

& ssh.exe $SshTarget "mkdir -p /tmp/koprik-phase3c-input"
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
  printf 'PHASE3C_V6_ERROR=%s\n' "$1" >&2
  exit 1
}

test "${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "environment_is_not_staging"
case "${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_be_disabled"
    ;;
esac

ARCHIVE="/tmp/koprik-phase3c-input/koprik-phase3c-source-final.tar.gz"
EXPECTED_ARCHIVE_SHA256="a1d7e6e1d287a0f7b8fb9bd0b43bb0bc88418538b5e98b1d570e5f9be1e291ff"
EXPECTED_SCHEMA="0004_phase3c_shared_login_v1"
EXPECTED_ALEMBIC_HEAD="0004_shared_login_cabinets"
WORK="/tmp/koprik-phase3c-v6-$(date +%Y%m%d-%H%M%S)"

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

DEPLOYED_SCHEMA="$(
  python - <<'PY'
from app.legacy_migration.runner_v6 import MIGRATION_SCHEMA_VERSION
print(MIGRATION_SCHEMA_VERSION)
PY
)"
test "$DEPLOYED_SCHEMA" = "$EXPECTED_SCHEMA" \
  || fail "v6_code_not_deployed"

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

koprik-migrate-legacy-v6 snapshot \
  --source "$SOURCE" \
  --output "$SNAPSHOT_DIR" \
  --media-root "$MEDIA" \
  | tee "$WORK/snapshot-result.json"

test -f "$SNAPSHOT_DB" || fail "snapshot_database_not_created"
test -f "$MANIFEST" || fail "media_manifest_not_created"

koprik-migrate-legacy report --run-id 4 --format json \
  > "$WORK/v5-run-4-report.json"
python - "$WORK/v5-run-4-report.json" "$SNAPSHOT_DB" "$MANIFEST" <<'PY'
import hashlib
import json
import sys

report_path, snapshot_path, manifest_path = sys.argv[1:]

def digest(path: str) -> str:
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)
assert digest(snapshot_path) == report["source_database_sha256"]
assert digest(manifest_path) == report["media_manifest_sha256"]
print("SNAPSHOT_FINGERPRINTS_MATCH_V5")
PY

export KOPRIK_LEGACY_MEDIA_ROOTS="$MEDIA"

koprik-migrate-legacy-v6 run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  | tee "$WORK/run-1.json"

RUN_ID="$(
  python - "$WORK/run-1.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    lines = [line.strip() for line in handle if line.strip()]
for line in reversed(lines):
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
test "$RUN_ID" != "4" || fail "v5_run_id_reused"

koprik-migrate-legacy-v6 verify --run-id "$RUN_ID" \
  | tee "$WORK/verify-1.json"

koprik-migrate-legacy-v6 run \
  --snapshot "$SNAPSHOT_DB" \
  --environment staging \
  | tee "$WORK/run-2.json"
RUN_ID_2="$(
  python - "$WORK/run-2.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    lines = [line.strip() for line in handle if line.strip()]
for line in reversed(lines):
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
test "$RUN_ID_2" = "$RUN_ID" || fail "snapshot_created_second_v6_run"

koprik-migrate-legacy-v6 verify --run-id "$RUN_ID" \
  | tee "$WORK/verify-2.json"
koprik-migrate-legacy-v6 report --run-id "$RUN_ID" --format json \
  > "$WORK/final-report.json"

python - "$WORK/final-report.json" "$WORK" <<'PY'
import json
import sys

report_path, work = sys.argv[1:]
with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)

assert report["schema_version"] == "0004_phase3c_shared_login_v1"
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
assert int(report["counters"].get("idempotency_created", -1)) == 0
accounts = report["counters"].get("accounts") or {}
businesses = report["counters"].get("businesses") or {}
assert int(accounts.get("quarantined", -1)) == 0
assert int(businesses.get("quarantined", -1)) == 0

print(
    "PHASE3C_V6_STAGING_COMPLETE "
    f"RUN_ID={report['run_id']} STATUS=completed "
    "VERIFY=passed IDEMPOTENCY_CREATED=0"
)
print(
    "USER_ACCOUNTS "
    f"CREATED={accounts.get('created', 0)} "
    f"REUSED={accounts.get('reused', 0)} "
    f"UPDATED={accounts.get('updated', 0)} "
    f"QUARANTINED={accounts.get('quarantined', 0)}"
)
print(
    "BUSINESS_ACCOUNTS "
    f"CREATED={businesses.get('created', 0)} "
    f"REUSED={businesses.get('reused', 0)} "
    f"UPDATED={businesses.get('updated', 0)} "
    f"QUARANTINED={businesses.get('quarantined', 0)}"
)
print("GATES=" + ",".join(
    gate["code"] for gate in report["verification"]["gates"]
))
print(f"WORK={work}")
PY
'@

Invoke-RemoteBash `
    -Script $ExecuteScript `
    -FailureCode "STAGING_V6_MIGRATION_FAILED" | Out-Null

Write-Host "Phase 3C V6 staging migration command finished."
Write-Host "Production migration was not started."
