# Ommaviy sahifalarda sessiya xatosidan himoya Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sessiya API vaqtincha ishlamasa ham `home`, `location`, `catalog` va `category` sahifalarini ishlatish mumkin bo‘lsin, xato va qayta urinish esa faqat `auth` yoki `cabinet` ko‘rinishida chiqsin.

**Architecture:** `App` public shell va public sahifalarni sessiya bootstrap holatidan ajratadi. 401 mavjud mehmon holatini saqlaydi; tarmoq yoki 5xx xatosi mehmon fallback’ini va retry holatini saqlaydi, account ko‘rinishlari esa shu xatoni bloklovchi `SessionStatus` orqali ko‘rsatadi.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite

## Global Constraints

- Faqat `frontend/src/app/App.tsx` va `frontend/src/app/App.test.tsx` o‘zgartiriladi.
- Backend API, PostgreSQL, Redis, R2, profil formalar, public sahifalar dizayni va marshrutlar o‘zgarmaydi.
- `home`, `location`, `catalog` va `category` sessiya yuklanayotganda yoki sessiya so‘rovi xato berganda ham render qilinadi.
- 401 javobi mehmon holatini saqlaydi.
- Tarmoq yoki 5xx xatosida public header `Kirish` holatini ko‘rsatadi.
- `auth` yoki `cabinet` ko‘rinishida `Server bilan bog‘lanib bo‘lmadi` va `Qayta urinish` ko‘rsatiladi.
- `Qayta urinish` haqiqiy sessiyani qayta yuklaydi.
- Mavjud login, profil, logout va public navigatsiya xatti-harakatlari regressiyasiz qoladi.

---

### Task 1: Sessiya bootstrap xatosini public sahifalardan ajratish

**Files:**
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/app/App.tsx`

**Interfaces:**
- Consumes: `AppApi.getSession(): Promise<SessionIdentity>`, `navigation.view`, mavjud `SessionStatus`
- Produces: public sahifalarda bloklamaydigan session fallback; `auth`/`cabinet` uchun retryable error

- [ ] **Step 1: Public `Manzil` regressiya testini yozish**

`frontend/src/app/App.test.tsx`dagi eski global network-error testini quyidagi test bilan almashtiring:

```tsx
it("keeps public location usable when session bootstrap fails", async () => {
  const user = userEvent.setup();
  const api = {
    getSession: vi.fn().mockRejectedValue(new TypeError("offline")),
  };

  render(<App api={api} />);

  expect(
    await screen.findByRole("heading", {
      name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
    }),
  ).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Manzil" }));

  expect(
    screen.getByRole("heading", { name: "Hududingizni tanlang" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Test joriy xatoni ushlashini tasdiqlash**

Run:

```bash
cd frontend
npm test -- src/app/App.test.tsx
```

Expected: yangi test FAIL bo‘ladi, chunki joriy `App.tsx` public home o‘rniga global `SessionStatus state="error"` render qiladi.

- [ ] **Step 3: Account ko‘rinishidagi xato va retry testini yozish**

Shu test fayliga quyidagi testni qo‘shing:

```tsx
it("keeps the retryable session error on account views", async () => {
  const user = userEvent.setup();
  const api = {
    getSession: vi.fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(userIdentity),
  };

  render(<App api={api} />);

  await screen.findByRole("heading", {
    name: "Kerakli mahsulot va xizmatni yaqiningizdan toping",
  });
  await user.click(screen.getByRole("button", { name: "Kirish" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Server bilan bog‘lanib bo‘lmadi.",
  );

  await user.click(screen.getByRole("button", { name: "Qayta urinish" }));

  expect(
    await screen.findByRole("heading", { name: "Oddiy kabinet" }),
  ).toBeInTheDocument();
  expect(api.getSession).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 4: Minimal session fallback implementatsiyasini yozish**

`frontend/src/app/App.tsx`da `authenticated` hisobidan oldin account ko‘rinishini aniqlang:

```tsx
const accountView = (
  navigation.view === "auth" || navigation.view === "cabinet"
);
```

`getSession()`ning 401 bo‘lmagan `.catch()` tarmog‘ida sessiyani mehmon fallback’iga o‘tkazib, retry xatosini saqlang:

```tsx
setSession({ status: "guest" });
setFailed(true);
```

`AppShell` ichidagi global render shartini account ko‘rinishiga cheklang:

```tsx
{failed && accountView ? (
  <SessionStatus
    state="error"
    onRetry={() => setAttempt((value) => value + 1)}
  />
) : renderPublicContent()}
```

`renderAccount()`ning mavjud `session.status === "loading"` tarmog‘i account view retry paytida loading holatini ko‘rsatishda davom etadi. Public view esa sessiya yuklanayotganida ham `renderPublicContent()` orqali darhol ochiladi.

- [ ] **Step 5: Maqsadli testlarni yashil holatga keltirish**

Run:

```bash
cd frontend
npm test -- src/app/App.test.tsx
```

Expected: `App.test.tsx`dagi barcha testlar PASS; yangi public-location testi global error ko‘rmasligi, account testi esa error va retry natijasini tasdiqlashi kerak.

- [ ] **Step 6: To‘liq frontend regressiya va build tekshiruvini bajarish**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: barcha frontend testlari PASS va TypeScript/Vite production build muvaffaqiyatli tugaydi.

- [ ] **Step 7: O‘zgarishni bitta mantiqiy commit sifatida saqlash**

```bash
git add frontend/src/app/App.tsx frontend/src/app/App.test.tsx
git commit -m "fix: keep public pages available during session outage"
```

### Task 2: GitHub va Railway’da integratsiyani tasdiqlash

**Files:**
- No source file changes

**Interfaces:**
- Consumes: Task 1 commit, GitHub CI, Railway frontend staging auto-deploy
- Produces: reviewable PR va ishlayotgan staging dalili

- [ ] **Step 1: Branchni push qilib draft PR yaratish**

```bash
git push -u origin codex/fix-public-session-fallback
gh pr create --draft \
  --base main \
  --head codex/fix-public-session-fallback \
  --title "Fix public pages during session API outages" \
  --body "Public sahifalarni session bootstrap xatosidan ajratadi; account view error va retryni saqlaydi."
```

- [ ] **Step 2: GitHub CI’ni tekshirish**

Run:

```bash
gh pr checks --watch
```

Expected: barcha required checklar PASS.

- [ ] **Step 3: PRni merge qilish va Railway deployni kutish**

GitHub’da PRni ready for review qiling, merge qiling va `frontend-staging` service yangi `main` commitni muvaffaqiyatli deploy qilganini tekshiring.

- [ ] **Step 4: Staging’da public regressiyani qo‘lda tasdiqlash**

1. `frontend-staging` public URL’ni oching.
2. `Manzil` tugmasini bosing.
3. `Hududingizni tanlang` sarlavhasi va manzil formasi ochilganini tekshiring.
4. Public header, bosh sahifa, katalog va category navigatsiyasi ishlashini tekshiring.
5. Railway API sog‘lom paytda `Kirish` va `Kabinet` oqimi avvalgidek ishlashini tekshiring.

Expected: public sahifalar global `Server bilan bog‘lanib bo‘lmadi` ekraniga almashtirilmaydi; account xatti-harakati regressiyasiz qoladi.
