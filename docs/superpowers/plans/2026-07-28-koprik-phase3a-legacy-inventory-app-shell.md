# Koprik Phase 3A Legacy Inventory and App Shell Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** BUILD v1656’dagi 98 ta ekran va kritik foydalanuvchi oqimini o‘zgarmas contract sifatida hujjatlashtirish, so‘ng Phase 2 autentifikatsiya va profil komponentlarini v1656 dizayn tokenlariga mos, responsive React app shell ichiga joylashtirish.

**Architecture:** `static/index.html` production rollback sifatida o‘zgarishsiz qoladi. Alohida exporter legacy DOM’dan ekran nomlarini deterministik ravishda oladi va committed parity snapshot bilan solishtiradi. React frontend umumiy `AppShell` komponenti, v1656 dizayn tokenlari va mavjud session bootstrap ustida ishlaydi; faqat amalda ishlaydigan kirish, kabinet, qayta urinish va chiqish amallari ko‘rsatiladi. Qidiruv, katalog, xarita, e’lonlar va boshqa katta legacy modullar bu deliverable’da soxta tugmalar bilan ko‘rsatilmaydi — ular keyingi ekran-migratsiya rejalariga qoladi.

**Tech Stack:** Python 3.12, unittest, React 19, TypeScript 5.8, Vite 7, Vitest, Testing Library, CSS custom properties, GitHub Actions, Railway staging

## Global Constraints

- Production `web` xizmati va `koprik.uz` domeniga tegilmaydi.
- `static/index.html` ichidagi `<!-- BUILD: v1656 -->` belgisi saqlanadi.
- `static/index.html` aynan 14 091 qator bo‘lib qoladi.
- 98 ta unique `data-screen` qiymatidan hech biri yo‘qolmaydi.
- Phase 2 auth, session, ordinary/business profile va media API contractlari o‘zgarmaydi.
- Frontendga Railway, PostgreSQL, Redis, R2 yoki Telegram sir qiymatlari kiritilmaydi.
- App shell faqat ishlaydigan amallarni ko‘rsatadi; hali ko‘chirilmagan modul “tayyor” deb ko‘rsatilmaydi.
- Har bir task alohida qizil/yashil test sikli va alohida commit bilan bajariladi.
- `scripts/verify_phase1.py` dagi foydalanuvchiga tegishli local o‘zgarish bu branch commitlariga qo‘shilmaydi.

---

## File Map

- `scripts/export_phase3_screen_inventory.py`: v1656 HTML’dan unique ekranlarni, guruhlarni va boshlang‘ich migratsiya holatini chiqaradi.
- `docs/architecture/legacy-v1656-screens.json`: 98 ta legacy ekran uchun machine-readable committed snapshot.
- `docs/phase3/legacy-parity.md`: kritik oqimlar, holat lug‘ati va keyingi migratsiya tartibi uchun inson o‘qiydigan parity xaritasi.
- `tests/test_phase3_screen_inventory.py`: exporter, snapshot va BUILD contractlarini real fayllar bilan tekshiradi.
- `frontend/src/app/design-tokens.css`: v1656’dagi rang, shrift, radius va soya tokenlari.
- `frontend/src/app/AppShell.tsx`: Koprik brand header’i va sahifa kontenti uchun umumiy responsive qobiq.
- `frontend/src/app/AppShell.test.tsx`: brand, session action va accessibility contractlari.
- `frontend/src/app/SessionStatus.tsx`: loading va retryable global xato holatlari.
- `frontend/src/app/SessionStatus.test.tsx`: loading/error/retry xulqini tekshiradi.
- `frontend/src/app/App.tsx`: mavjud session bootstrap, auth va profil komponentlarini yangi shell ichiga joylashtiradi.
- `frontend/src/app/App.test.tsx`: guest, user, business, retry va logout regressiyasini tekshiradi.
- `frontend/src/auth/AuthFlow.tsx`: “Phase 2” texnik yozuvini foydalanuvchi-facing Koprik matniga almashtiradi.
- `frontend/src/app/App.css`: v1656 tokenlariga tayangan auth/profile responsive layout.
- `scripts/verify_phase3a.py`: Phase 2, legacy inventory, frontend test va frontend build gate’larini bir buyruqda bajaradi.
- `.github/workflows/phase1-ci.yml`: CI’da `verify_phase3a.py`ni ishga tushiradi.
- `docs/deploy-phase3a-staging.md`: Railway acceptance, manual parity va rollback runbook’i.

### Task 1: 98 ta legacy ekran inventarini contract sifatida muzlatish

**Files:**
- Create: `scripts/export_phase3_screen_inventory.py`
- Create: `tests/test_phase3_screen_inventory.py`
- Create: `docs/architecture/legacy-v1656-screens.json`

**Interfaces:**
- Consumes: `static/index.html`.
- Produces: `collect_screen_inventory(root: Path) -> dict[str, object]`.
- Produces: `write_screen_inventory(root: Path, destination: Path) -> None`.

- [ ] **Step 1: Exporter contract testini yozish**

`tests/test_phase3_screen_inventory.py`:

```python
import json
from pathlib import Path
import unittest

from scripts.export_phase3_screen_inventory import collect_screen_inventory


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/architecture/legacy-v1656-screens.json"


class Phase3ScreenInventoryTests(unittest.TestCase):
    def test_committed_snapshot_matches_v1656_dom(self):
        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(collect_screen_inventory(ROOT), expected)

    def test_inventory_keeps_all_98_unique_screens(self):
        inventory = collect_screen_inventory(ROOT)
        names = [screen["name"] for screen in inventory["screens"]]

        self.assertEqual(inventory["build"], "v1656")
        self.assertEqual(inventory["screen_count"], 98)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("home", names)
        self.assertIn("login", names)
        self.assertIn("cabinet", names)
        self.assertIn("ucab", names)
        self.assertIn("staff-home", names)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test qizil ekanini tekshirish**

Run:

```bash
python -m unittest tests.test_phase3_screen_inventory -v
```

Expected: FAIL, chunki exporter va snapshot hali mavjud emas.

- [ ] **Step 3: Deterministik exporter yozish**

`scripts/export_phase3_screen_inventory.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import sys


BUILD_RE = re.compile(r"<!-- BUILD: (v\d+) -->")
SCREEN_RE = re.compile(r'data-screen="([^"]+)"')
AUTH_SCREENS = {"login", "register", "regform"}
STAFF_SCREENS = {"staff-login", "staff-home"}
PUBLIC_SCREENS = {
    "home",
    "taxi-call",
    "listings",
    "catalog",
    "cat-types",
    "loc",
    "list",
    "business",
    "user-page",
    "person",
    "help",
}


def screen_group(name: str) -> str:
    if name in AUTH_SCREENS:
        return "auth"
    if name in STAFF_SCREENS:
        return "staff"
    if name == "cabinet" or name.startswith("cab-"):
        return "business-cabinet"
    if name == "ucab" or name.startswith("ucab-"):
        return "user-cabinet"
    if name in PUBLIC_SCREENS:
        return "public"
    return "shared"


def collect_screen_inventory(root: Path) -> dict[str, object]:
    source = (root / "static/index.html").read_text(encoding="utf-8")
    build_match = BUILD_RE.search(source)
    names = list(dict.fromkeys(SCREEN_RE.findall(source)))
    return {
        "build": build_match.group(1) if build_match else "",
        "screen_count": len(names),
        "screens": [
            {
                "name": name,
                "group": screen_group(name),
                "phase3_status": "legacy",
            }
            for name in names
        ],
    }


def write_screen_inventory(root: Path, destination: Path) -> None:
    destination.write_text(
        json.dumps(
            collect_screen_inventory(root),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    destination = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else root / "docs/architecture/legacy-v1656-screens.json"
    )
    write_screen_inventory(root, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Snapshotni exporter bilan yaratish**

Run:

```bash
python scripts/export_phase3_screen_inventory.py
```

Expected: `docs/architecture/legacy-v1656-screens.json` yo‘li chiqadi va JSON ichida `screen_count` qiymati `98` bo‘ladi.

- [ ] **Step 5: Inventory testini yashil qilish**

Run:

```bash
python -m unittest tests.test_phase3_screen_inventory -v
```

Expected: 2 PASS.

- [ ] **Step 6: Mavjud v1656 contractlarini qayta tekshirish**

Run:

```bash
python -m unittest \
  tests.test_legacy_inventory_contract \
  tests.test_approved_home_catalog_contract \
  -v
```

Expected: 6 PASS va `static/index.html` o‘zgarmagan.

- [ ] **Step 7: Commit**

```bash
git add \
  scripts/export_phase3_screen_inventory.py \
  tests/test_phase3_screen_inventory.py \
  docs/architecture/legacy-v1656-screens.json
git commit -m "test: freeze Phase 3 legacy screen inventory"
```

### Task 2: Inson o‘qiydigan parity xaritasini qo‘shish

**Files:**
- Create: `docs/phase3/legacy-parity.md`

**Interfaces:**
- Consumes: Task 1’dagi ekran guruhlari.
- Produces: to‘rtta qat’iy holat — `legacy`, `in-progress`, `staging-accepted`, `production-accepted`.

- [ ] **Step 1: Parity hujjatini yozish**

`docs/phase3/legacy-parity.md` quyidagi bo‘limlarga ega bo‘lsin:

```markdown
# Koprik v1656 → Phase 3 parity xaritasi

## Holat lug‘ati

- `legacy`: faqat amaldagi v1656 production interfeysida ishlaydi.
- `in-progress`: React stagingga ko‘chirilmoqda, qabul qilinmagan.
- `staging-accepted`: stagingda avtomatik va qo‘lda qabul qilingan.
- `production-accepted`: production cutover’dan keyin kuzatuvdan o‘tgan.

## Kritik oqimlar

| Oqim | Boshlang‘ich holat | Phase 3 navbati |
| --- | --- | --- |
| Bosh sahifa → qidiruv → katalog → lokatsiya | legacy | Phase 3B |
| Kirish → Telegram kodi → sessiya | in-progress | Phase 3A |
| Oddiy kabinet → profil → avatar | in-progress | Phase 3A |
| Biznes kabinet → profil → logotip | in-progress | Phase 3A |
| E’lon → buyurtma → to‘lov | legacy | Phase 3C |
| Staff va admin oqimlari | legacy | Phase 3E |

## Qabul qoidasi

Ekran faqat avtomatik test, desktop/mobil qo‘lda tekshiruv va rollback
yo‘li tasdiqlangandan keyin `staging-accepted` holatiga o‘tadi.
```

- [ ] **Step 2: Hujjatni inventar bilan qo‘lda solishtirish**

Run:

```bash
python scripts/export_phase3_screen_inventory.py /tmp/phase3-screens.json
python -m unittest tests.test_phase3_screen_inventory -v
```

Expected: exporter 98 ta ekranni qayta chiqaradi va inventory testlari
2 PASS. Hujjatdagi Phase 3A/3B/3C/3E navbati approved dizayn bilan mos.

- [ ] **Step 3: Commit**

```bash
git add docs/phase3/legacy-parity.md
git commit -m "docs: map Phase 3 legacy parity gates"
```

### Task 3: v1656 dizayn tokenlari va umumiy AppShell

**Files:**
- Create: `frontend/src/app/design-tokens.css`
- Create: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/app/AppShell.test.tsx`
- Modify: `frontend/src/app/App.css`

**Interfaces:**
- Produces: `AppShell({ children, authenticated, onCabinet, onLogin })`.
- Preserves: semantic `<header role="banner">` va `<main>` content.

- [ ] **Step 1: AppShell component testini yozish**

`frontend/src/app/AppShell.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";


describe("AppShell", () => {
  it("shows the Koprik brand and a working login action for guests", async () => {
    const onLogin = vi.fn();
    render(
      <AppShell authenticated={false} onLogin={onLogin}>
        <p>Kontent</p>
      </AppShell>,
    );

    expect(screen.getByRole("banner")).toHaveTextContent("Koprik");
    await userEvent.click(screen.getByRole("button", { name: "Kirish" }));
    expect(onLogin).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kabinet" }))
      .not.toBeInTheDocument();
  });

  it("shows the cabinet action only for authenticated sessions", async () => {
    const onCabinet = vi.fn();
    render(
      <AppShell authenticated onCabinet={onCabinet}>
        <p>Kontent</p>
      </AppShell>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Kabinet" }));
    expect(onCabinet).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test qizil ekanini tekshirish**

Run:

```bash
cd frontend
npm ci
npm test -- src/app/AppShell.test.tsx
```

Expected: FAIL, chunki `AppShell.tsx` hali mavjud emas.

- [ ] **Step 3: v1656 tokenlarini ajratish**

`frontend/src/app/design-tokens.css`:

```css
:root {
  --koprik-bg: #f4f7f5;
  --koprik-card: #ffffff;
  --koprik-ink: #11201b;
  --koprik-soft: #5c6e66;
  --koprik-line: #e4ebe7;
  --koprik-primary: #0e8c84;
  --koprik-primary-ink: #ffffff;
  --koprik-primary-tint: #e2f3f1;
  --koprik-amber: #f0a21b;
  --koprik-shadow:
    0 1px 2px rgb(16 40 33 / 4%),
    0 8px 24px rgb(16 40 33 / 6%);
  --koprik-radius: 18px;
  --koprik-font-display:
    "Plus Jakarta Sans", Inter, ui-sans-serif, system-ui, sans-serif;
  --koprik-font-body:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}
```

`frontend/src/app/App.css` birinchi qatoriga qo‘shing:

```css
@import "./design-tokens.css";
```

- [ ] **Step 4: Minimal AppShell componentini yozish**

`frontend/src/app/AppShell.tsx`:

```tsx
import type { ReactNode } from "react";


type AppShellProps = {
  children: ReactNode;
  authenticated: boolean;
  onCabinet?: () => void;
  onLogin?: () => void;
};


export function AppShell({
  children,
  authenticated,
  onCabinet,
  onLogin,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <span className="app-shell__brand">Koprik</span>
        <nav aria-label="Akkaunt menyusi">
          {authenticated ? (
            <button type="button" onClick={onCabinet}>Kabinet</button>
          ) : (
            <button type="button" onClick={onLogin}>Kirish</button>
          )}
        </nav>
      </header>
      {children}
    </div>
  );
}
```

- [ ] **Step 5: AppShell CSS’ini v1656 tokenlari bilan yozish**

`frontend/src/app/App.css` ichidagi global rang va header qoidalarini
quyidagi contractga o‘tkazing:

```css
:root {
  font-family: var(--koprik-font-body);
  color: var(--koprik-ink);
  background: var(--koprik-bg);
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: var(--koprik-bg);
}

.app-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 68px;
  padding: 0 clamp(16px, 4vw, 48px);
  border-bottom: 1px solid var(--koprik-line);
  background: var(--koprik-card);
}

.app-shell__brand {
  color: var(--koprik-ink);
  font-family: var(--koprik-font-display);
  font-size: clamp(26px, 2.5vw, 34px);
  font-weight: 800;
  letter-spacing: -0.04em;
}

.app-shell__header button {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--koprik-line);
  border-radius: 12px;
  color: var(--koprik-primary);
  background: var(--koprik-card);
  font-weight: 800;
  cursor: pointer;
  box-shadow: var(--koprik-shadow);
}
```

- [ ] **Step 6: Component testini yashil qilish**

Run:

```bash
cd frontend
npm test -- src/app/AppShell.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 7: Commit**

```bash
git add \
  frontend/src/app/design-tokens.css \
  frontend/src/app/AppShell.tsx \
  frontend/src/app/AppShell.test.tsx \
  frontend/src/app/App.css
git commit -m "feat: add v1656 React app shell"
```

### Task 4: Loading va global xato holatini alohida componentga ajratish

**Files:**
- Create: `frontend/src/app/SessionStatus.tsx`
- Create: `frontend/src/app/SessionStatus.test.tsx`
- Modify: `frontend/src/app/App.css`

**Interfaces:**
- Produces: `SessionStatus({ state: "loading" | "error", onRetry? })`.
- Preserves: o‘zbekcha xato matni va retry amali.

- [ ] **Step 1: SessionStatus testlarini yozish**

`frontend/src/app/SessionStatus.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SessionStatus } from "./SessionStatus";


describe("SessionStatus", () => {
  it("announces a loading state", () => {
    render(<SessionStatus state="loading" />);
    expect(screen.getByRole("status")).toHaveTextContent("Yuklanmoqda…");
  });

  it("offers one working retry action for a network error", async () => {
    const onRetry = vi.fn();
    render(<SessionStatus state="error" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Server bilan bog‘lanib bo‘lmadi.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Qayta urinish" }),
    );
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Test qizil ekanini tekshirish**

Run:

```bash
cd frontend
npm test -- src/app/SessionStatus.test.tsx
```

Expected: FAIL, chunki `SessionStatus.tsx` hali mavjud emas.

- [ ] **Step 3: Minimal componentni yozish**

`frontend/src/app/SessionStatus.tsx`:

```tsx
export function SessionStatus({
  state,
  onRetry,
}: {
  state: "loading" | "error";
  onRetry?: () => void;
}) {
  if (state === "loading") {
    return (
      <main className="session-panel session-panel--message" role="status">
        Yuklanmoqda…
      </main>
    );
  }
  return (
    <main
      className="session-panel session-panel--message"
      role="alert"
    >
      <p>Server bilan bog‘lanib bo‘lmadi.</p>
      <button type="button" onClick={onRetry}>Qayta urinish</button>
    </main>
  );
}
```

- [ ] **Step 4: Testni yashil qilish**

Run:

```bash
cd frontend
npm test -- src/app/SessionStatus.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  frontend/src/app/SessionStatus.tsx \
  frontend/src/app/SessionStatus.test.tsx \
  frontend/src/app/App.css
git commit -m "refactor: isolate session status states"
```

### Task 5: Mavjud auth va profil oqimlarini yangi shell ichiga ulash

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/auth/AuthFlow.tsx`
- Modify: `frontend/src/auth/AuthFlow.test.tsx`
- Modify: `frontend/src/app/App.css`

**Interfaces:**
- Consumes: Task 3’dagi `AppShell`.
- Consumes: Task 4’dagi `SessionStatus`.
- Preserves: `api.getSession()`, `401 -> guest`, retry, ordinary/business profile va logout.

- [ ] **Step 1: App regressiya testlarini kengaytirish**

`frontend/src/app/App.test.tsx` ichiga quyidagi xulqlarni qo‘shing:

```tsx
  it("shows one guest login action inside the v1656 shell", async () => {
    const api = {
      getSession: vi.fn().mockRejectedValue(
        Object.assign(new Error("unauthorized"), { status: 401 }),
      ),
    };

    render(<App api={api} />);

    expect(await screen.findByRole("banner")).toHaveTextContent("Koprik");
    expect(
      screen.getByRole("heading", { name: "Koprik’ga kirish" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Kirish")).toHaveLength(2);
  });

  it("keeps the authenticated business profile under the cabinet action", async () => {
    const api = {
      getSession: vi.fn().mockResolvedValue({
        account_id: 7,
        account_type: "business",
        name: "Turon",
        login: "b_turon",
        csrf_token: "csrf",
        expires_at: "2026-08-27T08:00:00Z",
      }),
    };

    render(<App api={api} />);

    expect(
      await screen.findByRole("heading", { name: "Biznes kabinet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kabinet" }))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kirish" }))
      .not.toBeInTheDocument();
  });
```

Existing business testni ikkinchi test bilan birlashtiring; bir xil
scenario ikki marta takrorlanmasin.

- [ ] **Step 2: AuthFlow texnik label contractini yozish**

`frontend/src/auth/AuthFlow.test.tsx` ichidagi choice ekran testiga
quyidagilarni qo‘shing:

```tsx
expect(screen.queryByText("Koprik Phase 2")).not.toBeInTheDocument();
expect(screen.getByText("Koprik")).toBeInTheDocument();
```

- [ ] **Step 3: Testlar qizil ekanini tekshirish**

Run:

```bash
cd frontend
npm test -- src/app/App.test.tsx src/auth/AuthFlow.test.tsx
```

Expected: FAIL, chunki `App` hali `AppShell`/`SessionStatus`dan
foydalanmaydi va `AuthFlow` “Koprik Phase 2” yozuvini ko‘rsatadi.

- [ ] **Step 4: App’ni yangi componentlar bilan yig‘ish**

`frontend/src/app/App.tsx`:

- eski inline `<header>`ni olib tashlang;
- barcha contentni `<AppShell>` ichiga joylashtiring;
- `authenticated` qiymatini `session.status === "user" || session.status === "business"` orqali bering;
- loading holatida `<SessionStatus state="loading" />` ishlating;
- network xatosida `<SessionStatus state="error" onRetry={...} />` ishlating;
- guest auth, user profile va business profile branchlarini o‘zgartirmang;
- header’dagi `Kirish` amali auth formaning birinchi fokuslanadigan
  tugmasiga fokus bersin;
- header’dagi `Kabinet` amali profil sarlavhasiga fokus bersin.

Fokus uchun `App`da `contentRef` yarating va `AppShell` callbacklarida
`contentRef.current?.focus()` chaqiring. Auth/profile content wrapper’iga
`tabIndex={-1}` va `ref={contentRef}` bering.

- [ ] **Step 5: AuthFlow labelini foydalanuvchi matniga almashtirish**

`frontend/src/auth/AuthFlow.tsx`:

```tsx
<p className="session-panel__eyebrow">Koprik</p>
```

“Koprik Phase 2” matni frontend UI’da qolmasin.

- [ ] **Step 6: Auth/profile CSS’ini v1656 tokenlariga o‘tkazish**

`frontend/src/app/App.css` ichida:

- eski `#07152f`, `#123a72`, `#edf3ff`, `#b9c3d3` ranglarini tegishli
  `--koprik-*` tokenlariga almashtiring;
- primary tugmalar `--koprik-primary`;
- secondary tugmalar `--koprik-primary-tint`;
- form border’lari `--koprik-line`;
- card/background `--koprik-card`;
- focus ring `--koprik-amber`;
- desktop profile ikki ustun va `680px` ostida bir ustun contractini
  saqlang.

- [ ] **Step 7: Frontend testlarini yashil qilish**

Run:

```bash
cd frontend
npm test
```

Expected: barcha frontend testlari PASS.

- [ ] **Step 8: TypeScript va production buildni tekshirish**

Run:

```bash
cd frontend
npm run build
```

Expected: `tsc --noEmit` va `vite build` exit code 0.

- [ ] **Step 9: Commit**

```bash
git add \
  frontend/src/app/App.tsx \
  frontend/src/app/App.test.tsx \
  frontend/src/auth/AuthFlow.tsx \
  frontend/src/auth/AuthFlow.test.tsx \
  frontend/src/app/App.css
git commit -m "feat: place Phase 2 flows in v1656 shell"
```

### Task 6: Phase 3A verification gate va CI

**Files:**
- Create: `scripts/verify_phase3a.py`
- Modify: `.github/workflows/phase1-ci.yml`

**Interfaces:**
- Consumes: `scripts/verify_phase2.py`.
- Produces: bitta `python scripts/verify_phase3a.py` release gate’i.

- [ ] **Step 1: Verification scriptini yozish**

`scripts/verify_phase3a.py`:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    run([sys.executable, "scripts/verify_phase2.py"])
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_phase3_screen_inventory",
            "-v",
        ]
    )
    run(["npm", "test"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)
    print("Phase 3A: PASS")
    print("Legacy screens: 98")
    print("BUILD: v1656")
    print("static/index.html: 14091 qator")
    print("Production: o‘zgarmadi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: CI’ni yangi gate’ga o‘tkazish**

`.github/workflows/phase1-ci.yml`:

- workflow `name` qiymatini `phase3-legacy-ui-integration` qiling;
- oxirgi step nomini `Verify Phase 3A` qiling;
- oxirgi buyruqni `python scripts/verify_phase3a.py` qiling;
- Postgres, Redis, Python, Node va migration step’larini o‘zgartirmang.

- [ ] **Step 3: To‘liq Phase 3A gate’ni real dependencylar bilan bajarish**

Run:

```bash
python scripts/verify_phase3a.py
```

Expected yakun:

```text
Phase 3A: PASS
Legacy screens: 98
BUILD: v1656
static/index.html: 14091 qator
Production: o‘zgarmadi
```

- [ ] **Step 4: CI konfiguratsiyasini sintaktik tekshirish**

Run:

```bash
python -c "from pathlib import Path; import yaml; yaml.safe_load(Path('.github/workflows/phase1-ci.yml').read_text(encoding='utf-8')); print('workflow YAML: PASS')"
```

Expected: `workflow YAML: PASS`.

- [ ] **Step 5: Commit**

```bash
git add \
  scripts/verify_phase3a.py \
  .github/workflows/phase1-ci.yml
git commit -m "ci: verify Phase 3A legacy shell"
```

### Task 7: Railway staging acceptance va rollback runbook

**Files:**
- Create: `docs/deploy-phase3a-staging.md`

**Interfaces:**
- Produces: code yoki secret talab qilmaydigan, takrorlanuvchi manual acceptance checklist.

- [ ] **Step 1: Runbookni yozish**

`docs/deploy-phase3a-staging.md` quyidagi aniq ketma-ketlikni bersin:

1. GitHub checks yashil ekanini tekshirish.
2. Railway `frontend-staging` deployment successful ekanini tekshirish.
3. `VITE_API_BASE_URL` qiymati `api-staging` HTTPS domainiga qaraganini
   tekshirish.
4. `api-staging /readyz` statusi `200` ekanini tekshirish.
5. **Desktop qabul:** 1280 px kenglikda header, guest auth, oddiy kabinet
   va biznes kabinetni tekshirish.
6. **Mobil qabul:** 390 px kenglikda gorizontal scroll yo‘qligi, formalar
   bir ustun va tugmalar ko‘rinishini tekshirish.
7. **Auth qabul:** login → Telegram kod → kabinet → refresh → logout.
8. **Profil qabul:** oddiy profil/avatar va biznes profil/logotipni
   saqlash, refreshdan keyin qayta ko‘rinishini tekshirish.
9. Legacy `koprik.uz` alohida tabda v1656 bosh sahifa, qidiruv, katalog
   va kabinet bilan ishlashda davom etishini tekshirish.
10. **Rollback:** `frontend-staging`dagi oxirgi successful deploymentni
    qayta tanlash; `web` va `koprik.uz` o‘zgarmaydi.

- [ ] **Step 2: Runbookni approved Railway konfiguratsiyasi bilan solishtirish**

Qo‘lda tekshiring:

- staging servis nomlari `frontend-staging` va `api-staging`;
- frontend API manzili faqat `VITE_API_BASE_URL` orqali beriladi;
- acceptance desktop, mobil, auth va ikkala profilni qamrab oladi;
- rollback production `web` yoki `koprik.uz`ni o‘zgartirmaydi.

- [ ] **Step 3: Yakuniy verification**

Run:

```bash
python scripts/verify_phase3a.py
git diff --check
git status --short
```

Expected:

- Phase 3A verification PASS;
- whitespace xatosi yo‘q;
- faqat rejalashtirilgan Phase 3A fayllari commit qilingan;
- `static/index.html` diff’da yo‘q.

- [ ] **Step 4: Commit**

```bash
git add docs/deploy-phase3a-staging.md
git commit -m "docs: add Phase 3A staging acceptance"
```

## Phase 3A Exit Gate

- [ ] `docs/architecture/legacy-v1656-screens.json` 98 ta unique ekranni saqlaydi.
- [ ] `static/index.html` BUILD v1656 va 14 091 qator bo‘lib qoladi.
- [ ] React auth/profile oqimlari v1656 tokenli AppShell ichida ishlaydi.
- [ ] Guest, user, business, loading, retry va logout testlari yashil.
- [ ] Frontend production build yashil.
- [ ] GitHub Actions `verify_phase3a.py` bilan yashil.
- [ ] Desktop va mobil staging qabul checklisti bajarilgan.
- [ ] Production `web` va `koprik.uz` o‘zgarmagan.
- [ ] Phase 3B uchun bosh sahifa/qidiruv/katalog/lokatsiya migratsiya rejasi alohida yozilishi mumkin.
