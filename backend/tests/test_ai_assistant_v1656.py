from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.ai_assistant.repository import AIAssistantRepository
from app.ai_assistant.schemas import AIDocumentDraftRequest
from app.ai_assistant.service import AIAssistantService
from app.core.errors import ApiError


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
        return SimpleNamespace(account_id=business_id, name="Turon savdo", phone="+998901234567", direction="Savdo", activity_type="Do'kon", director="Bekzod", tax_id="123", address="Qumqo'rg'on")

    async def context(self, _session, _business_id, _start, _end):
        return {
            "today_summary": {"revenue": 500_000, "expenses": 120_000, "profit": 380_000},
            "debt_total": 75_000,
            "low_stock": [{"name": "Un", "qty": 2.0, "unit": "kg"}],
            "orders_by_status": {"new": 3},
            "top_products": [
                {"name": "Non", "qty": 12.0, "unit": "dona", "total": 48_000},
                {"name": "Sut", "qty": 5.0, "unit": "dona", "total": 40_000},
            ],
        }

    async def contractor(self, _session, business_id, contractor_id):
        assert business_id == 17
        assert contractor_id == 9
        return SimpleNamespace(
            id=9,
            name="Olma Savdo",
            director="Vali Karimov",
            phone="+998900000000",
            address="Toshkent",
            inn="309333444",
            account="20208000",
            bank="Milliy bank",
            mfo="00444",
        )

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
    assert "75 000 so'm" in result.answer
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
    service, _session = service_and_session()
    result = await service.document_draft(
        17,
        AIDocumentDraftRequest(
            prompt="Xizmat ko'rsatish shartnomasi 2 500 000 so'm",
            contractor_id=9,
        ),
    )
    assert result.doc_type == "Shartnoma"
    assert result.direction == "chiquvchi"
    assert result.source == "local"
    assert "XIZMAT KO'RSATISH SHARTNOMASI" in result.body
    assert "Olma Savdo" in result.body
    assert "2 500 000 so'm" in result.body
    assert result.note == "Bu AI draft. Saqlashdan oldin tekshiring."


@pytest.mark.asyncio
async def test_top_products_chip_returns_ranked_sales():
    service, _session = service_and_session()

    result = await service.chat(17, "Eng ko'p sotilgan")

    assert result.answer == (
        "🛒 Eng ko'p sotilganlar:\n"
        "• Non — 12 dona · 48 000 so'm\n"
        "• Sut — 5 dona · 40 000 so'm"
    )


@pytest.mark.parametrize(
    ("prompt", "expected_direction", "expected_type"),
    [
        ("mijozga invoice yoz", "chiquvchi", "Hisob-faktura"),
        ("tovar yetkazib berish", "chiquvchi", "Yuk xati"),
        ("ishonchnoma tayyorla", "chiquvchi", "Ishonchnoma"),
        ("solishtirma hujjat", "chiquvchi", "Solishtirma dalolatnoma"),
        ("yig'ilish bayonnomasi", "ichki", "Bayonnoma"),
        ("qarz uchun tilxat", "ichki", "Tilxat"),
        ("mijozga ogohlantirish", "ichki", "Xabarnoma"),
    ],
)
def test_document_type_detection_keeps_v1656_contract(
    prompt,
    expected_direction,
    expected_type,
):
    assert AIAssistantService._doc_type(prompt, "", "") == (
        expected_direction,
        expected_type,
    )


@pytest.mark.asyncio
async def test_document_title_keeps_v1656_ellipsis():
    service, _session = service_and_session()
    prompt = "a" * 71

    result = await service.document_draft(17, AIDocumentDraftRequest(prompt=prompt))

    assert result.title == "a" * 70 + "..."


@pytest.mark.asyncio
async def test_document_draft_keeps_legacy_business_override_fields():
    service, _session = service_and_session()

    result = await service.document_draft(
        17,
        AIDocumentDraftRequest(
            prompt="hisob faktura 900 000 so'm",
            firm_name="Yangi Firma",
            director="Ali Valiyev",
            inn="309111222",
        ),
    )

    assert "Yetkazib beruvchi: Yangi Firma" in result.body
    assert "STIR: 309111222" in result.body
    assert "Rahbar: ____________________ Ali Valiyev" in result.body


@pytest.mark.asyncio
async def test_document_draft_rejects_a_whitespace_only_legacy_prompt():
    service, _session = service_and_session()

    with pytest.raises(ApiError) as captured:
        await service.document_draft(17, AIDocumentDraftRequest(prompt="   "))

    assert captured.value.status_code == 400
    assert captured.value.message == "AI uchun hujjat topshirig'ini yozing."


class RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class ContextSession:
    def __init__(self):
        self.scalar_statements = []
        self._scalar_values = iter((500_000, 120_000, 75_000))
        self._row_values = iter((
            [("Un", 2, "kg")],
            [("new", 3)],
            [("Non", 12, "dona", 48_000)],
        ))

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return next(self._scalar_values)

    async def execute(self, _statement):
        return RowsResult(next(self._row_values))


@pytest.mark.asyncio
async def test_typed_context_excludes_debt_payments_and_supplies_top_products():
    session = ContextSession()
    repository = AIAssistantRepository()
    start = datetime(2026, 8, 10, tzinfo=UTC)
    end = datetime(2026, 8, 11, tzinfo=UTC)

    context = await repository.context(session, 17, start, end)

    assert "cash_receipts.source !=" in str(session.scalar_statements[0])
    assert context["top_products"] == [
        {"name": "Non", "qty": 12.0, "unit": "dona", "total": 48_000},
    ]
