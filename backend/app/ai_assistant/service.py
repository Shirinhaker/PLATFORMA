from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, time, timedelta, timezone
import json
import time as unix_time

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.documents import (
    build_document_context,
    contractor_snapshot,
    document_prompt_context,
    local_document_body,
    pick_document_type,
)
from app.ai_assistant.model import AIChatMessage
from app.ai_assistant.provider import OpenAIResponsesProvider
from app.ai_assistant.repository import AIAssistantRepository
from app.ai_assistant.schemas import AIChatAnswerRead, AIChatHistoryRead, AIChatMessageRead, AIDocumentDraftRead, AIDocumentDraftRequest
from app.core.errors import ApiError
from app.payments.model import BusinessSubscription


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
UZ_TZ = timezone(timedelta(hours=5))


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so'm"


class AIAssistantService:
    def __init__(self, session_factory: SessionFactory, provider: OpenAIResponsesProvider, *, repository: AIAssistantRepository | None = None) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._repository = repository or AIAssistantRepository()

    @property
    def openai_enabled(self) -> bool:
        return self._provider.enabled

    async def close(self) -> None:
        await self._provider.close()

    async def history(self, business_id: int, limit: int) -> AIChatHistoryRead:
        async with self._session_factory() as session:
            rows = await self._repository.history(session, business_id, max(1, min(limit, 100)))
            result = AIChatHistoryRead(history=[AIChatMessageRead(role=row.role, text=row.text, created_at=row.created_at) for row in rows])
            await session.rollback()
            return result

    async def quota_plan(self, business_id: int) -> str:
        async with self._session_factory() as session:
            plan = await session.scalar(
                select(BusinessSubscription.plan_code)
                .where(
                    BusinessSubscription.business_account_id == business_id,
                    BusinessSubscription.status == "active",
                    BusinessSubscription.expires_at > int(unix_time.time()),
                )
                .order_by(
                    case((BusinessSubscription.plan_code == "pro", 0), else_=1),
                    BusinessSubscription.expires_at.desc(),
                )
                .limit(1)
            )
            await session.rollback()
        return str(plan or "free")

    async def chat(
        self,
        business_id: int,
        message: str,
        *,
        allow_external_processing: bool = False,
    ) -> AIChatAnswerRead:
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
            context["today"] = local_day.isoformat()
            context["business"] = {
                "id": business_id,
                "name": business.name,
                "yon": business.direction,
                "tur": business.activity_type,
                "director": business.director,
                "inn": business.tax_id,
                "address": business.address,
                "phone": business.phone,
            }
            await session.rollback()
        answer = await self._provider.answer(
            "Sen Platforma biznes kabinetidagi AI yordamchisan. O'zbek "
            "tilida, sodda va aniq javob ber. Faqat berilgan biznes "
            "kontekstiga asoslan.",
            "Biznes konteksti:\n" + json.dumps(context, ensure_ascii=False, indent=2) + "\n\nSavol:\n" + message,
            max_output_tokens=1200,
        ) if allow_external_processing else ""
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
        user_prompt = body.prompt.strip()
        if not user_prompt:
            raise ApiError(
                400,
                "ai_document_prompt_required",
                "AI uchun hujjat topshirig'ini yozing.",
            )
        today = datetime.now(UZ_TZ).date().isoformat()
        async with self._session_factory() as session:
            business = await self._repository.business(session, business_id)
            if business is None:
                raise ApiError(404, "business_not_found", "Biznes profili topilmadi.")
            direction, doc_type = self._doc_type(
                user_prompt,
                body.direction,
                body.doc_type,
            )
            contractor = (
                await self._repository.contractor(
                    session,
                    business_id,
                    body.contractor_id,
                )
                if body.contractor_id is not None
                else None
            )
            context = build_document_context(
                business,
                body,
                contractor,
                today=today,
            )
            contractor_data = contractor_snapshot(contractor)
            await session.rollback()
        prompt_context = document_prompt_context(
            context,
            contractor_data,
            direction=direction,
            doc_type=doc_type,
            prompt=user_prompt,
        )
        prompt = (
            "Kontekst:\n"
            + json.dumps(prompt_context, ensure_ascii=False, indent=2)
            + "\n\nShu topshiriq bo'yicha hujjat draftini yoz."
        )
        text = await self._provider.answer(
            "Sen Platforma ilovasidagi AI hujjat generatorisan. "
            "Faqat o'zbek tilida rasmiy, sodda, tahrirlashga tayyor DRAFT "
            "hujjat matni yoz. Hujjatni yakuniy huquqiy maslahat deb "
            "ko'rsatma; foydalanuvchi tekshirishi kerak. Rekvizitlar "
            "yetishmasa [..] ko'rinishida joy qoldir. Faqat hujjat matnini "
            "qaytar.",
            prompt,
            max_output_tokens=2200,
        ) if body.allow_external_processing else ""
        source = "openai" if text else "local"
        if not text:
            text = local_document_body(user_prompt, direction, doc_type, context)
        title = body.title.strip() or (
            user_prompt[:70] + ("..." if len(user_prompt) > 70 else "")
        )
        return AIDocumentDraftRead(
            source=source,
            direction=direction,
            doc_type=doc_type,
            title=title,
            number=body.number.strip(),
            doc_date=body.doc_date.strip() or today,
            body=text.strip(),
        )

    @staticmethod
    def _doc_type(prompt: str, direction: str, doc_type: str) -> tuple[str, str]:
        return pick_document_type(prompt, direction, doc_type)

    @staticmethod
    def _local_answer(message: str, context: dict) -> str:
        lowered = message.lower()
        summary = context["today_summary"]
        if any(word in lowered for word in ("savdo", "tushum", "foyda", "statistika")):
            return (
                "📊 Bugungi xulosa:\n"
                "• Tushum: " + _money(summary["revenue"]) + "\n"
                "• Xarajat: " + _money(summary["expenses"]) + "\n"
                "• Sof foyda: " + _money(summary["profit"])
            )
        if any(word in lowered for word in ("ombor", "qoldiq", "kam")):
            rows = context["low_stock"]
            return (
                "📦 Hozir kam qolgan tovar topilmadi."
                if not rows
                else "📦 Kam qolgan tovarlar:\n"
                + "\n".join(
                    f"• {row['name'] or 'Nomsiz'} — "
                    f"{row['qty'] or 0} {row['unit'] or 'dona'}"
                    for row in rows[:6]
                )
            )
        if any(word in lowered for word in ("qarz", "debitor")):
            return "📒 Umumiy qarz qoldig'i: " + _money(context["debt_total"]) + "."
        if any(word in lowered for word in ("buyurtma", "zakaz")):
            rows = context["orders_by_status"]
            return "📥 Hozir buyurtmalar statistikasi topilmadi." if not rows else "📥 Buyurtmalar holati:\n" + "\n".join(f"• {key}: {value}" for key, value in rows.items())
        if any(
            word in lowered
            for word in ("eng ko'p", "eng ko‘p", "ko'p sot", "ko‘p sot", "top")
        ):
            rows = context.get("top_products") or []
            if not rows:
                return "🛒 Bugun sotilgan mahsulotlar topilmadi."
            return "🛒 Eng ko'p sotilganlar:\n" + "\n".join(
                f"• {row['name']} — {row['qty']:g} {row['unit']} · {_money(row['total'])}"
                for row in rows[:6]
            )
        return (
            "🤖 Bugungi qisqa xulosa:\n"
            "• Tushum: " + _money(summary["revenue"]) + "\n"
            "• Xarajat: " + _money(summary["expenses"]) + "\n"
            "• Sof foyda: " + _money(summary["profit"]) + "\n"
            "• Qarz qoldig'i: " + _money(context["debt_total"]) + "\n"
            "• Kam qolgan tovarlar: " + str(len(context.get("low_stock") or []))
            + " ta\n\nOmbor, qarz, buyurtma yoki savdo bo'yicha aniqroq "
            "so'rasangiz, batafsil aytaman."
        )
