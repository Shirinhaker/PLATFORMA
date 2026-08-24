import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LegacyWebhookForwarder:
    """Bizga tegishli bo'lmagan Telegram yangilanishlarini eski monolitga uzatadi.

    Telegram bitta botga bitta webhook manzilini biriktiradi, shuning uchun
    ikkala tizim ham ishlashi uchun yangilanish avval yangi backendga keladi
    va bu yerda taniqli bo'lmasa eski tizimga uzatiladi.
    """

    def __init__(self, url: str, secret: str, http: httpx.AsyncClient) -> None:
        self._url = url
        self._secret = secret
        self._http = http

    async def aclose(self) -> None:
        await self._http.aclose()

    async def forward(self, payload: dict[str, Any]) -> None:
        # Uzatish muvaffaqiyatsiz bo'lsa ham Telegramga xato qaytarmaymiz:
        # aks holda u butun yangilanishni qayta yuboradi va biz allaqachon
        # ko'rib chiqqan xabarni yana qayta ishlaymiz.
        try:
            response = await self._http.post(
                self._url,
                json=payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": self._secret},
            )
        except httpx.HTTPError:
            logger.warning("legacy_webhook_forward_failed", exc_info=True)
            return
        if response.status_code >= 400:
            logger.warning(
                "legacy_webhook_forward_rejected",
                extra={"status_code": response.status_code},
            )
