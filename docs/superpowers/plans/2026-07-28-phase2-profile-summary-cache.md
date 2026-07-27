# Phase 2 Profile Summary Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /api/v1/me` endpointini Redis profil xulosasi cache’i va bir akkauntga tegishli parallel cache miss’larni birlashtirish orqali 1000 parallel so‘rovda 0 xato va `p95 < 500 ms` mezoniga olib kelish.

**Architecture:** Yangi `ProfileSummaryService` ixcham `MeRead` javobini akkaunt turi va ID bo‘yicha Redis’da 30 soniya saqlaydi. Cache miss paytida service o‘z SQLAlchemy sessiyasini ochadi va bir xil akkaunt uchun bir vaqtda kelgan so‘rovlarni bitta in-flight task orqali bitta PostgreSQL o‘qishiga birlashtiradi; muvaffaqiyatli profil yozuvlari tegishli cache kalitini o‘chiradi.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Redis asyncio/fakeredis, Pydantic v2, pytest, Railway

## Global Constraints

- Production `web`, `koprik.uz`, BUILD `v1656` va legacy `static/index.html` o‘zgarmaydi.
- Frontend dizayni, auth session cache kontrakti, Telegram oqimi, R2 fayllari, DB pool hajmi va Railway replica soni o‘zgarmaydi.
- Cache kaliti `profile:me:v1:{account_type}:{account_id}` formatida bo‘ladi.
- Cache qiymatida faqat `account_id`, `account_type`, `name` va `profile_complete` saqlanadi.
- `KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS` standart `30`, minimum `5`, maksimum `300` soniya bo‘ladi.
- Redis xatosi `/me` yoki profil saqlashni yiqitmaydi; PostgreSQL fallback va warning log ishlaydi.
- Profil cache’i faqat muvaffaqiyatli DB commit’dan keyin invalidatsiya qilinadi.
- Phase 2 gate: `/me` uchun 1000 parallel so‘rov, 0 xato, barcha javoblar HTTP 200 va `p95 < 500 ms`.
- Har kod o‘zgarishi test-first tartibida bajariladi.

---

### Task 1: Profil cache TTL konfiguratsiyasi

**Files:**

- Modify: `backend/tests/test_config.py:45-58`
- Modify: `backend/app/core/config.py:32-36`
- Modify: `.env.example:19-22`

**Interfaces:**

- Consumes: Pydantic `Settings` va `KOPRIK_` environment prefiksi.
- Produces: `Settings.profile_summary_cache_ttl_seconds: int`.

- [ ] **Step 1: Standart TTL va chegaralar uchun failing test yozish**

`backend/tests/test_config.py` ga quyidagi testlarni qo‘shing va staging
secret testi ichidagi mavjud assertlarga yangi standart qiymatni kiriting:

```python
def test_profile_summary_cache_ttl_defaults_to_thirty_seconds():
    settings = Settings(environment="test")

    assert settings.profile_summary_cache_ttl_seconds == 30


@pytest.mark.parametrize("value", [4, 301])
def test_profile_summary_cache_ttl_rejects_values_outside_bounds(value):
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            profile_summary_cache_ttl_seconds=value,
        )
```

`test_staging_accepts_complete_auth_and_telegram_secrets` oxiriga:

```python
assert settings.profile_summary_cache_ttl_seconds == 30
```

- [ ] **Step 2: RED holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_config.py -v
```

Expected: yangi testlar `AttributeError` yoki extra fieldning e’tiborsiz
qolishi sabab `FAIL`.

- [ ] **Step 3: Minimal Settings maydonini qo‘shish**

`session_cache_ttl_seconds` dan keyin:

```python
profile_summary_cache_ttl_seconds: int = Field(
    default=30,
    ge=5,
    le=300,
)
```

`.env.example` ichida session cache TTL’dan keyin:

```env
KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS=30
```

- [ ] **Step 4: GREEN holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_config.py -v
```

Expected: barcha config testlari `PASS`.

- [ ] **Step 5: Commit**

```bash
git add .env.example backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat: configure profile summary cache ttl"
```

---

### Task 2: Profil xulosasini cache qilish va parallel miss’larni birlashtirish

**Files:**

- Create: `backend/app/profiles/summary_service.py`
- Create: `backend/tests/test_profile_summary_service.py`

**Interfaces:**

- Consumes: `SessionFactory`, Redis yoki `RedisClient`, `Settings`,
  `AccountType`, `get_user_profile`, `get_business_profile`.
- Produces:
  `ProfileSummaryService.resolve(account_type: AccountType, account_id: int) -> MeRead`.

- [ ] **Step 1: Test yordamchilarini va cache-hit failing testini yozish**

`backend/tests/test_profile_summary_service.py` ni quyidagi skelet bilan
yarating:

```python
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import fakeredis.aioredis

from app.accounts.model import AccountType
from app.core.config import Settings
from app.profiles.model import BusinessProfile, UserProfile
from app.profiles.summary_service import ProfileSummaryService


class CountingDatabase:
    def __init__(self):
        self.reads = 0
        self.rollbacks = 0
        self.profiles = {
            (UserProfile, 1): SimpleNamespace(
                account_id=1,
                name="Ali",
                phone="+998901112233",
            ),
            (BusinessProfile, 2): SimpleNamespace(
                account_id=2,
                name="Koprik Savdo",
                phone="+998907770000",
                direction="Savdo",
                address="Toshkent",
            ),
        }

    @asynccontextmanager
    async def session(self):
        database = self

        class Session:
            async def get(self, model, account_id):
                database.reads += 1
                await asyncio.sleep(0.01)
                return database.profiles.get((model, account_id))

            async def rollback(self):
                database.rollbacks += 1

        yield Session()


async def test_repeated_profile_summary_uses_redis_after_one_database_read():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        first = await service.resolve(AccountType.USER, 1)
        second = await service.resolve(AccountType.USER, 1)
    finally:
        await redis.aclose()

    assert first == second
    assert first.model_dump(mode="json") == {
        "account_id": 1,
        "account_type": "user",
        "name": "Ali",
        "profile_complete": True,
    }
    assert database.reads == 1
    assert database.rollbacks == 1
```

- [ ] **Step 2: RED holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py::test_repeated_profile_summary_uses_redis_after_one_database_read -v
```

Expected: import `ModuleNotFoundError`, chunki
`app.profiles.summary_service` hali yaratilmagan.

- [ ] **Step 3: Minimal service, kalit va Redis read/write oqimini yozish**

`backend/app/profiles/summary_service.py` da:

```python
import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.model import AccountType
from app.core.config import Settings
from app.profiles.repository import (
    get_business_profile,
    get_user_profile,
)
from app.profiles.schemas import MeRead


SessionFactory = Callable[
    [],
    AbstractAsyncContextManager[AsyncSession],
]

logger = logging.getLogger(__name__)
_CACHE_MISS = object()
_PROFILE_SUMMARY_CACHE_PREFIX = "profile:me:v1:"


class ProfileSummaryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        redis: Any,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings

    async def resolve(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> MeRead:
        cached = await self._read_cached_summary(
            account_type,
            account_id,
        )
        if cached is not _CACHE_MISS:
            return cached

        return await self._load_and_cache(account_type, account_id)

    async def _load_and_cache(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> MeRead:
        async with self._session_factory() as session:
            if account_type is AccountType.USER:
                profile = await get_user_profile(session, account_id)
                complete = bool(
                    profile.name.strip() and profile.phone.strip()
                )
            else:
                profile = await get_business_profile(session, account_id)
                complete = bool(
                    profile.name.strip()
                    and profile.phone.strip()
                    and profile.direction.strip()
                    and profile.address.strip()
                )
            summary = MeRead(
                account_id=account_id,
                account_type=account_type,
                name=profile.name,
                profile_complete=complete,
            )
            await session.rollback()
        await self._write_cached_summary(summary)
        return summary

    async def _read_cached_summary(
        self,
        account_type: AccountType,
        account_id: int,
    ) -> MeRead | object:
        redis = self._redis_connection()
        if redis is None:
            return _CACHE_MISS
        try:
            payload = await redis.get(
                self.cache_key(account_type, account_id)
            )
        except Exception:
            logger.warning(
                "Profile summary cache read failed; using database."
            )
            return _CACHE_MISS
        if payload is None:
            return _CACHE_MISS
        try:
            return MeRead.model_validate_json(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            try:
                await redis.delete(
                    self.cache_key(account_type, account_id)
                )
            except Exception:
                pass
            return _CACHE_MISS

    async def _write_cached_summary(self, summary: MeRead) -> None:
        redis = self._redis_connection()
        if redis is None:
            return
        try:
            await redis.set(
                self.cache_key(
                    summary.account_type,
                    summary.account_id,
                ),
                summary.model_dump_json(),
                ex=self._settings.profile_summary_cache_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Profile summary cache write failed; continuing without cache."
            )

    def _redis_connection(self):
        client = getattr(self._redis, "client", None)
        if client is not None and not callable(client):
            return client
        if callable(getattr(self._redis, "get", None)):
            return self._redis
        return None

    @staticmethod
    def cache_key(
        account_type: AccountType,
        account_id: int,
    ) -> str:
        return (
            f"{_PROFILE_SUMMARY_CACHE_PREFIX}"
            f"{account_type.value}:{account_id}"
        )
```

- [ ] **Step 4: Cache-hit testini GREEN qilish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py::test_repeated_profile_summary_uses_redis_after_one_database_read -v
```

Expected: `PASS`.

- [ ] **Step 5: Parallel cache miss uchun failing test qo‘shish**

```python
async def test_parallel_cache_misses_share_one_database_read():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        summaries = await asyncio.gather(
            *(
                service.resolve(AccountType.USER, 1)
                for _ in range(50)
            )
        )
    finally:
        await redis.aclose()

    assert len(summaries) == 50
    assert all(summary.name == "Ali" for summary in summaries)
    assert database.reads == 1
```

- [ ] **Step 6: Parallel testni ishga tushirish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py::test_parallel_cache_misses_share_one_database_read -v
```

Expected: `FAIL`; minimal cache implementatsiyasida barcha so‘rovlar cache
yozilishidan oldin miss ko‘radi va `database.reads == 50` bo‘ladi.

- [ ] **Step 7: Bir akkauntning in-flight task’larini birlashtirish**

`__init__` ga task xaritasini qo‘shing:

```python
self._resolution_tasks: dict[str, asyncio.Task[MeRead]] = {}
```

`resolve` ichidagi to‘g‘ridan-to‘g‘ri `_load_and_cache` chaqiruvini
quyidagiga almashtiring:

```python
cache_key = self.cache_key(account_type, account_id)
task = self._resolution_tasks.get(cache_key)
if task is None:
    task = asyncio.create_task(
        self._load_and_cache(account_type, account_id)
    )
    self._resolution_tasks[cache_key] = task

    def clear_completed(completed):
        if self._resolution_tasks.get(cache_key) is completed:
            self._resolution_tasks.pop(cache_key, None)

    task.add_done_callback(clear_completed)
return await asyncio.shield(task)
```

- [ ] **Step 8: Parallel testni GREEN qilish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py::test_parallel_cache_misses_share_one_database_read -v
```

Expected: `PASS`, `database.reads == 1`.

- [ ] **Step 9: User va business kalitlari ajratilganini test qilish**

```python
async def test_user_and_business_profile_summaries_use_separate_keys():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        user = await service.resolve(AccountType.USER, 1)
        business = await service.resolve(AccountType.BUSINESS, 2)
        keys = {
            key async for key in redis.scan_iter("profile:me:v1:*")
        }
    finally:
        await redis.aclose()

    assert user.profile_complete is True
    assert business.profile_complete is True
    assert keys == {
        "profile:me:v1:user:1",
        "profile:me:v1:business:2",
    }
```

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py -v
```

Expected: barcha service testlari `PASS`.

- [ ] **Step 10: Mavjud profil-topilmadi xatti-harakatini saqlash**

Test importlariga:

```python
import pytest

from app.core.errors import ApiError
```

Test:

```python
async def test_missing_profile_preserves_profile_not_found_error():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        with pytest.raises(ApiError) as raised:
            await service.resolve(AccountType.USER, 999)
        missing_cache = await redis.get("profile:me:v1:user:999")
    finally:
        await redis.aclose()

    assert raised.value.status_code == 404
    assert raised.value.code == "profile_not_found"
    assert missing_cache is None
```

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py -v
```

Expected: barcha service testlari `PASS`.

- [ ] **Step 11: Commit**

```bash
git add backend/app/profiles/summary_service.py backend/tests/test_profile_summary_service.py
git commit -m "feat: cache profile summary reads"
```

---

### Task 3: Cache invalidatsiya va Redis fail-open xatti-harakati

**Files:**

- Modify: `backend/app/profiles/summary_service.py`
- Modify: `backend/tests/test_profile_summary_service.py`

**Interfaces:**

- Consumes: Task 2 dagi `ProfileSummaryService.cache_key` va Redis
  connection adapteri.
- Produces:
  `ProfileSummaryService.invalidate(account_type: AccountType, account_id: int) -> None`.

- [ ] **Step 1: Invalid cache va invalidatsiya uchun failing testlar yozish**

```python
async def test_invalid_cached_json_is_deleted_and_reloaded_from_database():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("profile:me:v1:user:1", "{broken-json")
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        summary = await service.resolve(AccountType.USER, 1)
        cached = await redis.get("profile:me:v1:user:1")
    finally:
        await redis.aclose()

    assert summary.name == "Ali"
    assert database.reads == 1
    assert cached is not None
    assert "{broken-json" not in cached


async def test_invalidate_deletes_only_the_selected_account_cache():
    database = CountingDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        await service.resolve(AccountType.USER, 1)
        await service.resolve(AccountType.BUSINESS, 2)
        await service.invalidate(AccountType.USER, 1)
        user_cache = await redis.get("profile:me:v1:user:1")
        business_cache = await redis.get(
            "profile:me:v1:business:2"
        )
    finally:
        await redis.aclose()

    assert user_cache is None
    assert business_cache is not None
```

- [ ] **Step 2: RED holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py -v
```

Expected: invalid JSON testi ishlashi mumkin, lekin invalidatsiya testi
`AttributeError` bilan `FAIL`, chunki `invalidate` hali yo‘q.

- [ ] **Step 3: Fail-open invalidatsiyani yozish**

`ProfileSummaryService` ichiga:

```python
async def invalidate(
    self,
    account_type: AccountType,
    account_id: int,
) -> None:
    cache_key = self.cache_key(account_type, account_id)
    redis = self._redis_connection()
    if redis is None:
        return
    try:
        await redis.delete(cache_key)
    except Exception:
        logger.warning(
            "Profile summary cache invalidation failed; TTL fallback remains."
        )
```

- [ ] **Step 4: In-flight eski o‘qish cache’ni qayta to‘ldirmasligini test qilish**

`backend/tests/test_profile_summary_service.py` ga boshqariladigan sekin
o‘qish yordamchisini qo‘shing:

```python
class PausedDatabase(CountingDatabase):
    def __init__(self):
        super().__init__()
        self.read_started = asyncio.Event()
        self.allow_read_to_finish = asyncio.Event()

    @asynccontextmanager
    async def session(self):
        database = self

        class Session:
            async def get(self, model, account_id):
                database.reads += 1
                profile = database.profiles.get((model, account_id))
                snapshot = SimpleNamespace(**vars(profile))
                database.read_started.set()
                await database.allow_read_to_finish.wait()
                return snapshot

            async def rollback(self):
                database.rollbacks += 1

        yield Session()
```

So‘ng invalidatsiya eski davom etayotgan task’ning natijasini cache’ga
qayta yozmasligini tasdiqlang:

```python
async def test_invalidation_prevents_inflight_read_from_repopulating_cache():
    database = PausedDatabase()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = ProfileSummaryService(
        database.session,
        redis,
        Settings(environment="test"),
    )
    try:
        stale_read = asyncio.create_task(
            service.resolve(AccountType.USER, 1)
        )
        await database.read_started.wait()
        database.profiles[(UserProfile, 1)].name = "Yangi Ali"
        await service.invalidate(AccountType.USER, 1)
        database.allow_read_to_finish.set()
        stale = await stale_read
        cached_after_stale_read = await redis.get(
            "profile:me:v1:user:1"
        )
        fresh = await service.resolve(AccountType.USER, 1)
    finally:
        await redis.aclose()

    assert stale.name == "Ali"
    assert cached_after_stale_read is None
    assert fresh.name == "Yangi Ali"
    assert database.reads == 2
```

Bu testdagi birinchi, commit’dan oldin boshlangan request eski javobni olishi
mumkin. Lekin invalidatsiyadan keyingi request yangi task yaratadi va eski
task Redis cache’ni qayta eskirtira olmaydi.

- [ ] **Step 5: In-flight task’ni invalidatsiyadan keyin eskirtirmaydigan qilish**

`invalidate` ichida Redis delete’dan oldin shu kalitning in-flight
mapping’ini olib tashlang:

```python
self._resolution_tasks.pop(cache_key, None)
```

`_load_and_cache` boshida kalitni hisoblang:

```python
cache_key = self.cache_key(account_type, account_id)
```

DB sessiyasi yopilgach cache’ga faqat task hali shu kalitning faol task’i
bo‘lsa yozing:

```python
if self._resolution_tasks.get(cache_key) is asyncio.current_task():
    await self._write_cached_summary(summary)
```

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py::test_invalidation_prevents_inflight_read_from_repopulating_cache -v
```

Expected: `PASS`.

- [ ] **Step 6: Redis xatolari DB javobini to‘xtatmasligi testini yozish**

```python
class BrokenRedis:
    async def get(self, key):
        raise RuntimeError("redis read unavailable")

    async def set(self, key, value, *, ex):
        raise RuntimeError("redis write unavailable")

    async def delete(self, key):
        raise RuntimeError("redis delete unavailable")


async def test_redis_failure_falls_back_to_database_and_invalidation_survives():
    database = CountingDatabase()
    service = ProfileSummaryService(
        database.session,
        BrokenRedis(),
        Settings(environment="test"),
    )

    summary = await service.resolve(AccountType.USER, 1)
    await service.invalidate(AccountType.USER, 1)

    assert summary.name == "Ali"
    assert database.reads == 1
```

- [ ] **Step 7: Resilience testlarini GREEN qilish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profile_summary_service.py -v
```

Expected: barcha testlar `PASS`; warning loglar testni yiqitmaydi.

- [ ] **Step 8: Commit**

```bash
git add backend/app/profiles/summary_service.py backend/tests/test_profile_summary_service.py
git commit -m "feat: invalidate profile summary cache safely"
```

---

### Task 4: `/me` va profil yozuvlarini yangi service’ga ulash

**Files:**

- Modify: `backend/app/main.py:1-43`
- Modify: `backend/app/profiles/router.py:1-180`
- Modify: `backend/tests/test_profiles.py:1-260`

**Interfaces:**

- Consumes:
  `ProfileSummaryService.resolve(AccountType, int) -> MeRead` va
  `ProfileSummaryService.invalidate(AccountType, int) -> None`.
- Produces: `/api/v1/me` DB sessiyasini request dependency orqali ochmaydi;
  to‘rtta profil write endpointi commit’dan keyin cache’ni o‘chiradi.

- [ ] **Step 1: Profil test fixture’iga haqiqiy summary service qo‘shish**

`backend/tests/test_profiles.py` importlariga:

```python
import fakeredis.aioredis

from app.profiles.summary_service import ProfileSummaryService
```

`profile_clients` fixture’da `FakeDatabase` ni bitta o‘zgaruvchida saqlang:

```python
database = FakeDatabase(profiles)
redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
app = create_app(settings)
app.state.database = database
app.state.auth_service = FakeAuthService(identities)
app.state.profile_summary_service = ProfileSummaryService(
    database.session,
    redis,
    settings,
)
```

`AsyncExitStack` ichida uchta HTTP client yaratilgach, `yield` dan oldin
test yordamchilarini namespace’ga qo‘shing:

```python
clients["database"] = database
clients["redis"] = redis
yield SimpleNamespace(**clients)
```

Fixture yakunida, `AsyncExitStack` yopilgach:

```python
await redis.aclose()
```

- [ ] **Step 2: `/me` cache ulanishi va update invalidatsiyasi uchun failing testlar yozish**

Avval `/me` service cache’idan foydalanishini tekshiring:

```python
async def test_me_populates_profile_summary_cache(profile_clients):
    response = await profile_clients.first_user.get("/api/v1/me")
    cached = await profile_clients.redis.get(
        "profile:me:v1:user:1"
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ali"
    assert cached is not None
```

So‘ng update’dan keyin yangi qiymat ko‘rinishini tekshiring:

```python
async def test_user_profile_update_invalidates_cached_me(profile_clients):
    before = await profile_clients.first_user.get("/api/v1/me")
    assert before.json()["name"] == "Ali"
    assert await profile_clients.redis.get(
        "profile:me:v1:user:1"
    ) is not None

    updated = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"name": "Yangi Ali"},
    )
    after = await profile_clients.first_user.get("/api/v1/me")

    assert updated.status_code == 200
    assert after.status_code == 200
    assert after.json()["name"] == "Yangi Ali"
```

- [ ] **Step 3: RED holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profiles.py::test_me_populates_profile_summary_cache backend/tests/test_profiles.py::test_user_profile_update_invalidates_cached_me -v
```

Expected: joriy `/me` service’dan foydalanmagani sabab Redis kaliti
yaratilmaydi va ikkala test ham `FAIL`.

- [ ] **Step 4: Service dependency va `/me` ulanishini yozish**

`backend/app/profiles/router.py` ga:

```python
from app.profiles.summary_service import ProfileSummaryService
```

Dependency:

```python
def get_profile_summary_service(request: Request) -> ProfileSummaryService:
    return request.app.state.profile_summary_service


ProfileSummary = Annotated[
    ProfileSummaryService,
    Depends(get_profile_summary_service),
]
```

`get_me` ni quyidagicha almashtiring:

```python
@router.get("/me", response_model=MeRead)
async def get_me(
    current: CurrentRead,
    summaries: ProfileSummary,
) -> MeRead:
    return await summaries.resolve(
        current.account_type,
        current.account_id,
    )
```

Endi ishlatilmaydigan `user_profile_complete` va
`business_profile_complete` yordamchilarini `router.py` dan olib tashlang;
profil to‘liqligi uchun yagona manba `ProfileSummaryService` bo‘ladi.

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profiles.py::test_me_populates_profile_summary_cache -v
```

Expected: `/me` cache kalitini yaratadi va test `PASS`.

- [ ] **Step 5: Update testi hali RED ekanini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profiles.py::test_user_profile_update_invalidates_cached_me -v
```

Expected: update endpointi cache’ni hali o‘chirmagani sabab oxirgi `/me`
eski `"Ali"` qiymatini qaytaradi va test `FAIL`.

- [ ] **Step 6: Muvaffaqiyatli write’lardan keyin invalidatsiya qo‘shish**

Quyidagi to‘rtta handlerga `summaries: ProfileSummary` dependency qo‘shing:

- `update_user_profile`;
- `update_business_profile`;
- `attach_user_avatar`;
- `attach_business_logo`.

Har birida `await session.commit()` dan keyin, `return profile` dan oldin:

```python
await summaries.invalidate(
    current.account_type,
    current.account_id,
)
```

Update invalidatsiya testini qayta ishga tushiring. Expected: `PASS`.

- [ ] **Step 7: Ilova lifespan’ida service yaratish**

`backend/app/main.py` importlariga:

```python
from app.profiles.summary_service import ProfileSummaryService
```

`app.state.auth_service` yaratilganidan keyin:

```python
app.state.profile_summary_service = ProfileSummaryService(
    database.session,
    redis_client,
    resolved,
)
```

- [ ] **Step 8: Commit’dan oldin invalidatsiya bo‘lmasligi testini qo‘shish**

Mavjud duplicate username oqimidan foydalanib:

```python
async def test_failed_profile_update_keeps_existing_me_cache(profile_clients):
    first = await profile_clients.first_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.first_user.csrf},
        json={"public_username": "shared_name"},
    )
    assert first.status_code == 200

    cached_second = await profile_clients.second_user.get("/api/v1/me")
    assert cached_second.status_code == 200
    cache_key = "profile:me:v1:user:2"
    cached_before_failure = await profile_clients.redis.get(cache_key)
    assert cached_before_failure is not None

    duplicate = await profile_clients.second_user.put(
        "/api/v1/user-profile",
        headers={"X-CSRF-Token": profile_clients.second_user.csrf},
        json={"public_username": "shared_name"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "username_taken"
    assert await profile_clients.redis.get(cache_key) == cached_before_failure
    after = await profile_clients.second_user.get("/api/v1/me")
    assert after.status_code == 200
    assert after.json()["name"] == "Vali"
```

`FakeProfileSession.rollback` mavjud snapshot’ni tiklaydi. Testdan keyin
cache kaliti o‘zgarmagani va keyingi `/me` javobi `"Vali"` bo‘lib qolgani
rollback paytida invalidatsiya bo‘lmaganini bevosita isbotlaydi.

- [ ] **Step 9: Avatar va logo write’lari cache kalitini o‘chirishini test qilish**

User uchun oldin `/me` ni chaqiring, so‘ng quyidagi valid body bilan
`PUT /api/v1/user-profile/avatar` yuboring:

```python
{
    "object_key": "private/user/1/avatar/0123456789abcdef0123456789abcdef.webp",
    "x": 50,
    "y": 50,
    "zoom": 1,
}
```

Business uchun oldin `/me` ni chaqiring, so‘ng
`PUT /api/v1/business-profile/logo` ga:

```python
{
    "object_key": "private/business/3/logo/0123456789abcdef0123456789abcdef.webp",
    "x": 50,
    "y": 50,
    "zoom": 1,
}
```

Har requestdan oldin tegishli `/me` cache kaliti mavjudligini tekshiring.
Write HTTP 200 qaytargach user uchun
`profile:me:v1:user:1`, business uchun
`profile:me:v1:business:3` kaliti `None` bo‘lganini
`profile_clients.redis.get(...)` orqali bevosita assert qiling. So‘nggi
`/me` HTTP 200 qaytarishi cache’ning yangi DB o‘qishidan qayta yaratilganini
tasdiqlasin.

- [ ] **Step 10: Profil integratsiya testlarini GREEN qilish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_profiles.py backend/tests/test_profile_summary_service.py -v
```

Expected: barcha testlar `PASS`.

- [ ] **Step 11: Commit**

```bash
git add backend/app/main.py backend/app/profiles/router.py backend/tests/test_profiles.py
git commit -m "feat: serve me from profile summary cache"
```

---

### Task 5: Staging runbook va operatsion kontrakt

**Files:**

- Modify: `docs/deploy-auth-profile-staging.md:10-45`
- Modify: `tests/test_phase2_operational_contract.py`

**Interfaces:**

- Consumes: yangi Railway variable va mavjud latency diagnostika runneri.
- Produces: deploy operatori uchun TTL, invalidatsiya va Phase 2 gate
  ko‘rsatmasi.

- [ ] **Step 1: Runbook kontrakti uchun failing test yozish**

`tests/test_phase2_operational_contract.py` dagi
`Phase2OperationalContractTests` ichiga:

```python
def test_staging_runbook_documents_profile_summary_cache_gate(self):
    runbook = (
        ROOT / "docs/deploy-auth-profile-staging.md"
    ).read_text(encoding="utf-8")

    for expected in (
        "KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS=30",
        "profile:me:v1:",
        "1000 parallel",
        "0 xato",
        "p95 500 ms dan past",
    ):
        self.assertIn(expected, runbook)
```

- [ ] **Step 2: RED holatini tasdiqlash**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_phase2_operational_contract.Phase2OperationalContractTests.test_staging_runbook_documents_profile_summary_cache_gate -v
```

Expected: yangi variable va cache kaliti hujjatda yo‘qligi sabab `FAIL`.

- [ ] **Step 3: Runbook’ni aniq qiymatlar bilan yangilash**

`api-staging` variables blokiga:

```env
KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS=30
```

Session cache izohidan keyin quyidagi mazmunni kiriting:

```markdown
`KOPRIK_PROFILE_SUMMARY_CACHE_TTL_SECONDS` majburiy emas; standart `30`.
`/api/v1/me` javobining ixcham xulosasi
`profile:me:v1:{account_type}:{account_id}` kalitida saqlanadi. Profil,
avatar yoki logo muvaffaqiyatli saqlangach tegishli kalit o‘chiriladi.
Redis ishlamasa API PostgreSQL fallback orqali ishlashda davom etadi.
```

Latency diagnostika bo‘limi oxiriga:

```markdown
Phase 2 profil cache gate’i `/api/v1/me` uchun 1000 parallel so‘rovda
0 xato, barcha javoblar HTTP 200 va p95 500 ms dan past bo‘lganda o‘tadi.
```

- [ ] **Step 4: Operatsion kontraktni GREEN qilish**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_phase2_operational_contract.Phase2OperationalContractTests.test_staging_runbook_documents_profile_summary_cache_gate -v
```

Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
git add docs/deploy-auth-profile-staging.md tests/test_phase2_operational_contract.py
git commit -m "docs: document profile summary cache gate"
```

---

### Task 6: To‘liq regressiya, GitHub PR va Railway staging gate

**Files:**

- Verify only: `backend/`, `frontend/`, `static/index.html`, `tests/`
- Generated locally only: `phase2-latency-diagnostic-v2-result.json`

**Interfaces:**

- Consumes: Tasks 1–5 dagi barcha commitlar.
- Produces: yashil lokal regressiya, GitHub PR checks, Active Railway
  deployment va Phase 2 load natijasi.

- [ ] **Step 1: Focused backend testlarni qayta o‘tkazish**

Run:

```bash
../../.venv/bin/python -m pytest backend/tests/test_config.py backend/tests/test_profile_summary_service.py backend/tests/test_profiles.py -v
```

Expected: barcha focused testlar `PASS`.

- [ ] **Step 2: Phase 2 verifier’ni o‘tkazish**

Run:

```bash
../../.venv/bin/python scripts/verify_phase2.py
```

Expected: legacy, backend, frontend va contract bosqichlari `PASS`.

- [ ] **Step 3: Frontend test va production buildni alohida tekshirish**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: Vitest `PASS`, TypeScript va Vite production build `PASS`.

- [ ] **Step 4: Legacy BUILD va qator sonini tekshirish**

Run:

```bash
rg -n "BUILD: v1656" static/index.html
wc -l static/index.html
```

Expected:

```text
BUILD: v1656
14091 static/index.html
```

- [ ] **Step 5: Diff va ishchi daraxt tozaligini tekshirish**

Run:

```bash
git diff --check
git status --short --branch
git log --oneline -6
```

Expected: whitespace xatosi yo‘q; faqat rejalashtirilgan commitlar ko‘rinadi.

- [ ] **Step 6: GitHub draft PR ochish**

Branch:

```text
codex/phase2-profile-summary-cache
```

PR title:

```text
Cache Phase 2 profile summary reads
```

PR body’da quyidagilarni yozing:

- `/me` profil xulosasi Redis cache’i;
- bir akkaunt uchun parallel DB miss’larni birlashtirish;
- profil write’laridan keyingi invalidatsiya;
- Redis fail-open fallback;
- o‘tgan testlar, BUILD `v1656`, `static/index.html` 14091 qator;
- production `web` va `koprik.uz` o‘zgarmagani.

- [ ] **Step 7: GitHub checks yashil bo‘lgach PR’ni main’ga birlashtirish**

Expected: barcha required checks `PASS`, conflict yo‘q. Checks yashil
bo‘lmaguncha merge qilinmaydi.

- [ ] **Step 8: `api-staging`ga yangi main commitni deploy qilish**

Railway `api-staging` → Deployments orqali yangi merge commitni deploy
qiling. Quyidagilarni tasdiqlang:

- deployment `Active`;
- build va deploy `successful`;
- `/readyz` HTTP 200;
- logda `Application startup complete`;
- doimiy restart yo‘q.

- [ ] **Step 9: Windows latency diagnostikasini qayta ishga tushirish**

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\koprik-phase2-latency-diagnostic-v2.ps1"
```

Login, clipboarddagi parol va Telegram kodini mavjud xavfsiz oqim orqali
kiriting. Natija:

```text
C:\Users\55555555\phase2-latency-diagnostic-v2-result.json
```

- [ ] **Step 10: Phase 2 gate qarorini chiqarish**

`/api/v1/me` natijasida quyidagilarni tekshiring:

```text
requests = 1000
errors = 0
status_code 200 count = 1000
p95_ms < 500
```

To‘rtta shart bajarilsa Phase 2 performance gate o‘tgan deb belgilang.
Birortasi bajarilmasa JSON, Railway API/Redis/Postgres metrikalari va aniq
sinov vaqtini saqlab, keyingi bottleneckni o‘lchov bilan ajrating.
