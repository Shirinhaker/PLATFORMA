"""Kontragentlar, hujjatlar va hujjat almashinuvi.

`DocumentService` ilgari 530 qatorlik bitta faylda edi.
Endi har bir mavzu o'z mixin'ida:

    base            -> huquq tekshiruvi va javob shakli
    counterparties  -> kontragentlar
    documents       -> hujjatlar
    exchange        -> yuborish va javob

Klass nomi va metod nomlari o'zgarmadi.
"""

from app.documents.service_parts.service import DocumentService

__all__ = ["DocumentService"]
