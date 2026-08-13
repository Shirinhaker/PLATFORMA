param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$LegacyBaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedBotUsername,
    [string]$BotToken = $env:KOPRIK_TELEGRAM_BOT_TOKEN,
    [string]$WebhookSecret = $env:KOPRIK_TELEGRAM_WEBHOOK_SECRET,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Normalize-HttpsBaseUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    [Uri]$Parsed = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$Parsed)) {
        throw $FailureCode
    }
    if ($Parsed.Scheme -ne "https") {
        throw $FailureCode
    }
    if ($Parsed.AbsolutePath -notin @("", "/")) {
        throw $FailureCode
    }
    if ($Parsed.Query -or $Parsed.Fragment) {
        throw $FailureCode
    }
    return $Parsed.GetLeftPart([UriPartial]::Authority).TrimEnd("/")
}

function Read-BoolProperty {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $false
    }
    $Property = $Object.PSObject.Properties[$Name]
    if ($null -eq $Property) {
        return $false
    }
    return [bool]$Property.Value
}

function Invoke-TelegramApi {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [hashtable]$Body = @{}
    )

    $Uri = "https://api.telegram.org/bot$BotToken/$Method"
    $Json = $Body | ConvertTo-Json -Compress -Depth 8
    try {
        $Result = Invoke-RestMethod `
            -Method Post `
            -Uri $Uri `
            -ContentType "application/json" `
            -Body $Json `
            -TimeoutSec 20
    } catch {
        throw ("TELEGRAM_API_{0}_REQUEST_FAILED" -f $Method.ToUpperInvariant())
    }
    if (-not $Result.ok) {
        throw ("TELEGRAM_API_{0}_FAILED" -f $Method.ToUpperInvariant())
    }
    return $Result
}

function Get-ApiReady {
    try {
        return Invoke-RestMethod `
            -Method Get `
            -Uri "$ApiBase/readyz" `
            -TimeoutSec 20
    } catch {
        throw "TELEGRAM_CUTOVER_MODULAR_API_UNREACHABLE"
    }
}

function Get-LegacyReady {
    try {
        return Invoke-RestMethod `
            -Method Get `
            -Uri "$LegacyBase/readyz" `
            -TimeoutSec 20
    } catch {
        throw "TELEGRAM_CUTOVER_LEGACY_UNREACHABLE"
    }
}

function Test-LegacyFrozen {
    param(
        [Parameter(Mandatory = $true)]
        [object]$ReadyPayload
    )

    $Maintenance = Read-BoolProperty -Object $ReadyPayload -Name "maintenance"
    $WritesFrozen = Read-BoolProperty -Object $ReadyPayload -Name "writes_frozen"
    return $Maintenance -and $WritesFrozen
}

$ApiBase = Normalize-HttpsBaseUrl `
    -Value $ApiBaseUrl `
    -FailureCode "TELEGRAM_CUTOVER_API_BASE_URL_INVALID"
$LegacyBase = Normalize-HttpsBaseUrl `
    -Value $LegacyBaseUrl `
    -FailureCode "TELEGRAM_CUTOVER_LEGACY_BASE_URL_INVALID"
$ExpectedUsername = $ExpectedBotUsername.Trim().TrimStart([char]"@")

if (-not $ExpectedUsername) {
    throw "TELEGRAM_CUTOVER_EXPECTED_BOT_USERNAME_REQUIRED"
}
if (-not $BotToken) {
    throw "TELEGRAM_CUTOVER_BOT_TOKEN_REQUIRED"
}
if (-not $WebhookSecret) {
    throw "TELEGRAM_CUTOVER_WEBHOOK_SECRET_REQUIRED"
}
if ($WebhookSecret -notmatch '^[A-Za-z0-9_-]{1,256}$') {
    throw "TELEGRAM_CUTOVER_WEBHOOK_SECRET_INVALID"
}

$TargetWebhook = "$ApiBase/api/v1/auth/telegram/webhook"

Write-Host "SCRIPT_VERSION=9"
Write-Host "CUTOVER_MODE=TELEGRAM_WEBHOOK_TO_MODULAR_API"
Write-Host ("EXECUTE={0}" -f $Execute.IsPresent)
Write-Host ("API_BASE_URL={0}" -f $ApiBase)
Write-Host ("LEGACY_BASE_URL={0}" -f $LegacyBase)
Write-Host ("TARGET_WEBHOOK_URL={0}" -f $TargetWebhook)

$ApiReady = Get-ApiReady
if ($ApiReady.status -ne "ready") {
    throw "TELEGRAM_CUTOVER_MODULAR_API_NOT_READY"
}
Write-Host "MODULAR_API_READY=1"

$LegacyReady = Get-LegacyReady
$LegacyMaintenance = Read-BoolProperty -Object $LegacyReady -Name "maintenance"
$LegacyWritesFrozen = Read-BoolProperty -Object $LegacyReady -Name "writes_frozen"
$LegacyFrozen = $LegacyMaintenance -and $LegacyWritesFrozen
Write-Host ("LEGACY_MAINTENANCE={0}" -f [int]$LegacyMaintenance)
Write-Host ("LEGACY_WRITES_FROZEN={0}" -f [int]$LegacyWritesFrozen)

$Bot = Invoke-TelegramApi -Method "getMe"
$ActualUsername = [string]$Bot.result.username
if (-not $ActualUsername) {
    throw "TELEGRAM_CUTOVER_BOT_USERNAME_MISSING"
}
if ($ActualUsername -ine $ExpectedUsername) {
    throw "TELEGRAM_CUTOVER_WRONG_BOT"
}
Write-Host ("BOT_USERNAME={0}" -f $ActualUsername)

$Before = Invoke-TelegramApi -Method "getWebhookInfo"
$CurrentWebhook = [string]$Before.result.url
Write-Host ("CURRENT_WEBHOOK_URL={0}" -f $CurrentWebhook)

if (-not $Execute.IsPresent) {
    Write-Host "TELEGRAM_WEBHOOK_CUTOVER_DRY_RUN_OK=1"
    Write-Host "TELEGRAM_WEBHOOK_NOT_CHANGED=1"
    if (-not $LegacyFrozen) {
        Write-Host "NEXT_STEP=freeze_legacy_web_then_verify_and_rerun_with_execute"
    } else {
        Write-Host "NEXT_STEP=rerun_with_execute"
    }
    exit 0
}

if (-not $LegacyFrozen) {
    throw "TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN"
}

# Telegramga yozishdan darhol oldin ikkala servis holatini qayta tekshiramiz.
# Bu preflight va setWebhook orasida legacy servis qayta ochilib ketgan bo‘lsa
# webhookni xavfli almashtirishni to‘xtatadi.
$ApiReadyBeforeWrite = Get-ApiReady
if ($ApiReadyBeforeWrite.status -ne "ready") {
    throw "TELEGRAM_CUTOVER_MODULAR_API_NOT_READY_BEFORE_WRITE"
}
$LegacyReadyBeforeWrite = Get-LegacyReady
if (-not (Test-LegacyFrozen -ReadyPayload $LegacyReadyBeforeWrite)) {
    throw "TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN_BEFORE_WRITE"
}
Write-Host "PREWRITE_GUARDS_OK=1"

$SetResult = Invoke-TelegramApi -Method "setWebhook" -Body @{
    url = $TargetWebhook
    secret_token = $WebhookSecret
    allowed_updates = @("message")
    drop_pending_updates = $false
}
if (-not $SetResult.result) {
    throw "TELEGRAM_CUTOVER_SET_WEBHOOK_REJECTED"
}

$After = Invoke-TelegramApi -Method "getWebhookInfo"
$VerifiedWebhook = [string]$After.result.url
if ($VerifiedWebhook -ne $TargetWebhook) {
    throw "TELEGRAM_CUTOVER_WEBHOOK_VERIFY_FAILED"
}

Write-Host ("VERIFIED_WEBHOOK_URL={0}" -f $VerifiedWebhook)
Write-Host "TELEGRAM_WEBHOOK_CUTOVER_COMPLETE=1"
Write-Host "LEGACY_WEB_MUST_REMAIN_FROZEN=1"
Write-Host "NEXT_STEP=smoke_test_existing_user_and_business_login"
