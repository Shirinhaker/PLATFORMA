# Approved Home and Catalog UI Installation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the approved Koprik desktop/mobile home redesign and two-level catalog flow into the existing v1629 FastAPI frontend without changing backend behavior.

**Architecture:** Keep the existing monolithic `static/index.html`, live map, advertisements, stories, listings, search APIs, and catalog data. Replace only the public header/home discovery markup and its responsive CSS, then reuse the existing `catalog` and `cat-types` screens for the two-step catalog interaction.

**Tech Stack:** FastAPI static HTML, CSS, vanilla JavaScript, Python `unittest`, Leaflet.

## Global Constraints

- The brand is exactly `Koprik`; clicking it returns to the home screen.
- There is no separate `Bosh sahifa` navigation item.
- `E’lonlar` is visible in the public header on desktop and mobile and opens the listings screen.
- The home search block uses the approved title, separate search row, and `Katalog bo‘yicha` trigger.
- Catalog step one shows scope controls and 20 activity directions; selecting one opens its activity types.
- Native horizontal scrollbar chrome must not be visible.
- Preserve all existing backend/API behavior and uploaded source ZIP.

---

### Task 1: Public header contract

**Files:**
- Modify: `tests/test_web_home_frontend_contract.py`
- Modify: `tests/test_mobile_home_listings_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: existing `openWebHome()` and `openWebListings()` functions.
- Produces: `#webBrandBtn`, `#webListingsBtn`, and their click bindings.

- [ ] **Step 1: Write failing tests** for `Koprik`, removal of `#webHomeBtn`, and mobile-visible `E’lonlar`.
- [ ] **Step 2: Run tests and verify the old header fails the new contract.**
- [ ] **Step 3: Update header markup, styles, and bindings minimally.**
- [ ] **Step 4: Run the targeted tests and verify they pass.**

### Task 2: Approved home search composition

**Files:**
- Create: `tests/test_approved_home_catalog_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `openWebSearchType(type)`, `runSearch(q)`, and the live `#leafletMap`.
- Produces: `#homeQueryInput`, `#homeQueryClear`, `#homeSearchSubmit`, `#homeCatalogOpen`, and category shortcuts.

- [ ] **Step 1: Write failing tests** for the approved title, search controls, catalog trigger, location copy, and category shortcuts.
- [ ] **Step 2: Run the tests and verify missing controls fail.**
- [ ] **Step 3: Add accessible HTML/CSS and JavaScript bindings.**
- [ ] **Step 4: Run the targeted tests and verify they pass.**

### Task 3: Two-level catalog and responsive layout

**Files:**
- Modify: `tests/test_approved_home_catalog_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `YON`, `renderYon()`, `openYon(i)`, `openType(t)`, `nav(screen)`.
- Produces: responsive catalog list/cards and activity type selection using the existing navigation stack.

- [ ] **Step 1: Add failing tests** for 20 directions, scope controls, second-step rendering, mobile/desktop breakpoints, and hidden scrollbar chrome.
- [ ] **Step 2: Run the tests and verify they fail for the missing design contract.**
- [ ] **Step 3: Restyle the existing catalog and cat-types screens and ensure activity selection updates results.**
- [ ] **Step 4: Run all frontend contract tests.**

### Task 4: Runtime and visual verification

**Files:**
- Create: `design-qa.md`
- Create: `Platforma_v1629_approved_ui_installed.zip` outside the source folder.

**Interfaces:**
- Consumes: modified FastAPI frontend.
- Produces: verified responsive build and installable archive.

- [ ] **Step 1: Run the full available unit-test suite and record dependency-only baseline exclusions.**
- [ ] **Step 2: Start the actual application preview and inspect desktop/mobile layouts and primary interactions in the cloud browser.**
- [ ] **Step 3: Compare the rendered states against the approved references, fix P0–P2 issues, and write `design-qa.md` with `final result: passed`.**
- [ ] **Step 4: Package the modified project as a new ZIP without overwriting the uploaded source archive.**
