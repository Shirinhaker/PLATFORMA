# Ko‘prik Phase 1 Scalable Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ishlayotgan Ko‘prik v1656 funksiyalarini o‘zgartirmasdan alohida frontend, modulli FastAPI backend, PostgreSQL, Redis, R2, worker va CI uchun sinovdan o‘tgan foundation yaratish.

**Architecture:** Eski v1656 root fayllari production fallback sifatida o‘z joyida qoladi. Yangi `backend/` holatsiz FastAPI app factory, PostgreSQL/Redis/R2 adapterlari va worker foundation’ini beradi; yangi `frontend/` React + TypeScript shell bo‘ladi, lekin production foydalanuvchiga bu bosqichda yoqilmaydi. Keyingi funksional migratsiya rejalari shu interfeyslarga tayanadi.

**Tech Stack:** Python 3.12, FastAPI 0.139.2, Uvicorn 0.51.0, SQLAlchemy 2.x async, asyncpg, Alembic, redis-py async, boto3 S3 client, PostgreSQL 17, Redis 7, React 19, TypeScript 5, Vite 7, Vitest, Testing Library, pytest, Docker Compose, GitHub Actions, Railway, Cloudflare R2.

## Global Constraints

- `static/index.html`, root `api.py`, `database.py`, `main.py` va faol v1656 endpoint xulqi Phase 1’da o‘zgarmaydi.
- Root `APP_BUILD` va frontend BUILD marker `v1656` bo‘lib qoladi.
- `static/index.html` boshlang‘ich qator soni `14091`; Phase 1 yakunida ham `14091` bo‘lishi shart.
- Mavjud SQLite yoki production upload fayllari o‘chirilmaydi va ko‘chirilmaydi.
- Telegram Mini App va `koprik.uz` eski frontend orqali ishlashda davom etadi.
- Yangi frontend production route’ga ulanmaydi; faqat lokal va staging foundation sifatida build qilinadi.
- Yangi backend endpointlari `/api/v1` ostida bo‘ladi; `/healthz` va `/readyz` bundan mustasno.
- Barcha yangi Python kodida type hint, yangi JavaScript kodida TypeScript strict mode ishlatiladi.
- Sirlar repositoryga yozilmaydi; faqat `.env.example`da xavfsiz namuna nomlari bo‘ladi.
- Har bir task yakunida: o‘zgargan fayllar, BUILD va `static/index.html` qator soni qayd qilinadi.
- Har bir task alohida test sikli va alohida commit bilan yakunlanadi.

## Phase roadmap

Ushbu hujjat faqat **Phase 1 — Scalable Foundation**ni bajaradi. Keyingi
mustaqil rejalar quyidagi tartibda yoziladi:

1. PostgreSQL schema va SQLite migratsiya harness’i.
2. Identity va profiles.
3. Discovery, qidiruv, xarita va catalog.
4. Advertising, subscriptions va payments.
5. Commerce, order chat va notifications.
6. Moderation va admin.
7. React ekran migratsiyasi.
8. Production rehearsal, 10 000-user load test va cutover.

Phase 1 foydalanuvchi funksiyasini almashtirmaydi; keyingi rejalar ishlatadigan
aniq, testlangan platforma interfeyslarini yaratadi.

## File map

```text
backend/
  pyproject.toml
  Dockerfile
  alembic.ini
  app/
    __init__.py
    main.py
    core/
      config.py
      errors.py
      logging.py
      middleware.py
    db/
      base.py
      session.py
    cache/
      client.py
      rate_limit.py
    media/
      router.py
      storage.py
    outbox/
      model.py
      repository.py
      worker.py
    platform/
      router.py
  migrations/
    env.py
    script.py.mako
    versions/
      0001_foundation.py
  tests/
    conftest.py
    test_app.py
    test_database.py
    test_rate_limit.py
    test_media_storage.py
    test_errors.py
    test_outbox.py
frontend/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  src/
    main.tsx
    app/App.tsx
    api/client.ts
    auth/adapter.ts
    test/setup.ts
    app/App.test.tsx
    api/client.test.ts
infra/
  railway/
    api.railpack.json
    worker.railpack.json
compose.yaml
.env.example
.github/workflows/phase1-ci.yml
scripts/export_legacy_inventory.py
scripts/verify_phase1.py
tests/test_legacy_inventory_contract.py
docs/architecture/legacy-v1656-inventory.json
```

---

### Task 1: Freeze the v1656 legacy contract

**Files:**
- Create: `.gitignore`
- Create: `scripts/export_legacy_inventory.py`
- Create: `tests/test_legacy_inventory_contract.py`
- Create: `docs/architecture/legacy-v1656-inventory.json`
- Modify: none of the v1656 runtime files

**Interfaces:**
- Consumes: current root source tree and Python AST.
- Produces: `collect_inventory(root: pathlib.Path) -> dict[str, object]` and a committed v1656 inventory snapshot.

- [ ] **Step 0: Create a local git baseline when the ZIP has no repository**

Run:

```bash
git rev-parse --is-inside-work-tree || git init
git add .
git commit -m "chore: import koprik mvp v1656 source"
```

Expected: the extracted ZIP becomes a local git repository with one clean
baseline commit. Do not configure or push a remote in this task.

- [ ] **Step 1: Write the failing inventory contract test**

```python
# tests/test_legacy_inventory_contract.py
import json
from pathlib import Path
import unittest

from scripts.export_legacy_inventory import collect_inventory


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/architecture/legacy-v1656-inventory.json"


class LegacyInventoryContractTests(unittest.TestCase):
    def test_runtime_contract_matches_committed_snapshot(self):
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(collect_inventory(ROOT), expected)

    def test_phase_one_does_not_change_legacy_frontend(self):
        html = (ROOT / "static/index.html").read_text(encoding="utf-8")
        self.assertEqual(len(html.splitlines()), 14091)
        self.assertIn("<!-- BUILD: v1656 -->", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run:

```bash
python -m unittest tests.test_legacy_inventory_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.export_legacy_inventory'`.

- [ ] **Step 3: Implement deterministic inventory export**

```python
# scripts/export_legacy_inventory.py
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROUTE_FILES = ("api.py", "admin_api.py", "payment_api.py", "main.py")
RUNTIME_FILES = (
    "api.py",
    "database.py",
    "main.py",
    "static/index.html",
    "admin/app.js",
    "admin/index.html",
    "admin/styles.css",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _routes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = decorator.func
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route = decorator.args[0].value
            if isinstance(route, str):
                result.append(f"{target.attr.upper()} {route}")
    return sorted(result)


def collect_inventory(root: Path) -> dict[str, object]:
    main_text = (root / "main.py").read_text(encoding="utf-8")
    build = re.search(r'APP_BUILD\s*=\s*"([^"]+)"', main_text)
    table_count = len(
        re.findall(
            r"CREATE TABLE IF NOT EXISTS",
            (root / "database.py").read_text(encoding="utf-8"),
        )
    )
    return {
        "build": build.group(1) if build else "",
        "frontend_line_count": len(
            (root / "static/index.html").read_text(encoding="utf-8").splitlines()
        ),
        "database_table_declarations": table_count,
        "routes": {
            name: _routes(root / name)
            for name in ROUTE_FILES
        },
        "sha256": {
            name: _sha256(root / name)
            for name in RUNTIME_FILES
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    json.dump(
        collect_inventory(root),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the committed snapshot**

Run:

```bash
python scripts/export_legacy_inventory.py > docs/architecture/legacy-v1656-inventory.json
```

Expected: valid JSON with `build: "v1656"`, `frontend_line_count: 14091`,
route lists and SHA-256 values.

- [ ] **Step 5: Add generated and secret paths to `.gitignore`**

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
node_modules/
frontend/dist/
backend/.coverage
backend/htmlcov/
.superpowers/
platforma.db
*.sqlite
*.sqlite3
uploads/
backups/
```

- [ ] **Step 6: Run the contract test**

Run:

```bash
python -m unittest tests.test_legacy_inventory_contract -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Record the task checkpoint**

Run:

```bash
git add .gitignore scripts/export_legacy_inventory.py tests/test_legacy_inventory_contract.py docs/architecture/legacy-v1656-inventory.json
git commit -m "test: freeze koprik v1656 legacy contract"
```

Checkpoint report:

```text
O‘zgargan fayllar: .gitignore, scripts/export_legacy_inventory.py,
tests/test_legacy_inventory_contract.py,
docs/architecture/legacy-v1656-inventory.json
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 2: Create the standalone FastAPI application shell

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/platform/router.py`
- Create: `backend/tests/test_app.py`

**Interfaces:**
- Consumes: environment variables with prefix `KOPRIK_`.
- Produces: `Settings`, `get_settings()`, `create_app(settings: Settings | None = None) -> FastAPI`, `/healthz`, `/api/v1/build`.

- [ ] **Step 1: Write failing app-factory tests**

```python
# backend/tests/test_app.py
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_healthz_is_process_only():
    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "koprik-api",
        "environment": "test",
    }


def test_v1_build_identifies_foundation_without_changing_legacy_build():
    app = create_app(Settings(environment="test"))
    response = TestClient(app).get("/api/v1/build")
    assert response.status_code == 200
    assert response.json() == {
        "api_version": "v1",
        "foundation": "phase1",
        "legacy_build": "v1656",
    }
```

- [ ] **Step 2: Run the tests and verify import failure**

Run:

```bash
cd backend
python -m pytest tests/test_app.py -v
```

Expected: collection FAIL because `app.core.config` does not exist.

- [ ] **Step 3: Add the backend package configuration**

```toml
# backend/pyproject.toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "koprik-backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi==0.139.2",
  "uvicorn[standard]==0.51.0",
  "httpx==0.28.1",
  "pydantic-settings>=2.7,<3",
  "sqlalchemy[asyncio]>=2.0,<3",
  "asyncpg>=0.30,<1",
  "alembic>=1.14,<2",
  "redis>=5,<8",
  "boto3>=1.35,<2",
  "python-json-logger>=3,<4",
]

[project.optional-dependencies]
test = [
  "pytest>=8,<10",
  "pytest-asyncio>=0.25,<2",
  "fakeredis>=2.27,<3",
]

[tool.pytest.ini_options]
addopts = "-ra"
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 4: Implement settings**

```python
# backend/app/core/config.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KOPRIK_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "koprik-api"
    environment: str = "development"
    legacy_build: str = "v1656"
    database_url: str = "postgresql+asyncpg://koprik:koprik@localhost:5432/koprik"
    redis_url: str = "redis://localhost:6379/0"
    r2_endpoint_url: str = "https://example.r2.cloudflarestorage.com"
    r2_bucket: str = "koprik-development"
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Implement the platform router and app factory**

```python
# backend/app/platform/router.py
from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@router.get("/api/v1/build")
async def build(request: Request) -> dict[str, str]:
    return {
        "api_version": "v1",
        "foundation": "phase1",
        "legacy_build": request.app.state.settings.legacy_build,
    }
```

```python
# backend/app/main.py
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.platform.router import router as platform_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="Ko‘prik API", version="1.0.0")
    app.state.settings = resolved
    app.include_router(platform_router)
    return app


app = create_app()
```

```python
# backend/app/__init__.py
"""Ko‘prikning yangi modulli backend paketi."""
```

- [ ] **Step 6: Install and run tests**

Run:

```bash
cd backend
python -m pip install -e ".[test]"
python -m pytest tests/test_app.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Run legacy freeze test**

Run:

```bash
cd ..
python -m unittest tests.test_legacy_inventory_contract -v
```

Expected: 2 tests PASS; legacy hashes unchanged.

- [ ] **Step 8: Commit the backend shell**

```bash
git add backend/pyproject.toml backend/app backend/tests/test_app.py
git commit -m "feat: add standalone koprik api shell"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/pyproject.toml, backend/app/**,
backend/tests/test_app.py
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 3: Add PostgreSQL pooling, migrations, and readiness

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_foundation.py`
- Create: `backend/tests/test_database.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/platform/router.py`

**Interfaces:**
- Consumes: `Settings.database_url`.
- Produces: `Database`, `Database.start()`, `Database.stop()`, `Database.ready() -> bool`, `Database.session()`, foundation tables `platform_outbox` and `idempotency_keys`.

- [ ] **Step 1: Write failing database lifecycle tests**

```python
# backend/tests/test_database.py
import os

import pytest
from sqlalchemy import text

from app.db.session import Database


DATABASE_URL = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_database_pool_and_readiness():
    database = Database(DATABASE_URL, pool_size=5, max_overflow=5)
    await database.start()
    assert await database.ready() is True
    async with database.session() as session:
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    await database.stop()
```

- [ ] **Step 2: Run the test and verify missing module failure**

Run:

```bash
cd backend
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m pytest tests/test_database.py -v
```

Expected: collection FAIL because `app.db.session` does not exist.

- [ ] **Step 3: Implement the SQLAlchemy base and database wrapper**

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# backend/app/db/session.py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 20,
        max_overflow: int = 20,
    ) -> None:
        self.url = url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None

    async def start(self) -> None:
        self.engine = create_async_engine(
            self.url,
            pool_pre_ping=True,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=10,
        )
        self._sessions = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def stop(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self._sessions = None

    async def ready(self) -> bool:
        if self.engine is None:
            return False
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessions is None:
            raise RuntimeError("Database.start() chaqirilmagan.")
        async with self._sessions() as session:
            yield session
```

- [ ] **Step 4: Add the foundation migration**

Generate Alembic’s standard async scaffold first:

```bash
cd backend
python -m alembic init -t async migrations
```

Set `backend/alembic.ini` to:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Replace `backend/migrations/env.py` with:

```python
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

Keep the generated async `script.py.mako` unchanged.

```python
# backend/migrations/versions/0001_foundation.py
from alembic import op
import sqlalchemy as sa


revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(length=120)),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_platform_outbox_due",
        "platform_outbox",
        ["status", "available_at", "id"],
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("scope", sa.String(length=80), primary_key=True),
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_idempotency_expiry",
        "idempotency_keys",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("platform_outbox")
```

- [ ] **Step 5: Wire database lifecycle into the app**

Update `create_app()` to use an async lifespan:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(resolved.database_url)
        await database.start()
        app.state.database = database
        try:
            yield
        finally:
            await database.stop()

    app = FastAPI(
        title="Ko‘prik API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.include_router(platform_router)
    return app
```

Add readiness to `backend/app/platform/router.py`:

```python
from fastapi.responses import JSONResponse


@router.get("/readyz")
async def readyz(request: Request):
    database_ready = await request.app.state.database.ready()
    payload = {"status": "ready" if database_ready else "not_ready",
               "database": database_ready}
    return JSONResponse(payload, status_code=200 if database_ready else 503)
```

- [ ] **Step 6: Apply migration and run tests**

Run:

```bash
cd backend
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic upgrade head
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m pytest tests/test_database.py tests/test_app.py -v
```

Expected: migrations succeed; database and app tests PASS.

- [ ] **Step 7: Commit database foundation**

```bash
git add backend/alembic.ini backend/app/db backend/migrations backend/app/main.py backend/app/platform/router.py backend/tests/test_database.py
git commit -m "feat: add postgres foundation and readiness"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/alembic.ini, backend/app/db/**,
backend/migrations/**, backend/app/main.py,
backend/app/platform/router.py, backend/tests/test_database.py
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 4: Add Redis lifecycle and atomic distributed rate limiting

**Files:**
- Create: `backend/app/cache/client.py`
- Create: `backend/app/cache/rate_limit.py`
- Create: `backend/tests/test_rate_limit.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/platform/router.py`

**Interfaces:**
- Consumes: `Settings.redis_url`.
- Produces: `RedisClient.start()`, `RedisClient.stop()`, `RedisClient.ready()`, `consume_rate_limit(redis, key, limit, window_seconds) -> RateLimitResult`.

- [ ] **Step 1: Write failing rate-limit tests**

```python
# backend/tests/test_rate_limit.py
import fakeredis.aioredis

from app.cache.rate_limit import consume_rate_limit


async def test_rate_limit_is_shared_and_atomic():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first = await consume_rate_limit(redis, "search:user:42", 2, 60)
    second = await consume_rate_limit(redis, "search:user:42", 2, 60)
    third = await consume_rate_limit(redis, "search:user:42", 2, 60)

    assert (first.allowed, first.remaining) == (True, 1)
    assert (second.allowed, second.remaining) == (True, 0)
    assert (third.allowed, third.remaining) == (False, 0)
    assert third.retry_after_seconds >= 1
```

- [ ] **Step 2: Run and verify missing module failure**

Run:

```bash
cd backend
python -m pytest tests/test_rate_limit.py -v
```

Expected: collection FAIL because `app.cache.rate_limit` does not exist.

- [ ] **Step 3: Implement the Redis client**

```python
# backend/app/cache/client.py
from redis.asyncio import Redis


class RedisClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.client: Redis | None = None

    async def start(self) -> None:
        self.client = Redis.from_url(self.url, decode_responses=True)

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.client = None

    async def ready(self) -> bool:
        if self.client is None:
            return False
        try:
            return bool(await self.client.ping())
        except Exception:
            return False
```

- [ ] **Step 4: Implement the atomic Lua rate limiter**

```python
# backend/app/cache/rate_limit.py
from dataclasses import dataclass
import time

from redis.asyncio import Redis


SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


async def consume_rate_limit(
    redis: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    bucket = int(time.time()) // window_seconds
    count, ttl = await redis.eval(
        SCRIPT,
        1,
        f"rate:{key}:{bucket}",
        window_seconds,
    )
    count = int(count)
    ttl = max(1, int(ttl))
    return RateLimitResult(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=ttl,
    )
```

- [ ] **Step 5: Add Redis to lifespan and readiness**

Update the lifespan body to start Redis after PostgreSQL and close it before
PostgreSQL:

```python
redis_client = RedisClient(resolved.redis_url)
await database.start()
await redis_client.start()
app.state.database = database
app.state.redis = redis_client
try:
    yield
finally:
    await redis_client.stop()
    await database.stop()
```

Extend `/readyz` to:

```python
database_ready = await request.app.state.database.ready()
redis_ready = await request.app.state.redis.ready()
ready = database_ready and redis_ready
payload = {
    "status": "ready" if ready else "not_ready",
    "database": database_ready,
    "redis": redis_ready,
}
return JSONResponse(payload, status_code=200 if ready else 503)
```

Return 503 when either dependency is false.

- [ ] **Step 6: Run tests**

Run:

```bash
cd backend
python -m pytest tests/test_rate_limit.py tests/test_app.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit Redis foundation**

```bash
git add backend/app/cache backend/app/main.py backend/app/platform/router.py backend/tests/test_rate_limit.py
git commit -m "feat: add redis lifecycle and shared rate limits"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/app/cache/**, backend/app/main.py,
backend/app/platform/router.py, backend/tests/test_rate_limit.py
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 5: Add secure R2 direct-upload foundation

**Files:**
- Create: `backend/app/media/storage.py`
- Create: `backend/app/media/router.py`
- Create: `backend/tests/test_media_storage.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: R2 settings and authenticated actor information supplied by future identity middleware.
- Produces: `R2Storage.create_upload_grant(*, actor_id: int, filename: str, content_type: str, size_bytes: int) -> UploadGrant` and `POST /api/v1/media/upload-grants`.

- [ ] **Step 1: Write failing storage tests**

```python
# backend/tests/test_media_storage.py
import pytest

from app.media.storage import R2Storage, UploadRejected


def test_upload_grant_uses_private_actor_prefix(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    grant = storage.create_upload_grant(
        actor_id=42,
        filename="logo.png",
        content_type="image/png",
        size_bytes=1024,
    )
    assert grant.object_key.startswith("private/uploads/42/")
    assert grant.object_key.endswith(".png")
    assert grant.method == "PUT"
    assert grant.headers == {"Content-Type": "image/png"}


def test_executable_upload_is_rejected(s3_client):
    storage = R2Storage(s3_client, bucket="koprik-test")
    with pytest.raises(UploadRejected, match="Fayl turi ruxsat etilmagan"):
        storage.create_upload_grant(
            actor_id=42,
            filename="bad.exe",
            content_type="application/octet-stream",
            size_bytes=1024,
        )
```

Add an `s3_client` fixture in `backend/tests/conftest.py` using:

```python
import boto3
import pytest


@pytest.fixture
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="auto",
    )
```

- [ ] **Step 2: Run and verify missing module failure**

Run:

```bash
cd backend
python -m pytest tests/test_media_storage.py -v
```

Expected: collection FAIL because `app.media.storage` does not exist.

- [ ] **Step 3: Implement validated presigned upload grants**

```python
# backend/app/media/storage.py
from dataclasses import dataclass
from pathlib import Path
import secrets


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "application/pdf": ".pdf",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadGrant:
    object_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class R2Storage:
    def __init__(self, client, *, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def create_upload_grant(
        self,
        *,
        actor_id: int,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadGrant:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UploadRejected("Fayl turi ruxsat etilmagan.")
        if size_bytes < 1 or size_bytes > MAX_UPLOAD_BYTES:
            raise UploadRejected("Fayl hajmi ruxsat etilgan chegaradan tashqarida.")
        suffix = ALLOWED_CONTENT_TYPES[content_type]
        object_key = (
            f"private/uploads/{actor_id}/"
            f"{secrets.token_hex(16)}{suffix}"
        )
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )
        return UploadGrant(
            object_key=object_key,
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=900,
        )
```

- [ ] **Step 4: Add a foundation-only upload route**

```python
# backend/app/media/router.py
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.media.storage import UploadRejected


router = APIRouter(prefix="/api/v1/media", tags=["media"])


class UploadGrantRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)


@router.post("/upload-grants")
async def create_upload_grant(
    body: UploadGrantRequest,
    request: Request,
    x_foundation_actor_id: int | None = Header(default=None),
):
    settings = request.app.state.settings
    if settings.environment not in {"test", "staging"}:
        raise HTTPException(
            status_code=503,
            detail="Media autentifikatsiyasi hali production uchun yoqilmagan.",
        )
    if x_foundation_actor_id is None or x_foundation_actor_id < 1:
        raise HTTPException(
            status_code=401,
            detail="Foundation actor identifikatori talab qilinadi.",
        )
    try:
        grant = request.app.state.r2.create_upload_grant(
            actor_id=x_foundation_actor_id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return grant
```

The `X-Foundation-Actor-Id` header is enabled only in `test` and `staging`.
Production always returns 503 in Phase 1.

- [ ] **Step 5: Build R2 client during app startup**

Add this helper to `backend/app/media/storage.py`:

```python
import boto3

from app.core.config import Settings


def build_r2_storage(settings: Settings) -> R2Storage:
    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    return R2Storage(client, bucket=settings.r2_bucket)
```

In `create_app()`, set `app.state.r2 = build_r2_storage(resolved)` before
including `media_router`. Do not contact R2 during `/healthz`; `/readyz` adds
`r2_configured`, which is true in `development` and `test`, and in other
environments is true only when bucket, access key and secret are non-empty.

- [ ] **Step 6: Run tests**

Run:

```bash
cd backend
python -m pytest tests/test_media_storage.py tests/test_app.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit media foundation**

```bash
git add backend/app/media backend/app/main.py backend/tests/conftest.py backend/tests/test_media_storage.py
git commit -m "feat: add secure r2 upload grants"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/app/media/**, backend/app/main.py,
backend/tests/conftest.py, backend/tests/test_media_storage.py
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 6: Standardize request IDs, errors, and structured logs

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/core/middleware.py`
- Create: `backend/tests/test_errors.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: every HTTP request and uncaught application exception.
- Produces: `ApiError`, `RequestIdMiddleware`, JSON error contract `{code, message, request_id}`, `X-Request-Id` response header.

- [ ] **Step 1: Write failing error-contract tests**

```python
# backend/tests/test_errors.py
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.core.config import Settings
from app.main import create_app


def test_api_error_has_safe_uzbek_message_and_request_id():
    app = create_app(Settings(environment="test"))
    router = APIRouter()

    @router.get("/explode")
    async def explode():
        raise ApiError(409, "duplicate_request", "Bu so‘rov oldin bajarilgan.")

    app.include_router(router)
    response = TestClient(app).get(
        "/explode",
        headers={"X-Request-Id": "req-test-123"},
    )
    assert response.status_code == 409
    assert response.headers["X-Request-Id"] == "req-test-123"
    assert response.json() == {
        "code": "duplicate_request",
        "message": "Bu so‘rov oldin bajarilgan.",
        "request_id": "req-test-123",
    }
```

- [ ] **Step 2: Run and verify missing module failure**

Run:

```bash
cd backend
python -m pytest tests/test_errors.py -v
```

Expected: collection FAIL because `app.core.errors` does not exist.

- [ ] **Step 3: Implement error and middleware types**

```python
# backend/app/core/errors.py
class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
```

```python
# backend/app/core/middleware.py
from contextvars import ContextVar
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="",
)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("X-Request-Id", "")
        request_id = (
            supplied
            if SAFE_REQUEST_ID.fullmatch(supplied)
            else str(uuid.uuid4())
        )
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response
```

- [ ] **Step 4: Register handlers and JSON logging**

In `create_app()`:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import ApiError
from app.core.middleware import RequestIdMiddleware, request_id_context


app.add_middleware(RequestIdMiddleware)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": request_id_context.get(),
        },
    )
```

Implement structured logging:

```python
# backend/app/core/logging.py
from __future__ import annotations

import logging
from datetime import UTC, datetime

from pythonjsonlogger.json import JsonFormatter

from app.core.middleware import request_id_context


class KoprikLogFilter(logging.Filter):
    def __init__(self, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.timestamp = datetime.now(UTC).isoformat()
        record.service = self.service
        record.environment = self.environment
        record.request_id = request_id_context.get()
        return True


def configure_logging(service: str, environment: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(KoprikLogFilter(service, environment))
    handler.setFormatter(
        JsonFormatter(
            "%(timestamp)s %(levelname)s %(service)s %(environment)s "
            "%(request_id)s %(name)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

Call `configure_logging(resolved.service_name, resolved.environment)` once in
`create_app()`. Endpoint log calls may contain actor numeric IDs, route names
and status codes; they must not include authorization, cookie, Telegram init
data, password, receipt URL or R2 signed URL values.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
python -m pytest tests/test_errors.py tests/test_app.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit observability foundation**

```bash
git add backend/app/core/errors.py backend/app/core/logging.py backend/app/core/middleware.py backend/app/main.py backend/tests/test_errors.py
git commit -m "feat: standardize api errors and request tracing"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/app/core/errors.py,
backend/app/core/logging.py, backend/app/core/middleware.py,
backend/app/main.py, backend/tests/test_errors.py
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 7: Add a durable outbox worker foundation

**Files:**
- Create: `backend/app/outbox/model.py`
- Create: `backend/app/outbox/repository.py`
- Create: `backend/app/outbox/worker.py`
- Create: `backend/tests/test_outbox.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Consumes: `platform_outbox` created by migration `0001_foundation`.
- Produces: `enqueue_event(session, topic, payload)`, `claim_events(session, worker_id, *, limit)`, `mark_processed(session, event_id)`, `mark_failed(session, event_id, error)`, `run_worker(settings: Settings, *, once: bool = False)`.

- [ ] **Step 1: Write failing outbox integration test**

```python
# backend/tests/test_outbox.py
import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.outbox.repository import (
    claim_events,
    enqueue_event,
    mark_processed,
)


DATABASE_URL = os.environ.get("KOPRIK_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not DATABASE_URL, reason="KOPRIK_TEST_DATABASE_URL required")
async def test_outbox_claim_is_durable_and_exclusive():
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as session:
        event_id = await enqueue_event(
            session,
            "notification.telegram",
            {"user_id": 42, "text": "Sinov"},
        )
    async with sessions.begin() as session:
        claimed = await claim_events(session, "worker-a", limit=10)
        assert [event.id for event in claimed] == [event_id]
        await mark_processed(session, event_id)
    async with sessions.begin() as session:
        assert await claim_events(session, "worker-b", limit=10) == []
    await engine.dispose()
```

- [ ] **Step 2: Run and verify missing module failure**

Run:

```bash
cd backend
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m pytest tests/test_outbox.py -v
```

Expected: collection FAIL because `app.outbox.repository` does not exist.

- [ ] **Step 3: Map the outbox table**

```python
# backend/app/outbox/model.py
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutboxEvent(Base):
    __tablename__ = "platform_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    last_error: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Implement transaction-safe repository functions**

Use UTC timestamps and PostgreSQL `FOR UPDATE SKIP LOCKED`:

```python
# backend/app/outbox/repository.py
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.outbox.model import OutboxEvent


async def enqueue_event(
    session: AsyncSession,
    topic: str,
    payload: dict[str, Any],
) -> int:
    now = datetime.now(UTC)
    event = OutboxEvent(
        topic=topic,
        payload=payload,
        status="pending",
        attempts=0,
        available_at=now,
        last_error="",
        created_at=now,
    )
    session.add(event)
    await session.flush()
    return event.id


async def claim_events(
    session: AsyncSession,
    worker_id: str,
    *,
    limit: int,
) -> list[OutboxEvent]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(OutboxEvent)
        .where(
            OutboxEvent.status.in_(("pending", "retry")),
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = list(result.scalars())
    for event in events:
        event.status = "processing"
        event.locked_at = now
        event.locked_by = worker_id
        event.attempts += 1
    await session.flush()
    return events


async def mark_processed(session: AsyncSession, event_id: int) -> None:
    event = await session.get(OutboxEvent, event_id, with_for_update=True)
    if event is None:
        raise LookupError(f"Outbox event topilmadi: {event_id}")
    event.status = "processed"
    event.processed_at = datetime.now(UTC)
    event.locked_at = None
    event.locked_by = None


async def mark_failed(
    session: AsyncSession,
    event_id: int,
    error: str,
) -> None:
    event = await session.get(OutboxEvent, event_id, with_for_update=True)
    if event is None:
        raise LookupError(f"Outbox event topilmadi: {event_id}")
    event.status = "failed" if event.attempts >= 5 else "retry"
    event.available_at = datetime.now(UTC) + timedelta(
        seconds=min(3600, 30 * (2 ** max(0, event.attempts - 1)))
    )
    event.last_error = error[:1000]
    event.locked_at = None
    event.locked_by = None
```

- [ ] **Step 5: Implement the worker entry point**

```python
# backend/app/outbox/worker.py
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import os
import signal
import socket
from typing import Any

from app.core.config import Settings
from app.db.session import Database
from app.outbox.repository import (
    claim_events,
    mark_failed,
    mark_processed,
)


Handler = Callable[[dict[str, Any]], Awaitable[None]]


async def foundation_echo(payload: dict[str, Any]) -> None:
    if payload.get("message") != "phase1":
        raise ValueError("Foundation echo payload noto‘g‘ri.")


HANDLERS: dict[str, Handler] = {
    "foundation.echo": foundation_echo,
}


async def process_batch(
    database: Database,
    worker_id: str,
    *,
    limit: int = 50,
) -> int:
    async with database.session() as session:
        async with session.begin():
            events = await claim_events(session, worker_id, limit=limit)
    for event in events:
        handler = HANDLERS.get(event.topic)
        if handler is None:
            async with database.session() as session:
                async with session.begin():
                    await mark_failed(
                        session,
                        event.id,
                        f"Ro‘yxatdan o‘tmagan topic: {event.topic}",
                    )
            continue
        try:
            await handler(event.payload)
        except Exception as exc:
            async with database.session() as session:
                async with session.begin():
                    await mark_failed(session, event.id, str(exc))
        else:
            async with database.session() as session:
                async with session.begin():
                    await mark_processed(session, event.id)
    return len(events)


async def run_worker(settings: Settings, *, once: bool = False) -> None:
    database = Database(settings.database_url)
    await database.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    try:
        while not stop.is_set():
            count = await process_batch(database, worker_id)
            if once:
                return
            if count == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    continue
    finally:
        await database.stop()


def main() -> None:
    settings = Settings()
    once = os.environ.get("KOPRIK_WORKER_ONCE") == "1"
    asyncio.run(run_worker(settings, once=once))


if __name__ == "__main__":
    main()
```

Add this exact entry point:

```toml
[project.scripts]
koprik-worker = "app.outbox.worker:main"
```

- [ ] **Step 6: Run migration and outbox tests**

Run:

```bash
cd backend
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic upgrade head
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m pytest tests/test_outbox.py -v
```

Expected: outbox integration test PASS.

- [ ] **Step 7: Commit worker foundation**

```bash
git add backend/app/outbox backend/tests/test_outbox.py backend/pyproject.toml
git commit -m "feat: add durable outbox worker foundation"
```

Checkpoint:

```text
O‘zgargan fayllar: backend/app/outbox/**,
backend/tests/test_outbox.py, backend/pyproject.toml
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 8: Create the separate React frontend shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/adapter.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/app/App.test.tsx`
- Create: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: `VITE_API_BASE_URL`, browser location, Telegram WebApp init data.
- Produces: `ApiClient`, `resolveAuthContext()`, production-buildable React shell that calls `/api/v1/build`.

- [ ] **Step 1: Write failing frontend tests**

```tsx
// frontend/src/app/App.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("shows the foundation build without replacing v1656 production UI", async () => {
    const api = {
      getBuild: vi.fn().mockResolvedValue({
        api_version: "v1",
        foundation: "phase1",
        legacy_build: "v1656",
      } as const),
    };
    render(<App api={api} />);
    expect(
      await screen.findByText("Ko‘prik yangi platforma foundation’i tayyor"),
    ).toBeInTheDocument();
    expect(screen.getByText("Eski faol BUILD: v1656")).toBeInTheDocument();
  });
});
```

```ts
// frontend/src/api/client.test.ts
import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";


describe("ApiClient", () => {
  it("uses the versioned API and exactly one auth mechanism", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          api_version: "v1",
          foundation: "phase1",
          legacy_build: "v1656",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = new ApiClient("https://api.koprik.uz", fetcher, {
      kind: "telegram",
      initData: "signed-init-data",
    });
    await client.getBuild();
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.koprik.uz/api/v1/build",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          "X-Telegram-Init-Data": "signed-init-data",
        }),
      }),
    );
  });
});
```

- [ ] **Step 2: Create package and TypeScript configuration**

```json
{
  "name": "koprik-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^19.1.0",
    "react-dom": "^19.1.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.3.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "jsdom": "^26.1.0",
    "typescript": "^5.8.0",
    "vite": "^7.0.0",
    "vitest": "^3.2.0"
  }
}
```

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "noUncheckedIndexedAccess": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

```ts
// frontend/vite.config.ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

- [ ] **Step 3: Run tests and verify missing implementation failures**

Run:

```bash
cd frontend
npm install
npm test
```

Expected: tests FAIL because `App`, `ApiClient` and auth adapter do not exist.

- [ ] **Step 4: Implement auth resolution**

```ts
// frontend/src/auth/adapter.ts
export type AuthContext =
  | { kind: "telegram"; initData: string }
  | { kind: "web" };

type TelegramWindow = Window & {
  Telegram?: { WebApp?: { initData?: string } };
};

export function resolveAuthContext(
  source: TelegramWindow = window as TelegramWindow,
): AuthContext {
  const initData = source.Telegram?.WebApp?.initData?.trim() ?? "";
  return initData
    ? { kind: "telegram", initData }
    : { kind: "web" };
}
```

- [ ] **Step 5: Implement the versioned API client**

```ts
// frontend/src/api/client.ts
import type { AuthContext } from "../auth/adapter";

export type BuildInfo = {
  api_version: "v1";
  foundation: "phase1";
  legacy_build: "v1656";
};

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch,
    private readonly auth: AuthContext,
  ) {}

  async getBuild(): Promise<BuildInfo> {
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (this.auth.kind === "telegram") {
      headers["X-Telegram-Init-Data"] = this.auth.initData;
    }
    const response = await this.fetcher(
      `${this.baseUrl}/api/v1/build`,
      { credentials: "include", headers },
    );
    if (!response.ok) {
      throw new Error(`API xatosi: ${response.status}`);
    }
    return response.json() as Promise<BuildInfo>;
  }
}
```

- [ ] **Step 6: Implement the shell**

```tsx
// frontend/src/app/App.tsx
import { useEffect, useState } from "react";

import type { ApiClient, BuildInfo } from "../api/client";


type BuildApi = Pick<ApiClient, "getBuild">;


export function App({ api }: { api: BuildApi }) {
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api.getBuild()
      .then((value) => {
        if (active) setBuild(value);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [api]);

  if (failed) {
    return <main>Yangi platforma foundation’iga ulanib bo‘lmadi.</main>;
  }
  if (build === null) {
    return <main>Yuklanmoqda…</main>;
  }
  return (
    <main>
      <h1>Ko‘prik yangi platforma foundation’i tayyor</h1>
      <p>Eski faol BUILD: {build.legacy_build}</p>
    </main>
  );
}
```

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiClient } from "./api/client";
import { App } from "./app/App";
import { resolveAuthContext } from "./auth/adapter";


const api = new ApiClient(
  import.meta.env.VITE_API_BASE_URL || window.location.origin,
  window.fetch.bind(window),
  resolveAuthContext(),
);
const root = document.getElementById("root");
if (root === null) {
  throw new Error("Frontend root elementi topilmadi.");
}
createRoot(root).render(
  <StrictMode>
    <App api={api} />
  </StrictMode>,
);
```

```ts
// frontend/src/test/setup.ts
import "@testing-library/jest-dom/vitest";
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="uz">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Ko‘prik</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Do not copy legacy UI or business logic into this shell.

- [ ] **Step 7: Run tests and production build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all tests PASS and `frontend/dist/index.html` exists.

- [ ] **Step 8: Verify legacy frontend is untouched**

Run:

```bash
cd ..
python -m unittest tests.test_legacy_inventory_contract -v
```

Expected: 2 tests PASS; `static/index.html` remains 14091 lines.

- [ ] **Step 9: Commit frontend shell**

```bash
git add frontend
git commit -m "feat: add standalone react frontend shell"
```

Checkpoint:

```text
O‘zgargan fayllar: frontend/**
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 9: Add local infrastructure and Railway deployment units

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `backend/Dockerfile`
- Create: `infra/railway/api.railpack.json`
- Create: `infra/railway/worker.railpack.json`
- Create: `scripts/verify_phase1.py`
- Create: `.github/workflows/phase1-ci.yml`

**Interfaces:**
- Consumes: backend/frontend commands and environment variables created in Tasks 2–8.
- Produces: reproducible local Postgres/Redis stack, API container, separate worker command, CI verification, Railway API/worker definitions.

- [ ] **Step 1: Write the phase verification script**

```python
# scripts/verify_phase1.py
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_legacy_inventory import collect_inventory


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    expected = json.loads(
        (ROOT / "docs/architecture/legacy-v1656-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    if collect_inventory(ROOT) != expected:
        raise SystemExit("Legacy v1656 contract o‘zgargan.")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    for smoke in (
        "tests/admin-ui-smoke.cjs",
        "tests/ad-upload-ui-smoke.cjs",
        "tests/district-offers-ui-smoke.cjs",
        "tests/story-ui-smoke.cjs",
        "tests/subscription-ui-smoke.cjs",
    ):
        run(["node", smoke])
    run([sys.executable, "-m", "pytest", "tests", "-v"], ROOT / "backend")
    run(["npm", "test"], ROOT / "frontend")
    run(["npm", "run", "build"], ROOT / "frontend")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add local Postgres and Redis services**

```yaml
# compose.yaml
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: koprik
      POSTGRES_PASSWORD: koprik
      POSTGRES_DB: koprik
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U koprik -d koprik"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - koprik_postgres:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - koprik_redis:/data

  api:
    build:
      context: ./backend
    environment:
      KOPRIK_ENVIRONMENT: development
      KOPRIK_DATABASE_URL: postgresql+asyncpg://koprik:koprik@postgres:5432/koprik
      KOPRIK_REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build:
      context: ./backend
    command: ["python", "-m", "app.outbox.worker"]
    environment:
      KOPRIK_ENVIRONMENT: development
      KOPRIK_DATABASE_URL: postgresql+asyncpg://koprik:koprik@postgres:5432/koprik
      KOPRIK_REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  koprik_postgres:
  koprik_redis:
```

- [ ] **Step 3: Add environment template**

```dotenv
KOPRIK_ENVIRONMENT=development
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik
KOPRIK_REDIS_URL=redis://localhost:6379/0
KOPRIK_R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
KOPRIK_R2_BUCKET=koprik-development
KOPRIK_R2_ACCESS_KEY_ID=
KOPRIK_R2_SECRET_ACCESS_KEY=
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 4: Add backend container**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN python -m pip install .

USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Add Railway service definitions**

`infra/railway/api.railpack.json`:

```json
{
  "$schema": "https://schema.railpack.com",
  "provider": "python",
  "deploy": {
    "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/readyz",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

`infra/railway/worker.railpack.json`:

```json
{
  "$schema": "https://schema.railpack.com",
  "provider": "python",
  "deploy": {
    "startCommand": "cd backend && python -m app.outbox.worker",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

The API and worker are separate Railway services using the same build source,
PostgreSQL, Redis and private network. API starts with one replica in staging;
replica scaling is enabled only after readiness and load smoke pass.

- [ ] **Step 6: Add CI**

```yaml
# .github/workflows/phase1-ci.yml
name: phase1-foundation

on:
  push:
  pull_request:

jobs:
  verify:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: koprik
          POSTGRES_PASSWORD: koprik
          POSTGRES_DB: koprik
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U koprik -d koprik"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 20
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 20
    env:
      KOPRIK_ENVIRONMENT: test
      KOPRIK_DATABASE_URL: postgresql+asyncpg://koprik:koprik@localhost:5432/koprik
      KOPRIK_TEST_DATABASE_URL: postgresql+asyncpg://koprik:koprik@localhost:5432/koprik
      KOPRIK_REDIS_URL: redis://localhost:6379/0
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install legacy dependencies
        run: python -m pip install -r requirements.txt
      - name: Install backend
        run: python -m pip install -e "./backend[test]"
      - name: Install frontend
        working-directory: frontend
        run: npm ci
      - name: Apply foundation migration
        working-directory: backend
        run: python -m alembic upgrade head
      - name: Verify Phase 1
        run: python scripts/verify_phase1.py
```

Commit `frontend/package-lock.json` created in Task 8 so CI can use `npm ci`.

- [ ] **Step 7: Run the complete local foundation verification**

Run:

```bash
docker compose up -d postgres redis
cd backend
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic upgrade head
cd ..
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
KOPRIK_REDIS_URL=redis://localhost:6379/0 \
python scripts/verify_phase1.py
```

Expected:

```text
Legacy inventory contract: PASS
Backend tests: PASS
Frontend tests: PASS
Frontend build: PASS
BUILD: v1656
static/index.html: 14091 qator
```

- [ ] **Step 8: Run API and readiness smoke**

Run API:

```bash
cd backend
KOPRIK_ENVIRONMENT=staging \
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
KOPRIK_REDIS_URL=redis://localhost:6379/0 \
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
curl --fail http://127.0.0.1:8000/api/v1/build
```

Expected: three HTTP 200 responses; build response includes
`legacy_build: "v1656"`.

- [ ] **Step 9: Commit infrastructure**

```bash
git add compose.yaml .env.example backend/Dockerfile infra/railway scripts/verify_phase1.py .github/workflows/phase1-ci.yml frontend/package-lock.json
git commit -m "ci: verify scalable foundation on postgres and redis"
```

Checkpoint:

```text
O‘zgargan fayllar: compose.yaml, .env.example, backend/Dockerfile,
infra/railway/**, scripts/verify_phase1.py,
.github/workflows/phase1-ci.yml, frontend/package-lock.json
BUILD: v1656
static/index.html: 14091 qator
```

---

### Task 10: Final Phase 1 acceptance and handoff

**Files:**
- Create: `docs/architecture/phase1-foundation-verification.md`
- Modify: none of the runtime files

**Interfaces:**
- Consumes: all Phase 1 test results and git history.
- Produces: auditable Phase 1 acceptance report and the exact prerequisites for the PostgreSQL schema/migration plan.

- [ ] **Step 1: Run all verification commands from a clean checkout**

Run:

```bash
docker compose up -d postgres redis
cd backend
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic upgrade head
cd ..
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
KOPRIK_REDIS_URL=redis://localhost:6379/0 \
python scripts/verify_phase1.py
git status --short
```

Expected: verification PASS and `git status --short` empty.

- [ ] **Step 2: Verify migration rollback**

Run:

```bash
cd backend
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic downgrade base
KOPRIK_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m alembic upgrade head
```

Expected: downgrade and re-upgrade both succeed.

- [ ] **Step 3: Verify separate API and worker processes**

Run:

```bash
docker compose up -d --build api worker
curl --fail http://127.0.0.1:8000/readyz
docker compose restart worker
curl --fail http://127.0.0.1:8000/readyz
docker compose ps --status running api worker
cd backend
KOPRIK_TEST_DATABASE_URL=postgresql+asyncpg://koprik:koprik@localhost:5432/koprik \
python -m pytest tests/test_outbox.py -v
```

Expected:

- `/readyz` is HTTP 200 before and after worker restart;
- `api` and `worker` are separate running containers;
- outbox exclusivity integration test PASS;
- the same event cannot be claimed after it reaches `processed`.

- [ ] **Step 4: Write the acceptance report**

Create `docs/architecture/phase1-foundation-verification.md` with:

```markdown
# Phase 1 Foundation Verification

- Legacy BUILD: v1656
- Legacy frontend line count: 14091
- Legacy inventory contract: PASS
- Backend unit/integration tests: PASS
- Frontend tests/build: PASS
- PostgreSQL migration up/down/up: PASS
- Redis distributed rate limit: PASS
- R2 presigned upload validation: PASS
- API and worker process isolation: PASS
- Production traffic switched: NO
- Legacy SQLite modified: NO
- Legacy uploads modified: NO

## Phase 2 prerequisites

- PostgreSQL and Redis staging service URLs are configured.
- R2 staging bucket and restricted API credentials are configured.
- v1656 inventory snapshot is committed.
- Phase 1 CI is green.
- SQLite schema mapping may start without changing production traffic.
```

- [ ] **Step 5: Run placeholder and contract scans**

Run:

```bash
rg -n "T[B]D|T[O]DO|F[I]XME|X[X]X" backend frontend infra scripts docs/architecture
python -m unittest tests.test_legacy_inventory_contract -v
```

Expected: `rg` prints no matches; contract tests PASS.

- [ ] **Step 6: Commit Phase 1 acceptance**

```bash
git add docs/architecture/phase1-foundation-verification.md
git commit -m "docs: accept koprik scalable foundation"
```

Final checkpoint:

```text
O‘zgargan fayllar: docs/architecture/phase1-foundation-verification.md
BUILD: v1656
static/index.html: 14091 qator
Production foydalanuvchi oqimi: o‘zgarmadi
Keyingi reja: PostgreSQL schema va SQLite migration harness
```
