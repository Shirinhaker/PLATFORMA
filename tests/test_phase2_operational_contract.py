import re
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

    def test_ci_uses_phase2_verifier_and_fake_test_secrets(self):
        workflow = (
            ROOT / ".github/workflows/phase1-ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("python scripts/verify_phase2.py", workflow)
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


if __name__ == "__main__":
    unittest.main()
