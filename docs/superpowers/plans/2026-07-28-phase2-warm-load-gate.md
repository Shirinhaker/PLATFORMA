# Phase 2 Warm Authenticated Load Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an official Windows PowerShell staging gate that authenticates through Telegram OTP, reuses HTTPS connections, and requires zero errors plus `p95 < 500 ms` at 100, 500, and 1000 parallel `/api/v1/me` requests.

**Architecture:** A Windows PowerShell 5.1-compatible script owns the operator flow, cookie container, safe JSON report, and cleanup. A small in-process C# helper performs concurrent timed requests through one shared `HttpClient`; cold connection latency is measured separately and excluded from the gate. Existing Python operational-contract tests protect the script shape and the staging runbook explains how to execute and interpret it.

**Tech Stack:** Windows PowerShell 5.1, .NET `System.Net.Http.HttpClient`, inline C# via `Add-Type`, Python 3.12 `unittest`, existing FastAPI staging endpoints, GitHub Actions.

## Global Constraints

- Default API URL is exactly `https://platforma-production-f753.up.railway.app`.
- Measured endpoint is exactly `GET /api/v1/me`.
- Measured concurrency stages are exactly `100`, `500`, then `1000`.
- Every stage requires `errors == 0`, every status `HTTP 200`, and `p95_ms < 500`.
- `max_connections_per_server` is exactly `1000`.
- A single long-lived authenticated HTTP client and connection pool is reused for authentication, warm-up, and all measured stages.
- Cold latency is one fresh-client `GET /healthz`, reported as `cold_total_ms`, and never participates in the warm gate.
- Warm-up requests never participate in measured percentiles or status counts.
- Login, password, Telegram OTP, session/cookie, CSRF token, Telegram bot token, and webhook secret never appear in the JSON report.
- Password and OTP are memory-only; the clipboard is cleared immediately after reading the password.
- Existing `scripts/phase2_load.js`, API business logic, frontend, database migrations, Redis topology, Railway resources, `web`, and `koprik.uz` remain unchanged.
- Existing legacy contract remains `BUILD: v1656` and `static/index.html: 14091 qator`.

## File Structure

- Create `scripts/phase2_load.ps1`: operator prompts, authentication, cold diagnostic, warm-up, measured stages, strict gate, safe report, logout, and cleanup.
- Modify `tests/test_phase2_operational_contract.py`: static operational contract for connection reuse, stages, gate, cleanup, and secret-safe report; retain all existing k6 assertions.
- Modify `docs/deploy-auth-profile-staging.md`: official Windows command, interpretation, optional k6 role, and Phase 2 completion evidence.
- No production source file is modified.

---

### Task 1: Add the Windows warm-load gate under an executable contract

**Files:**
- Create: `scripts/phase2_load.ps1`
- Modify: `tests/test_phase2_operational_contract.py`
- Test: `tests/test_phase2_operational_contract.py`

**Interfaces:**
- Consumes: `POST /api/v1/auth/login/start` with `{login, password}`; `POST /api/v1/auth/login/verify` with `{request_id, code, device_name}`; `GET /api/v1/me`; `POST /api/v1/auth/logout` with `X-CSRF-Token`.
- Produces: `scripts/phase2_load.ps1 -ApiBaseUrl <uri> -OutputPath <file>`; safe JSON fields `generated_at`, `api_base_url`, `account_type`, `connection_model`, `max_connections_per_server`, `cold_total_ms`, `stages`, and `gate`.
- Internal helper signature: `[Koprik.LoadRunner]::Run([System.Net.Http.HttpClient] $client, [string] $url, [int] $count) -> Koprik.LoadSample[]`.
- Internal stage signature: `Invoke-WarmStage -Client <HttpClient> -Url <string> -Concurrency <int> -P95LimitMs <int> -> PSCustomObject`.

- [ ] **Step 1: Write the failing operational-contract test**

Add `import re` after `import unittest`, then add this method without changing the existing k6 test:

```python
    def test_windows_load_gate_reuses_connections_and_protects_report(self):
        load_script = (ROOT / "scripts/phase2_load.ps1").read_text(
            encoding="utf-8"
        )

        for expected in (
            "$StageConcurrencies = @(100, 500, 1000)",
            "$P95LimitMs = 500",
            "$MaxConnectionsPerServer = 1000",
            "Koprik.LoadRunner]::Run",
            "ResponseContentRead",
            "/healthz",
            "/api/v1/auth/login/start",
            "/api/v1/auth/login/verify",
            "/api/v1/me",
            "/api/v1/auth/logout",
            "Set-Clipboard -Value \" \"",
            "warmup",
            "cold_total_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "$errorCount -eq 0",
            "$p95 -lt $P95LimitMs",
            "reused_https_connections",
            "finally",
        ):
            self.assertIn(expected, load_script)

        self.assertEqual(
            load_script.count("New-Object System.Net.Http.HttpClient("),
            1,
        )
        report = re.search(
            r"\$safeReport\s*=\s*\[ordered\]@\{"
            r"(?P<body>.*?)"
            r"\n\s*\}\n\s*\$safeReport\s*\|",
            load_script,
            re.DOTALL,
        )
        self.assertIsNotNone(report)
        report_body = report.group("body").lower()
        for forbidden in (
            "login",
            "password",
            "otp",
            "session",
            "cookie",
            "csrf",
            "telegram",
        ):
            self.assertNotIn(forbidden, report_body)
```

- [ ] **Step 2: Run the new test and confirm it fails for the missing script**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py::Phase2OperationalContractTests::test_windows_load_gate_reuses_connections_and_protects_report -v
```

Expected: `FAIL` with `FileNotFoundError` for `scripts/phase2_load.ps1`.

- [ ] **Step 3: Create the PowerShell entry point and shared concurrent runner**

Create `scripts/phase2_load.ps1` with these exact parameters, constants, assembly load, and C# helper:

```powershell
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
```

The helper intentionally returns exception type names only; it never returns messages that could contain request data.

- [ ] **Step 4: Add HTTP client, JSON request, percentile, and stage functions**

Append these functions:

```powershell
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
```

- [ ] **Step 5: Add cold diagnostic, Telegram OTP auth, strict report, logout, and cleanup**

Append this main flow:

```powershell
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
```

- [ ] **Step 6: Run the targeted test and fix only implementation defects**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py::Phase2OperationalContractTests::test_windows_load_gate_reuses_connections_and_protects_report -v
```

Expected: `1 passed`.

- [ ] **Step 7: Run the complete operational-contract file**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py -v
```

Expected: all existing k6, CI, environment, runbook, cache, and new PowerShell contract tests pass.

- [ ] **Step 8: Commit the executable gate**

```bash
git add scripts/phase2_load.ps1 tests/test_phase2_operational_contract.py
git commit -m "feat: add Windows Phase 2 warm load gate"
```

---

### Task 2: Document the official Windows gate and Phase 2 evidence

**Files:**
- Modify: `tests/test_phase2_operational_contract.py`
- Modify: `docs/deploy-auth-profile-staging.md`
- Test: `tests/test_phase2_operational_contract.py`

**Interfaces:**
- Consumes: `scripts/phase2_load.ps1` command-line interface from Task 1.
- Produces: a runbook command that a Windows operator can copy exactly; completion rules distinguishing cold diagnostics, warm gate, and optional k6 smoke.

- [ ] **Step 1: Write the failing runbook contract**

Add this method to `Phase2OperationalContractTests`:

```python
    def test_staging_runbook_documents_official_windows_warm_gate(self):
        runbook = (
            ROOT / "docs/deploy-auth-profile-staging.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "scripts\\phase2_load.ps1",
            "phase2-warm-load-result.json",
            "cold_total_ms",
            "warm-up",
            "qayta ishlatiladigan HTTPS ulanishlari",
            "har bir bosqichda 0 xato",
            "har bir bosqichda p95 500 ms dan past",
            "k6 CI yoki Linux/macOS",
            "Phase 2 tugagan",
        ):
            self.assertIn(expected, runbook)
```

- [ ] **Step 2: Run the new runbook test and confirm it fails**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py::Phase2OperationalContractTests::test_staging_runbook_documents_official_windows_warm_gate -v
```

Expected: `FAIL` because the existing runbook only documents the k6 command.

- [ ] **Step 3: Replace Section 5 with the official Windows flow**

Replace the current `## 5. Xavfsiz yuklama o‘lchovi` section, up to but not including `## 6. Rollback`, with:

````markdown
## 5. Xavfsiz yuklama o‘lchovi

Phase 2 ning rasmiy staging gate’i Windows PowerShell orqali ishlaydi.
Repository root papkasida quyidagi buyruqni bajaring:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\phase2_load.ps1" `
  -OutputPath ".\phase2-warm-load-result.json"
```

Skript staging loginini so‘raydi. Telegramdagi Koprik parolini clipboardga
nusxalang va so‘ralganda Enter bosing; skript parolni olgach clipboardni
darhol tozalaydi. Keyin Telegram bot yuborgan 6 xonali kodni kiriting.
Login, parol, Telegram kodi va sessiya natija fayliga yozilmaydi.

Skript avval yangi ulanish bilan bitta `/healthz` so‘rovini o‘lchaydi.
Bu `cold_total_ms` faqat diagnostika bo‘lib, gate natijasiga kirmaydi.
Asosiy test bir xil qayta ishlatiladigan HTTPS ulanishlari bilan har bir
bosqichni warm-up qiladi, warm-up natijalarini tashlab yuboradi va keyin
`/api/v1/me` uchun 100, 500, 1000 parallel so‘rovni o‘lchaydi.

Phase 2 warm-load gate faqat quyidagi holatda o‘tadi:

- har bir bosqichda 0 xato;
- barcha measured javoblar HTTP 200;
- har bir bosqichda p95 500 ms dan past.

Natija `phase2-warm-load-result.json` fayliga yoziladi. Faylda secret
yo‘qligini tekshiring va uni Phase 2 staging dalili sifatida saqlang.
Skript non-zero exit code qaytarsa, gate o‘tmagan hisoblanadi.

Mavjud `scripts/phase2_load.js` o‘zgarmaydi. k6 CI yoki Linux/macOS
uchun qo‘shimcha smoke/capacity vositasi bo‘lib qoladi:

```bash
KOPRIK_API_BASE_URL=https://platforma-production-f753.up.railway.app \
KOPRIK_LOAD_SESSION=STAGING_TEST_SESSION \
k6 run scripts/phase2_load.js
```

k6 natijasi rasmiy Windows warm gate o‘rnini bosmaydi. Ushbu gate butun
tizim 10 000 concurrent userni ko‘taradi degan da’vo emas. 10 000 uchun
alohida capacity test, Railway replica masshtablash va DB/Redis/R2
metrikalari talab qilinadi.

Phase 2 tugagan deb belgilashdan oldin:

1. GitHub CI yashil;
2. `api-staging`, `worker-staging`, `frontend-staging` healthy;
3. user va business Telegram login hamda profil/media oqimlari ishlaydi;
4. Postgres backup olingan;
5. `phase2-warm-load-result.json` uchala bosqich uchun 0 xato va
   p95 500 ms dan past natijani ko‘rsatadi;
6. natija faylida maxfiy qiymat yo‘q.
````

- [ ] **Step 4: Run the runbook contract**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py::Phase2OperationalContractTests::test_staging_runbook_documents_official_windows_warm_gate -v
```

Expected: `1 passed`.

- [ ] **Step 5: Run the full Phase 2 verifier**

Run:

```bash
python scripts/verify_phase2.py
```

Expected final markers:

```text
backend tests: PASS
frontend tests: PASS
frontend build: PASS
legacy contract: PASS
BUILD: v1656
static/index.html: 14091 qator
Production: o‘zgarmadi
```

- [ ] **Step 6: Commit the runbook**

```bash
git add docs/deploy-auth-profile-staging.md tests/test_phase2_operational_contract.py
git commit -m "docs: document Phase 2 Windows load gate"
```

---

### Task 3: Perform final repository safety checks and prepare staging handoff

**Files:**
- Verify only: `docs/superpowers/specs/2026-07-28-phase2-warm-load-gate-design.md`
- Verify only: `docs/superpowers/plans/2026-07-28-phase2-warm-load-gate.md`
- Verify only: `scripts/phase2_load.ps1`
- Verify only: `tests/test_phase2_operational_contract.py`
- Verify only: `docs/deploy-auth-profile-staging.md`

**Interfaces:**
- Consumes: the two commits from Tasks 1 and 2.
- Produces: a reviewable implementation branch with no unrelated changes and an exact operator command for staging.

- [ ] **Step 1: Confirm the diff contains only the five intended files**

Run:

```bash
git diff --name-only main...HEAD
```

Expected:

```text
docs/deploy-auth-profile-staging.md
docs/superpowers/plans/2026-07-28-phase2-warm-load-gate.md
docs/superpowers/specs/2026-07-28-phase2-warm-load-gate-design.md
scripts/phase2_load.ps1
tests/test_phase2_operational_contract.py
```

- [ ] **Step 2: Check whitespace and conflict markers**

Run:

```bash
git diff --check main...HEAD
rg -n '^(<<<<<<<|=======|>>>>>>>)' scripts/phase2_load.ps1 tests/test_phase2_operational_contract.py docs/deploy-auth-profile-staging.md
```

Expected: both commands produce no errors; `rg` returns no matches.

- [ ] **Step 3: Scan the changed files for accidentally committed secret formats**

Run:

```bash
rg -n '(bot[0-9]{6,}:|csrf_token"\s*:|koprik_session=)' scripts/phase2_load.ps1 tests/test_phase2_operational_contract.py docs/deploy-auth-profile-staging.md
rg -n '^KOPRIK_LOAD_SESSION=' docs/deploy-auth-profile-staging.md
```

Expected: the first command finds nothing. The second command finds exactly the
literal documentation placeholder
`KOPRIK_LOAD_SESSION=STAGING_TEST_SESSION \`; no real token, session, or CSRF
value is present.

- [ ] **Step 4: Re-run targeted and complete verification**

Run:

```bash
python -m pytest tests/test_phase2_operational_contract.py -v
python scripts/verify_phase2.py
```

Expected: all tests pass and legacy markers remain unchanged.

- [ ] **Step 5: Hand the exact staging command to the operator**

After merge and healthy `api-staging` deployment, run on Windows from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\scripts\phase2_load.ps1" `
  -OutputPath ".\phase2-warm-load-result.json"
```

Expected successful report:

```json
{
  "connection_model": "reused_https_connections",
  "max_connections_per_server": 1000,
  "stages": [
    {"concurrency": 100, "errors": 0, "passed": true},
    {"concurrency": 500, "errors": 0, "passed": true},
    {"concurrency": 1000, "errors": 0, "passed": true}
  ],
  "gate": {
    "zero_errors": true,
    "p95_below_500_ms": true,
    "passed": true
  }
}
```

The real report also contains p50/p95/p99 and status counts. Do not merge any follow-up that changes production service code merely to force this operational gate to pass; diagnose staging latency separately if it fails.
