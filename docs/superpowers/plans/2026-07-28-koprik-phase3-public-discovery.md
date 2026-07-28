# Koprik Phase 3 Public Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Phase 3 public catalog to a safe, paginated PostgreSQL search API for active Koprik user and business profiles without changing the legacy v1656 production interface.

**Architecture:** Add an isolated `public_discovery` backend module with typed schemas, SQLAlchemy queries, a 30-second Redis read-through cache, and one unauthenticated FastAPI route. Extend the existing typed frontend client and public catalog/category screens so public profile results load independently of the authentication session bootstrap.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy asyncio, PostgreSQL, Redis, Pydantic v2, React 19, TypeScript, Vite, Vitest, Testing Library.

## Global Constraints

- Keep `static/index.html`, legacy BUILD v1656, the Railway `web/koprik.uz` service, and existing private profile endpoints unchanged.
- Never return phone, login, password hash, Telegram user ID, payment data, tax ID, director, exact coordinates, session data, or private object keys.
- Only accounts whose `accounts.status == "active"` may appear.
- Public search must work without a login and must remain usable when session bootstrap fails.
- Redis failure must degrade to PostgreSQL, not to an API error.
- The first slice searches profiles only. Products, services, listings, reviews, and ordering remain Phase 3C.
- Each implementation task begins with a failing test, then the smallest passing change, then a focused commit.

---

## Task 1: Define the Public Search Contract

**Files:**

- Create: `backend/app/public_discovery/__init__.py`
- Create: `backend/app/public_discovery/schemas.py`
- Create: `backend/tests/test_public_discovery_schemas.py`

- [ ] Write failing tests proving the public card contains only `kind`, `public_id`, `name`, `public_username`, `description`, `direction`, `activity_type`, `region`, `district`, `mahalla`, and `image_url`.
- [ ] Test query constraints: `q` max 120, page at least 1, and page size from 1 through 50.
- [ ] Run `cd backend && pytest tests/test_public_discovery_schemas.py -q`; confirm RED because the module does not exist.
- [ ] Implement `PublicResultType`, `PublicProfileKind`, `PublicSearchQuery`, `PublicProfileCard`, and `PublicSearchResponse` in Pydantic v2.
- [ ] Normalize query strings with `strip()` while preserving display text.
- [ ] Re-run the focused tests and confirm GREEN.
- [ ] Commit with `feat: define public discovery contract`.

## Task 2: Query Active Profiles Safely

**Files:**

- Create: `backend/app/public_discovery/repository.py`
- Create: `backend/tests/test_public_discovery_repository.py`

- [ ] Write PostgreSQL repository tests using the existing transactional fixture.
- [ ] Prove inactive accounts never appear and public results never expose private fields.
- [ ] Cover case-insensitive user name/username matching.
- [ ] Cover business name, username, description, direction, and activity-type matching.
- [ ] Cover exact case-insensitive `direction`, `activity_type`, `region`, `district`, and `mahalla` filters.
- [ ] Cover `result_type=user|business|all`, deterministic ordering, total count, and pagination.
- [ ] Run `cd backend && pytest tests/test_public_discovery_repository.py -q`; confirm RED.
- [ ] Implement separate user/business SQLAlchemy selects joined to `Account` and constrained to `Account.status == "active"`.
- [ ] Select only allowlisted columns; derive opaque IDs as `u_<account_id>` and `b_<account_id>`.
- [ ] Rank exact normalized name, prefix name, other matches, then normalized name and `public_id`.
- [ ] Set `image_url=None` until a safe public media delivery URL is available.
- [ ] Re-run the focused tests and confirm GREEN.
- [ ] Commit with `feat: query active public profiles`.

## Task 3: Add a 30-Second Redis Read-Through Cache

**Files:**

- Create: `backend/app/public_discovery/service.py`
- Create: `backend/tests/test_public_discovery_service.py`
- Modify: `backend/app/core/config.py`

- [ ] Write failing tests for cache hits, canonical keys, 30-second TTL, validation, and Redis failure fallback.
- [ ] Prove a repeated identical search reaches PostgreSQL only once.
- [ ] Prove changing any filter or page changes the cache key.
- [ ] Run `cd backend && pytest tests/test_public_discovery_service.py -q`; confirm RED.
- [ ] Add `public_search_cache_ttl_seconds: int = Field(default=30, ge=5, le=300)`.
- [ ] Implement a canonical JSON cache key from `query.model_dump(mode="json")`.
- [ ] Follow the existing profile-summary Redis compatibility pattern and log cache failures.
- [ ] On any Redis read/write failure, continue against PostgreSQL rather than failing the request.
- [ ] Re-run the focused tests and confirm GREEN.
- [ ] Commit with `feat: cache public discovery results`.

## Task 4: Publish the Unauthenticated Search Endpoint

**Files:**

- Create: `backend/app/public_discovery/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_public_discovery_api.py`

- [ ] Write failing HTTP tests for `GET /api/v1/public/search` with no cookie, token, or CSRF header.
- [ ] Test every query parameter and FastAPI validation, including `page_size=51 -> 422`.
- [ ] Assert the response contains no session or CSRF fields.
- [ ] Run `cd backend && pytest tests/test_public_discovery_api.py -q`; confirm `404 Not Found`.
- [ ] Add the unauthenticated router with typed query parameters.
- [ ] Construct `PublicDiscoveryService` in the application lifespan using the existing database and Redis clients.
- [ ] Store the service in `app.state.public_discovery_service` and include the router.
- [ ] Run `cd backend && pytest tests/test_public_discovery_api.py -q && pytest -q`.
- [ ] Commit with `feat: expose public profile search`.

## Task 5: Extend the Typed Frontend API Client

**Files:**

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`

- [ ] Write failing Vitest coverage for public-search query serialization.
- [ ] Assert empty optional filters are omitted, parameter order is stable, and no CSRF header is added.
- [ ] Run `cd frontend && npm test -- src/api/client.test.ts`; confirm RED because `searchPublicProfiles` is missing.
- [ ] Add TypeScript equivalents of the backend public query, card, kind, and paginated response contracts.
- [ ] Implement `searchPublicProfiles()` using `URLSearchParams` and `GET /api/v1/public/search`.
- [ ] Re-run the focused client tests and confirm GREEN.
- [ ] Commit with `feat: add public discovery client`.

## Task 6: Render Real Public Results in Catalog and Category Screens

**Files:**

- Create: `frontend/src/legacy/public/PublicSearchResults.tsx`
- Create: `frontend/src/legacy/public/PublicSearchResults.test.tsx`
- Modify: `frontend/src/legacy/public/CatalogScreen.tsx`
- Modify: `frontend/src/legacy/public/CategoryScreen.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/app/App.css`

- [ ] Write failing component tests for loading, success, empty state, API error, retry, pagination, type labels, and filter changes.
- [ ] Prove public search still renders when `getSession()` fails.
- [ ] Prove phone numbers and other private values are never rendered.
- [ ] Run `cd frontend && npm test -- src/legacy/public/PublicSearchResults.test.tsx src/app/App.test.tsx`; confirm RED.
- [ ] Implement `PublicSearchResults` with stale-request protection, accessible status text, retry, and previous/next controls.
- [ ] Keep local catalog directions; when a trimmed text query exists, render real API results below the filters.
- [ ] Map `Barchasi -> all`, `Biznes -> business`, `Mutaxassis/Foydalanuvchi -> user`.
- [ ] Keep `Mahsulot` and `Xizmat` as an explicit Phase 3C notice.
- [ ] In a category, query business profiles by selected direction and activity type.
- [ ] Pass a `PublicDiscoveryApi` from `App` independently of auth/profile APIs.
- [ ] Add responsive styles using the existing public-shell tokens without changing legacy `static/index.html`.
- [ ] Run focused tests, `npm test`, and `npm run build`; confirm GREEN.
- [ ] Commit with `feat: connect public profile discovery`.

## Task 7: Regression, Contract, and Rollout Documentation

**Files:**

- Create: `docs/deploy-phase3-public-discovery-staging.md`
- Create: `tests/test_phase3_public_discovery_contract.py`
- Modify only if needed: `.github/workflows/phase1-ci.yml`

- [ ] Add a cross-layer contract test proving backend/frontend field names, filter names, endpoint path, and pagination metadata agree.
- [ ] Assert forbidden private field names do not occur in public schemas.
- [ ] Assert `static/index.html` still declares BUILD v1656.
- [ ] Write a Railway staging/rollback runbook covering deployment order, `/healthz`, `/readyz`, public-search smoke tests, guest/user/business browser checks, Redis-off fallback, and rollback.
- [ ] Run `python scripts/verify_phase1.py` and `python scripts/verify_phase2.py`.
- [ ] Run `cd backend && pytest -q`.
- [ ] Run `cd frontend && npm test && npm run build`.
- [ ] Run `pytest tests/test_phase3_public_discovery_contract.py -q`.
- [ ] Verify unauthenticated access, active-only results, safe allowlist, deterministic pagination, 30-second cache, PostgreSQL fallback, frontend states, session independence, and no Phase 3C scope creep.
- [ ] Scan for placeholders and private-field leaks with `rg`.
- [ ] Commit with `docs: add public discovery rollout gate`.
- [ ] Push `codex/phase3-public-discovery` and open a draft PR to `main` with exact verification results, staging screenshots, a public API example, legacy-preservation statement, and rollback steps.
