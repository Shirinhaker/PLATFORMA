"""Permanent retired shell for the former v1656 Railway web service.

The legacy production cutover is complete.  This module intentionally has no
code path that can delegate requests to the old monolith.  If an old Railway
service is accidentally started again, it stays read-only/offline from the
application point of view: health probes succeed, while public navigation,
API mutations, Telegram webhook traffic, websockets, and background writers
remain unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MAINTENANCE_HTML = ROOT / "frontend" / "public" / "maintenance.html"


def _maintenance_html_bytes() -> bytes:
    try:
        return MAINTENANCE_HTML.read_bytes()
    except OSError:
        return (
            "<!doctype html><html lang='uz'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Koprik — eski servis o‘chirilgan</title>"
            "<body><h1>Eski servis productiondan chiqarilgan</h1>"
            "<p>Koprik yangi modular tizimda ishlaydi.</p>"
            "</body></html>"
        ).encode("utf-8")


def _headers(content_type: str, body: bytes) -> list[tuple[bytes, bytes]]:
    return [
        (b"content-type", content_type.encode("ascii")),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
        (b"retry-after", b"3600"),
        (b"x-koprik-maintenance", b"legacy-retired"),
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


class RetiredLegacyApp:
    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        scope_type = scope.get("type")

        if scope_type == "lifespan":
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
                    "retired": True,
                    "maintenance": True,
                    "writes_frozen": True,
                    "legacy_runtime_enabled": False,
                    "mode": "legacy_retired",
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

        if method in ("GET", "HEAD") and path == "/maintenance.html":
            body = _maintenance_html_bytes()
            await _send_http(
                send,
                status=200,
                body=body,
                content_type="text/html; charset=utf-8",
                head_only=head_only,
            )
            return

        if method in ("GET", "HEAD") and not (
            path.startswith("/api/") or path == "/webhook"
        ):
            body = _maintenance_html_bytes()
            await _send_http(
                send,
                status=503,
                body=body,
                content_type="text/html; charset=utf-8",
                head_only=head_only,
            )
            return

        body = json.dumps(
            {
                "detail": "Eski v1656 servis productiondan chiqarilgan.",
                "code": "legacy_retired",
                "retired": True,
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


app = RetiredLegacyApp()
