import httpx


class OpenAIResponsesProvider:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: int = 45) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "gpt-4o-mini"
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def answer(self, system: str, user: str, *, max_output_tokens: int) -> str:
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
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return ""
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()
        parts: list[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        return "\n".join(parts).strip()
