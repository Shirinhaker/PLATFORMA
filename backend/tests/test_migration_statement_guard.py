"""Migratsiyadagi `op.execute()` bitta buyruqdan iborat bo'lishi.

asyncpg har `execute` ni tayyorlangan buyruq sifatida yuboradi va
bittadan ortiq buyruqni qabul qilmaydi:

    asyncpg.exceptions.PostgresSyntaxError:
    cannot insert multiple commands into a prepared statement

Bu xatoni `alembic upgrade --sql` ushlay olmaydi — u SQL matnini
yozadi, lekin bajarmaydi. Shu sababli faqat CI'dagi haqiqiy
PostgreSQL'da chiqadi. Test uni lokalda ushlaydi.
"""

import ast
import re
from pathlib import Path

import pytest


VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"
# Satr ichidagi `;` dan keyin yana SQL kelsa — ikkinchi buyruq.
TRAILING_SQL = re.compile(r";\s*\S")


def _execute_arguments(tree: ast.AST):
    """`op.execute(...)` ga berilgan matn argumentlari."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "execute":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(
                argument.value, str
            ):
                yield argument.lineno, argument.value


def _statement_sources(path: Path):
    """Bevosita va o'zgaruvchi orqali berilgan SQL matnlari."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    yield from _execute_arguments(tree)
    # `op.execute(SQL)` ko'rinishi uchun modul darajasidagi matnlar.
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        ]
        if any(name.endswith("SQL") for name in names):
            yield node.lineno, node.value.value


@pytest.mark.parametrize(
    "path",
    sorted(VERSIONS.glob("*.py")),
    ids=lambda path: path.stem,
)
def test_migration_executes_one_statement_at_a_time(path):
    problems = []
    for lineno, sql in _statement_sources(path):
        body = sql.strip()
        # Oxiridagi nuqta-vergul muammo emas.
        if body.endswith(";"):
            body = body[:-1]
        if TRAILING_SQL.search(body):
            problems.append(f"{path.name}:{lineno}")
    assert problems == [], (
        "Bitta `op.execute()` ichida bir nechta SQL buyrug'i bor — "
        "asyncpg buni rad etadi. Har buyruqni alohida `op.execute()` "
        "bilan yuboring: " + ", ".join(problems)
    )


def test_guard_detects_multiple_statements():
    """Qo'riqchining o'zi ishlayotganini tasdiqlaydi."""
    assert TRAILING_SQL.search("UPDATE a SET x = 1; UPDATE b SET y = 2")
    assert not TRAILING_SQL.search("UPDATE a SET x = 1")
    assert not TRAILING_SQL.search("UPDATE a SET x = 1;")
