[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "https://platforma-production-f753.up.railway.app",
    [int]$Concurrency = 1000,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")
if ($Concurrency -le 0) {
    throw "Parallel so'rovlar soni musbat bo'lishi kerak."
}
[System.Net.ServicePointManager]::DefaultConnectionLimit = $Concurrency

Write-Host "Koprik Phase 2 qatlamlar bo'yicha latency diagnostikasi v2"
Write-Host "Login, parol, Telegram kodi va sessiya faylga yozilmaydi."
Write-Host "Faqat staging GET endpointlari o'lchanadi."

$login = (Read-Host "Staging test loginini kiriting").Trim()
Write-Host "Telegramdagi Koprik parolini nusxalang."
Read-Host "Parol nusxalangach Enter bosing" | Out-Null
try {
    $password = (Get-Clipboard -Raw).Trim()
}
finally {
    Set-Clipboard -Value " "
}
Write-Host "Clipboard tozalandi."

if ($password -notmatch '^[A-Za-z0-9_-]{16}$') {
    $password = $null
    throw "Clipboarddagi parol formati noto'g'ri. Telegramdagi faqat parol qiymatini qayta nusxalang."
}

$webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{
    login = $login
    password = $password
} | ConvertTo-Json -Compress

try {
    $challenge = Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBaseUrl/api/v1/auth/login/start" `
        -ContentType "application/json" `
        -Body $loginBody `
        -WebSession $webSession `
        -TimeoutSec $TimeoutSeconds
}
finally {
    $password = $null
    $loginBody = $null
}

Write-Host "Telegramga yuborilgan 6 xonali kodni kiriting."
$telegramCode = (Read-Host "Telegram kodi").Trim()
$verifyBody = @{
    request_id = [int64]$challenge.request_id
    code = $telegramCode
    device_name = "phase2-latency-diagnostic"
} | ConvertTo-Json -Compress

$verified = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/v1/auth/login/verify" `
    -ContentType "application/json" `
    -Body $verifyBody `
    -WebSession $webSession `
    -TimeoutSec $TimeoutSeconds
$telegramCode = $null
$verifyBody = $null

$identity = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/api/v1/me" `
    -WebSession $webSession `
    -TimeoutSec $TimeoutSeconds
if ($identity.account_type -notin @("user", "business")) {
    throw "Test sessiyasi akkaunt turini qaytarmadi."
}

Add-Type -AssemblyName System.Net.Http
$httpAssemblyPath = [System.Net.Http.HttpClient].Assembly.Location
Add-Type -ReferencedAssemblies $httpAssemblyPath -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.Http;
using System.Threading.Tasks;

public sealed class KoprikDiagnosticResult
{
    public int StatusCode { get; set; }
    public long LatencyMs { get; set; }
    public string Error { get; set; }
}

public static class KoprikPhase2Diagnostic
{
    private static async Task<KoprikDiagnosticResult> ReadEndpoint(
        HttpClient client,
        string url)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            using (var response = await client.GetAsync(url))
            {
                timer.Stop();
                return new KoprikDiagnosticResult
                {
                    StatusCode = (int)response.StatusCode,
                    LatencyMs = timer.ElapsedMilliseconds,
                    Error = ""
                };
            }
        }
        catch (Exception error)
        {
            timer.Stop();
            return new KoprikDiagnosticResult
            {
                StatusCode = 0,
                LatencyMs = timer.ElapsedMilliseconds,
                Error = error.GetType().Name
            };
        }
    }

    public static async Task WarmUp(HttpClient client, string url)
    {
        var result = await ReadEndpoint(client, url);
        if (result.StatusCode != 200)
        {
            throw new InvalidOperationException(
                "Warm-up HTTP status: " + result.StatusCode);
        }
    }

    public static async Task<KoprikDiagnosticResult[]> RunStage(
        HttpClient client,
        string url,
        int concurrency)
    {
        var pending =
            new List<Task<KoprikDiagnosticResult>>(concurrency);
        for (var index = 0; index < concurrency; index++)
        {
            pending.Add(ReadEndpoint(client, url));
        }
        return await Task.WhenAll(pending);
    }
}
"@

function Get-Percentile {
    param(
        [double[]]$SortedValues,
        [double]$Percentile
    )
    if ($SortedValues.Count -eq 0) {
        return $null
    }
    $index = [int][Math]::Max(
        0,
        [Math]::Ceiling($SortedValues.Count * $Percentile) - 1
    )
    return $SortedValues[$index]
}

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.CookieContainer = $webSession.Cookies
$handler.MaxConnectionsPerServer = $Concurrency
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)

$endpoints = @(
    [ordered]@{
        name = "healthz_cold"
        path = "/healthz"
        layer = "api_without_database_new_connections"
    },
    [ordered]@{
        name = "healthz_reused"
        path = "/healthz"
        layer = "api_without_database_reused_connections"
    },
    [ordered]@{
        name = "auth_session"
        path = "/api/v1/auth/session"
        layer = "authentication_database"
    },
    [ordered]@{
        name = "me"
        path = "/api/v1/me"
        layer = "authentication_and_profile_database"
    }
)

$endpointReports = New-Object System.Collections.Generic.List[object]
$completed = $false
try {
    foreach ($endpoint in $endpoints) {
        $url = "$ApiBaseUrl$($endpoint.path)"
        Write-Host "Warm-up: $($endpoint.name)"
        [void][KoprikPhase2Diagnostic]::WarmUp(
            $client,
            $url
        ).GetAwaiter().GetResult()

        Write-Host "Diagnostika: $($endpoint.name), $Concurrency parallel GET"
        $stageTimer = [System.Diagnostics.Stopwatch]::StartNew()
        $stageResults = [KoprikPhase2Diagnostic]::RunStage(
            $client,
            $url,
            $Concurrency
        ).GetAwaiter().GetResult()
        $stageTimer.Stop()

        $latencies = @($stageResults | ForEach-Object {
            [double]$_.LatencyMs
        } | Sort-Object)
        $errorCount = @($stageResults | Where-Object {
            $_.StatusCode -ne 200
        }).Count
        $statusCounts = @(
            $stageResults |
                Where-Object { $_.StatusCode -ne 0 } |
                Group-Object StatusCode |
                Sort-Object Name |
                ForEach-Object {
                    [ordered]@{
                        status_code = [int]$_.Name
                        count = $_.Count
                    }
                }
        )
        $errorTypes = @(
            $stageResults |
                Where-Object { $_.Error } |
                Group-Object Error |
                Sort-Object Name |
                ForEach-Object {
                    [ordered]@{
                        error_type = [string]$_.Name
                        count = $_.Count
                    }
                }
        )
        $endpointReports.Add([ordered]@{
            name = [string]$endpoint.name
            path = [string]$endpoint.path
            layer = [string]$endpoint.layer
            concurrency = $Concurrency
            requests = $stageResults.Count
            errors = $errorCount
            p50_ms = Get-Percentile $latencies 0.50
            p95_ms = Get-Percentile $latencies 0.95
            p99_ms = Get-Percentile $latencies 0.99
            duration_ms = $stageTimer.ElapsedMilliseconds
            status_counts = $statusCounts
            error_types = $errorTypes
        })
    }

    $completed = ($endpointReports.Count -eq 4)
    $report = [ordered]@{
        generated_at = [DateTime]::UtcNow.ToString("o")
        api_base_url = $ApiBaseUrl
        account_type = [string]$identity.account_type
        concurrency = $Concurrency
        max_connections_per_server = $Concurrency
        endpoints = $endpointReports
        completed = $completed
    }

    $resultPath = Join-Path (
        Get-Location
    ) "phase2-latency-diagnostic-v2-result.json"
    $report | ConvertTo-Json -Depth 7 | Set-Content `
        -Path $resultPath `
        -Encoding UTF8
    $report | ConvertTo-Json -Depth 7
    Write-Host "Natija: $resultPath"
}
finally {
    try {
        if ($verified.csrf_token) {
            Invoke-RestMethod `
                -Method Post `
                -Uri "$ApiBaseUrl/api/v1/auth/logout" `
                -Headers @{
                    "X-CSRF-Token" = [string]$verified.csrf_token
                } `
                -WebSession $webSession `
                -TimeoutSec $TimeoutSeconds | Out-Null
        }
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

if (-not $completed) {
    throw "To'rtta diagnostika bosqichi yakunlanmadi."
}
