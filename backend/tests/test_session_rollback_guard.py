"""`session.rollback()` dan keyin ORM obyektiga murojaat qilinmasligi.

Rollback sessiyadagi obyektlarni "eskirgan" deb belgilaydi. Shundan keyin
ularning maydoniga murojaat qilinsa, SQLAlchemy bazaga qayta so'rov
yubormoqchi bo'ladi va async kontekstda `MissingGreenlet` bilan yiqiladi.
SQLite'da bu sezilmaydi — xato faqat PostgreSQL'da, ya'ni productionda
chiqadi.

Shu sabab qoida bitta va qat'iy: **javob rollbackdan oldin yig'iladi**,
rollbackdan keyin faqat tayyor qiymat qaytariladi yoki xato ko'tariladi.

Bu xato loyihada besh marta takrorlangan (#63, #64, #70 va ikki modulda
mustaqil). Har safar faqat topilgan metod tuzatilib, test o'sha metod
nomiga bog'lab qo'yilgan edi — shuning uchun keyingi yangi metodda yana
takrorlangan. Bu test metodlarni sanab chiqmaydi: sinf ichidagi hamma
metodni avtomatik tekshiradi, shuning uchun yangi modul qo'shilganda ham
qamrovda qoladi.
"""

import ast
import importlib
import inspect
import textwrap

import pytest


# `session.rollback()` chaqiradigan barcha servislar.
ROLLBACK_SERVICES = (
    ("app.auth.service", "AuthService"),
    ("app.cash_register.service", "CashRegisterService"),
    ("app.catalog.service", "CatalogService"),
    ("app.debt_ledger.service", "DebtLedgerService"),
    ("app.dining.service", "DiningService"),
    ("app.education.service", "EducationEnrollmentService"),
    ("app.expenses.service", "ExpenseService"),
    ("app.follows.service", "FollowService"),
    ("app.inventory.service", "InventoryService"),
    ("app.listings.service", "ListingService"),
    ("app.orders.service", "OrderService"),
    ("app.payments.service", "PaymentService"),
    ("app.profiles.summary_service", "ProfileSummaryService"),
    ("app.public_discovery.service", "PublicDiscoveryService"),
    ("app.queues.service", "QueueService"),
    ("app.staff.service", "StaffService"),
)


def _statement_blocks(node: ast.AST):
    """Daraxtdagi barcha buyruq bloklari (`body`, `orelse`, `finalbody`)."""
    for inner in ast.walk(node):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(inner, field, None)
            if (
                isinstance(block, list)
                and block
                and isinstance(block[0], ast.stmt)
            ):
                yield block


def _is_rollback(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Await)
        and isinstance(statement.value.value, ast.Call)
        and isinstance(statement.value.value.func, ast.Attribute)
        and statement.value.value.func.attr == "rollback"
    )


def _violations(service_class: type) -> list[str]:
    """Rollbackdan keyin maydonga murojaat qilingan joylar."""
    source = textwrap.dedent(inspect.getsource(service_class))
    tree = ast.parse(source)
    first_line = inspect.getsourcelines(service_class)[1]
    found: list[str] = []

    for function in ast.walk(tree):
        if not isinstance(function, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for block in _statement_blocks(function):
            for index, statement in enumerate(block):
                if not _is_rollback(statement):
                    continue
                for later in block[index + 1:]:
                    for inner in ast.walk(later):
                        if not isinstance(inner, ast.Attribute):
                            continue
                        found.append(
                            f"{service_class.__name__}.{function.name} "
                            f"(fayl qatori ~{first_line + inner.lineno - 1}): "
                            f"rollbackdan keyin `.{inner.attr}` o'qilyapti"
                        )
    return found


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    ROLLBACK_SERVICES,
    ids=[class_name for _module, class_name in ROLLBACK_SERVICES],
)
def test_service_never_reads_orm_state_after_rollback(module_name, class_name):
    service_class = getattr(importlib.import_module(module_name), class_name)
    violations = _violations(service_class)
    assert violations == [], (
        "Rollbackdan keyin ma'lumot o'qilmoqda — productionda "
        "MissingGreenlet xatosi beradi. Javobni rollbackdan oldin "
        "`response` o'zgaruvchisiga yig'ing:\n  "
        + "\n  ".join(violations)
    )


def test_every_service_using_rollback_is_covered():
    """Ro'yxat kod bazasidan orqada qolmasligini tekshiradi."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    covered = {module for module, _class in ROLLBACK_SERVICES}
    missing: list[str] = []
    for path in sorted((backend / "app").rglob("*service*.py")):
        if "session.rollback()" not in path.read_text(encoding="utf-8"):
            continue
        module = ".".join(path.relative_to(backend).with_suffix("").parts)
        if module not in covered:
            missing.append(module)
    assert missing == [], (
        "Bu modullar `session.rollback()` ishlatadi, lekin qo'riqchi "
        "ro'yxatida yo'q — ROLLBACK_SERVICES ga qo'shing: "
        + ", ".join(missing)
    )


def test_guard_detects_a_known_bad_pattern():
    """Qo'riqchining o'zi ishlayotganini tasdiqlaydi.

    Tekshiruv mantiqi buzilib qolsa, yuqoridagi testlar hech narsani
    ushlamay turib ham yashil bo'lib qolardi.
    """

    class Broken:
        async def load(self, session, rows):
            await session.rollback()
            return [row.name for row in rows]

    problems = _violations(Broken)
    assert problems, "Qo'riqchi yomon naqshni ushlay olmadi."
    assert any(".name" in problem for problem in problems)
