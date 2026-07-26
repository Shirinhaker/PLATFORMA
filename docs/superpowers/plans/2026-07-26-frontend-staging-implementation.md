# Ko‘prik Frontend Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production `koprik.uz` xizmatiga tegmasdan React foundation sahifasini alohida Railway `frontend-staging` servisida ishga tushirish va uni `api-staging` bilan xavfsiz CORS orqali ulash.

**Architecture:** Backend aniq HTTPS origin’lar ro‘yxatini `KOPRIK_CORS_ORIGINS` orqali oladi va faqat shu ro‘yxat uchun CORS headerlarini beradi. React/Vite frontend `/frontend` root’dan alohida build va preview jarayonida ishlaydi, `VITE_API_BASE_URL` orqali staging API’ning `/api/v1/build` endpointini chaqiradi. Mavjud `web`, legacy SQLite runtime va production trafik o‘zgarmaydi.

**Tech Stack:** Python 3.12, FastAPI 0.139.2, Pydantic Settings 2.x, Pytest, React 19, TypeScript 5.8, Vite 7, Vitest, Railway

## Global Constraints

- Legacy BUILD aynan `v1656` bo‘lib qoladi.
- `static/index.html` aynan 14 091 qator bo‘lib qoladi.
- Production `web` (`koprik.uz`) konfiguratsiyasi va trafiki o‘zgarmaydi.
- CORS wildcard (`*`) qabul qilinmaydi.
- CORS uchun faqat aniq HTTPS origin’lar qabul qilinadi.
- R2, PostgreSQL va Redis credential’lari frontendga berilmaydi.
- Birinchi frontend staging faqat foundation status sahifasini ko‘rsatadi.
- Login, profil, katalog, qidiruv va boshqa v1656 funksiyalari bu rejaga kirmaydi.

---

## File Map

- `backend/app/core/config.py`: CORS environment qiymatini tekshiradi va origin’lar ro‘yxatini beradi.
- `backend/tests/test_config.py`: CORS konfiguratsiyasining normalizatsiya va rad etish qoidalarini tekshiradi.
- `backend/app/main.py`: `CORSMiddleware`ni faqat origin ro‘yxati bo‘sh bo‘lmaganda o‘rnatadi.
- `backend/tests/test_app.py`: ruxsat etilgan va noma’lum origin uchun HTTP xulqini tekshiradi.
- `frontend/package.json`: Railway ishlatadigan `preview` scriptini e’lon qiladi.
- `docs/deploy-frontend-staging.md`: Railway sozlash, acceptance va rollback runbook’i.

### Task 1: CORS konfiguratsiya kontrakti

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: `Settings` uchun mavjud `KOPRIK_` environment prefix’i.
- Produces: `Settings.cors_origins: str` va `Settings.cors_origin_list: list[str]`.

- [ ] **Step 1: CORS normalizatsiya testini yozish**

`backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_are_normalized_to_exact_https_origins():
    settings = Settings(
        cors_origins=(
            " https://frontend-one.up.railway.app/,"
            "https://frontend-two.up.railway.app "
        )
    )

    assert settings.cors_origins == (
        "https://frontend-one.up.railway.app,"
        "https://frontend-two.up.railway.app"
    )
    assert settings.cors_origin_list == [
        "https://frontend-one.up.railway.app",
        "https://frontend-two.up.railway.app",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "http://frontend-staging.up.railway.app",
        "https://frontend-staging.up.railway.app/path",
    ],
)
def test_cors_origins_reject_wildcard_insecure_and_path_values(value: str):
    with pytest.raises(ValidationError):
        Settings(cors_origins=value)
```

- [ ] **Step 2: Test qizil ekanini tekshirish**

Run:

```bash
cd backend
python -m pytest tests/test_config.py -v
```

Expected: FAIL, chunki `Settings`da `cors_origins` va
`cors_origin_list` hali mavjud emas.

- [ ] **Step 3: Minimal konfiguratsiya implementatsiyasini yozish**

`backend/app/core/config.py` importlariga qo‘shing:

```python
from urllib.parse import urlsplit

from pydantic import Field, field_validator
```

`Settings` maydonlariga qo‘shing:

```python
    cors_origins: str = ""

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [
            origin.strip().rstrip("/")
            for origin in value.split(",")
            if origin.strip()
        ]
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS origin to‘liq va xavfsiz HTTPS origin bo‘lishi kerak."
                )
        return ",".join(dict.fromkeys(origins))

    @property
    def cors_origin_list(self) -> list[str]:
        return self.cors_origins.split(",") if self.cors_origins else []
```

- [ ] **Step 4: CORS konfiguratsiya testini yashil qilish**

Run:

```bash
cd backend
python -m pytest tests/test_config.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Backend regressiya testlarini bajarish**

Run:

```bash
cd backend
python -m pytest tests -v
```

Expected: barcha backend testlari PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat: validate staging cors origins"
```

### Task 2: FastAPI CORS middleware

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_app.py`

**Interfaces:**
- Consumes: `Settings.cors_origin_list: list[str]` Task 1’dan.
- Produces: configured origin uchun CORS preflight va response headerlari.

- [ ] **Step 1: Middleware xulqi uchun testlarni yozish**

`backend/tests/test_app.py` oxiriga qo‘shing:

```python
def test_cors_allows_only_the_configured_frontend_origin():
    origin = "https://frontend-staging.up.railway.app"
    app = create_app(
        Settings(environment="test", cors_origins=origin)
    )
    client = TestClient(app)

    preflight = client.options(
        "/api/v1/build",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == origin
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"

    unknown = client.get(
        "/api/v1/build",
        headers={"Origin": "https://unknown.example"},
    )
    assert unknown.status_code == 200
    assert "Access-Control-Allow-Origin" not in unknown.headers


def test_cors_is_disabled_when_no_origin_is_configured():
    app = create_app(Settings(environment="test", cors_origins=""))
    response = TestClient(app).get(
        "/api/v1/build",
        headers={"Origin": "https://frontend-staging.up.railway.app"},
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
```

- [ ] **Step 2: Middleware testlari qizil ekanini tekshirish**

Run:

```bash
cd backend
python -m pytest tests/test_app.py -v
```

Expected: yangi configured-origin testi FAIL, chunki CORS middleware hali
o‘rnatilmagan.

- [ ] **Step 3: Minimal middleware implementatsiyasini yozish**

`backend/app/main.py` importlariga qo‘shing:

```python
from fastapi.middleware.cors import CORSMiddleware
```

`FastAPI` yaratilgandan keyin va `RequestIdMiddleware`dan oldin qo‘shing:

```python
    if resolved.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
```

- [ ] **Step 4: Middleware testlarini yashil qilish**

Run:

```bash
cd backend
python -m pytest tests/test_app.py -v
```

Expected: barcha `test_app.py` testlari PASS.

- [ ] **Step 5: To‘liq backend testini bajarish**

Run:

```bash
cd backend
python -m pytest tests -v
```

Expected: barcha backend testlari PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_app.py
git commit -m "feat: allow configured staging frontend origin"
```

### Task 3: Railway frontend preview jarayoni

**Files:**
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: Vite build yaratgan `frontend/dist/`.
- Produces: `npm run preview`, `--host` va `--port` argumentlarini qabul qiladigan uzoq ishlovchi frontend jarayoni.

- [ ] **Step 1: Script hali yo‘qligini test qilish**

Run:

```bash
cd frontend
npm run preview -- --help
```

Expected: FAIL va `Missing script: "preview"` xabari.

- [ ] **Step 2: Minimal preview scriptini qo‘shish**

`frontend/package.json` scripts bo‘limini quyidagicha qiling:

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
```

- [ ] **Step 3: Frontend test va production buildni bajarish**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: Vitest PASS va Vite build exit code 0.

- [ ] **Step 4: Preview jarayonini haqiqiy HTTP so‘rov bilan tekshirish**

Run:

```bash
cd frontend
npm run preview -- --host 127.0.0.1 --port 4173 >/tmp/koprik-preview.log 2>&1 &
PREVIEW_PID=$!
for attempt in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:4173/ >/tmp/koprik-preview.html; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:4173/ | grep '<div id="root"></div>'
kill "$PREVIEW_PID"
wait "$PREVIEW_PID" || true
```

Expected: root HTML topiladi va preview jarayoni boshqarilgan tarzda
to‘xtaydi.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json
git commit -m "feat: add frontend staging preview command"
```

### Task 4: Railway deploy runbook va to‘liq lokal acceptance

**Files:**
- Create: `docs/deploy-frontend-staging.md`

**Interfaces:**
- Consumes: Task 1–3’dagi CORS va preview kontraktlari.
- Produces: bir xil takrorlanadigan Railway frontend staging deploy va rollback tartibi.

- [ ] **Step 1: Deploy runbook’ini yozish**

`docs/deploy-frontend-staging.md` quyidagi aniq bo‘limlarni o‘z ichiga olsin:

```markdown
# Frontend Staging Deploy

## O‘zgarmaydigan production

- `web` va `koprik.uz`ga tegmang.
- `worker-staging`ga public domain yaratmang.
- `api-staging`ning mavjud domenini o‘chirmang.

## Frontend service

1. GitHub repo: `Shirinhaker/PLATFORMA`
2. Branch: `main`
3. Root Directory: `/frontend`
4. Build Command: `npm ci && npm run build`
5. Start Command:
   `/bin/sh -c "exec npm run preview -- --host 0.0.0.0 --port $PORT"`
6. Variable:
   `VITE_API_BASE_URL=https://platforma-production-f753.up.railway.app`
7. Healthcheck Path: `/`
8. Public domain target port: `8080`

## CORS

Frontend domeni yaratilgach, uning to‘liq `https://...` origin qiymatini
`api-staging` servisidagi `KOPRIK_CORS_ORIGINS`ga yozing va faqat
`api-staging`ni qayta deploy qiling.

## Acceptance

- frontend deployment `ACTIVE`;
- foundation sahifasi ochiladi;
- `API v1`, `Phase 1`, `Eski faol BUILD: v1656` ko‘rinadi;
- browser console’da CORS xatosi yo‘q;
- `/healthz` status `ok`;
- `/readyz` status `ready`, database/redis/r2 qiymatlari `true`;
- `web`, `worker-staging`, PostgreSQL va Redis Online.

## Rollback

1. `api-staging`ni oldingi muvaffaqiyatli deploymentga rollback qiling.
2. `frontend-staging`ni vaqtincha o‘chiring yoki oldingi deploymentga qaytaring.
3. `web` va `koprik.uz`ni o‘zgartirmang.
```

- [ ] **Step 2: Runbook majburiy sozlamalarini tekshirish**

Run:

```bash
rg -n \
  'Root Directory: `/frontend`|VITE_API_BASE_URL=|KOPRIK_CORS_ORIGINS|Healthcheck Path: `/`|target port: `8080`' \
  docs/deploy-frontend-staging.md
```

Expected: barcha besh sozlama topiladi.

- [ ] **Step 3: To‘liq lokal tekshiruvni bajarish**

Run:

```bash
cd backend
python -m pytest tests -v
cd ../frontend
npm test
npm run build
cd ..
git diff --exit-code -- static/index.html
test "$(wc -l < static/index.html)" -eq 14091
```

Expected: backend va frontend test/build PASS; legacy HTML diff yo‘q va
qatorlar soni 14 091.

- [ ] **Step 4: Commit**

```bash
git add docs/deploy-frontend-staging.md
git commit -m "docs: add frontend staging deploy runbook"
```

### Task 5: GitHub va Railway staging rollout

**Files:**
- Verify only: `.github/workflows/phase1-ci.yml`
- Verify only: Railway `api-staging`, `worker-staging`, `web`, PostgreSQL, Redis va `koprik media`.

**Interfaces:**
- Consumes: main branch’dagi Task 1–4 commitlari.
- Produces: public, production’dan ajratilgan `frontend-staging` URL va tasdiqlangan CORS ulanishi.

- [ ] **Step 1: Branchni GitHub’ga chiqarish va PR ochish**

PR sarlavhasi:

```text
Add isolated frontend staging deployment
```

PR matnida quyidagilarni yozing:

```markdown
## Natija

- aniq HTTPS origin’lar uchun CORS konfiguratsiyasi;
- alohida Railway frontend preview jarayoni;
- frontend staging deploy va rollback runbook’i;
- production `web`, BUILD v1656 va legacy HTML o‘zgarmadi.

## Tekshiruv

- backend tests PASS
- frontend tests PASS
- frontend build PASS
- static/index.html 14 091 qator
```

- [ ] **Step 2: GitHub Actions yashil bo‘lishini kutish**

Expected: `phase1-foundation / verify` PASS.

- [ ] **Step 3: PR’ni `main`ga merge qilish**

Expected: merge commit `main`da va `api-staging`/`worker-staging` auto-deploy
jarayoni muvaffaqiyatli.

- [ ] **Step 4: `frontend-staging` Railway servisni yaratish**

`docs/deploy-frontend-staging.md`dagi GitHub, root, build, start,
`VITE_API_BASE_URL` va healthcheck sozlamalarini aynan kiriting. Public
domain yaratishda port `8080`ni tanlang.

- [ ] **Step 5: Frontend origin’ni API CORS ro‘yxatiga qo‘shish**

Railway yaratgan frontend domenining faqat origin qismini, path va oxirgi
slashsiz, `api-staging`dagi `KOPRIK_CORS_ORIGINS` qiymatiga kiriting.
`api-staging`ni deploy qiling.

- [ ] **Step 6: API readiness va CORS headerini tekshirish**

Run, bunda `FRONTEND_ORIGIN` qiymati Railway ko‘rsatgan aniq HTTPS
frontend origin bo‘ladi:

```bash
curl -fsS https://platforma-production-f753.up.railway.app/healthz
curl -fsS https://platforma-production-f753.up.railway.app/readyz
curl -fsS -D - \
  -H "Origin: $FRONTEND_ORIGIN" \
  https://platforma-production-f753.up.railway.app/api/v1/build
```

Expected:

- health `status` — `ok`;
- readiness `status` — `ready`;
- database, Redis va R2 — `true`;
- build javobi — `api_version: v1`, `foundation: phase1`,
  `legacy_build: v1656`;
- response header — `Access-Control-Allow-Origin: $FRONTEND_ORIGIN`.

- [ ] **Step 7: Browser acceptance**

Frontend domenini desktop va mobil viewport’da oching. `API v1`,
`Phase 1`, `Eski faol BUILD: v1656` ko‘rinishi va CORS xatosi yo‘qligini
tasdiqlang. `koprik.uz`ni alohida ochib production smoke-test bajaring.

- [ ] **Step 8: Yakuniy holatni yozib qo‘yish**

Qabul natijasida quyidagilarni hisobotga yozing:

- frontend staging public URL;
- active frontend va API deployment identifikatorlari;
- `/healthz` va `/readyz` javoblari;
- GitHub Actions run identifikatori;
- BUILD `v1656`;
- `static/index.html` 14 091 qator;
- production trafik o‘zgarmagani.
