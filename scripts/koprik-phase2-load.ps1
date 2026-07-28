[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "https://platforma-production-f753.up.railway.app",
    [int[]]$Stages = @(100, 500, 1000),
    [int]$RequestsPerWorker = 1,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")
$maxConcurrency = [int](($Stages | Measure-Object -Maximum).Maximum)
if ($maxConcurrency -le 0) {
    throw "Yuklama bosqichlari musbat bo'lishi kerak."
}
[System.Net.ServicePointManager]::DefaultConnectionLimit = $maxConcurrency

Write-Host "Koprik Phase 2 xavfsiz staging yuklama tekshiruvi"
Write-Host "Login, parol, Telegram kodi va sessiya faylga yozilmaydi."
Write-Host "Faqat GET /api/v1/me so'rovlari yuboriladi."

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
    device_name = "phase2-load-probe"
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
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;

public sealed class KoprikProbeResult
{
    public int StatusCode { get; set; }
    public long LatencyMs { get; set; }
    public string Error { get; set; }
}

public static class KoprikPhase2Probe
{
    private static async Task<KoprikProbeResult> ReadMe(
        HttpClient client,
        string url)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            using (var response = await client.GetAsync(url))
            {
                timer.Stop();
                return new KoprikProbeResult
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
            return new KoprikProbeResult
            {
                StatusCode = 0,
                LatencyMs = timer.ElapsedMilliseconds,
                Error = error.GetType().Name
            };
        }
    }

    public static async Task<KoprikProbeResult[]> RunStage(
        HttpClient client,
        string url,
        int concurrency,
        int requestsPerWorker)
    {
        var pending = new List<Task<KoprikProbeResult>>();
        var total = checked(concurrency * requestsPerWorker);
        for (var index = 0; index < total; index++)
        {
            pending.Add(ReadMe(client, url));
        }
        return await Task.WhenAll(pending);
    }
}
"@

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.CookieContainer = $webSession.Cookies
$handler.MaxConnectionsPerServer = $maxConcurrency
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)

$allResults = New-Object System.Collections.Generic.List[object]
$stageReports = New-Object System.Collections.Generic.List[object]
foreach ($stage in $Stages) {
    Write-Host "Bosqich boshlandi: $stage parallel o'qish"
    $stageTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $stageResults = [KoprikPhase2Probe]::RunStage(
        $client,
        "$ApiBaseUrl/api/v1/me",
        $stage,
        $RequestsPerWorker
    ).GetAwaiter().GetResult()
    $stageTimer.Stop()

    foreach ($row in $stageResults) {
        $allResults.Add($row)
    }
    $latencies = @($stageResults | ForEach-Object {
        [double]$_.LatencyMs
    } | Sort-Object)
    $errorCount = @($stageResults | Where-Object {
        $_.StatusCode -ne 200
    }).Count
    $p95Index = [int][Math]::Max(
        0,
        [Math]::Ceiling($latencies.Count * 0.95) - 1
    )
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
    $stageReports.Add([ordered]@{
        concurrency = $stage
        requests = $stageResults.Count
        errors = $errorCount
        p95_ms = $latencies[$p95Index]
        duration_ms = $stageTimer.ElapsedMilliseconds
        status_counts = $statusCounts
        error_types = $errorTypes
    })
}

$allLatencies = @($allResults | ForEach-Object {
    [double]$_.LatencyMs
} | Sort-Object)
$allErrors = @($allResults | Where-Object {
    $_.StatusCode -ne 200
}).Count
$overallP95Index = [int][Math]::Max(
    0,
    [Math]::Ceiling($allLatencies.Count * 0.95) - 1
)
$errorRate = if ($allResults.Count -eq 0) {
    1.0
}
else {
    $allErrors / [double]$allResults.Count
}
$passed = ($errorRate -lt 0.01) -and (
    $allLatencies[$overallP95Index] -lt 500
)

$report = [ordered]@{
    generated_at = [DateTime]::UtcNow.ToString("o")
    api_base_url = $ApiBaseUrl
    account_type = [string]$identity.account_type
    max_connections_per_server = $maxConcurrency
    stages = $stageReports
    total_requests = $allResults.Count
    error_count = $allErrors
    error_rate = [Math]::Round($errorRate, 6)
    p95_ms = $allLatencies[$overallP95Index]
    gate = [ordered]@{
        error_rate_below_one_percent = ($errorRate -lt 0.01)
        p95_below_500_ms = ($allLatencies[$overallP95Index] -lt 500)
        passed = $passed
    }
}

$resultPath = Join-Path (Get-Location) "phase2-load-result.json"
$report | ConvertTo-Json -Depth 6 | Set-Content `
    -Path $resultPath `
    -Encoding UTF8
$report | ConvertTo-Json -Depth 6
Write-Host "Natija: $resultPath"

try {
    if ($verified.csrf_token) {
        Invoke-RestMethod `
            -Method Post `
            -Uri "$ApiBaseUrl/api/v1/auth/logout" `
            -Headers @{ "X-CSRF-Token" = [string]$verified.csrf_token } `
            -WebSession $webSession `
            -TimeoutSec $TimeoutSeconds | Out-Null
    }
}
finally {
    $client.Dispose()
    $handler.Dispose()
}

if (-not $passed) {
    throw "Phase 2 yuklama gate o'tmadi."
}
