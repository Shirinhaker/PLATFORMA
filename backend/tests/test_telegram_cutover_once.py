from __future__ import annotations

from pathlib import Path

import pytest

from app.auth import telegram_cutover_once as cutover


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "backend/Dockerfile"


def _production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_SERVICE_ID", cutover.TARGET_SERVICE_ID)
    monkeypatch.setenv(
        "RAILWAY_ENVIRONMENT_ID",
        cutover.TARGET_ENVIRONMENT_ID,
    )
    monkeypatch.setenv(
        "RAILWAY_PUBLIC_DOMAIN",
        "platforma-production-f753.up.railway.app",
    )
    monkeypatch.setenv("KOPRIK_TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("KOPRIK_TELEGRAM_BOT_USERNAME", "koprik_test_bot")
    monkeypatch.setenv("KOPRIK_TELEGRAM_WEBHOOK_SECRET", "secret-value")


def test_cutover_skips_outside_exact_railway_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "other-service")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "other-environment")

    assert cutover.run() == 0
    assert "TELEGRAM_WEBHOOK_CUTOVER_SKIPPED=1" in capsys.readouterr().out


def test_cutover_rejects_invalid_secret_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _production_env(monkeypatch)
    monkeypatch.setenv("KOPRIK_TELEGRAM_WEBHOOK_SECRET", "bad secret")

    def forbidden_freeze() -> None:
        raise AssertionError("network must not start with an invalid secret")

    monkeypatch.setattr(cutover, "_verify_legacy_freeze", forbidden_freeze)

    with pytest.raises(
        cutover.CutoverError,
        match="telegram_webhook_secret_invalid",
    ):
        cutover.run()


def test_cutover_verifies_freeze_twice_then_sets_and_verifies_webhook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _production_env(monkeypatch)
    freeze_checks = 0
    calls: list[tuple[str, dict | None]] = []
    webhook_reads = 0

    def fake_freeze() -> None:
        nonlocal freeze_checks
        freeze_checks += 1

    def fake_telegram_api(token: str, method: str, body=None):
        nonlocal webhook_reads
        assert token == "secret-token"
        calls.append((method, body))
        if method == "getMe":
            return {"ok": True, "result": {"username": "koprik_test_bot"}}
        if method == "getWebhookInfo":
            webhook_reads += 1
            url = (
                "https://old.example/webhook"
                if webhook_reads == 1
                else "https://platforma-production-f753.up.railway.app"
                "/api/v1/auth/telegram/webhook"
            )
            return {"ok": True, "result": {"url": url}}
        if method == "setWebhook":
            return {"ok": True, "result": True}
        raise AssertionError(method)

    monkeypatch.setattr(cutover, "_verify_legacy_freeze", fake_freeze)
    monkeypatch.setattr(cutover, "_telegram_api", fake_telegram_api)

    assert cutover.run() == 0
    assert freeze_checks == 2
    assert [method for method, _ in calls] == [
        "getMe",
        "getWebhookInfo",
        "setWebhook",
        "getWebhookInfo",
    ]
    set_body = calls[2][1]
    assert set_body is not None
    assert set_body["url"].endswith("/api/v1/auth/telegram/webhook")
    assert set_body["secret_token"] == "secret-value"
    assert set_body["allowed_updates"] == ["message"]
    assert set_body["drop_pending_updates"] is False


def test_cutover_fails_before_telegram_write_if_legacy_is_not_frozen(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _production_env(monkeypatch)

    def blocked_freeze() -> None:
        raise cutover.CutoverError("legacy_writes_not_frozen")

    def forbidden_telegram(*args, **kwargs):
        raise AssertionError("Telegram must not be called before freeze passes")

    monkeypatch.setattr(cutover, "_verify_legacy_freeze", blocked_freeze)
    monkeypatch.setattr(cutover, "_telegram_api", forbidden_telegram)

    assert cutover.main() == 1
    error = capsys.readouterr().err
    assert "legacy_writes_not_frozen" in error
    assert "secret-token" not in error
    assert "secret-value" not in error


def test_api_docker_cutover_requires_explicit_opt_in() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    guard = "KOPRIK_TELEGRAM_CUTOVER_ONCE:-0"
    cutover_command = "python -m app.auth.telegram_cutover_once"
    uvicorn_command = "exec uvicorn app.main:app"

    assert guard in dockerfile
    assert cutover_command in dockerfile
    assert uvicorn_command in dockerfile
    assert '= \\"1\\" ]; then' in dockerfile
    assert "fi && exec uvicorn app.main:app" in dockerfile
    assert "python -m app.auth.telegram_cutover_once && exec uvicorn" not in dockerfile
    assert dockerfile.index(guard) < dockerfile.index(cutover_command) < dockerfile.index(uvicorn_command)


def test_cutover_source_never_logs_secret_values() -> None:
    source = Path(cutover.__file__).read_text(encoding="utf-8")

    for unsafe in (
        "print(token",
        "print(webhook_secret",
        "BOT_TOKEN={",
        "WEBHOOK_SECRET={",
    ):
        assert unsafe not in source
