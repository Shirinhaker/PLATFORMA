from __future__ import annotations

import logging
from datetime import UTC, datetime

from pythonjsonlogger.json import JsonFormatter

from app.core.middleware import request_id_context


class KoprikLogFilter(logging.Filter):
    def __init__(self, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.timestamp = datetime.now(UTC).isoformat()
        record.service = self.service
        record.environment = self.environment
        record.request_id = request_id_context.get()
        return True


def configure_logging(service: str, environment: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(KoprikLogFilter(service, environment))
    handler.setFormatter(
        JsonFormatter(
            "%(timestamp)s %(levelname)s %(service)s %(environment)s "
            "%(request_id)s %(name)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
