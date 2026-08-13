from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


TARGET_SERVICE_ID = "8e765ac7-2bde-4b6c-a7db-639e3dc2442c"
TARGET_ENVIRONMENT_ID = "3c37f08c-227b-4560-9c4d-f7c8ef8fca86"
LEGACY_FREEZE_URL = "https://web-production-302eb.up.railway.app/readyz"
WEBHOOK_PATH = "/api/v1/auth/telegram/webhook"
TIMEOUT_SECONDS = 15


class CutoverError(RuntimeError):
    pass


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _should_run() -> bool:
    return (
        _env("RAILWAY_SERVICE_ID") == TARGET_SERVICE_ID
        and _env("RAILWAY_ENVIRONMENT_ID") == TARGET_ENVIRONMENT_ID
    )


def _request_json(
    url: str,
    *,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    method = "GET"
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise CutoverError("http_status_not_200")
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CutoverError("http_request_failed") from None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise CutoverError("http_response_not_json") from None
    if not isinstance(payload, dict):
        raise CutoverError("http_response_not_object")
    return payload


def _verify_legacy_freeze() -> None:
    payload = _request_json(LEGACY_FREEZE_URL)
    if payload.get("maintenance") is not True:
        raise CutoverError("legacy_maintenance_not_active")
    if payload.get("writes_frozen") is not True:
        raise CutoverError("legacy_writes_not_frozen")


def _telegram_api(
    token: str,
    method: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _request_json(
        f"https://api.telegram.org/bot{token}/{method}",
        body=body or {},
    )
    if payload.get("ok") is not True:
        raise CutoverError(f"telegram_{method.lower()}_failed")
    return payload


def _result_object(payload: dict[str, Any], code: str) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise CutoverError(code)
    return result


def run() -> int:
    if not _should_run():
        print("TELEGRAM_WEBHOOK_CUTOVER_SKIPPED=1", flush=True)
        return 0

    public_domain = _env("RAILWAY_PUBLIC_DOMAIN")
    token = _env("KOPRIK_TELEGRAM_BOT_TOKEN")
    expected_username = _env("KOPRIK_TELEGRAM_BOT_USERNAME").lstrip("@")
    webhook_secret = _env("KOPRIK_TELEGRAM_WEBHOOK_SECRET")

    if not public_domain:
        raise CutoverError("railway_public_domain_missing")
    if not token:
        raise CutoverError("telegram_bot_token_missing")
    if not expected_username:
        raise CutoverError("telegram_bot_username_missing")
    if not webhook_secret:
        raise CutoverError("telegram_webhook_secret_missing")

    target_url = f"https://{public_domain}{WEBHOOK_PATH}"

    # Telegramga yozishdan oldin legacy servisning real write-freeze holatini
    # tekshiramiz. Freeze bo'lmasa yangi API deployi fail bo'ladi.
    _verify_legacy_freeze()

    bot = _result_object(
        _telegram_api(token, "getMe"),
        "telegram_getme_result_invalid",
    )
    actual_username = str(bot.get("username") or "").lstrip("@")
    if actual_username.casefold() != expected_username.casefold():
        raise CutoverError("telegram_wrong_bot")

    before = _result_object(
        _telegram_api(token, "getWebhookInfo"),
        "telegram_getwebhookinfo_result_invalid",
    )
    current_url = str(before.get("url") or "")
    if current_url == target_url:
        print("TELEGRAM_WEBHOOK_ALREADY_TARGET=1", flush=True)
        print(f"TELEGRAM_WEBHOOK_URL={target_url}", flush=True)
        return 0

    # Preflight va setWebhook orasidagi race'ni yopish uchun freeze'ni yana
    # bir marta tekshiramiz.
    _verify_legacy_freeze()

    set_result = _telegram_api(
        token,
        "setWebhook",
        {
            "url": target_url,
            "secret_token": webhook_secret,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        },
    )
    if set_result.get("result") is not True:
        raise CutoverError("telegram_setwebhook_rejected")

    after = _result_object(
        _telegram_api(token, "getWebhookInfo"),
        "telegram_getwebhookinfo_verify_result_invalid",
    )
    verified_url = str(after.get("url") or "")
    if verified_url != target_url:
        raise CutoverError("telegram_webhook_verify_failed")

    print("TELEGRAM_WEBHOOK_CUTOVER_COMPLETE=1", flush=True)
    print(f"TELEGRAM_WEBHOOK_URL={target_url}", flush=True)
    return 0


def main() -> int:
    try:
        return run()
    except CutoverError as exc:
        print(
            f"TELEGRAM_WEBHOOK_CUTOVER_ERROR={exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
