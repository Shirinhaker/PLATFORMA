import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase2OperationalContractTests(unittest.TestCase):
    def test_single_verifier_keeps_phase1_and_legacy_gates(self):
        verifier = (ROOT / "scripts/verify_phase2.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("scripts/verify_phase1.py", verifier)
        self.assertIn("BUILD: v1656", verifier)
        self.assertIn("static/index.html: 14091 qator", verifier)
        self.assertIn("Production: o‘zgarmadi", verifier)

    def test_verifier_isolates_repeatable_legacy_sqlite_runs(self):
        verifier = (ROOT / "scripts/verify_phase2.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("TemporaryDirectory", verifier)
        self.assertIn('legacy_env["DB_PATH"]', verifier)

    def test_load_probe_is_authenticated_staged_and_bounded(self):
        load_script = (ROOT / "scripts/phase2_load.js").read_text(
            encoding="utf-8"
        )

        for expected in (
            "KOPRIK_LOAD_SESSION",
            "KOPRIK_API_BASE_URL",
            "/api/v1/me",
            "target: 100",
            "target: 500",
            "target: 1000",
            'http_req_failed: ["rate<0.01"]',
            'http_req_duration: ["p(95)<500"]',
        ):
            self.assertIn(expected, load_script)

    def test_windows_load_runner_keeps_credentials_and_session_private(self):
        runner = (ROOT / "scripts/koprik-phase2-load.ps1").read_text(
            encoding="utf-8"
        )

        for expected in (
            "Read-Host",
            "Get-Clipboard -Raw",
            'Set-Clipboard -Value " "',
            "^[A-Za-z0-9_-]{16}$",
            "Clipboard tozalandi",
            "[System.Net.Http.HttpClient].Assembly.Location",
            "-ReferencedAssemblies $httpAssemblyPath",
            "/api/v1/auth/login/start",
            "/api/v1/auth/login/verify",
            "/api/v1/me",
            "100, 500, 1000",
            "p95_ms",
            "error_rate",
            "phase2-load-result.json",
        ):
            self.assertIn(expected, runner)

        self.assertNotIn("-AsSecureString", runner)
        self.assertNotIn("SecureStringToBSTR", runner)
        self.assertNotIn("PtrToStringBSTR", runner)
        self.assertNotIn('Set-Clipboard -Value ""', runner)
        self.assertNotIn("Write-Host $password", runner)
        self.assertNotIn("Write-Host $sessionToken", runner)
        self.assertNotIn("KOPRIK_LOAD_SESSION=", runner)

    def test_windows_load_runner_scales_client_connections_and_reports_failures(
        self,
    ):
        runner = (ROOT / "scripts/koprik-phase2-load.ps1").read_text(
            encoding="utf-8"
        )

        for expected in (
            "$maxConcurrency = [int](($Stages | "
            "Measure-Object -Maximum).Maximum)",
            "[System.Net.ServicePointManager]::DefaultConnectionLimit = "
            "$maxConcurrency",
            "$handler.MaxConnectionsPerServer = $maxConcurrency",
            "duration_ms",
            "status_counts",
            "error_types",
            "max_connections_per_server",
        ):
            self.assertIn(expected, runner)

    def test_windows_latency_diagnostic_is_layered_and_secret_safe(self):
        diagnostic = (
            ROOT / "scripts/koprik-phase2-latency-diagnostic.ps1"
        ).read_text(encoding="utf-8")

        for expected in (
            '[int]$Concurrency = 1000',
            '"healthz_cold"',
            '"healthz_reused"',
            '"/healthz"',
            '"auth_session"',
            '"/api/v1/auth/session"',
            '"me"',
            '"/api/v1/me"',
            "WarmUp",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "duration_ms",
            "status_counts",
            "error_types",
            "phase2-latency-diagnostic-v2-result.json",
            "$handler.MaxConnectionsPerServer = $Concurrency",
            "$endpointReports.Count -eq 4",
        ):
            self.assertIn(expected, diagnostic)

        for forbidden in (
            "Write-Host $password",
            "Write-Host $telegramCode",
            "Write-Host $sessionToken",
            "KOPRIK_LOAD_SESSION=",
            "phase2-load-result.json",
        ):
            self.assertNotIn(forbidden, diagnostic)

    def test_ci_uses_phase3a_verifier_and_preserves_phase2_gate(self):
        workflow = (
            ROOT / ".github/workflows/phase1-ci.yml"
        ).read_text(encoding="utf-8")
        phase3_verifier = (
            ROOT / "scripts/verify_phase3a.py"
        ).read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_phase3a.py", workflow)
        self.assertIn('"scripts/verify_phase2.py"', phase3_verifier)
        self.assertIn("KOPRIK_OTP_SECRET: ci-otp-secret", workflow)
        self.assertIn("KOPRIK_CSRF_SECRET: ci-csrf-secret", workflow)
        self.assertIn(
            "KOPRIK_TELEGRAM_WEBHOOK_SECRET: ci-webhook-secret",
            workflow,
        )
        self.assertIn(
            "KOPRIK_OUTBOX_ENCRYPTION_KEY: "
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            workflow,
        )
        self.assertNotIn("KOPRIK_TELEGRAM_BOT_TOKEN:", workflow)

    def test_example_and_runbook_cover_staging_without_production_mutation(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        runbook = (
            ROOT / "docs/deploy-auth-profile-staging.md"
        ).read_text(encoding="utf-8")

        for variable in (
            "KOPRIK_CORS_ORIGINS",
            "KOPRIK_TELEGRAM_BOT_TOKEN",
            "KOPRIK_TELEGRAM_BOT_USERNAME",
            "KOPRIK_TELEGRAM_WEBHOOK_SECRET",
            "KOPRIK_OTP_SECRET",
            "KOPRIK_CSRF_SECRET",
            "KOPRIK_OUTBOX_ENCRYPTION_KEY",
            "KOPRIK_AUTH_COOKIE_NAME",
            "KOPRIK_SESSION_TTL_SECONDS",
        ):
            self.assertIn(f"{variable}=", env_example)
            self.assertIn(variable, runbook)

        for gate in (
            "alembic upgrade head",
            "api-staging",
            "worker-staging",
            "frontend-staging",
            "Telegram webhook",
            "k6 run scripts/phase2_load.js",
            "scripts\\koprik-phase2-load.ps1",
            "phase2-load-result.json",
            "rollback",
            "koprik.uz",
            "hech qachon",
        ):
            self.assertIn(gate, runbook)

    def test_staging_runbook_documents_profile_summary_cache_gate(self):
        runbook = (
            ROOT / "docs/deploy-auth-profile-staging.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS=30",
            "profile:me:v1:",
            "1000 parallel",
            "0 xato",
            "p95 500 ms dan past",
        ):
            self.assertIn(expected, runbook)


if __name__ == "__main__":
    unittest.main()
