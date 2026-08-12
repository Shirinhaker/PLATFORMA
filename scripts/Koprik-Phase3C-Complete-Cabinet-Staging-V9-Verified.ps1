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

$BaseScript = Join-Path $PSScriptRoot "Koprik-Phase3C-Complete-Cabinet-Staging-V9.ps1"
if (-not (Test-Path -LiteralPath $BaseScript -PathType Leaf)) {
    throw "V9_BASE_SCRIPT_NOT_FOUND"
}

Write-Host "SCRIPT_VERSION=9-verified"
Write-Host "MIGRATION_MODE=FRESH_CURRENT_TYPED_CABINETS_WITH_PROFILE_MEDIA_GATE"

$RunParams = @{
    Archive = $Archive
    ExpectedArchiveSha256 = $ExpectedArchiveSha256
    SshTarget = $SshTarget
    NormalizationBatchSize = $NormalizationBatchSize
}
if ($Execute.IsPresent) {
    $RunParams.Execute = $true
}
if ($BackupConfirmed.IsPresent) {
    $RunParams.BackupConfirmed = $true
}

& $BaseScript @RunParams

if (-not $Execute.IsPresent) {
    Write-Host "VERIFIED_WRAPPER_DRY_RUN_COMPLETE DATABASE_WRITES=0"
    exit 0
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
    $InputPath = Join-Path $TempRoot "koprik-v9-verify-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v9-verify-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v9-verify-$Token.err"
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

$VerifyScript = @'
set -Eeuo pipefail

fail() {
  printf 'PHASE3C_V9_VERIFY_ERROR=%s\n' "$1" >&2
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

WORK="$(
  find /tmp -maxdepth 1 -type d -name 'koprik-phase3c-v9-*' \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | head -n 1 \
    | cut -d' ' -f2-
)"
test -n "$WORK" || fail "v9_work_directory_not_found"
test -d "$WORK" || fail "v9_work_directory_not_found"

REPORT="$WORK/final-report.json"
SNAPSHOT="$WORK/snapshot/platforma.snapshot.db"
MANIFEST="$WORK/snapshot/media-manifest.json"
test -f "$REPORT" || fail "final_report_not_found"
test -f "$SNAPSHOT" || fail "snapshot_not_found"
test -f "$MANIFEST" || fail "media_manifest_not_found"

RUN_ID="$(python - "$REPORT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
assert report["schema_version"] == "0009_phase3c_real_subscriptions_v1"
assert report["environment"] == "staging"
assert report["status"] == "completed"
assert report["stage"] == "verify"
assert report["verification"]["passed"] is True
print(int(report["run_id"]))
PY
)" || fail "final_report_invalid"
test -n "$RUN_ID" || fail "run_id_missing"

VERIFY_OUTPUT="$(
  python -m app.legacy_migration.profile_media_verify_v9 \
    --snapshot "$SNAPSHOT" \
    --run-id "$RUN_ID" \
    --environment staging
)" || fail "profile_media_verify_failed"
printf '%s\n' "$VERIFY_OUTPUT"
printf '%s\n' "$VERIFY_OUTPUT" \
  | grep -q '^PROFILE_MEDIA_V9_VERIFY_OK ' \
  || fail "profile_media_verify_confirmation_missing"

printf 'PHASE3C_V9_VERIFIED_COMPLETE RUN_ID=%s WORK=%s\n' "$RUN_ID" "$WORK"
'@

$VerifyOutput = Invoke-RemoteBash `
    -Script $VerifyScript `
    -FailureCode "STAGING_V9_PROFILE_MEDIA_GATE_FAILED"
$VerifyText = $VerifyOutput -join "`n"
if ($VerifyText -notmatch "PHASE3C_V9_VERIFIED_COMPLETE") {
    throw "STAGING_V9_VERIFIED_CONFIRMATION_MISSING"
}

Write-Host "Phase 3C V9 candidate + profile media gate finished."
Write-Host "Production migration was not started."
