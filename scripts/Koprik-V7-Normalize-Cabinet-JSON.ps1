param(
    [ValidateSet("DryRun", "Execute", "Verify")]
    [string]$Mode = "DryRun",
    [ValidateRange(1, 1000)]
    [int]$BatchSize = 100
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SshTarget = "koprik-api-staging"
$ExpectedSchema = "0006_v7_cabinet_records"

Write-Host "SCRIPT=KOPRIK_V7_NORMALIZE_CABINET_JSON_STAGING"
Write-Host "SCRIPT_VERSION=2"
Write-Host "TARGET=$SshTarget"
Write-Host "MODE=$Mode"
Write-Host "BATCH_SIZE=$BatchSize"

function Invoke-RemoteBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,
        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    $Token = [Guid]::NewGuid().ToString("N")
    $TempRoot = [IO.Path]::GetTempPath()
    $InputPath = Join-Path $TempRoot "koprik-v7-normalize-$Token.sh"
    $OutputPath = Join-Path $TempRoot "koprik-v7-normalize-$Token.out"
    $ErrorPath = Join-Path $TempRoot "koprik-v7-normalize-$Token.err"
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

$RemoteMode = switch ($Mode) {
    "DryRun" { "dry-run" }
    "Execute" { "execute" }
    "Verify" { "verify" }
}

$RemoteScript = @"
set -Eeuo pipefail

fail() {
  printf 'V7_NORMALIZATION_ERROR=%s\n' "`$1" >&2
  exit 1
}

test "`${KOPRIK_ENVIRONMENT:-}" = "staging" \
  || fail "environment_is_not_staging"
case "`${KOPRIK_PHASE3C_PUBLIC_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    fail "phase3c_public_flag_must_be_disabled"
    ;;
esac

find_backend_dir() {
  for candidate in "`$PWD" "`$PWD/backend" /app /app/backend; do
    if test -f "`$candidate/alembic.ini" \
      && test -f "`$candidate/pyproject.toml" \
      && test -d "`$candidate/app/cabinet_records"; then
      printf '%s\n' "`$candidate"
      return 0
    fi
  done
  return 1
}

BACKEND_DIR="`$(find_backend_dir)" || fail "backend_directory_not_found"
cd "`$BACKEND_DIR"

DEPLOYED_SCHEMA="`$(python - <<'PY'
from app.cabinet_records.contract import NORMALIZATION_SCHEMA_VERSION
print(NORMALIZATION_SCHEMA_VERSION)
PY
)"
test "`$DEPLOYED_SCHEMA" = "$ExpectedSchema" \
  || fail "normalization_code_not_deployed"

python -c 'import app.cabinet_records.cli' \
  || fail "normalization_cli_not_deployed"

ALEMBIC_CURRENT="`$(python -m alembic current)"
printf '%s\n' "`$ALEMBIC_CURRENT"
printf '%s' "`$ALEMBIC_CURRENT" | grep -q "$ExpectedSchema" \
  || fail "unexpected_alembic_head"

case "$RemoteMode" in
  dry-run)
    python -m app.cabinet_records.cli
    ;;
  execute)
    python -m app.cabinet_records.cli --execute --batch-size $BatchSize
    ;;
  verify)
    python -m app.cabinet_records.cli --verify-only
    ;;
  *)
    fail "invalid_mode"
    ;;
esac
"@

$Output = Invoke-RemoteBash `
    -Script $RemoteScript `
    -FailureCode "V7_NORMALIZATION_REMOTE_FAILED"
$Text = $Output -join "`n"

if ($Text -notmatch "NORMALIZATION_COMPLETE") {
    throw "NORMALIZATION_COMPLETION_MISSING"
}
if ($Text -notmatch "VERIFY_OK=1") {
    throw "NORMALIZATION_VERIFY_FAILED"
}
if ($Text -notmatch "JSON_KEYS_DELETED=0") {
    throw "UNEXPECTED_JSON_CLEANUP"
}
if ($Text -notmatch "PROFILES_TOTAL=(\d+)") {
    throw "PROFILES_TOTAL_MISSING"
}
$ProfilesTotal = [int]$Matches[1]
if ($Text -notmatch "PROFILES_VERIFIED=(\d+)") {
    throw "PROFILES_VERIFIED_MISSING"
}
$ProfilesVerified = [int]$Matches[1]
if ($ProfilesTotal -ne $ProfilesVerified) {
    throw "PROFILE_PARITY_MISMATCH"
}
if ($Text -notmatch "SOURCE_DIGEST=([0-9a-f]{64})") {
    throw "SOURCE_DIGEST_MISSING"
}
$SourceDigest = $Matches[1]
if ($Text -notmatch "TARGET_DIGEST=([0-9a-f]{64})") {
    throw "TARGET_DIGEST_MISSING"
}
$TargetDigest = $Matches[1]
if ($SourceDigest -ne $TargetDigest) {
    throw "DIGEST_PARITY_MISMATCH"
}

switch ($Mode) {
    "DryRun" {
        if ($Text -notmatch "DATABASE_WRITES=0") {
            throw "DRY_RUN_WRITE_GUARD_FAILED"
        }
    }
    "Verify" {
        if ($Text -notmatch "DATABASE_WRITES=0") {
            throw "VERIFY_WRITE_GUARD_FAILED"
        }
        if ($Text -notmatch "MARKER_MISMATCHES=0") {
            throw "MARKER_PARITY_MISMATCH"
        }
    }
    "Execute" {
        if ($Text -notmatch "DATABASE_WRITES=RELATIONAL_AND_SYNCED_FALLBACK") {
            throw "EXECUTE_WRITE_MODE_MISMATCH"
        }
    }
}

Write-Host "V7_NORMALIZATION_${Mode}_OK PROFILES=$ProfilesVerified DIGEST=$SourceDigest"
