"""`DocumentService` — mixin'lardan yig'iladi."""

from __future__ import annotations

from app.documents.service_parts.base import DocumentServiceBase
from app.documents.service_parts.counterparties import CounterpartiesMixin
from app.documents.service_parts.documents import DocumentsMixin
from app.documents.service_parts.exchange import ExchangeMixin


class DocumentService(
    CounterpartiesMixin,
    DocumentsMixin,
    ExchangeMixin,
    DocumentServiceBase,
):
    """Kontragentlar, hujjatlar va hujjat almashinuvi."""
