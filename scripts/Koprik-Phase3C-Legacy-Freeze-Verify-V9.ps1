param(
    [Parameter(Mandatory = $true)]
    [string]$LegacyBaseUrl
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Normalize-HttpsBaseUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    [Uri]$Parsed = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$Parsed)) {
        throw "LEGACY_FREEZE_BASE_URL_INVALID"
    }
    if ($Parsed.Scheme -ne "https") {
        throw "LEGACY_FREEZE_BASE_URL_INVALID"
    }
    if ($Parsed.AbsolutePath -notin @("", "/")) {
        throw "LEGACY_FREEZE_BASE_URL_INVALID"
    }
    if ($Parsed.Query -or $Parsed.Fragment) {
        throw "LEGACY_FREEZE_BASE_URL_INVALID"
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

function Invoke-Probe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [string]$Body = ""
    )

    $Client = [System.Net.Http.HttpClient]::new()
    $Client.Timeout = [TimeSpan]::FromSeconds(20)
    $Request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::new($Method),
        $Uri
    )
    if ($Body) {
        $Request.Content = [System.Net.Http.StringContent]::new(
            $Body,
            [Text.Encoding]::UTF8,
            "application/json"
        )
    }
    $Response = $null
    try {
        $Response = $Client.SendAsync($Request).GetAwaiter().GetResult()
        $Content = $Response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return [PSCustomObject]@{
            status = [int]$Response.StatusCode
            body = $Content
        }
    }
    catch {
        throw "LEGACY_FREEZE_PROBE_FAILED"
    }
    finally {
        if ($null -ne $Response) {
            $Response.Dispose()
        }
        $Request.Dispose()
        $Client.Dispose()
    }
}

$LegacyBase = Normalize-HttpsBaseUrl -Value $LegacyBaseUrl
Write-Host "SCRIPT_VERSION=9"
Write-Host "CUTOVER_MODE=VERIFY_LEGACY_WRITE_FREEZE"
Write-Host ("LEGACY_BASE_URL={0}" -f $LegacyBase)

$Ready = Invoke-Probe -Method "GET" -Uri "$LegacyBase/readyz"
if ($Ready.status -ne 200) {
    throw "LEGACY_FREEZE_READYZ_NOT_200"
}
try {
    $ReadyJson = $Ready.body | ConvertFrom-Json
} catch {
    throw "LEGACY_FREEZE_READYZ_NOT_JSON"
}
$MaintenanceEnabled = Read-BoolProperty -Object $ReadyJson -Name "maintenance"
$WritesFrozen = Read-BoolProperty -Object $ReadyJson -Name "writes_frozen"
if (-not $MaintenanceEnabled -or -not $WritesFrozen) {
    throw "LEGACY_FREEZE_NOT_ACTIVE"
}
Write-Host "LEGACY_READYZ_FROZEN=1"

$Maintenance = Invoke-Probe -Method "GET" -Uri "$LegacyBase/maintenance.html"
if ($Maintenance.status -ne 200) {
    throw "LEGACY_FREEZE_MAINTENANCE_PAGE_NOT_200"
}
if ($Maintenance.body -notmatch "Texnik ishlar") {
    throw "LEGACY_FREEZE_MAINTENANCE_PAGE_INVALID"
}
Write-Host "LEGACY_MAINTENANCE_PAGE_OK=1"

$Root = Invoke-Probe -Method "GET" -Uri "$LegacyBase/"
if ($Root.status -ne 503) {
    throw "LEGACY_FREEZE_ROOT_NOT_503"
}
Write-Host "LEGACY_PUBLIC_TRAFFIC_FROZEN=1"

$ApiMutation = Invoke-Probe `
    -Method "POST" `
    -Uri "$LegacyBase/api/_setup" `
    -Body "{}"
if ($ApiMutation.status -ne 503) {
    throw "LEGACY_FREEZE_API_MUTATION_NOT_503"
}
Write-Host "LEGACY_API_WRITES_FROZEN=1"

$Webhook = Invoke-Probe `
    -Method "POST" `
    -Uri "$LegacyBase/webhook" `
    -Body "{}"
if ($Webhook.status -ne 503) {
    throw "LEGACY_FREEZE_WEBHOOK_NOT_503"
}
Write-Host "LEGACY_WEBHOOK_FROZEN=1"

Write-Host "LEGACY_WRITE_FREEZE_VERIFIED=1"
Write-Host "NEXT_STEP=run_guarded_telegram_webhook_cutover"
