# Profile Complaints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe `⋮ → Shikoyat qilish` flow to public ordinary and business profiles, returning guests to the same profile after login and feeding the existing admin moderation queue.

**Architecture:** The existing `/api/reports`, `moderation_reports`, and admin moderation endpoints remain the single backend workflow. The frontend adds shared profile-menu/report helpers used by every actual public profile renderer, extends the existing in-app input modal with a bounded multiline field, and stores only the pending profile kind/id in `sessionStorage` while authentication is in progress.

**Tech Stack:** Python 3.13, FastAPI, SQLite, vanilla HTML/CSS/JavaScript, `unittest`/`pytest`.

## Global Constraints

- The report action appears only inside an ordinary public profile or business public profile.
- The action is `⋮` followed by `Shikoyat qilish`.
- The action is absent on the signed-in user’s own ordinary profile and own business profile.
- Guests may see the action; clicking it opens login and returns to the same profile after successful authentication.
- Reason codes are exactly `fraud`, `spam`, `illegal`, `abuse`, and `other`.
- Comment is optional and limited to 500 characters in both frontend and backend.
- Ordinary profiles submit `content_kind="profile"`; businesses submit `content_kind="business"`.
- A reporter cannot report their own profile/business, cannot create a second `open`/`reviewing` report for the same profile, and cannot exceed 10 reports in 24 hours.
- Reporter identity remains private from profile owners and other users.
- The existing admin `Shikoyatlar` queue, assign/resolve/dismiss actions, restrictions, and append-only audit remain the only admin workflow.
- Story reporting is unrelated and remains guarded by the existing MVP story flag.
- Existing MVP guards for stories, listings, chat, and systemization must not change.
- Build after implementation is `v1655`; if the hourly-advertisement plan already set `v1655`, add only the `profile_reports_v1655` marker.
- The supplied source directory currently has no `.git`; run commit steps only in a Git clone, otherwise record the listed files as the task checkpoint.

---

## File Structure

- Modify `api.py`: tighten existing report eligibility to require a publicly allowed owner.
- Modify `static/index.html`: shared public-profile action menu, report modal, guest auth return, and insertion in all active user/business render paths.
- Modify `main.py`: expose `profile_reports_v1655`.
- Create `tests/test_profile_reports_v1655.py`: backend profile/business report rules.
- Create `tests/test_profile_reports_frontend_v1655_contract.py`: UI, payload, self-hide, and auth-return contract.
- Modify `tests/test_admin_api_v1653.py`: prove profile/business reports use the unchanged admin queue and audit flow.
- Modify `tests/test_production_foundation.py`: lock the build/feature marker without changing MVP guards.

---

### Task 1: Lock and Tighten the Existing Profile Report API

**Files:**
- Modify: `api.py:83-220`
- Create: `tests/test_profile_reports_v1655.py`

**Interfaces:**
- Consumes: existing `require_user`, `_report_content_owner`, `content_is_public`, `public_owner_allowed`, `REPORT_REASONS`, and `moderation_reports`.
- Produces: unchanged `POST /api/reports` request/response contract with stricter public-owner eligibility.

- [ ] **Step 1: Create a self-contained report API test fixture**

Create `tests/test_profile_reports_v1655.py` with this fixture:

```python
import hashlib
import os
import shutil
import tempfile
import time
import unittest

os.environ["TEST_MODE"] = "1"
os.environ["TEST_OTP_CODE"] = "123456"

from fastapi.testclient import TestClient

import access_config
import database
from database import db, init_db
from main import app


class ProfileReportsV1655Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="koprik-profile-report-v1655-")
        cls.old_db = database.DB_PATH
        cls.old_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        database.DB_PATH = os.path.join(cls.root, "platforma.db")
        access_config.PROJECT_ACCESS_RESTRICTED = False
        init_db()
        cls.stamp = int(time.time())
        conn = db()
        cls.reporter_id = cls._insert_user(
            conn, 90001, "Reporter", cls.stamp
        )
        cls.target_user_id = cls._insert_user(
            conn, 90002, "Target User", cls.stamp
        )
        cls.target_owner_id = cls._insert_user(
            conn, 90003, "Target Owner", cls.stamp
        )
        cls.own_business_id = cls._insert_business(
            conn, cls.reporter_id, "Reporter Business", cls.stamp
        )
        cls.target_business_id = cls._insert_business(
            conn, cls.target_owner_id, "Target Business", cls.stamp
        )
        cls.reporter_token = "profile-report-token-v1655"
        conn.execute(
            """
            INSERT INTO mobile_sessions(
              user_id,token_hash,created_at,expires_at,last_used_at,revoked_at
            ) VALUES(?,?,?,?,?,0)
            """,
            (
                cls.reporter_id,
                hashlib.sha256(cls.reporter_token.encode()).hexdigest(),
                cls.stamp,
                cls.stamp + 3600,
                cls.stamp,
            ),
        )
        conn.commit()
        conn.close()
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @staticmethod
    def _insert_user(conn, tg_id, name, stamp):
        cursor = conn.execute(
            """
            INSERT INTO users(
              tg_id,login,pass_hash,role,name,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                tg_id,
                "u" + str(tg_id),
                "hash",
                "user",
                name,
                stamp,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _insert_business(conn, user_id, name, stamp):
        cursor = conn.execute(
            """
            INSERT INTO businesses(
              user_id,name,yon,tur,phone,address,status,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                name,
                "Savdo",
                "Do'kon",
                "+998900000000",
                "Markaz",
                "active",
                stamp,
            ),
        )
        return int(cursor.lastrowid)

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)
        database.DB_PATH = cls.old_db
        access_config.PROJECT_ACCESS_RESTRICTED = cls.old_restricted
        shutil.rmtree(cls.root, ignore_errors=True)

    @property
    def auth(self):
        return {"Authorization": "Bearer " + self.reporter_token}

    def post_report(self, kind, content_id, reason="fraud", comment=""):
        return self.client.post(
            "/api/reports",
            headers=self.auth,
            json={
                "content_kind": kind,
                "content_id": content_id,
                "reason_code": reason,
                "comment": comment,
            },
        )

    def tearDown(self):
        conn = db()
        conn.execute(
            "DELETE FROM moderation_reports WHERE reporter_user_id=?",
            (self.reporter_id,),
        )
        conn.execute(
            """
            DELETE FROM account_restrictions
            WHERE actor_type IN ('user','business')
            """
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 2: Add the failing/locking API behavior tests**

Append:

```python
def test_profile_and_business_reports_enter_open_queue(self):
    profile = self.post_report(
        "profile",
        self.target_user_id,
        reason="fraud",
        comment="Profil ma'lumoti shubhali",
    )
    self.assertEqual(profile.status_code, 201, profile.text)
    self.assertEqual(profile.json()["status"], "open")
    business = self.post_report(
        "business",
        self.target_business_id,
        reason="spam",
        comment="Takroriy reklama",
    )
    self.assertEqual(business.status_code, 201, business.text)
    self.assertEqual(business.json()["content_kind"], "business")


def test_guest_cannot_submit_report(self):
    response = self.client.post(
        "/api/reports",
        json={
            "content_kind": "profile",
            "content_id": self.target_user_id,
            "reason_code": "fraud",
            "comment": "",
        },
    )
    self.assertEqual(response.status_code, 401)


def test_self_profile_and_own_business_are_rejected(self):
    self.assertEqual(
        self.post_report("profile", self.reporter_id).status_code,
        400,
    )
    self.assertEqual(
        self.post_report("business", self.own_business_id).status_code,
        400,
    )


def test_duplicate_open_report_is_rejected(self):
    first = self.post_report("profile", self.target_user_id)
    self.assertEqual(first.status_code, 201)
    duplicate = self.post_report(
        "profile", self.target_user_id, reason="other"
    )
    self.assertEqual(duplicate.status_code, 409)


def test_invalid_reason_and_long_comment_are_rejected(self):
    self.assertEqual(
        self.post_report(
            "profile", self.target_user_id, reason="made-up"
        ).status_code,
        400,
    )
    self.assertEqual(
        self.post_report(
            "profile",
            self.target_user_id,
            comment="x" * 501,
        ).status_code,
        400,
    )


def test_eleventh_report_in_24_hours_is_rejected(self):
    conn = db()
    targets = []
    for offset in range(20, 31):
        targets.append(self._insert_user(
            conn, 91000 + offset, "Target " + str(offset), self.stamp
        ))
    conn.commit()
    conn.close()
    for target_id in targets[:10]:
        response = self.post_report("profile", target_id)
        self.assertEqual(response.status_code, 201, response.text)
    self.assertEqual(
        self.post_report("profile", targets[10]).status_code,
        429,
    )


def test_restricted_profile_is_not_reportable_as_public(self):
    conn = db()
    conn.execute(
        """
        INSERT INTO account_restrictions(
          actor_type,actor_id,restriction,status,reason,
          created_by_tg_id,created_at
        ) VALUES('user',?,'account_blocked','active','Tekshiruv',1,?)
        """,
        (self.target_user_id, self.stamp),
    )
    conn.commit()
    conn.close()
    response = self.post_report("profile", self.target_user_id)
    self.assertEqual(response.status_code, 404)
```

- [ ] **Step 3: Run the API tests and observe the eligibility gap**

Run:

```bash
python -m pytest tests/test_profile_reports_v1655.py -q
```

Expected: existing basic report rules pass; the restricted-profile test fails because the current endpoint checks content moderation status but not owner account restrictions.

- [ ] **Step 4: Require a public owner before accepting a report**

In `create_moderation_report`, immediately after resolving `owner`, replace the public check with:

```python
if (
    not owner
    or not public_owner_allowed(conn, owner[0], owner[1])
    or not content_is_public(conn, kind, content_id)
):
    raise HTTPException(404, "Ochiq kontent topilmadi.")
```

Do not alter:

- reason validation;
- comment limit;
- self-report check;
- duplicate index behavior;
- 10-per-24-hour query;
- response fields.

- [ ] **Step 5: Run report API and moderation regression**

Run:

```bash
python -m pytest tests/test_profile_reports_v1655.py tests/test_admin_api_v1653.py -q
```

Expected: all report and existing admin moderation cases pass.

- [ ] **Step 6: Commit the API checkpoint**

```bash
git add api.py tests/test_profile_reports_v1655.py
git commit -m "fix: require public profiles for moderation reports"
```

If this directory is still not a Git clone, record the two files as the checkpoint and continue.

---

### Task 2: Reusable Profile Action Menu and Report Form

**Files:**
- Modify: `static/index.html:12441-12520` and shared styles/scripts
- Create: `tests/test_profile_reports_frontend_v1655_contract.py`

**Interfaces:**
- Consumes: existing `askInput`, `askConfirm`, `api`, `showMsg`, `showLogin`, `ME`, and `esc`.
- Produces:
  - `isOwnReportTarget(kind: "profile" | "business", id: number) -> boolean`
  - `profileActionMenuHtml(kind, id) -> string`
  - `openProfileReport(kind, id) -> Promise<void> | void`
  - `submitProfileReport(kind, id, reasonCode, comment) -> Promise`
  - `askInput` support for `{multiline: true, maxlength: 500}`.

- [ ] **Step 1: Write failing shared-UI contract tests**

Create `tests/test_profile_reports_frontend_v1655_contract.py`:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


class ProfileReportFrontendV1655ContractTests(unittest.TestCase):
    def test_shared_menu_and_report_functions_exist(self):
        for marker in (
            "function isOwnReportTarget(",
            "function profileActionMenuHtml(",
            "function openProfileReport(",
            "function submitProfileReport(",
        ):
            self.assertIn(marker, HTML)
        self.assertIn("data-profile-report-menu", HTML)
        self.assertIn("Shikoyat qilish", HTML)

    def test_all_reason_codes_have_user_facing_labels(self):
        expected = {
            "fraud": "Yolg‘on yoki noto‘g‘ri ma’lumot / firibgarlik",
            "spam": "Keraksiz yoki takroriy reklama",
            "illegal": "Noqonuniy yoki taqiqlangan faoliyat",
            "abuse": "Haqorat, bezovta qilish yoki nomaqbul xatti-harakat",
            "other": "Boshqa sabab",
        }
        for code, label in expected.items():
            self.assertIn('value:"' + code + '"', HTML)
            self.assertIn(label, HTML)

    def test_report_payload_uses_existing_endpoint(self):
        self.assertIn('api("POST","/api/reports"', HTML)
        self.assertIn("content_kind:kind", HTML)
        self.assertIn("content_id:Number(id)", HTML)
        self.assertIn("reason_code:reasonCode", HTML)
        self.assertIn("comment:comment", HTML)

    def test_comment_is_optional_multiline_and_bounded(self):
        self.assertIn("multiline:true", HTML)
        self.assertIn("maxlength:500", HTML)
        self.assertIn("f.multiline", HTML)
        ask_input = re.search(
            r"function askInput\(.*?(?=\\n  function |\\n  /\\*)",
            HTML,
            re.S,
        ).group(0)
        self.assertIn("parseInt(f.maxlength||500,10)", ask_input)
        self.assertIn("'maxlength=\"'+max+'\"'", ask_input)

    def test_self_target_logic_covers_user_and_business(self):
        own_function = re.search(
            r"function isOwnReportTarget\(.*?\n  }",
            HTML,
            re.S,
        ).group(0)
        self.assertIn("ME.id", own_function)
        self.assertIn("ME.business_id", own_function)
```

- [ ] **Step 2: Run the UI contract and verify failure**

Run:

```bash
python -m pytest tests/test_profile_reports_frontend_v1655_contract.py -q
```

Expected: shared report functions and multiline modal support are missing.

- [ ] **Step 3: Extend `askInput` with a bounded multiline field**

Before the current plain `<input>` return, add:

```javascript
if(f.multiline){
  var max=Math.max(1,Math.min(5000,parseInt(f.maxlength||500,10)||500));
  return label+
    '<textarea class="textarea" data-ai="'+i+'" '+
    'maxlength="'+max+'" placeholder="'+esc(f.placeholder||"")+'">'+
    esc(f.value||"")+
    '</textarea>';
}
```

The existing submit collector already reads `.value`, so no collector change is required. Keep `askInput`’s select, numeric, dependency, cancel, overlay, and validation behavior unchanged.

- [ ] **Step 4: Add shared profile action helpers**

Add:

```javascript
var PROFILE_REPORT_REASONS=[
  {
    value:"fraud",
    label:"Yolg‘on yoki noto‘g‘ri ma’lumot / firibgarlik"
  },
  {value:"spam",label:"Keraksiz yoki takroriy reklama"},
  {value:"illegal",label:"Noqonuniy yoki taqiqlangan faoliyat"},
  {
    value:"abuse",
    label:"Haqorat, bezovta qilish yoki nomaqbul xatti-harakat"
  },
  {value:"other",label:"Boshqa sabab"}
];

function isOwnReportTarget(kind,id){
  if(!ME||!ME.registered)return false;
  var targetId=Number(id);
  if(kind==="profile")return Number(ME.id)===targetId;
  if(kind==="business")return Number(ME.business_id)===targetId;
  return false;
}

function profileActionMenuHtml(kind,id){
  if(isOwnReportTarget(kind,id))return "";
  return '<div class="profile-action-wrap">'+
    '<button type="button" class="profile-more" '+
      'data-profile-menu-toggle="'+esc(kind)+':'+Number(id)+'" '+
      'aria-label="Profil amallari" aria-expanded="false">⋮</button>'+
    '<div class="profile-action-menu" data-profile-report-menu="'+
      esc(kind)+':'+Number(id)+'" hidden>'+
      '<button type="button" data-profile-report="'+
        esc(kind)+':'+Number(id)+'">Shikoyat qilish</button>'+
    '</div>'+
  '</div>';
}

function submitProfileReport(kind,id,reasonCode,comment){
  return api("POST","/api/reports",{
    content_kind:kind,
    content_id:Number(id),
    reason_code:reasonCode,
    comment:comment
  });
}
```

Add local CSS for `.profile-action-wrap`, `.profile-more`, and `.profile-action-menu`. The menu must be absolutely positioned inside the profile hero, stay within a 320px mobile viewport, have a minimum 44px tap target, and use existing color variables. Do not introduce an external library.

- [ ] **Step 5: Add the report form and event delegation**

Implement:

```javascript
function openProfileReport(kind,id){
  if(isOwnReportTarget(kind,id)){
    showMsg("O‘z profilingiz ustidan shikoyat qilib bo‘lmaydi.");
    return;
  }
  if(!ME||!ME.registered){
    savePendingProfileReport(kind,id);
    showLogin("shikoyat yuborish");
    return;
  }
  askInput({
    title:"Profil ustidan shikoyat",
    okText:"Yuborish",
    fields:[
      {
        key:"reason",
        label:"Sababi",
        required:true,
        placeholder:"Sababni tanlang",
        options:PROFILE_REPORT_REASONS
      },
      {
        key:"comment",
        label:"Qo‘shimcha izoh — ixtiyoriy",
        placeholder:"500 belgigacha",
        multiline:true,
        maxlength:500
      }
    ]
  }).then(function(data){
    if(!data)return;
    var comment=(data.comment||"").trim();
    if(comment.length>500){
      showMsg("Izoh 500 belgidan oshmasin.");
      return;
    }
    return submitProfileReport(
      kind,id,data.reason,comment
    ).then(function(){
      showMsg("Shikoyatingiz yuborildi.");
    }).catch(function(error){
      showMsg(error.message||"Shikoyat yuborilmadi.");
    });
  });
}
```

Add one document click listener that:

1. toggles only the requested menu;
2. closes other open profile menus;
3. calls `openProfileReport` for `[data-profile-report]`;
4. closes menus when clicking elsewhere;
5. updates `aria-expanded`.

Do not reuse the story-report endpoint or free-text-only story reason modal.

- [ ] **Step 6: Run shared UI and syntax tests**

Run:

```bash
python -m pytest tests/test_profile_reports_frontend_v1655_contract.py -q
python - <<'PY'
from pathlib import Path
import re
html = Path("static/index.html").read_text(encoding="utf-8")
scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
Path("/tmp/koprik-inline.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/koprik-inline.js
```

Expected: UI contract passes and JavaScript syntax is valid.

- [ ] **Step 7: Commit the shared-UI checkpoint**

```bash
git add static/index.html tests/test_profile_reports_frontend_v1655_contract.py
git commit -m "feat: add reusable profile complaint form"
```

---

### Task 3: Install the Menu in Every Public Profile Renderer

**Files:**
- Modify: `static/index.html:4811-4860,4930-4990,5573-5645`
- Modify: `tests/test_profile_reports_frontend_v1655_contract.py`

**Interfaces:**
- Consumes: `profileActionMenuHtml` from Task 2.
- Produces: consistent report access in `renderUser`, `renderBizPage`, and `openBizSrv`.

- [ ] **Step 1: Add failing renderer-coverage assertions**

Append to the frontend contract:

```python
def function_body(name):
    match = re.search(
        rf"function {name}\(.*?(?=\\n  function |\\n  /\\*)",
        HTML,
        re.S,
    )
    if not match:
        raise AssertionError(name + " function not found")
    return match.group(0)


def test_every_active_public_profile_renderer_has_action_menu(self):
    self.assertIn(
        'profileActionMenuHtml("profile",u.id)',
        function_body("renderUser"),
    )
    self.assertIn(
        'profileActionMenuHtml("business",b.id)',
        function_body("renderBizPage"),
    )
    self.assertIn(
        'profileActionMenuHtml("business",b.id)',
        function_body("openBizSrv"),
    )


def test_menu_is_inside_profile_hero_not_global_navigation(self):
    user = function_body("renderUser")
    self.assertLess(
        user.index('profileActionMenuHtml("profile",u.id)'),
        user.index('profileStoriesHtml("user",u.id)'),
    )
```

- [ ] **Step 2: Run the renderer coverage and verify failure**

Run:

```bash
python -m pytest tests/test_profile_reports_frontend_v1655_contract.py -q
```

Expected: all three active render paths are missing the action menu.

- [ ] **Step 3: Insert the ordinary-profile menu**

In `renderUser`, make the hero positionable and append:

```javascript
profileActionMenuHtml("profile",u.id)
```

inside `.public-profile-hero`, after the profile metadata but before the closing `</div>`. Do not place it above/below the profile screen or beside listings/stories.

- [ ] **Step 4: Insert the menu in both business render paths**

In `renderBizPage`, append:

```javascript
profileActionMenuHtml("business",b.id)
```

inside `.public-profile-hero`.

In `openBizSrv`, append the same helper beside the business heading/metadata inside the business hero/title area. Preserve follow, message, call, items, queue, reviews, and profile stories behavior.

- [ ] **Step 5: Verify own-profile hiding in rendered HTML**

Add this exact contract assertion:

```python
def test_menu_helper_returns_empty_for_own_target(self):
    helper = function_body("profileActionMenuHtml")
    self.assertIn("if(isOwnReportTarget(kind,id))return \"\";", helper)
    ownership = function_body("isOwnReportTarget")
    self.assertIn('if(kind==="profile")', ownership)
    self.assertIn("Number(ME.id)===targetId", ownership)
    self.assertIn('if(kind==="business")', ownership)
    self.assertIn("Number(ME.business_id)===targetId", ownership)
```

Manually inspect these four states in a browser at 390px and 1280px widths:

```text
guest → other ordinary profile: menu visible
signed-in user → own ordinary profile: menu absent
signed-in business owner → own business profile: menu absent
signed-in user → another business profile: menu visible
```

- [ ] **Step 6: Run profile frontend regression**

Run:

```bash
python -m pytest \
  tests/test_profile_reports_frontend_v1655_contract.py \
  tests/test_story_frontend_contract.py \
  tests/test_subscription_frontend_contract.py -q
node --check /tmp/koprik-inline.js
```

Expected: profile menu tests pass and story/subscription profile sections remain unchanged.

- [ ] **Step 7: Commit the renderer checkpoint**

```bash
git add static/index.html tests/test_profile_reports_frontend_v1655_contract.py
git commit -m "feat: expose complaints on public profiles"
```

---

### Task 4: Return Guests to the Same Profile After Login

**Files:**
- Modify: `static/index.html:4811-4820,4930-4940,5000-5065,5286-5300,8515-8610,13820-13860`
- Modify: `tests/test_profile_reports_frontend_v1655_contract.py`

**Interfaces:**
- Consumes: existing Telegram login persistence and `afterAuth`.
- Produces:
  - `PROFILE_REPORT_PENDING_KEY = "koprik_profile_report_pending_v1655"`
  - `savePendingProfileReport(kind, id)`
  - `readPendingProfileReport()`
  - `clearPendingProfileReport()`
  - `resumePendingProfileReport() -> boolean`
  - `openUser(userId) -> Promise`
  - `openBizPage(id) -> Promise`

- [ ] **Step 1: Add failing auth-return contract assertions**

Append:

```python
def test_guest_report_is_persisted_only_as_profile_kind_and_id(self):
    self.assertIn(
        'PROFILE_REPORT_PENDING_KEY="koprik_profile_report_pending_v1655"',
        HTML,
    )
    for marker in (
        "function savePendingProfileReport(",
        "function readPendingProfileReport(",
        "function clearPendingProfileReport(",
        "function resumePendingProfileReport(",
    ):
        self.assertIn(marker, HTML)
    self.assertIn("sessionStorage.setItem(PROFILE_REPORT_PENDING_KEY", HTML)
    self.assertNotIn("localStorage.setItem(PROFILE_REPORT_PENDING_KEY", HTML)


def test_login_and_session_restore_resume_pending_profile(self):
    self.assertGreaterEqual(
        HTML.count("resumePendingProfileReport()"),
        2,
    )
    self.assertIn("return api(\"GET\",\"/api/user/\"+userId)", HTML)
    self.assertIn("return api(\"GET\",\"/api/business/\"+id)", HTML)


def test_pending_report_expires(self):
    self.assertIn("expires_at", HTML)
    self.assertIn("15*60*1000", HTML)
```

- [ ] **Step 2: Run auth-return tests and verify failure**

Run:

```bash
python -m pytest tests/test_profile_reports_frontend_v1655_contract.py -q
```

Expected: pending profile-report state and resume calls are missing.

- [ ] **Step 3: Add minimal expiring session state**

Implement:

```javascript
var PROFILE_REPORT_PENDING_KEY="koprik_profile_report_pending_v1655";

function savePendingProfileReport(kind,id){
  if(["profile","business"].indexOf(kind)<0)return;
  try{
    sessionStorage.setItem(
      PROFILE_REPORT_PENDING_KEY,
      JSON.stringify({
        kind:kind,
        id:Number(id),
        expires_at:Date.now()+15*60*1000
      })
    );
  }catch(e){}
}

function readPendingProfileReport(){
  try{
    var raw=sessionStorage.getItem(PROFILE_REPORT_PENDING_KEY);
    if(!raw)return null;
    var value=JSON.parse(raw);
    if(
      !value ||
      ["profile","business"].indexOf(value.kind)<0 ||
      !Number(value.id) ||
      Number(value.expires_at||0)<=Date.now()
    ){
      clearPendingProfileReport();
      return null;
    }
    return value;
  }catch(e){
    clearPendingProfileReport();
    return null;
  }
}

function clearPendingProfileReport(){
  try{sessionStorage.removeItem(PROFILE_REPORT_PENDING_KEY);}catch(e){}
}
```

Store no profile name, reason, comment, token, login, password, or Telegram data.

- [ ] **Step 4: Make profile-opening functions awaitable**

Change `openUser` and `openBizPage` to return their existing `api(...).then(...).catch(...)` chain:

```javascript
function openUser(userId){
  el("userBody").innerHTML=...;
  nav("user-page");
  return api("GET","/api/user/"+userId)
    .then(function(user){
      renderUser(user);
      return user;
    })
    .catch(function(error){
      el("userBody").innerHTML=...;
      return null;
    });
}
```

Apply the same return shape to `openBizPage`: resolve to the rendered business object on success and `null` after rendering the existing error state. Preserve all current rendering and error copy so existing click handlers do not gain unhandled promise rejections.

- [ ] **Step 5: Resume after authentication and trusted-session boot**

Implement:

```javascript
function resumePendingProfileReport(){
  var pending=readPendingProfileReport();
  if(!pending||!ME||!ME.registered)return false;
  clearPendingProfileReport();
  var opened=pending.kind==="business"
    ?openBizPage(pending.id)
    :openUser(pending.id);
  Promise.resolve(opened).then(function(profile){
    if(profile&&!isOwnReportTarget(pending.kind,pending.id)){
      openProfileReport(pending.kind,pending.id);
    }
  });
  return true;
}
```

Call it:

1. inside `afterAuth`, after `/api/me` assigns the full `ME`; do not resume before `ME.id` and `ME.business_id` exist;
2. inside the `MOBILE_TOKEN` boot `/api/me` success path after `loggedIn=true`.

If resume returns true, do not force the user back to `cabinet`/`ucab` afterward. In `afterAuth`, move the current `nav(role==="business" ? "cabinet" : "ucab")` into the `/api/me` completion:

```javascript
api("GET","/api/me").then(function(d){
  if(d&&d.registered){
    ME={
      registered:true,
      role:d.role,
      name:d.name,
      id:d.id,
      has_business:!!d.has_business,
      business_id:d.business?d.business.id:null,
      is_privileged:!!d.is_privileged
    };
    applyPrivilegedVisibility();
    updateHomeStoriesVisibility();
  }
  if(!resumePendingProfileReport()){
    nav(role==="business"?"cabinet":"ucab");
  }
}).catch(function(){
  nav(role==="business"?"cabinet":"ucab");
});
```

Remove the old immediate cabinet navigation below the asynchronous request. Keep `startActionNotifyPolling()` running exactly once.

- [ ] **Step 6: Run auth-return and browser-history regression**

Run:

```bash
python -m pytest \
  tests/test_profile_reports_frontend_v1655_contract.py \
  tests/test_telegram_auth_frontend_contract.py \
  tests/test_browser_history_navigation_contract.py -q
node --check /tmp/koprik-inline.js
```

Expected: pending report resumes once, browser back remains in-site, and Telegram OTP restoration still works.

- [ ] **Step 7: Commit the auth-return checkpoint**

```bash
git add static/index.html tests/test_profile_reports_frontend_v1655_contract.py
git commit -m "feat: restore profile complaints after login"
```

---

### Task 5: Admin Queue Integration and Audit Regression

**Files:**
- Modify: `tests/test_admin_api_v1653.py`
- Modify: `admin/app.js`

**Interfaces:**
- Consumes: unchanged `GET /api/admin/reports`, assign, resolve, dismiss, and audit endpoints.
- Produces: verified handling of `profile` and `business` report kinds in the existing queue.

- [ ] **Step 1: Add an admin workflow test for both profile kinds**

In `tests/test_admin_api_v1653.py`, add a separate test that clears any earlier report for its target, creates one `profile` report and one `business` report, then verifies:

```python
profile = self.client.post(
    "/api/reports",
    headers=self.reporter_auth,
    json={
        "content_kind": "profile",
        "content_id": self.owner_id,
        "reason_code": "fraud",
        "comment": "Profil ma'lumoti noto'g'ri",
    },
)
business = self.client.post(
    "/api/reports",
    headers=self.reporter_auth,
    json={
        "content_kind": "business",
        "content_id": self.business_id,
        "reason_code": "illegal",
        "comment": "Faoliyatni tekshirish kerak",
    },
)
self.assertEqual(profile.status_code, 201, profile.text)
self.assertEqual(business.status_code, 201, business.text)

queue = self.client.get(
    "/api/admin/reports?status=open",
    cookies=self.admin_cookies,
)
self.assertEqual(queue.status_code, 200, queue.text)
kinds = {item["content_kind"] for item in queue.json()["items"]}
self.assertTrue({"profile", "business"}.issubset(kinds))

assigned = self.client.post(
    f"/api/admin/reports/{profile.json()['id']}/assign",
    cookies=self.admin_cookies,
    json={},
)
self.assertEqual(assigned.json()["status"], "reviewing")

resolved = self.client.post(
    f"/api/admin/reports/{profile.json()['id']}/resolve",
    cookies=self.admin_cookies,
    json={
        "resolution": "Profil tekshirildi",
        "moderation_action": "content_hidden",
    },
)
self.assertEqual(resolved.json()["status"], "resolved")

dismissed = self.client.post(
    f"/api/admin/reports/{business.json()['id']}/dismiss",
    cookies=self.admin_cookies,
    json={
        "resolution": "Asos topilmadi",
        "moderation_action": "none",
    },
)
self.assertEqual(dismissed.json()["status"], "dismissed")
```

Finally assert `/api/admin/audit` includes `report.assign`, `report.resolved`, and `report.dismissed`.

- [ ] **Step 2: Run the admin workflow test**

Run:

```bash
python -m pytest tests/test_admin_api_v1653.py -q
```

Expected: the existing generic admin workflow accepts profile and business kinds without a new endpoint or table.

- [ ] **Step 3: Add friendly kind labels without changing workflow**

Add this presentation map in `admin/app.js`:

```javascript
var REPORT_KIND_LABELS={
  profile:"Oddiy profil",
  business:"Biznes profil",
  product:"Mahsulot",
  service:"Xizmat",
  advertisement:"Reklama",
  listing:"E'lon",
  story:"Istoriya"
};
```

Use `REPORT_KIND_LABELS[row.content_kind] || row.content_kind` in the existing list. Do not add a second queue, alternate resolution endpoint, or client-side status mutation.

- [ ] **Step 4: Re-run admin and audit tests**

Run:

```bash
python -m pytest tests/test_admin_api_v1653.py tests/test_admin_host_v1654.py -q
```

Expected: profile/business reports, admin authentication, host routing, and append-only audit all pass.

- [ ] **Step 5: Commit the admin checkpoint**

```bash
git add tests/test_admin_api_v1653.py admin/app.js
git commit -m "test: cover profile complaints in admin moderation"
```

---

### Task 6: Build Marker and Full Regression

**Files:**
- Modify: `main.py`
- Modify: `tests/test_production_foundation.py`
- Test: `tests/test_profile_reports_v1655.py`
- Test: `tests/test_profile_reports_frontend_v1655_contract.py`

**Interfaces:**
- Consumes: all preceding profile-report behavior.
- Produces: build/readiness evidence for `profile_reports_v1655`.

- [ ] **Step 1: Add the failing build marker assertion**

In `tests/test_production_foundation.py`, require:

```python
self.assertIn('"profile_reports_v1655": True', self.main_text)
```

If the hourly-advertisement plan has not yet run, change the existing build assertion to:

```python
self.assertIn('APP_BUILD = "v1655"', self.main_text)
```

- [ ] **Step 2: Run build tests and verify failure**

Run:

```bash
python -m pytest tests/test_production_foundation.py -q
```

Expected: the profile-report feature marker is missing.

- [ ] **Step 3: Expose the build marker without changing guards**

In `main.py`, set `APP_BUILD = "v1655"` if it is still `v1654`, and add:

```python
"profile_reports_v1655": True,
```

to the build feature payload. Keep these values unchanged:

```python
"mvp_release_v1654": True
"stories_enabled": False
"listings_enabled": False
"general_chat_enabled": False
"systemization_enabled": False
```

- [ ] **Step 4: Run focused profile-report regression**

Run:

```bash
python -m pytest \
  tests/test_profile_reports_v1655.py \
  tests/test_profile_reports_frontend_v1655_contract.py \
  tests/test_admin_api_v1653.py \
  tests/test_production_foundation.py \
  tests/test_mvp_guards_v1651_api.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Run complete regression and syntax verification**

Run:

```bash
python -m pytest tests -q
python -m compileall -q .
python - <<'PY'
from pathlib import Path
import re
html = Path("static/index.html").read_text(encoding="utf-8")
scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S)
Path("/tmp/koprik-inline.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/koprik-inline.js
```

Expected: no failures; the previous 358-test baseline plus the new report tests pass.

- [ ] **Step 6: Inspect scope and record handoff facts**

Run in a Git clone:

```bash
git status --short
git diff --stat
git diff --check
wc -l static/index.html
```

Expected changed production files for this plan:

```text
api.py
static/index.html
main.py
```

`admin/app.js` is also expected only when friendly report-kind labels are added. Report the exact changed-file list, build value, `static/index.html` line count, and complete test result.

- [ ] **Step 7: Commit the completed profile-complaints feature**

```bash
git add api.py static/index.html main.py admin/app.js tests/test_profile_reports_v1655.py tests/test_profile_reports_frontend_v1655_contract.py tests/test_admin_api_v1653.py tests/test_production_foundation.py
git commit -m "feat: release profile complaints v1655"
```
