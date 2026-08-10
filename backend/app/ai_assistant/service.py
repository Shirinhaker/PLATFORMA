from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, time, timedelta, timezone
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.model import AIChatMessage
from app.ai_assistant.provider import OpenAIResponsesProvider
from app.ai_assistant.repository import AIAssistantRepository
from app.ai_assistant.schemas import AIChatAnswerRead, AIChatHistoryRead, AIChatMessageRead, AIDocumentDraftRead, AIDocumentDraftRequest
from app.core.errors import ApiError


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
UZ_TZ = timezone(timedelta(hours=5))


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so‘m"


class AIAssistantService:
    def __init__(self, session_factory: SessionFactory, provider: OpenAIResponsesProvider, *, repository: AIAssistantRepository | None = None) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._repository = repository or AIAssistantRepository()

    @property
    def openai_enabled(self) -> bool:
        return self._provider.enabled

    async def history(self, business_id: int, limit: int) -> AIChatHistoryRead:
        async with self._session_factory() as session:
            rows = await self._repository.history(session, business_id, max(1, min(limit, 100)))
            result = AIChatHistoryRead(history=[AIChatMessageRead(role=row.role, text=row.text, created_at=row.created_at) for row in rows])
            await session.rollback()
            return result

    async def chat(self, business_id: int, message: str) -> AIChatAnswerRead:
        message = message.strip()
        if not message:
            raise ApiError(400, "ai_message_required", "Savol yozing.")
        now = datetime.now(UTC)
        local_day = now.astimezone(UZ_TZ).date()
        start = datetime.combine(local_day, time.min, UZ_TZ).astimezone(UTC)
        end = start + timedelta(days=1)
        async with self._session_factory() as session:
            business = await self._repository.business(session, business_id)
            if business is None:
                raise ApiError(404, "business_not_found", "Biznes profili topilmadi.")
            context = await self._repository.context(session, business_id, start, end)
            context["business"] = {"name": business.name, "direction": business.direction, "activity_type": business.activity_type}
            await session.rollback()
        answer = await self._provider.answer(
            "Sen Koprik biznes kabinetidagi AI yordamchisan. O‘zbek tilida sodda va aniq javob ber. Faqat berilgan biznes kontekstiga asoslan. Hech qanday ma’lumotni o‘zgartirma.",
            "Biznes konteksti:\n" + json.dumps(context, ensure_ascii=False, indent=2) + "\n\nSavol:\n" + message,
            max_output_tokens=1200,
        )
        source = "openai" if answer else "local"
        if not answer:
            answer = self._local_answer(message, context)
        async with self._session_factory() as session:
            session.add_all([
                AIChatMessage(business_account_id=business_id, role="user", text=message, source="user", created_at=now),
                AIChatMessage(business_account_id=business_id, role="assistant", text=answer, source=source, created_at=now),
            ])
            await session.commit()
            return AIChatAnswerRead(answer=answer, source=source)

    async def document_draft(self, business_id: int, body: AIDocumentDraftRequest) -> AIDocumentDraftRead:
        async with self._session_factory() as session:
            business = await self._repository.business(session, business_id)
            if business is None:
                raise ApiError(404, "business_not_found", "Biznes profili topilmadi.")
            direction, doc_type = self._doc_type(body.prompt, body.direction, body.doc_type)
            business_snapshot = {"name": business.name, "director": business.director, "tax_id": business.tax_id, "address": business.address}
            await session.rollback()
        prompt = json.dumps({"business": business_snapshot, "direction": direction, "doc_type": doc_type, "number": body.number, "date": body.doc_date, "task": body.prompt}, ensure_ascii=False)
        text = await self._provider.answer("O‘zbek tilida rasmiy, tahrirlashga tayyor DRAFT hujjat yoz. Yetishmagan rekvizitlarga [..] joy qoldir. Faqat hujjat matnini qaytar.", prompt, max_output_tokens=2200)
        source = "openai" if text else "local"
        if not text:
            text = f"{business_snapshot['name']}\n\n{doc_type.upper()}\n\n{body.prompt}\n\nRahbar: ____________________ {business_snapshot['director'] or '[F.I.Sh.]'}\nM.O‘."
        return AIDocumentDraftRead(source=source, direction=direction, doc_type=doc_type, title=body.title or body.prompt[:70], number=body.number, doc_date=body.doc_date or datetime.now(UZ_TZ).date().isoformat(), body=text)

    @staticmethod
    def _doc_type(prompt: str, direction: str, doc_type: str) -> tuple[str, str]:
        if doc_type and doc_type != "Erkin shakldagi hujjat":
            return direction or "ichki", doc_type
        lowered = prompt.lower()
        for token, resolved_direction, resolved_type in (("shartnoma", "chiquvchi", "Shartnoma"), ("hisob", "chiquvchi", "Hisob-faktura"), ("akt", "chiquvchi", "Akt"), ("buyruq", "ichki", "Buyruq"), ("ariza", "ichki", "Ariza"), ("dalolatnoma", direction or "ichki", "Dalolatnoma")):
            if token in lowered:
                return resolved_direction, resolved_type
        return direction or "ichki", "Erkin shakldagi hujjat"

    @staticmethod
    def _local_answer(message: str, context: dict) -> str:
        lowered = message.lower(); summary = context["today_summary"]
        if any(word in lowered for word in ("ombor", "qoldiq", "kam")):
            rows = context["low_stock"]
            return "📦 Hozir kam qolgan tovar topilmadi." if not rows else "📦 Kam qolgan tovarlar:\n" + "\n".join(f"• {row['name']} — {row['qty']:g} {row['unit']}" for row in rows[:6])
        if any(word in lowered for word in ("qarz", "debitor")):
            return "📒 Umumiy qarz qoldig‘i: " + _money(context["debt_total"]) + "."
        if any(word in lowered for word in ("buyurtma", "zakaz")):
            rows = context["orders_by_status"]
            return "📥 Hozir buyurtmalar statistikasi topilmadi." if not rows else "📥 Buyurtmalar holati:\n" + "\n".join(f"• {key}: {value}" for key, value in rows.items())
        return "📊 Bugungi xulosa:\n• Tushum: " + _money(summary["revenue"]) + "\n• Xarajat: " + _money(summary["expenses"]) + "\n• Sof foyda: " + _money(summary["profit"]) + "\n• Qarz qoldig‘i: " + _money(context["debt_total"])
