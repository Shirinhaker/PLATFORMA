[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "https://platforma-production-f753.up.railway.app",
    [string]$OutputPath = (Join-Path (Get-Location) "phase2-warm-load-result.json")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$StageConcurrencies = @(100, 500, 1000)
$P95LimitMs = 500
$MaxConnectionsPerServer = 1000

Add-Type -AssemblyName System.Net.Http

if (-not ("Koprik.LoadRunner" -as [type])) {
    $runnerSource = @"
using System;
using System.Diagnostics;
using System.Net.Http;
using System.Threading.Tasks;

namespace Koprik
{
    public sealed class LoadSample
    {
        public int StatusCode { get; set; }
        public long ElapsedMilliseconds { get; set; }
        public string ErrorType { get; set; }
    }

    public static class LoadRunner
    {
        private static async Task<LoadSample> MeasureAsync(
            HttpClient client,
            string url)
        {
            var timer = Stopwatch.StartNew();
            try
            {
                using (var request = new HttpRequestMessage(HttpMethod.Get, url))
                using (var response = await client.SendAsync(
                    request,
                    HttpCompletionOption.ResponseContentRead
                ).ConfigureAwait(false))
                {
                    timer.Stop();
                    return new LoadSample
                    {
                        StatusCode = (int)response.StatusCode,
                        ElapsedMilliseconds = timer.ElapsedMilliseconds,
                        ErrorType = ""
                    };
                }
            }
            catch (Exception exception)
            {
                timer.Stop();
                return new LoadSample
                {
                    StatusCode = 0,
                    ElapsedMilliseconds = timer.ElapsedMilliseconds,
                    ErrorType = exception.GetType().Name
                };
            }
        }

        public static LoadSample[] Run(
            HttpClient client,
            string url,
            int count)
        {
            var tasks = new Task<LoadSample>[count];
            for (var index = 0; index < count; index++)
            {
                tasks[index] = MeasureAsync(client, url);
            }
            return Task.WhenAll(tasks).GetAwaiter().GetResult();
        }
    }
}
"@
    Add-Type `
        -TypeDefinition $runnerSource `
        -Language CSharp `
        -ReferencedAssemblies ([System.Net.Http.HttpClient].Assembly.Location)
}

function New-KoprikHttpBundle {
    param([int]$MaxConnections)

    [System.Net.ServicePointManager]::DefaultConnectionLimit = $MaxConnections
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseCookies = $true
    $handler.CookieContainer = New-Object System.Net.CookieContainer
    if ($handler.PSObject.Properties.Name -contains "MaxConnectionsPerServer") {
        $handler.MaxConnectionsPerServer = $MaxConnections
    }
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(30)
    $client.DefaultRequestHeaders.Accept.ParseAdd("application/json")
    return [pscustomobject]@{
        Client = $client
        Handler = $handler
    }
}

function Invoke-JsonPost {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [hashtable]$Body
    )

    $response = $null
    $content = New-Object System.Net.Http.StringContent(
        ($Body | ConvertTo-Json -Compress),
        [System.Text.Encoding]::UTF8,
        "application/json"
    )
    try {
        $response = $Client.PostAsync($Url, $content).GetAwaiter().GetResult()
        $raw = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            throw "API POST xatosi: HTTP $([int]$response.StatusCode)."
        }
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return $null
        }
        return $raw | ConvertFrom-Json
    }
    finally {
        $content.Dispose()
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

function Invoke-JsonGet {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url
    )

    $response = $null
    try {
        $response = $Client.GetAsync(
            $Url,
            [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
        ).GetAwaiter().GetResult()
        $raw = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            throw "API GET xatosi: HTTP $([int]$response.StatusCode)."
        }
        return $raw | ConvertFrom-Json
    }
    finally {
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

function Get-Percentile {
    param(
        [long[]]$Values,
        [int]$Percent
    )

    if ($Values.Count -eq 0) {
        return 0
    }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling(($Percent / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($index, $sorted.Count - 1))
    return [long]$sorted[$index]
}

function Invoke-WarmStage {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [int]$Concurrency,
        [int]$P95LimitMs
    )

    Write-Host "Warm-up boshlandi: $Concurrency parallel GET"
    $warmup = [Koprik.LoadRunner]::Run($Client, $Url, $Concurrency)
    $warmupErrors = @(
        $warmup | Where-Object {
            $_.StatusCode -ne 200 -or
            -not [string]::IsNullOrWhiteSpace($_.ErrorType)
        }
    ).Count
    if ($warmupErrors -ne 0) {
        throw "Warm-up muvaffaqiyatsiz: $warmupErrors xato."
    }

    Write-Host "O'lchov boshlandi: $Concurrency parallel GET"
    $stageTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $samples = [Koprik.LoadRunner]::Run($Client, $Url, $Concurrency)
    $stageTimer.Stop()
    $durations = [long[]]@($samples | ForEach-Object {
        $_.ElapsedMilliseconds
    })
    $errorCount = @(
        $samples | Where-Object {
            $_.StatusCode -ne 200 -or
            -not [string]::IsNullOrWhiteSpace($_.ErrorType)
        }
    ).Count
    $p50 = Get-Percentile -Values $durations -Percent 50
    $p95 = Get-Percentile -Values $durations -Percent 95
    $p99 = Get-Percentile -Values $durations -Percent 99
    $statusCounts = [ordered]@{}
    foreach ($group in ($samples | Group-Object StatusCode)) {
        $statusCounts[[string]$group.Name] = $group.Count
    }
    $passed = ($errorCount -eq 0 -and $p95 -lt $P95LimitMs)

    return [pscustomobject][ordered]@{
        concurrency = $Concurrency
        requests = $samples.Count
        errors = $errorCount
        p50_ms = $p50
        p95_ms = $p95
        p99_ms = $p99
        duration_ms = $stageTimer.ElapsedMilliseconds
        status_counts = $statusCounts
        passed = $passed
    }
}

function Invoke-Logout {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [string]$CsrfToken
    )

    $request = New-Object System.Net.Http.HttpRequestMessage(
        [System.Net.Http.HttpMethod]::Post,
        $Url
    )
    $response = $null
    try {
        $request.Headers.Add("X-CSRF-Token", $CsrfToken)
        $response = $Client.SendAsync($request).GetAwaiter().GetResult()
        if ([int]$response.StatusCode -ne 204) {
            throw "Logout xatosi: HTTP $([int]$response.StatusCode)."
        }
    }
    finally {
        $request.Dispose()
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")
$coldBundle = $null
$mainBundle = $null
$password = $null
$otp = $null
$csrfToken = $null
$stageResults = @()
$coldTotalMs = $null

try {
    $validatedApiUri = [Uri]$ApiBaseUrl
    if ($validatedApiUri.Scheme -ne "https") {
        throw "API URL HTTPS bo'lishi kerak."
    }

    $coldResponse = $null
    try {
        $coldBundle = New-KoprikHttpBundle -MaxConnections 1
        $coldTimer = [System.Diagnostics.Stopwatch]::StartNew()
        $coldResponse = $coldBundle.Client.GetAsync(
            "$ApiBaseUrl/healthz",
            [System.Net.Http.HttpCompletionOption]::ResponseContentRead
        ).GetAwaiter().GetResult()
        $coldTimer.Stop()
        if ([int]$coldResponse.StatusCode -eq 200) {
            $coldTotalMs = $coldTimer.ElapsedMilliseconds
        }
        else {
            Write-Warning (
                "Cold healthz diagnostikasi HTTP " +
                "$([int]$coldResponse.StatusCode) qaytardi; warm gate davom etadi."
            )
        }
    }
    catch {
        Write-Warning (
            "Cold healthz diagnostikasi olinmadi: " +
            "$($_.Exception.GetType().Name); warm gate davom etadi."
        )
    }
    finally {
        if ($null -ne $coldResponse) {
            $coldResponse.Dispose()
        }
        if ($null -ne $coldBundle) {
            $coldBundle.Client.Dispose()
            $coldBundle.Handler.Dispose()
            $coldBundle = $null
        }
    }

    $mainBundle = New-KoprikHttpBundle `
        -MaxConnections $MaxConnectionsPerServer
    $login = (Read-Host "Staging test loginini kiriting").Trim()
    if ([string]::IsNullOrWhiteSpace($login)) {
        throw "Login bo'sh bo'lmasligi kerak."
    }

    Write-Host "Parolni clipboardga nusxalang va Enter bosing."
    Read-Host | Out-Null
    $password = (Get-Clipboard -Raw).Trim()
    Set-Clipboard -Value " "
    if ($password.Length -lt 8) {
        throw "Parol kamida 8 belgidan iborat bo'lishi kerak."
    }

    $challenge = Invoke-JsonPost `
        -Client $mainBundle.Client `
        -Url "$ApiBaseUrl/api/v1/auth/login/start" `
        -Body @{ login = $login; password = $password }
    $password = $null
    if ($null -eq $challenge.request_id) {
        throw "Login challenge request_id qaytarmadi."
    }

    $otp = (Read-Host "Telegramga yuborilgan 6 xonali kodni kiriting").Trim()
    if ($otp -notmatch "^\d{6}$") {
        throw "Telegram kodi aynan 6 xonali bo'lishi kerak."
    }
    $authenticated = Invoke-JsonPost `
        -Client $mainBundle.Client `
        -Url "$ApiBaseUrl/api/v1/auth/login/verify" `
        -Body @{
            request_id = [int]$challenge.request_id
            code = $otp
            device_name = "phase2-warm-load-gate"
        }
    $otp = $null
    $csrfToken = [string]$authenticated.csrf_token
    if ([string]::IsNullOrWhiteSpace($csrfToken)) {
        throw "CSRF token qaytmadi."
    }

    $me = Invoke-JsonGet `
        -Client $mainBundle.Client `
        -Url "$ApiBaseUrl/api/v1/me"
    if ($null -eq $me.account_type) {
        throw "/api/v1/me account_type qaytarmadi."
    }

    foreach ($concurrency in $StageConcurrencies) {
        $stageResults += Invoke-WarmStage `
            -Client $mainBundle.Client `
            -Url "$ApiBaseUrl/api/v1/me" `
            -Concurrency $concurrency `
            -P95LimitMs $P95LimitMs
    }
    $allPassed = @($stageResults | Where-Object {
        -not $_.passed
    }).Count -eq 0

    $safeReport = [ordered]@{
        generated_at = [DateTime]::UtcNow.ToString("o")
        api_base_url = $ApiBaseUrl
        account_type = [string]$me.account_type
        connection_model = "reused_https_connections"
        max_connections_per_server = $MaxConnectionsPerServer
        cold_total_ms = $coldTotalMs
        stages = $stageResults
        gate = [ordered]@{
            zero_errors = @($stageResults | Where-Object {
                $_.errors -ne 0
            }).Count -eq 0
            p95_below_500_ms = @($stageResults | Where-Object {
                $_.p95_ms -ge $P95LimitMs
            }).Count -eq 0
            passed = $allPassed
        }
    }
    $safeReport |
        ConvertTo-Json -Depth 8 |
        Set-Content -Path $OutputPath -Encoding UTF8
    $safeReport | ConvertTo-Json -Depth 8
    Write-Host "Natija: $OutputPath"

    if (-not $allPassed) {
        throw "Phase 2 warm-load gate o'tmadi."
    }
}
finally {
    try {
        if (
            $null -ne $mainBundle -and
            -not [string]::IsNullOrWhiteSpace($csrfToken)
        ) {
            Invoke-Logout `
                -Client $mainBundle.Client `
                -Url "$ApiBaseUrl/api/v1/auth/logout" `
                -CsrfToken $csrfToken
        }
    }
    finally {
        $password = $null
        $otp = $null
        $csrfToken = $null
        $login = $null
        Set-Clipboard -Value " "
        if ($null -ne $coldBundle) {
            $coldBundle.Client.Dispose()
            $coldBundle.Handler.Dispose()
        }
        if ($null -ne $mainBundle) {
            $mainBundle.Client.Dispose()
            $mainBundle.Handler.Dispose()
        }
    }
}
