import logging

import httpx

logger = logging.getLogger(__name__)


class OpenAIResponsesProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int = 45,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "gpt-4o-mini"
        self.timeout_seconds = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def answer(
        self, system: str, user: str | list[dict], *, max_output_tokens: int
    ) -> str:
        if not self.enabled:
            return ""
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        try:
            response = await self._client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            logger.warning("OpenAI Responses so'rovi bajarilmadi", exc_info=True)
            return ""
        logger.info(
            "OpenAI Responses javobi olindi",
            extra={"openai_request_id": response.headers.get("x-request-id", "")},
        )
        if not isinstance(data, dict):
            return ""
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()
        parts: list[str] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                if isinstance(content.get("text"), str):
                    parts.append(content["text"])
                elif isinstance(content.get("content"), str):
                    parts.append(content["content"])
        return "\n".join(parts).strip()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
