import httpx


class TelegramClient:
    def __init__(self, bot_token: str, http: httpx.AsyncClient) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}"
        self._http = http

    async def send_message(self, chat_id: int, text: str) -> None:
        try:
            response = await self._http.post(
                f"{self._url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
        except httpx.HTTPError:
            raise RuntimeError("Telegram xabarni qabul qilmadi.") from None
        if response.status_code >= 400:
            raise RuntimeError("Telegram xabarni qabul qilmadi.")
