from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEBHOOK_SCRIPT = (
    ROOT / "scripts/Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1"
)
FREEZE_SCRIPT = (
    ROOT / "scripts/Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1"
)
RUNBOOK = ROOT / "docs/phase3c-v9-telegram-monolith-cutover.md"
PRODUCTION_RUNBOOK = ROOT / "docs/deploy-phase3c-production.md"


def test_webhook_cutover_is_dry_run_by_default_and_requires_legacy_freeze():
    script = WEBHOOK_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$Execute" in script
    assert "/api/v1/auth/telegram/webhook" in script
    assert 'Invoke-TelegramApi -Method "getMe"' in script
    assert 'Invoke-TelegramApi -Method "getWebhookInfo"' in script
    assert 'Invoke-TelegramApi -Method "setWebhook"' in script
    assert "TELEGRAM_WEBHOOK_NOT_CHANGED=1" in script
    assert "TELEGRAM_CUTOVER_WRONG_BOT" in script
    assert "TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN" in script
    assert "TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN_BEFORE_WRITE" in script
    assert "PREWRITE_GUARDS_OK=1" in script
    assert "LEGACY_WRITES_FROZEN" in script
    assert "drop_pending_updates = $false" in script
    assert 'allowed_updates = @("message")' in script
    assert "TELEGRAM_WEBHOOK_CUTOVER_COMPLETE=1" in script

    freeze_check = script.index("TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN")
    prewrite_check = script.index(
        "TELEGRAM_CUTOVER_LEGACY_NOT_FROZEN_BEFORE_WRITE"
    )
    set_webhook = script.index('Invoke-TelegramApi -Method "setWebhook"')
    verify_webhook = script.rindex('Invoke-TelegramApi -Method "getWebhookInfo"')
    assert freeze_check < prewrite_check < set_webhook < verify_webhook


def test_webhook_cutover_does_not_log_token_or_secret_values():
    script = WEBHOOK_SCRIPT.read_text(encoding="utf-8")

    for unsafe in (
        'Write-Host $BotToken',
        'Write-Host $WebhookSecret',
        'BOT_TOKEN={0}',
        'WEBHOOK_SECRET={0}',
    ):
        assert unsafe not in script
    assert "TELEGRAM_API_{0}_REQUEST_FAILED" in script


def test_legacy_freeze_verifier_checks_public_api_and_webhook_boundaries():
    script = FREEZE_SCRIPT.read_text(encoding="utf-8")

    assert '"$LegacyBase/readyz"' in script
    assert '"$LegacyBase/maintenance.html"' in script
    assert '"$LegacyBase/"' in script
    assert '"$LegacyBase/api/_setup"' in script
    assert '"$LegacyBase/webhook"' in script
    assert "LEGACY_FREEZE_NOT_ACTIVE" in script
    assert "LEGACY_FREEZE_ROOT_NOT_503" in script
    assert "LEGACY_FREEZE_API_MUTATION_NOT_503" in script
    assert "LEGACY_FREEZE_WEBHOOK_NOT_503" in script
    assert "LEGACY_WRITE_FREEZE_VERIFIED=1" in script

    ready_gate = script.index("LEGACY_FREEZE_NOT_ACTIVE")
    api_probe = script.index('"$LegacyBase/api/_setup"')
    webhook_probe = script.index('"$LegacyBase/webhook"')
    assert ready_gate < api_probe < webhook_probe


def test_runtime_cutover_runbook_preserves_safe_order_and_rollback_evidence():
    runbook = RUNBOOK.read_text(encoding="utf-8")

    required_order = [
        "legacy freeze",
        "freeze verify",
        "Telegram webhook cutover",
        "real auth smoke",
        "legacy auto-deploy/service off",
    ]
    positions = [runbook.index(item) for item in required_order]
    assert positions == sorted(positions)

    assert "KOPRIK_MIGRATION_MAINTENANCE=1" in runbook
    assert "Koprik-Phase3C-Legacy-Freeze-Verify-V9.ps1" in runbook
    assert "Koprik-Phase3C-Telegram-Webhook-Cutover-V9.ps1" in runbook
    assert "Demo akkaunt yaratish shart emas." in runbook
    assert "SQLite volume, backup, source archive" in runbook
    assert "o‘chirmang" in runbook
    assert "ko‘r-ko‘rona qaytish mumkin emas" in runbook


def test_production_runbook_requires_runtime_cutover_before_legacy_shutdown():
    runbook = PRODUCTION_RUNBOOK.read_text(encoding="utf-8")

    assert "phase3c-v9-telegram-monolith-cutover.md" in runbook
    runtime_cutover = runbook.index("phase3c-v9-telegram-monolith-cutover.md")
    old_web_stop = runbook.index("auto-deploy/service'ni to‘xtating")
    public_open = runbook.index("public Phase 3C flag/maintenance blokini")
    assert runtime_cutover < old_web_stop < public_open
    assert "SQLite volume, backup va migratsiya dalillarini" in runbook
