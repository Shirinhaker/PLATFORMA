from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.ai_assistant.service import AIAssistantService


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add_all(self, rows):
        self.added.extend(rows)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeRepository:
    async def business(self, _session, business_id):
        return SimpleNamespace(account_id=business_id, name="Turon savdo", direction="Savdo", activity_type="Do‘kon", director="Bekzod", tax_id="123", address="Qumqo‘rg‘on")

    async def context(self, _session, _business_id, _start, _end):
        return {"today_summary": {"revenue": 500_000, "expenses": 120_000, "profit": 380_000}, "debt_total": 75_000, "low_stock": [{"name": "Un", "qty": 2.0, "unit": "kg"}], "orders_by_status": {"new": 3}}

    async def history(self, _session, _business_id, _limit):
        return [SimpleNamespace(role="user", text="Salom", created_at=datetime.now(UTC))]


class FakeProvider:
    enabled = False

    async def answer(self, *_args, **_kwargs):
        return ""


def service_and_session():
    session = FakeSession()

    @asynccontextmanager
    async def factory():
        yield session

    return AIAssistantService(factory, FakeProvider(), repository=FakeRepository()), session


@pytest.mark.asyncio
async def test_local_fallback_uses_only_tenant_context_and_saves_both_messages():
    service, session = service_and_session()
    result = await service.chat(17, "Qarzlar qancha")
    assert result.source == "local"
    assert "75 000 so‘m" in result.answer
    assert [row.role for row in session.added] == ["user", "assistant"]
    assert {row.business_account_id for row in session.added} == {17}
    assert session.committed is True


@pytest.mark.asyncio
async def test_history_keeps_v1656_order():
    service, session = service_and_session()
    result = await service.history(17, 30)
    assert result.history[0].text == "Salom"
    assert session.rolled_back is True


@pytest.mark.asyncio
async def test_document_draft_remains_draft_and_local_fallback():
    from app.ai_assistant.schemas import AIDocumentDraftRequest

    service, _session = service_and_session()
    result = await service.document_draft(17, AIDocumentDraftRequest(prompt="Xizmat shartnomasi tuz"))
    assert result.doc_type == "Shartnoma"
    assert result.direction == "chiquvchi"
    assert result.source == "local"
    assert result.note == "Bu AI draft. Saqlashdan oldin tekshiring."
