# Koprik Phase 3B Public Shell and Navigation Implementation Plan

> **For Codex:** Execute this plan task-by-task with `superpowers:executing-plans`. Use test-driven development for every behavior change. Do not modify `static/index.html`; it remains the v1656 rollback contract.

**Goal:** Make `frontend-staging` open with the familiar Koprik v1656 public shell and implement the first migrated public flow: home → catalog → activity types → location, while preserving the working Phase 2 authentication and profile cabinets.

**Architecture:** Continue the approved strangler migration. The React frontend owns only the migrated public screens and Phase 2 account flows. `static/index.html` stays byte-for-byte unchanged as the legacy reference and production rollback path. A small typed navigation state controls React views; public components own only real local interaction, and account actions delegate to the existing API-backed Phase 2 components.

**Tech Stack:** React 19, TypeScript 5.8, Vite 7, Vitest, Testing Library, existing FastAPI API client.

---

## Non-negotiable constraints

- Do not change `static/index.html`, its `BUILD: v1656` marker, or its 14,091-line rollback artifact.
- Do not change production `web`/`koprik.uz` deployment configuration.
- Do not add iframe embedding.
- Do not add buttons that pretend to work. Unmigrated E’lonlar, Savat, Taxi, payment, order, admin, and staff flows stay outside Phase 3B.
- Keep existing Phase 2 auth, session, profile, avatar, logo, Redis session cache, PostgreSQL, and R2 behavior intact.
- Preserve keyboard access, semantic buttons, labels, focus states, reduced motion, and responsive behavior.
- Keep the brand spelling exactly `Koprik`.

## Phase 3B acceptance contract

The phase is accepted only when all of the following are true:

1. A guest opening the frontend root sees a recognizable v1656 public home, not the login form.
2. The header exposes working Home, Location, and Login/Cabinet actions.
3. Home search and the catalog entry open the migrated catalog screen.
4. Catalog filtering is deterministic and local until the public search API is migrated.
5. Choosing an activity opens its migrated activity-type screen.
6. Location opens a real, persistent district selection flow without pretending geolocation/map support exists.
7. Login opens the existing `AuthFlow`; successful auth opens the correct existing cabinet.
8. Logout returns to the public home.
9. Existing Phase 2 tests continue to pass.
10. `static/index.html` remains unchanged and the Phase 3 inventory contract remains at 98 screens.

---

## Task 1: Freeze the Phase 3B public-flow contract

**Files:**

- Create: `frontend/src/legacy/public/public-contract.ts`
- Create: `frontend/src/legacy/public/public-contract.test.ts`
- Modify: `docs/phase3/legacy-parity.md`

### Step 1: Write the failing contract test

Create a contract test that asserts:

- the migrated route names are `home`, `catalog`, `category`, `location`, `auth`, and `cabinet`;
- the public header actions are Home, Location, and Account;
- catalog exposes the six v1656 search types;
- the Phase 3B migration does not claim E’lonlar, Taxi, Savat, payment, admin, or staff support.

Run:

```bash
cd frontend
npm test -- src/legacy/public/public-contract.test.ts
```

Expected: FAIL because the module does not exist.

### Step 2: Implement the minimal typed contract

Export readonly TypeScript constants and derived union types. Do not introduce runtime dependencies.

### Step 3: Re-run the focused test

Run:

```bash
cd frontend
npm test -- src/legacy/public/public-contract.test.ts
```

Expected: PASS.

### Step 4: Mark Phase 3B rows as in progress

In `docs/phase3/legacy-parity.md`, change only:

- home;
- catalog;
- cat-types;
- loc;

from `legacy` to `in-progress`, and name the React owner files. Do not mark them migrated yet.

### Step 5: Commit

```bash
git add frontend/src/legacy/public/public-contract.ts \
  frontend/src/legacy/public/public-contract.test.ts \
  docs/phase3/legacy-parity.md
git commit -m "test: freeze Phase 3B public flow contract"
```

---

## Task 2: Add typed public navigation

**Files:**

- Create: `frontend/src/legacy/public/public-navigation.ts`
- Create: `frontend/src/legacy/public/public-navigation.test.ts`

### Step 1: Write failing reducer tests

Cover:

- default view is `home`;
- `OPEN_CATALOG` stores the current query and opens `catalog`;
- `OPEN_CATEGORY` stores a valid category id and opens `category`;
- `OPEN_LOCATION` opens `location`;
- `OPEN_AUTH` opens `auth`;
- `OPEN_CABINET` opens `cabinet`;
- `GO_HOME` clears transient query/category state;
- `BACK` returns category → catalog, catalog/location/auth/cabinet → home.

Run:

```bash
cd frontend
npm test -- src/legacy/public/public-navigation.test.ts
```

Expected: FAIL because the reducer does not exist.

### Step 2: Implement the reducer

Use a discriminated action union and a serializable state:

```ts
interface PublicNavigationState {
  view: PublicView;
  query: string;
  categoryId: string | null;
}
```

The reducer must remain pure and must not access browser globals.

### Step 3: Re-run the focused test

Expected: PASS.

### Step 4: Commit

```bash
git add frontend/src/legacy/public/public-navigation.ts \
  frontend/src/legacy/public/public-navigation.test.ts
git commit -m "feat: add Phase 3B public navigation state"
```

---

## Task 3: Replace the technical header with the v1656 public shell

**Files:**

- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/app/AppShell.test.tsx`
- Modify: `frontend/src/app/App.css`
- Create: `frontend/src/legacy/public/PublicHeader.tsx`
- Create: `frontend/src/legacy/public/PublicHeader.test.tsx`
- Create: `frontend/src/legacy/public/legacy-public.css`

### Step 1: Write failing header tests

Assert:

- brand button says `Koprik` and calls Home;
- location button says `Manzil` and calls Location;
- guest account button says `Kirish`;
- authenticated account button says `Kabinet`;
- subview header exposes `Orqaga`;
- no E’lonlar, Savat, or Taxi button exists in Phase 3B.

Run:

```bash
cd frontend
npm test -- src/legacy/public/PublicHeader.test.tsx src/app/AppShell.test.tsx
```

Expected: FAIL.

### Step 2: Implement the header

Port only the approved v1656 topbar structure needed by the four migrated public screens. Reuse the original icon geometry through inline SVG. Keep actions callback-driven.

### Step 3: Integrate it into `AppShell`

Change `AppShell` from a fixed login/cabinet header to a layout component that accepts:

```ts
interface AppShellProps {
  authenticated: boolean;
  title?: string;
  isHome: boolean;
  onHome(): void;
  onLocation(): void;
  onAccount(): void;
  onBack(): void;
  children: ReactNode;
}
```

### Step 4: Port only required shell CSS

Use Koprik design tokens. Match the v1656 desktop and mobile proportions without copying unrelated monolith CSS.

### Step 5: Re-run tests

Expected: PASS.

### Step 6: Commit

```bash
git add frontend/src/app/AppShell.tsx \
  frontend/src/app/AppShell.test.tsx \
  frontend/src/app/App.css \
  frontend/src/legacy/public/PublicHeader.tsx \
  frontend/src/legacy/public/PublicHeader.test.tsx \
  frontend/src/legacy/public/legacy-public.css
git commit -m "feat: add v1656 public React shell"
```

---

## Task 4: Build the recognizable v1656 home screen

**Files:**

- Create: `frontend/src/legacy/public/HomeScreen.tsx`
- Create: `frontend/src/legacy/public/HomeScreen.test.tsx`
- Modify: `frontend/src/legacy/public/legacy-public.css`

### Step 1: Write failing home tests

Assert:

- heading is `Kerakli mahsulot va xizmatni yaqiningizdan toping`;
- query input placeholder is `Nima qidiryapsiz?`;
- Enter and `Qidirish` call `onSearch(query)`;
- blank search does not navigate;
- `Katalog bo‘yicha` calls `onOpenCatalog`;
- current district text defaults to `Hudud tanlanmagan`;
- `Manzilni tanlash` calls `onOpenLocation`;
- there are no fake ad, map, or district-offer actions.

Run:

```bash
cd frontend
npm test -- src/legacy/public/HomeScreen.test.tsx
```

Expected: FAIL.

### Step 2: Implement the home component

Port the v1656 approved copy and responsive visual hierarchy:

- hero/search card;
- catalog call-to-action;
- location status;
- a non-interactive visual discovery panel that clearly directs users to select a district.

Do not render fake map pins, ads, results, or district offers.

### Step 3: Re-run the focused test

Expected: PASS.

### Step 4: Commit

```bash
git add frontend/src/legacy/public/HomeScreen.tsx \
  frontend/src/legacy/public/HomeScreen.test.tsx \
  frontend/src/legacy/public/legacy-public.css
git commit -m "feat: migrate v1656 public home"
```

---

## Task 5: Build the catalog and activity-type screens

**Files:**

- Create: `frontend/src/legacy/public/catalog-data.ts`
- Create: `frontend/src/legacy/public/catalog-data.test.ts`
- Create: `frontend/src/legacy/public/CatalogScreen.tsx`
- Create: `frontend/src/legacy/public/CatalogScreen.test.tsx`
- Create: `frontend/src/legacy/public/CategoryScreen.tsx`
- Create: `frontend/src/legacy/public/CategoryScreen.test.tsx`
- Modify: `frontend/src/legacy/public/legacy-public.css`

### Step 1: Extract and test catalog data

Extract the v1656 activity direction labels and child activity types into typed readonly data.

Tests must assert:

- stable ids;
- unique ids;
- exactly the v1656 direction count expected by the UI;
- every direction has at least one type;
- search normalizes Uzbek apostrophe variants and case.

Run:

```bash
cd frontend
npm test -- src/legacy/public/catalog-data.test.ts
```

Expected: FAIL, then PASS after the data module exists.

### Step 2: Write failing catalog interaction tests

Cover:

- six search-type chips;
- four scope chips;
- query filters visible directions;
- initial query from Home is used;
- clearing the query restores all directions;
- clicking a direction calls `onOpenCategory(id)`.

### Step 3: Implement `CatalogScreen`

Keep filters local and deterministic. Do not call the legacy `/api/search` endpoint yet because its public result contract is not part of Phase 3B.

### Step 4: Write and implement `CategoryScreen`

Tests must assert:

- selected direction title;
- all matching activity types;
- Back action remains owned by the parent shell;
- selecting an unmigrated type shows an honest, non-success informational state rather than navigating to a fake result.

### Step 5: Re-run focused tests

Run:

```bash
cd frontend
npm test -- \
  src/legacy/public/catalog-data.test.ts \
  src/legacy/public/CatalogScreen.test.tsx \
  src/legacy/public/CategoryScreen.test.tsx
```

Expected: PASS.

### Step 6: Commit

```bash
git add frontend/src/legacy/public/catalog-data.ts \
  frontend/src/legacy/public/catalog-data.test.ts \
  frontend/src/legacy/public/CatalogScreen.tsx \
  frontend/src/legacy/public/CatalogScreen.test.tsx \
  frontend/src/legacy/public/CategoryScreen.tsx \
  frontend/src/legacy/public/CategoryScreen.test.tsx \
  frontend/src/legacy/public/legacy-public.css
git commit -m "feat: migrate v1656 catalog navigation"
```

---

## Task 6: Add honest persistent location selection

**Files:**

- Create: `frontend/src/legacy/public/location-storage.ts`
- Create: `frontend/src/legacy/public/location-storage.test.ts`
- Create: `frontend/src/legacy/public/LocationScreen.tsx`
- Create: `frontend/src/legacy/public/LocationScreen.test.tsx`
- Create: `frontend/src/legacy/public/location-data.ts`
- Modify: `frontend/src/legacy/public/legacy-public.css`

### Step 1: Write failing storage tests

Cover:

- empty storage returns `null`;
- valid JSON returns region/district/neighborhood;
- malformed JSON is ignored;
- save writes the exact versioned schema;
- storage access failure does not crash the app.

Use key `koprik_home_location_v1` to remain compatible with v1656.

### Step 2: Implement storage helpers

Keep browser storage behind injected `Storage` or safe wrappers so tests remain deterministic.

### Step 3: Write failing location UI tests

Cover:

- heading and privacy copy match v1656;
- district is required;
- selecting region resets an invalid district;
- neighborhood is optional;
- Save persists and calls `onSaved`;
- `Avtomatik aniqlash` is not shown until a real geolocation/map implementation exists.

### Step 4: Implement location data and screen

Use the existing canonical Uzbek region/district data if already present in the repository. If the only source is v1656, extract that exact data without broadening scope.

### Step 5: Re-run focused tests

Expected: PASS.

### Step 6: Commit

```bash
git add frontend/src/legacy/public/location-storage.ts \
  frontend/src/legacy/public/location-storage.test.ts \
  frontend/src/legacy/public/LocationScreen.tsx \
  frontend/src/legacy/public/LocationScreen.test.tsx \
  frontend/src/legacy/public/location-data.ts \
  frontend/src/legacy/public/legacy-public.css
git commit -m "feat: migrate v1656 location selection"
```

---

## Task 7: Integrate public navigation with Phase 2 auth and cabinets

**Files:**

- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/app/App.css`

### Step 1: Replace old App tests with the new user journey

Add tests for:

- guest root shows Home, not Login;
- Login opens AuthFlow;
- registration/login completion opens the appropriate cabinet;
- existing authenticated session starts on Home and Account opens cabinet;
- logout clears session and returns Home;
- Home search opens Catalog with the query;
- Catalog → Category → Back works;
- Location save updates Home district text;
- retryable session bootstrap error still renders the retry state.

Run:

```bash
cd frontend
npm test -- src/app/App.test.tsx
```

Expected: FAIL.

### Step 2: Implement navigation composition

Use `useReducer(publicNavigationReducer, initialPublicNavigationState)`.

Rendering rules:

- `home` → `HomeScreen`;
- `catalog` → `CatalogScreen`;
- `category` → `CategoryScreen`;
- `location` → `LocationScreen`;
- `auth` → existing `AuthFlow`;
- `cabinet` → existing `UserProfile` or `BusinessProfile`.

Session bootstrap remains independent from the public view.

### Step 3: Preserve existing API capability checks

- Missing auth methods must show the existing technical fallback only when Auth is opened.
- Missing profile methods must show the existing technical fallback only when Cabinet is opened.
- Public Home/Catalog/Location must remain usable when the API is temporarily unavailable.

### Step 4: Re-run App and all existing frontend tests

Run:

```bash
cd frontend
npm test
```

Expected: PASS.

### Step 5: Commit

```bash
git add frontend/src/app/App.tsx frontend/src/app/App.test.tsx frontend/src/app/App.css
git commit -m "feat: connect Phase 2 accounts to v1656 public shell"
```

---

## Task 8: Add Phase 3B verification and staging runbook

**Files:**

- Create: `scripts/verify_phase3b.py`
- Create: `tests/test_phase3b_public_shell.py`
- Modify: `.github/workflows/phase1-ci.yml`
- Create: `docs/deploy-phase3b-staging.md`
- Modify: `docs/phase3/legacy-parity.md`

### Step 1: Write the failing repository-level verification test

Assert:

- expected Phase 3B React owners exist;
- App contains the six approved views;
- no iframe appears in the new public components;
- `static/index.html` still contains `BUILD: v1656`;
- inventory still reports 98 screens;
- production configuration references are unchanged;
- Phase 3B parity rows are `in-progress` before manual staging acceptance.

Run:

```bash
python -m pytest tests/test_phase3b_public_shell.py -q
```

Expected: FAIL.

### Step 2: Implement the verifier

`scripts/verify_phase3b.py` must run:

1. Phase 3A verifier;
2. backend tests;
3. frontend tests;
4. frontend build;
5. Phase 3B repository contract tests.

### Step 3: Add CI invocation

Extend the existing workflow with:

```bash
python scripts/verify_phase3b.py
```

Do not rename the workflow or introduce a second conflicting required check.

### Step 4: Write the staging runbook

Document:

- `frontend-staging` only;
- expected root, catalog, activity-type, location, login, ordinary cabinet, and business cabinet checks;
- desktop and mobile viewport checks;
- rollback to the previous frontend-staging deployment;
- explicit confirmation that `web`/`koprik.uz` remains untouched.

### Step 5: Re-run verification

Run:

```bash
python scripts/verify_phase3b.py
```

Expected: PASS.

### Step 6: Commit

```bash
git add scripts/verify_phase3b.py \
  tests/test_phase3b_public_shell.py \
  .github/workflows/phase1-ci.yml \
  docs/deploy-phase3b-staging.md \
  docs/phase3/legacy-parity.md
git commit -m "ci: verify Phase 3B public shell"
```

---

## Task 9: Final verification and handoff

### Step 1: Verify the working tree

Run:

```bash
git status --short
git diff --check
```

Expected: clean working tree after the plan document commit and no whitespace errors.

### Step 2: Run the final automated gate

Run:

```bash
python scripts/verify_phase3b.py
```

Expected: PASS.

### Step 3: Confirm immutable legacy evidence

Run:

```bash
grep -n "BUILD: v1656" static/index.html
wc -l static/index.html
python scripts/export_phase3_screen_inventory.py --check
```

Expected:

- BUILD remains `v1656`;
- `static/index.html` remains 14,091 lines;
- inventory check passes with 98 screens.

### Step 4: Review the diff

Run:

```bash
git diff main...HEAD --stat
git log --oneline --decorate -12
```

Confirm no production deployment or secret files changed.

### Step 5: Request review before merge

Use the repository’s existing review/check flow. Merge only after:

- all CI checks pass;
- frontend-staging manual acceptance passes;
- rollback instructions are confirmed.

After merge, verify the new `frontend-staging` deployment. Do not enable or alter production `web` automatically.

