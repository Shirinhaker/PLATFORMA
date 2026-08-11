"""Railway cutover wrapper for the v1656 production web service.

Normal mode delegates every ASGI scope to ``main:app`` unchanged.
During the final V8 cutover, set ``KOPRIK_MIGRATION_MAINTENANCE=1``.
In that mode the legacy application is deliberately not imported or started,
so its Telegram webhook and background workers cannot write to SQLite while the
final source snapshot is being taken.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


MAINTENANCE_ENV = "KOPRIK_MIGRATION_MAINTENANCE"
ROOT = Path(__file__).resolve().parent
MAINTENANCE_HTML = ROOT / "frontend" / "public" / "maintenance.html"


def _env_enabled(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() not in ("", "0", "false", "no", "off")


MAINTENANCE_MODE = _env_enabled(MAINTENANCE_ENV)

# Importing main creates the normal v1656 FastAPI application.  We intentionally
# do not even import it in maintenance mode, because its lifespan starts the
# Telegram/outbox background workers.  This is the write-freeze boundary.
if not MAINTENANCE_MODE:
    from main import app as _normal_app
else:
    _normal_app = None


def _maintenance_html_bytes() -> bytes:
    try:
        return MAINTENANCE_HTML.read_bytes()
    except OSError:
        return (
            "<!doctype html><html lang='uz'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Koprik — texnik ishlar</title>"
            "<body><h1>Texnik ishlar olib borilmoqda</h1>"
            "<p>Ma’lumotlarni xavfsiz ko‘chiryapmiz. Iltimos, birozdan keyin qayta kiring.</p>"
            "</body></html>"
        ).encode("utf-8")


def _headers(content_type: str, body: bytes) -> list[tuple[bytes, bytes]]:
    return [
        (b"content-type", content_type.encode("ascii")),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        (b"retry-after", b"120"),
        (b"x-koprik-maintenance", b"migration-write-freeze"),
    ]


async def _send_http(
    send: Any,
    *,
    status: int,
    body: bytes,
    content_type: str,
    head_only: bool = False,
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": _headers(content_type, body),
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"" if head_only else body,
            "more_body": False,
        }
    )


class CutoverApp:
    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if not MAINTENANCE_MODE:
            assert _normal_app is not None
            await _normal_app(scope, receive, send)
            return

        scope_type = scope.get("type")
        if scope_type == "lifespan":
            # Do not enter main.py's lifespan in maintenance mode.  A successful
            # wrapper lifespan keeps Railway healthy while legacy writers stay off.
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            
        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 1013})
            return

        if scope_type != "http":
            return

        method = str(scope.get("method") or "GET").upper()
        path = str(scope.get("path") or "/")
        head_only = method == "HEAD"

        if method in ("GET", "HEAD") and path in ("/healthz", "/readyz"):
            body = json.dumps(
                {
                    "ok": True,
                    "maintenance": True,
                    "writes_frozen": True,
                    "mode": "v8_cutover",
                },
                separators=(",", ":"),
            ).encode("utf-8")
            await _send_http(
                send,
                status=200,
                body=body,
                content_type="application/json; charset=utf-8",
                head_only=head_only,
            )
            return

        if method in ("GET", "HEAD") and not (
            path.startswith("/api/") or path == "/webhook"
        ):
            body = _maintenance_html_bytes()
            await _send_http(
                send,
                status=200 if path == "/maintenance.html" else 503,
                body=body,
                content_type="text/html; charset=utf-8",
                head_only=head_only,
            )
            return

        body = json.dumps(
            {
                "detail": "V8 migratsiyasi uchun yozuvlar vaqtincha to‘xtatilgan.",
                "code": "migration_maintenance",
                "writes_frozen": True,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        await _send_http(
            send,
            status=503,
            body=body,
            content_type="application/json; charset=utf-8",
            head_only=head_only,
        )


app = CutoverApp()
