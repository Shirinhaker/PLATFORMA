"""Kabinet payloadining JSON yo'li.

Ilgari bularning hammasi bitta `payload_service.py` faylida edi —
2 159 qator. Endi mavzu bo'yicha bo'lingan:

| Modul | Nima |
|---|---|
| `constants` | resurs ta'riflari, holat ro'yxatlari, reklama narxlari |
| `helpers` | qidirish, tozalash, tur o'girish — domendan xabarsiz |
| `spec` | qaysi yo'nalish qaysi resursga tega oladi |
| `education` | guruhlar va arizalar |
| `medical` | shifokorlar, xodimlar, navbat |
| `dining` | tayyorlangan taomlar, stol faolligi |
| `advertisements` | reklama narxi |
| `actions` | amal dispetcheri |
| `service` | `BusinessOnlinePayloadService` klassi |

Bog'liqlik yo'nalishi bir tomonlama:
`constants -> helpers -> {education, medical, advertisements} -> spec
-> dining -> actions -> service`.
Aylanma import yo'q, `tests/test_payload_package_layering.py` shuni
tekshiradi.
"""

from app.business_online.payload.service import (
    BusinessOnlinePayloadService,
)

__all__ = ["BusinessOnlinePayloadService"]
