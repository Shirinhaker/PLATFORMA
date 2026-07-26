# Ko‘prik Auth and Profile Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved dark Ko‘prik visual system to location, login, registration, employee login, and profile/cabinet screens without changing their existing behavior.

**Architecture:** Keep the monolithic `static/index.html` architecture and all current DOM IDs/event bindings. Add one scoped `v1647` presentation layer and only the minimal semantic wrappers/classes needed by the selected screens; preserve backend endpoints and data models.

**Tech Stack:** Static HTML/CSS/JavaScript, FastAPI, Leaflet, Python `unittest`.

## Global Constraints

- Visual-only redesign; do not change API payloads, database schema, authentication, Telegram verification, role separation, or staff permissions.
- Preserve ordinary/business actor separation, profile district privacy, story/subscription independence, and existing map/search behavior.
- Support phone `<720px`, tablet `720–1079px`, and desktop `>=1080px`.
- Preserve every existing element ID referenced by JavaScript or tests.
- Use the supplied design comparison images and prototype files as the visual source of truth.
- Run the full existing test suite after each independently testable task.

---

### Task 1: Add the v1647 design contract

**Files:**
- Create: `tests/test_auth_profile_design_v1647_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: existing screen names and stable DOM IDs.
- Produces: scoped hooks `koprik-flow-shell`, `koprik-auth-shell`, `koprik-location-shell`, `koprik-profile-surface`, and `data-ui-release="v1647"`.

- [ ] **Step 1: Write the failing contract test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AuthProfileDesignV1647ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    def test_v1647_design_hooks_exist(self):
        for token in (
            'data-ui-release="v1647"',
            ".koprik-flow-shell",
            ".koprik-auth-shell",
            ".koprik-location-shell",
            ".koprik-profile-surface",
        ):
            self.assertIn(token, self.html)

    def test_existing_behavior_ids_are_preserved(self):
        for token in (
            'id="locSave"',
            'id="passwordLoginGo"',
            'id="loginVerify"',
            'id="goRegister"',
            'id="slEnter"',
            'id="cabDashboardMetrics"',
            'id="ucabDashboardMetrics"',
        ):
            self.assertIn(token, self.html)
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract -v`

Expected: FAIL because `data-ui-release="v1647"` and the new scoped hooks do not exist.

- [ ] **Step 3: Add the release hook and shared CSS surface**

Add `data-ui-release="v1647"` to `<html>` and add a scoped CSS block that defines:

```css
[data-ui-release="v1647"] .koprik-flow-shell {
  width:min(100%,760px);
  margin:0 auto;
  border:1px solid var(--line);
  border-radius:24px;
  background:var(--card);
  box-shadow:var(--shadow-lg);
}
[data-ui-release="v1647"] .koprik-auth-shell {
  max-width:560px;
  padding:clamp(18px,4vw,34px);
}
[data-ui-release="v1647"] .koprik-profile-surface {
  border:1px solid var(--line);
  background:var(--card);
  border-radius:20px;
}
```

- [ ] **Step 4: Run the contract and full suite**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract -v`

Expected: PASS.

Run: `python -m unittest discover -s tests -q`

Expected: all existing tests PASS.

### Task 2: Restyle the Manzilim flow

**Files:**
- Modify: `tests/test_auth_profile_design_v1647_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `locAuto`, `locViloyat`, `locTuman`, `locMahalla`, `userLocMap`, `locSave`.
- Produces: semantic classes `koprik-location-shell`, `location-actions`, and `location-privacy-note`.

- [ ] **Step 1: Add failing location assertions**

```python
def test_location_flow_uses_new_shell_without_losing_map(self):
    for token in (
        'class="form-wrap koprik-flow-shell koprik-location-shell"',
        'class="location-privacy-note"',
        'id="userLocMap"',
        'id="locAuto"',
        'id="locSave"',
    ):
        self.assertIn(token, self.html)
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract.AuthProfileDesignV1647ContractTests.test_location_flow_uses_new_shell_without_losing_map -v`

Expected: FAIL because the new semantic classes are missing.

- [ ] **Step 3: Apply the visual-only location markup and CSS**

Change the existing Manzilim wrapper to:

```html
<div class="form-wrap koprik-flow-shell koprik-location-shell">
```

Keep every existing field and map ID. Style the automatic location action as the primary call to action, group privacy copy in `location-privacy-note`, and use responsive two-column select fields above `720px`.

- [ ] **Step 4: Verify location and first-visit contracts**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract tests.test_first_visit_district_profile_stories_v1638_contract -v`

Expected: PASS.

### Task 3: Restyle login, registration, and employee login

**Files:**
- Modify: `tests/test_auth_profile_design_v1647_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: existing Telegram auth IDs and handlers, `regRoleChoice`, `regBody`, and staff-login IDs.
- Produces: `koprik-auth-shell`, `koprik-role-grid`, `koprik-staff-shell`, and consistent focus/disabled/error states.

- [ ] **Step 1: Add failing auth assertions**

```python
def test_auth_flows_use_selected_design_and_keep_telegram_ids(self):
    for token in (
        'class="form-wrap koprik-flow-shell koprik-auth-shell"',
        'class="koprik-role-grid"',
        'class="koprik-flow-shell koprik-auth-shell koprik-staff-shell"',
        'id="loginOpenTelegram"',
        'id="loginResend"',
        'id="regBody"',
        'id="slFirm"',
        'id="slLogin"',
        'id="slPass"',
    ):
        self.assertIn(token, self.html)
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract.AuthProfileDesignV1647ContractTests.test_auth_flows_use_selected_design_and_keep_telegram_ids -v`

Expected: FAIL because the new layout classes are missing.

- [ ] **Step 3: Implement the auth presentation layer**

Wrap the existing login and registration content in the approved dark panels. Convert the two role cards into a responsive grid. Replace the employee screen’s inline outer layout with `koprik-staff-shell`, but keep all current IDs and button text used by Telegram/staff handlers.

- [ ] **Step 4: Verify auth contracts**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract tests.test_telegram_auth_frontend_contract tests.test_telegram_auth_bot_contract -v`

Expected: PASS.

### Task 4: Unify ordinary, specialist, and business profile surfaces

**Files:**
- Modify: `tests/test_auth_profile_design_v1647_contract.py`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: current `user-profile-card`, dashboard IDs, profile renderer functions, online/system groups, and existing navigation attributes.
- Produces: common `koprik-profile-surface` presentation and responsive cabinet dashboard styling.

- [ ] **Step 1: Add failing profile assertions**

```python
def test_profile_and_cabinet_surfaces_are_unified(self):
    for token in (
        "koprik-profile-surface",
        ".dashboard-screen .dashboard-shell",
        ".specialist-card",
        'id="cabGroupOnline"',
        'id="cabGroupTizim"',
        'id="ucabRecentActivity"',
    ):
        self.assertIn(token, self.html)
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract.AuthProfileDesignV1647ContractTests.test_profile_and_cabinet_surfaces_are_unified -v`

Expected: FAIL until the shared profile surface is applied.

- [ ] **Step 3: Apply shared visual tokens**

Add `koprik-profile-surface` to static profile cards and to profile HTML returned by the business/user/specialist renderer functions. Restyle dashboard identity, KPI, menu, and activity cards using the selected teal/dark card hierarchy. Do not alter `data-nav`, `data-chats`, API requests, actor type, or permission checks.

- [ ] **Step 4: Verify cabinet/profile regression tests**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract tests.test_cabinet_dashboard_v1637_contract tests.test_first_visit_district_profile_stories_v1638_contract -v`

Expected: PASS.

### Task 5: Release metadata, responsive verification, and design QA

**Files:**
- Modify: `main.py`
- Modify: `static/index.html`
- Create: `docs/v1647-auth-profile-design.md`
- Create: `design-qa.md`

**Interfaces:**
- Consumes: completed presentation layer and all existing contract tests.
- Produces: build `v1647`, release note, final QA evidence.

- [ ] **Step 1: Add failing release assertions**

Add to `tests/test_auth_profile_design_v1647_contract.py`:

```python
def test_release_metadata_is_v1647(self):
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    self.assertIn('APP_BUILD = "v1647"', main)
    self.assertIn('<!-- BUILD: v1647 -->', self.html)
    self.assertIn('"auth_profile_design_v1647": True', main)
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_auth_profile_design_v1647_contract.AuthProfileDesignV1647ContractTests.test_release_metadata_is_v1647 -v`

Expected: FAIL while release metadata is still `v1646`.

- [ ] **Step 3: Update metadata and release notes**

Set `APP_BUILD` and the HTML build comment to `v1647`, add the health flag `auth_profile_design_v1647`, and document changed screens plus preserved behavior in `docs/v1647-auth-profile-design.md`.

- [ ] **Step 4: Run full automated verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

Run: `wc -l static/index.html`

Expected: report the exact final line count.

- [ ] **Step 5: Run visual QA**

Capture phone, tablet, and desktop states for Manzilim, login, registration, employee login, ordinary profile, specialist profile, and business cabinet. Compare each capture with `upload/design-comparison-mobile.png`, `upload/design-comparison.png`, and the matching prototype surfaces. Record P0/P1/P2 findings and fixes in `design-qa.md`; completion requires:

```text
final result: passed
```

