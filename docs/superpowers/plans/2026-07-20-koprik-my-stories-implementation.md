# Ko‘prik “Istoriyalarim” Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shaxsiy va biznes kabinetlariga alohida “Istoriyalarim” ekranini qo‘shish; faol istoriyalarni 24 soat ommaga ko‘rsatish, muddati tugaganlarini esa egasi o‘chirguncha yopiq arxivda saqlash.

**Architecture:** Mavjud `stories`, `story_views` va `story_reports` jadvallari saqlanadi; arxiv holati `expires_at` orqali so‘rov vaqtida hisoblanadi. Backend joriy aktyorga tegishli metadata va autentifikatsiyalangan media endpointlarini beradi, frontend esa arxiv media fayllarini `fetch` + `Blob` + `URL.createObjectURL` orqali ko‘rsatadi. Shaxsiy va biznes ekranlari alohida bo‘ladi, lekin bir xil render va media yordamchilaridan foydalanadi.

**Tech Stack:** Python 3.12, FastAPI, SQLite, stdlib `unittest`, HTML/CSS/vanilla JavaScript, Node.js syntax check, Playwright smoke test, FFmpeg.

## Global Constraints

- Asosiy kod bazasi: Ko‘prik `v1609`; yakuniy build: `v1610`.
- Istoriya ommaga aniq 24 soat ko‘rinadi; `expires_at > now` — `active`, `expires_at <= now` — `archived`.
- Arxivdagi istoriya egasi o‘chirguncha saqlanadi; avtomatik tozalash yoki fon vazifasi qo‘shilmaydi.
- Alohida arxiv jadvali va media nusxasi yaratilmaydi.
- Faqat `status='active'` va `deleted_at=0` yozuvlari “Istoriyalarim” ro‘yxatiga kiradi; `failed` va eski `deleted` yozuvlari chiqmaydi.
- `actor_type=user` va `actor_type=business` ma’lumotlari aralashmaydi.
- `ads` ruxsatiga ega xodim biznes istoriyalarini boshqarishi mumkin; shaxsiy istoriyalarni boshqara olmaydi.
- Arxiv ro‘yxati va media fayli begona aktyorga berilmaydi.
- Rasm/video fayllari mavjud story papkasida saqlanadi; o‘chirishda media, video muqovasi, `stories` qatori, ko‘rishlar va reportlar tozalanadi.
- Arxiv kartasi videoning to‘liq faylini oldindan yuklamaydi; to‘liq media faqat “Ko‘rish” bosilganda olinadi.
- Arxivda qayta joylash, tahrirlash va yuklab olish funksiyalari `v1610` doirasiga kirmaydi.
- Mobil kenglikda gorizontal overflow bo‘lmaydi; 390×844 telefon va 820×1180 planshet o‘lchamlari tekshiriladi.
- Yangi Python yoki npm paketi qo‘shilmaydi.
- Import qilingan ZIP Git repozitoriy emas; commit qadamlari o‘rniga har task oxirida yangi test natijasi va o‘zgargan fayllar ro‘yxati nazorat nuqtasi bo‘ladi.

---

## File Map

- Modify: `stories.py` — egaga tegishli faol/arxiv ro‘yxati, ko‘rishlar soni, ruxsatli story qatori va hard-delete domen funksiyalari.
- Modify: `api.py` — `GET /api/stories/mine`, `GET /api/stories/{story_id}/owner-media` va mavjud DELETE endpointining hard-delete oqimi.
- Modify: `static/index.html` — ikki kabinet menyusi/ekrani, kartalar, tablar, autentifikatsiyalangan Blob media yuklash, viewer integratsiyasi va responsive uslublar.
- Modify: `main.py` — buildni `v1610` ga ko‘tarish va `story_archive` feature flagini berish.
- Modify: `tests/test_stories.py` — lifecycle, actor ajratilishi, view count va cascade delete unit testlari.
- Modify: `tests/test_story_api_contract.py` — yangi route va build kontraktlari.
- Modify: `tests/test_story_integration.py` — egasi, begona foydalanuvchi, biznes egasi va `ads` ruxsatli/ruxsatsiz xodim integratsiya testlari.
- Modify: `tests/test_story_frontend_contract.py` — ikki ekran, tablar, Blob yordamchilari, bo‘sh/xato holatlari va CSS kontraktlari.
- Modify: `tests/story-ui-smoke.cjs` — telefon/planshetda “Istoriyalarim” navigatsiyasi, thumbnail, viewer, delete va overflow sinovi.
- Create: `Platforma_v1610_my_stories.zip` — to‘liq deploy arxivi.
- Create: `Platforma_v1610_my_stories_changed_files.zip` — faqat o‘zgargan runtime va test fayllari.

---

### Task 1: Story domenida faol/arxiv ro‘yxati va hard-delete

**Files:**
- Modify: `stories.py:198-249`
- Test: `tests/test_stories.py:7-24, 145-235`

**Interfaces:**
- Consumes: mavjud `stories`, `story_views`, `story_reports` jadvallari va `STORY_TTL_SECONDS`.
- Produces: `list_managed_stories(conn, owner_type: str, owner_id: int, state: str = "all", now: int | None = None) -> list[sqlite3.Row]`.
- Produces: `managed_story(conn, story_id: int, owner_type: str, owner_id: int) -> sqlite3.Row | None`.
- Produces: `hard_delete_story(conn, story_id: int) -> None`.
- Row contract: `lifecycle_state` is `"active"|"archived"`; `view_count` is an integer-compatible SQLite value.

- [ ] **Step 1: Import the new domain functions in the unit test**

Replace the story lifecycle imports in `tests/test_stories.py` so they contain these names and no longer import `soft_delete_story`:

```python
from stories import (
    MAX_ACTIVE_STORIES,
    STORY_TTL_SECONDS,
    StoryValidationError,
    activate_story,
    active_story,
    can_manage_story,
    create_story_record,
    ensure_story_tables,
    fail_story,
    hard_delete_story,
    list_managed_stories,
    list_owner_stories,
    list_story_feed,
    list_story_viewers,
    managed_story,
    record_story_view,
    report_story,
    sniff_media_type,
    validate_story_upload,
)
```

- [ ] **Step 2: Write failing lifecycle, actor and cascade tests**

Replace `test_soft_deleted_story_is_not_returned` and add the following tests inside `StoryLifecycleTests`:

```python
    def test_managed_stories_split_active_and_archive_with_view_counts(self):
        archived_id = self.create_active_story(filename="archive.jpg", now=1_000)
        active_id = self.create_active_story(
            filename="active.jpg",
            now=1_000 + STORY_TTL_SECONDS,
        )
        record_story_view(
            self.conn,
            archived_id,
            2,
            now=1_001,
        )
        check_at = 1_000 + STORY_TTL_SECONDS + 1

        active = list_managed_stories(
            self.conn, "user", 1, state="active", now=check_at
        )
        archived = list_managed_stories(
            self.conn, "user", 1, state="archived", now=check_at
        )

        self.assertEqual([row["id"] for row in active], [active_id])
        self.assertEqual(active[0]["lifecycle_state"], "active")
        self.assertEqual([row["id"] for row in archived], [archived_id])
        self.assertEqual(archived[0]["lifecycle_state"], "archived")
        self.assertEqual(int(archived[0]["view_count"]), 1)

    def test_managed_stories_are_newest_first_and_exclude_non_active_rows(self):
        older_id = self.create_active_story(filename="older.jpg", now=1_500)
        newer_id = self.create_active_story(filename="newer.jpg", now=1_600)
        failed_id = create_story_record(
            self.conn,
            {"owner_type": "user", "owner_id": 1, "created_by_user_id": 1},
            {
                "media_type": "image",
                "mime_type": "image/jpeg",
                "caption": "",
                "duration_seconds": 0,
            },
            "failed-managed.jpg",
            "",
            now=1_700,
        )
        fail_story(self.conn, failed_id)
        deleted_id = self.create_active_story(filename="old-deleted.jpg", now=1_800)
        self.conn.execute(
            "UPDATE stories SET status='deleted',deleted_at=? WHERE id=?",
            (1_801, deleted_id),
        )
        self.conn.commit()

        rows = list_managed_stories(
            self.conn, "user", 1, state="all", now=1_900
        )

        self.assertEqual([row["id"] for row in rows], [newer_id, older_id])

    def test_managed_stories_keep_user_and_business_actors_separate(self):
        user_id = self.create_active_story(filename="user.jpg", now=2_000)
        business_id = self.create_active_story(
            owner_type="business",
            owner_id=10,
            creator_id=1,
            filename="business.jpg",
            now=2_001,
        )

        user_rows = list_managed_stories(
            self.conn, "user", 1, state="all", now=2_010
        )
        business_rows = list_managed_stories(
            self.conn, "business", 10, state="all", now=2_010
        )

        self.assertEqual([row["id"] for row in user_rows], [user_id])
        self.assertEqual([row["id"] for row in business_rows], [business_id])

    def test_managed_story_rejects_wrong_owner(self):
        story_id = self.create_active_story(now=3_000)
        self.assertIsNotNone(managed_story(self.conn, story_id, "user", 1))
        self.assertIsNone(managed_story(self.conn, story_id, "user", 2))
        self.assertIsNone(managed_story(self.conn, story_id, "business", 10))

    def test_managed_stories_reject_invalid_state(self):
        with self.assertRaisesRegex(StoryValidationError, "Holat"):
            list_managed_stories(
                self.conn, "user", 1, state="unknown", now=4_000
            )

    def test_hard_delete_cascades_views_and_reports(self):
        story_id = self.create_active_story(filename="delete.jpg", now=5_000)
        record_story_view(self.conn, story_id, 2, now=5_001)
        report_story(
            self.conn,
            story_id,
            2,
            "Nomaqbul kontent",
            now=5_002,
        )

        hard_delete_story(self.conn, story_id)

        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM stories WHERE id=?", (story_id,)
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM story_views WHERE story_id=?", (story_id,)
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM story_reports WHERE story_id=?", (story_id,)
            ).fetchone()[0],
            0,
        )
```

- [ ] **Step 3: Run the focused unit tests and confirm red state**

Run:

```bash
python -m unittest tests.test_stories.StoryLifecycleTests -v
```

Expected: import failure for `hard_delete_story`, `list_managed_stories`, or `managed_story` because the new functions do not exist yet.

- [ ] **Step 4: Implement managed queries and hard-delete**

In `stories.py`, keep `list_owner_stories` unchanged for the public 24-hour feed. Replace `soft_delete_story` with these three functions immediately after `can_manage_story`:

```python
def managed_story(conn, story_id, owner_type, owner_id):
    return conn.execute(
        "SELECT * FROM stories WHERE id=? AND owner_type=? AND owner_id=? "
        "AND status='active' AND deleted_at=0",
        (story_id, owner_type, owner_id),
    ).fetchone()


def list_managed_stories(
    conn,
    owner_type,
    owner_id,
    state="all",
    now=None,
):
    now = int(time.time() if now is None else now)
    state = (state or "all").strip().lower()
    if state not in ("active", "archived", "all"):
        raise StoryValidationError("Holat active, archived yoki all bo‘lishi kerak.")
    lifecycle_filter = ""
    values = [now, owner_type, owner_id]
    if state == "active":
        lifecycle_filter = " AND s.expires_at>?"
        values.append(now)
    elif state == "archived":
        lifecycle_filter = " AND s.expires_at<=?"
        values.append(now)
    return conn.execute(
        "SELECT s.*,COUNT(sv.viewer_user_id) AS view_count,"
        "CASE WHEN s.expires_at>? THEN 'active' ELSE 'archived' END "
        "AS lifecycle_state FROM stories s "
        "LEFT JOIN story_views sv ON sv.story_id=s.id "
        "WHERE s.owner_type=? AND s.owner_id=? AND s.status='active' "
        "AND s.deleted_at=0" + lifecycle_filter +
        " GROUP BY s.id ORDER BY s.created_at DESC,s.id DESC",
        values,
    ).fetchall()


def hard_delete_story(conn, story_id):
    conn.execute("DELETE FROM stories WHERE id=?", (story_id,))
    conn.commit()
```

- [ ] **Step 5: Run the domain suite and confirm green state**

Run:

```bash
python -m unittest tests.test_stories -v
```

Expected: every test in `tests.test_stories` passes, including active/archive split, actor separation, view count and cascade delete.

- [ ] **Step 6: Record the task checkpoint**

Run:

```bash
python -m unittest tests.test_stories -v
rg -n "def (managed_story|list_managed_stories|hard_delete_story)" stories.py
```

Expected: the suite reports `OK`; `rg` prints all three new function definitions. Checkpoint files: `stories.py`, `tests/test_stories.py`.

---

### Task 2: Owner-only metadata/media API and permanent delete

**Files:**
- Modify: `api.py:32-55, 287-339, 402-660`
- Test: `tests/test_story_api_contract.py:8-35`
- Test: `tests/test_story_integration.py:20-130`

**Interfaces:**
- Consumes: `list_managed_stories`, `managed_story`, `hard_delete_story` from Task 1 and existing `_story_actor`, `delete_story_files`, `story_storage_dir`.
- Produces: `GET /api/stories/mine?actor_type=user|business&state=active|archived|all` returning newest-first owner payloads.
- Produces: `GET /api/stories/{story_id}/owner-media?actor_type=user|business&thumbnail=0|1` returning authenticated `FileResponse`.
- Produces: `DELETE /api/stories/{story_id}?actor_type=user|business` that hard-deletes the database row and deletes its media files.
- Payload fields: `id`, `owner_type`, `owner_id`, `media_type`, `caption`, `duration_seconds`, `created_at`, `expires_at`, `state`, `view_count`, `media_url`, `thumbnail_url`.

- [ ] **Step 1: Write the API route contract tests**

Extend `test_authenticated_routes_exist` in `tests/test_story_api_contract.py` with the two route strings below:

```python
            '@router.get("/stories/mine")',
            '@router.get("/stories/{story_id}/owner-media")',
```

Add this test to the same class:

```python
    def test_owner_media_is_not_a_public_route(self):
        self.assertIn(
            '@router.get("/stories/{story_id}/owner-media")',
            self.api,
        )
        self.assertNotIn(
            '@public_router.get("/stories/{story_id}/owner-media")',
            self.api,
        )
```

- [ ] **Step 2: Add integration fixtures for business and staff actors**

In `StoryApiIntegrationTests.setUpClass`, after creating the viewer mobile session and before `conn.commit()`, add:

```python
        conn.execute(
            "INSERT INTO users(login,pass_hash,role,name,created_at) "
            "VALUES(?,?,?,?,?)",
            ("story_business", "x", "business", "Story biznes", now),
        )
        cls.business_owner_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        cls.business_owner_token = "business-owner-token"
        conn.execute(
            "INSERT INTO mobile_sessions(user_id,token_hash,created_at,expires_at,"
            "last_used_at,revoked_at) VALUES(?,?,?,?,?,0)",
            (
                cls.business_owner_id,
                hashlib.sha256(cls.business_owner_token.encode()).hexdigest(),
                now,
                now + 3600,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO businesses(user_id,name,status,created_at) VALUES(?,?,?,?)",
            (cls.business_owner_id, "Story biznes", "active", now),
        )
        cls.business_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO staff(business_id,name,status,created_at,perms,can_login) "
            "VALUES(?,?,?,?,?,?)",
            (cls.business_id, "Reklama xodimi", "active", now, "ads", 1),
        )
        ads_staff_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        cls.ads_staff_token = "story-ads-staff"
        conn.execute(
            "INSERT INTO staff_sessions(token,staff_id,business_id,created_at) "
            "VALUES(?,?,?,?)",
            (cls.ads_staff_token, ads_staff_id, cls.business_id, now),
        )
        conn.execute(
            "INSERT INTO staff(business_id,name,status,created_at,perms,can_login) "
            "VALUES(?,?,?,?,?,?)",
            (cls.business_id, "Oddiy xodim", "active", now, "items", 1),
        )
        plain_staff_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        cls.plain_staff_token = "story-plain-staff"
        conn.execute(
            "INSERT INTO staff_sessions(token,staff_id,business_id,created_at) "
            "VALUES(?,?,?,?)",
            (cls.plain_staff_token, plain_staff_id, cls.business_id, now),
        )
```

Add this helper under `auth`:

```python
    def staff_auth(self, token):
        return {
            "X-Telegram-Init-Data": "staff:" + token,
            "X-Staff-Token": token,
        }
```

- [ ] **Step 3: Write failing owner archive and permission integration tests**

Add these methods to `StoryApiIntegrationTests`:

```python
    def test_owner_can_list_and_open_expired_story_but_stranger_cannot(self):
        created = self.client.post(
            "/api/stories",
            headers=self.auth(self.owner_token),
            files={"file": ("archive.png", PNG_1X1, "image/png")},
            data={"caption": "Arxiv sinovi", "actor_type": "user"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        story_id = created.json()["story"]["id"]
        conn = db()
        conn.execute(
            "UPDATE stories SET expires_at=? WHERE id=?",
            (int(time.time()) - 1, story_id),
        )
        conn.commit()
        conn.close()

        archive = self.client.get(
            "/api/stories/mine?actor_type=user&state=archived",
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(archive.status_code, 200, archive.text)
        item = next(row for row in archive.json() if row["id"] == story_id)
        self.assertEqual(item["state"], "archived")
        self.assertEqual(item["view_count"], 0)
        self.assertIn("owner-media", item["media_url"])

        public_media = self.client.get(f"/story-media/{story_id}")
        self.assertEqual(public_media.status_code, 404)
        owner_media = self.client.get(
            item["media_url"],
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(owner_media.status_code, 200, owner_media.text)
        self.assertEqual(owner_media.content, PNG_1X1)
        stranger_media = self.client.get(
            item["media_url"],
            headers=self.auth(self.viewer_token),
        )
        self.assertEqual(stranger_media.status_code, 403)
        invalid_thumbnail = self.client.get(
            item["media_url"] + "&thumbnail=2",
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(invalid_thumbnail.status_code, 400)

    def test_business_archive_is_available_to_owner_and_ads_staff_only(self):
        created = self.client.post(
            "/api/stories",
            headers=self.auth(self.business_owner_token),
            files={"file": ("business.png", PNG_1X1, "image/png")},
            data={"caption": "Biznes istoriyasi", "actor_type": "business"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        story_id = created.json()["story"]["id"]

        owner_list = self.client.get(
            "/api/stories/mine?actor_type=business&state=active",
            headers=self.auth(self.business_owner_token),
        )
        self.assertEqual(owner_list.status_code, 200, owner_list.text)
        self.assertIn(story_id, [row["id"] for row in owner_list.json()])
        staff_list = self.client.get(
            "/api/stories/mine?actor_type=business&state=active",
            headers=self.staff_auth(self.ads_staff_token),
        )
        self.assertEqual(staff_list.status_code, 200, staff_list.text)
        denied = self.client.get(
            "/api/stories/mine?actor_type=business&state=active",
            headers=self.staff_auth(self.plain_staff_token),
        )
        self.assertEqual(denied.status_code, 403)

    def test_delete_removes_archived_row_media_views_and_reports(self):
        created = self.client.post(
            "/api/stories",
            headers=self.auth(self.owner_token),
            files={"file": ("delete-archive.png", PNG_1X1, "image/png")},
            data={"caption": "O‘chirish", "actor_type": "user"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        story_id = created.json()["story"]["id"]
        viewed = self.client.post(
            f"/api/stories/{story_id}/view",
            headers=self.auth(self.viewer_token),
        )
        self.assertEqual(viewed.status_code, 200, viewed.text)
        conn = db()
        filename = conn.execute(
            "SELECT media_filename FROM stories WHERE id=?", (story_id,)
        ).fetchone()["media_filename"]
        conn.execute(
            "UPDATE stories SET expires_at=? WHERE id=?",
            (int(time.time()) - 1, story_id),
        )
        conn.commit()
        conn.close()

        deleted = self.client.delete(
            f"/api/stories/{story_id}?actor_type=user",
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        conn = db()
        self.assertIsNone(
            conn.execute("SELECT 1 FROM stories WHERE id=?", (story_id,)).fetchone()
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM story_views WHERE story_id=?", (story_id,)
            ).fetchone()[0],
            0,
        )
        conn.close()
        story_path = os.path.join(os.environ["STORY_UPLOAD_DIR"], filename)
        self.assertFalse(os.path.exists(story_path))
```

- [ ] **Step 4: Run API tests and confirm red state**

Run:

```bash
python -m unittest tests.test_story_api_contract tests.test_story_integration -v
```

Expected: contract test reports missing `/stories/mine` and `/owner-media`; integration tests receive 404 for those routes or keep a deleted database row.

- [ ] **Step 5: Import Task 1 functions and add owner payload**

In `api.py`, remove `soft_delete_story` from the `stories` import and add:

```python
    hard_delete_story,
    list_managed_stories,
    managed_story,
```

After `_story_payload`, add:

```python
def _managed_story_payload(row, actor_type):
    sid = int(row["id"])
    media_base = (
        "/api/stories/" + str(sid) + "/owner-media?actor_type=" + actor_type
    )
    return {
        "id": sid,
        "owner_type": row["owner_type"],
        "owner_id": int(row["owner_id"]),
        "media_type": row["media_type"],
        "media_url": media_base,
        "thumbnail_url": media_base + "&thumbnail=1",
        "caption": row["caption"] or "",
        "duration_seconds": float(row["duration_seconds"] or 0),
        "created_at": int(row["created_at"]),
        "expires_at": int(row["expires_at"]),
        "state": row["lifecycle_state"],
        "view_count": int(row["view_count"] or 0),
    }
```

- [ ] **Step 6: Implement `GET /api/stories/mine`**

Add this route immediately after `stories_feed` and before `/stories/owner/{owner_type}/{owner_id}`:

```python
@router.get("/stories/mine")
async def stories_mine(
    actor_type: str = "user",
    state: str = "all",
    x_telegram_init_data: str = Header(default=""),
):
    conn = db()
    try:
        actor = _story_actor(conn, x_telegram_init_data, actor_type)
        rows = list_managed_stories(
            conn,
            actor["owner_type"],
            actor["owner_id"],
            state=state,
        )
        return [
            _managed_story_payload(row, actor["owner_type"])
            for row in rows
        ]
    except StoryValidationError as exc:
        raise HTTPException(400, str(exc))
    finally:
        conn.close()
```

- [ ] **Step 7: Refactor media response and implement owner-only media**

Replace `_story_file_response` with a row-based helper plus the public wrapper:

```python
def _story_row_file_response(row, thumbnail=False):
    filename = (
        row["thumbnail_filename"]
        if thumbnail and row["thumbnail_filename"]
        else row["media_filename"]
    )
    if not filename or os.path.basename(filename) != filename:
        raise HTTPException(404, "Media topilmadi.")
    from main import UPLOAD_DIR

    path = os.path.join(story_storage_dir(UPLOAD_DIR), filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Media topilmadi.")
    media_type = (
        "image/jpeg"
        if thumbnail and row["thumbnail_filename"]
        else row["mime_type"]
    )
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


def _story_file_response(story_id, thumbnail=False):
    conn = db()
    try:
        row = active_story(conn, story_id)
        if not row:
            raise HTTPException(404, "Istoriya topilmadi yoki muddati tugagan.")
        return _story_row_file_response(row, thumbnail=thumbnail)
    finally:
        conn.close()
```

Add this authenticated route before the two `@public_router` media routes:

```python
@router.get("/stories/{story_id}/owner-media")
async def story_owner_media(
    story_id: int,
    actor_type: str = "user",
    thumbnail: int = 0,
    x_telegram_init_data: str = Header(default=""),
):
    conn = db()
    try:
        if thumbnail not in (0, 1):
            raise HTTPException(400, "thumbnail 0 yoki 1 bo‘lishi kerak.")
        actor = _story_actor(conn, x_telegram_init_data, actor_type)
        row = managed_story(
            conn,
            story_id,
            actor["owner_type"],
            actor["owner_id"],
        )
        if not row:
            raise HTTPException(403, "Bu istoriya sizga tegishli emas.")
        return _story_row_file_response(row, thumbnail=bool(thumbnail))
    finally:
        conn.close()
```

- [ ] **Step 8: Replace soft-delete with permanent delete in the existing endpoint**

Replace the body after `_story_actor` inside `story_delete` with:

```python
        actor = _story_actor(conn, x_telegram_init_data, actor_type)
        row = managed_story(
            conn,
            story_id,
            actor["owner_type"],
            actor["owner_id"],
        )
        if not row:
            raise HTTPException(
                403,
                "Faqat o‘zingizning istoriyangizni o‘chira olasiz.",
            )
        media_filename = row["media_filename"]
        thumbnail_filename = row["thumbnail_filename"]
        hard_delete_story(conn, story_id)
        delete_story_files(folder, media_filename, thumbnail_filename)
        return {"ok": True}
```

- [ ] **Step 9: Run API contract and integration tests**

Run:

```bash
python -m unittest tests.test_story_api_contract tests.test_story_integration -v
```

Expected: all API contract and integration tests pass; expired media is 404 publicly, 200 for its owner and 403 for a stranger; business `ads` staff receives 200 while plain staff receives 403.

- [ ] **Step 10: Record the task checkpoint**

Run:

```bash
python -m unittest tests.test_stories tests.test_story_api_contract tests.test_story_integration -v
rg -n '@router.get\("/stories/mine"\)|@router.get\("/stories/\{story_id\}/owner-media"\)|hard_delete_story' api.py
```

Expected: all three suites report `OK`; `rg` prints both new routes and the hard-delete call. Checkpoint files: `stories.py`, `api.py`, `tests/test_stories.py`, `tests/test_story_api_contract.py`, `tests/test_story_integration.py`.

---

### Task 3: Ikki kabinet ekrani va responsive kartalar

**Files:**
- Modify: `static/index.html:392-397, 579-645, 922-958, 1436-1454, 1771-1814, 3721-3743`
- Test: `tests/test_story_frontend_contract.py:8-70`

**Interfaces:**
- Consumes: existing `.menu-card`, `.ad-tabs`, `.ad-tab`, `.empty`, `.btn`, `nav()` and `BACKMAP` patterns.
- Produces: `data-screen="ucab-stories"` with `ucabStoriesTabs` and `ucabStoriesList`.
- Produces: `data-screen="cab-stories"` with `cabStoriesTabs` and `cabStoriesList`.
- Produces: `data-my-story-state="active|archived"`, `data-my-story-open`, `data-my-story-delete`, `data-my-stories-retry` hooks.

- [ ] **Step 1: Write failing markup and responsive contract tests**

Add these tests to `StoryFrontendContractTests`:

```python
    def test_personal_and_business_my_story_screens_exist(self):
        for value in (
            'data-nav="ucab-stories"',
            'data-nav="cab-stories"',
            'data-screen="ucab-stories"',
            'data-screen="cab-stories"',
            'id="ucabStoriesTabs"',
            'id="ucabStoriesList"',
            'id="cabStoriesTabs"',
            'id="cabStoriesList"',
            'story_archive:{title:"Istoriyalarim"',
        ):
            self.assertIn(value, self.html)

    def test_my_story_tabs_and_card_actions_exist(self):
        for value in (
            'data-my-story-state="active"',
            'data-my-story-state="archived"',
            'data-my-story-open',
            'data-my-story-delete',
            'data-my-stories-retry',
            "24 soati tugagan istoriyalar shu yerda saqlanadi",
            "Hali istoriya joylamagansiz",
            "Media topilmadi",
        ):
            self.assertIn(value, self.html)

    def test_my_story_grid_has_mobile_safe_constraints(self):
        self.assertIn(".my-stories-grid", self.html)
        self.assertIn("minmax(0,1fr)", self.html)
        self.assertIn("min-width:0", self.html)
        self.assertIn("overflow:hidden", self.html)
```

- [ ] **Step 2: Run the frontend contract and confirm red state**

Run:

```bash
python -m unittest tests.test_story_frontend_contract -v
```

Expected: the three new tests fail because the screens and CSS do not exist.

- [ ] **Step 3: Add responsive “Istoriyalarim” CSS**

Append this block after the existing story styles and before the current story media queries:

```css
  .my-stories-shell{padding:2px 0 22px;min-width:0;overflow:hidden;}
  .my-stories-tabs{display:flex;gap:8px;margin-bottom:14px;}
  .my-stories-tabs .ad-tab{flex:1;min-width:0;}
  .my-stories-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;min-width:0;}
  .my-story-card{display:grid;grid-template-columns:112px minmax(0,1fr);gap:12px;min-width:0;overflow:hidden;border:1.5px solid var(--line);border-radius:18px;background:var(--card);padding:10px;box-shadow:var(--shadow);}
  .my-story-thumb{position:relative;width:112px;height:144px;overflow:hidden;border-radius:14px;background:#071514;display:grid;place-items:center;color:#fff;}
  .my-story-thumb img{width:100%;height:100%;object-fit:cover;display:block;}
  .my-story-thumb-fallback{text-align:center;padding:8px;font-size:12px;color:rgba(255,255,255,.8);}
  .my-story-video-badge{position:absolute;right:7px;bottom:7px;border-radius:999px;background:rgba(0,0,0,.62);padding:4px 7px;font-size:11px;font-weight:800;}
  .my-story-main{display:flex;flex-direction:column;min-width:0;}
  .my-story-caption{font-weight:800;font-size:14px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
  .my-story-meta{margin-top:5px;color:var(--soft);font-size:12px;line-height:1.45;}
  .my-story-state{display:inline-flex;align-items:center;width:max-content;max-width:100%;margin-top:7px;border-radius:999px;padding:5px 8px;background:var(--primary-tint);color:var(--primary);font-size:11px;font-weight:900;}
  .my-story-state.archived{background:var(--line);color:var(--soft);}
  .my-story-actions{display:flex;gap:7px;margin-top:auto;padding-top:9px;}
  .my-story-actions button{flex:1;min-width:0;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);padding:8px 6px;font:inherit;font-size:12px;font-weight:800;cursor:pointer;}
  .my-story-actions button.danger{color:#DC2626;}
  .my-stories-status{grid-column:1/-1;}
  @media(max-width:759px){.my-stories-grid{grid-template-columns:minmax(0,1fr)}.my-story-card{grid-template-columns:96px minmax(0,1fr)}.my-story-thumb{width:96px;height:126px}}
```

- [ ] **Step 4: Add personal and business menu cards**

In the business `data-screen="cabinet"` menu, immediately after `cab-elon`, add:

```html
        <div class="menu-card" data-nav="cab-stories"><div class="menu-ic">🎞️</div><div class="menu-main"><h4>Istoriyalarim</h4><p>Faol va arxivdagi biznes istoriyalari</p></div><span class="chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></span></div>
```

In the personal `data-screen="ucab"` menu, immediately after `ucab-elon`, add:

```html
        <div class="menu-card" data-nav="ucab-stories"><div class="menu-ic">🎞️</div><div class="menu-main"><h4>Istoriyalarim</h4><p>Faol va arxivdagi shaxsiy istoriyalar</p></div><span class="chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></span></div>
```

- [ ] **Step 5: Add the two separate screens**

Insert these screens after `ucab-settings` and before the follower screens:

```html
      <section class="screen" data-screen="ucab-stories">
        <div class="my-stories-shell">
          <div class="my-stories-tabs ad-tabs" id="ucabStoriesTabs">
            <button type="button" class="ad-tab on" data-my-story-state="active">Faol</button>
            <button type="button" class="ad-tab" data-my-story-state="archived">Arxiv</button>
          </div>
          <div class="my-stories-grid" id="ucabStoriesList"></div>
        </div>
      </section>

      <section class="screen" data-screen="cab-stories">
        <div class="my-stories-shell">
          <div class="my-stories-tabs ad-tabs" id="cabStoriesTabs">
            <button type="button" class="ad-tab on" data-my-story-state="active">Faol</button>
            <button type="button" class="ad-tab" data-my-story-state="archived">Arxiv</button>
          </div>
          <div class="my-stories-grid" id="cabStoriesList"></div>
        </div>
      </section>
```

- [ ] **Step 6: Register screen titles and back navigation**

Add the following keys to `titles`:

```javascript
    "cab-stories":"Istoriyalarim",
    "ucab-stories":"Istoriyalarim",
```

Add these entries after the `BACKMAP` object is declared:

```javascript
  BACKMAP["ucab-stories"]="ucab";
  BACKMAP["cab-stories"]="cabinet";
```

- [ ] **Step 7: Expose the business screen to `ads` staff without removing their ads card**

Add this entry to `STAFF_SECTIONS` immediately after `ads`:

```javascript
    story_archive:{title:"Istoriyalarim",ic:"🎞️",desc:"Faol va arxivdagi biznes istoriyalari",nav:"cab-stories"},
```

In `renderStaffHome(d)`, immediately after the existing `}).join("");` line that assigns the generated permission cards to `cards`, append the extra card only when the same staff member has `ads` permission:

```javascript
    if(perms.indexOf("ads")>=0){
      var storySection=STAFF_SECTIONS.story_archive;
      cards+='<div class="menu-card" data-nav="'+storySection.nav+'"><div class="menu-ic">'+storySection.ic+'</div><div class="menu-main"><h4>'+esc(storySection.title)+'</h4><p>'+esc(storySection.desc)+'</p></div><span class="chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></span></div>';
    }
```

Add `"cab-stories"` to the array in `staffBoot()` that assigns business-section `BACKMAP` values to `"staff-home"`. This ensures an `ads` staff member’s back button returns to the staff home instead of the owner’s business cabinet.

- [ ] **Step 8: Add static empty, error and card action templates used by contract tests**

The JavaScript implementation in Task 4 must include these exact returned fragments; add the named render helpers as stubs now so markup tests pass while the next task replaces their bodies:

```javascript
  function myStoriesEmptyHtml(state){
    return state==="archived"
      ? '<div class="empty my-stories-status"><h3>Arxiv hozircha bo‘sh</h3><p>24 soati tugagan istoriyalar shu yerda saqlanadi.</p></div>'
      : '<div class="empty my-stories-status"><h3>Hali istoriya joylamagansiz</h3><p>Rasm yoki 1 daqiqagacha video joylang.</p><button class="btn btn-primary" type="button" data-my-story-add>Istoriya joylash</button></div>';
  }
  function myStoriesErrorHtml(){
    return '<div class="empty my-stories-status"><h3>Istoriyalar yuklanmadi</h3><p>Internet aloqasini tekshirib qayta urining.</p><button class="btn btn-outline" type="button" data-my-stories-retry>Qayta yuklash</button></div>';
  }
  function myStoryMissingMediaHtml(){
    return '<span class="my-story-thumb-fallback">Media topilmadi</span>';
  }
  function myStoryActionTemplate(){
    return '<button type="button" data-my-story-open>Ko‘rish</button><button type="button" class="danger" data-my-story-delete>O‘chirish</button>';
  }
```

- [ ] **Step 9: Run the frontend markup/CSS tests**

Run:

```bash
python -m unittest tests.test_story_frontend_contract -v
```

Expected: all frontend contract tests pass, including both separate screens, action hooks and mobile-safe CSS rules.

- [ ] **Step 10: Record the task checkpoint**

Run:

```bash
python -m unittest tests.test_story_frontend_contract -v
rg -n 'data-(screen|nav)="(ucab-stories|cab-stories)"|my-stories-grid|data-my-story-state' static/index.html
```

Expected: frontend contract reports `OK`; `rg` prints both menu cards, both screens, the grid and both tab states. Checkpoint files: `static/index.html`, `tests/test_story_frontend_contract.py`.

---

### Task 4: Authenticated Blob loader, tab rendering, viewer and delete refresh

**Files:**
- Modify: `static/index.html:2020-2060, 2070-2320, 3754-3780, 9680-9721`
- Test: `tests/test_story_frontend_contract.py:8-90`

**Interfaces:**
- Consumes: Task 2 owner payload and Task 3 screen IDs/action hooks; existing `apiHeaders()`, `api()`, `esc()`, `showMsg()`, `askConfirm()`, `openStoryComposer()`, `openStoryViewer()`, `closeStoryViewer()`, `loadStories()`.
- Produces: `loadMyStories(screen: string, state?: string) -> Promise<void>`.
- Produces: `fetchStoryObjectUrl(url: string) -> Promise<string>`.
- Produces: `revokeMyStoryObjectUrls() -> void`.
- Produces: `openManagedStory(storyId: number, screen: string) -> void`.
- State contract: `MY_STORIES.ucab` and `MY_STORIES.cab` each contain `{state, items}`; full-view Blob URL is restored/revoked through `MANAGED_STORY_VIEW_CONTEXT`.

- [ ] **Step 1: Write failing JavaScript contract tests**

Add these tests to `StoryFrontendContractTests`:

```python
    def test_my_story_blob_and_render_functions_exist(self):
        for function_name in (
            "loadMyStories",
            "fetchStoryObjectUrl",
            "revokeMyStoryObjectUrls",
            "hydrateMyStoryThumbnails",
            "openManagedStory",
            "refreshMyStoryScreen",
        ):
            self.assertIn(f"function {function_name}(", self.html)

    def test_my_story_media_uses_authenticated_blob_urls(self):
        self.assertIn("fetch(url,{headers:apiHeaders()})", self.html)
        self.assertIn("URL.createObjectURL", self.html)
        self.assertIn("URL.revokeObjectURL", self.html)
        self.assertIn("MY_STORY_OBJECT_URLS", self.html)
        self.assertIn("MANAGED_STORY_VIEW_CONTEXT", self.html)

    def test_my_story_screen_loads_from_navigation(self):
        self.assertIn(
            'screen==="ucab-stories" || screen==="cab-stories"',
            self.html,
        )
        self.assertIn('"/api/stories/mine?actor_type="', self.html)

    def test_permission_errors_return_to_the_correct_cabinet_root(self):
        self.assertIn("error.status=r.status", self.html)
        self.assertIn("error.status===401||error.status===403", self.html)
        self.assertIn(
            'nav(config.actorType==="business"?"cabinet":"ucab")',
            self.html,
        )
```

- [ ] **Step 2: Run the focused frontend test and confirm red state**

Run:

```bash
python -m unittest tests.test_story_frontend_contract -v
```

Expected: failures for missing Blob and render functions.

- [ ] **Step 3: Preserve HTTP status in the shared API error object**

Inside `api(method, path, body)`, replace the current `throw new Error(msg);` line with:

```javascript
          var error=new Error(msg);
          error.status=r.status;
          throw error;
```

This keeps every existing caller’s `error.message` behavior unchanged and lets the management screen distinguish authentication/permission failures from retryable network errors.

- [ ] **Step 4: Replace Task 3 render stubs with complete state, formatting and Blob helpers**

Near the existing story globals, add:

```javascript
  var MY_STORIES={
    ucab:{state:"active",items:[]},
    cab:{state:"active",items:[]}
  };
  var MY_STORY_OBJECT_URLS=[];
  var MANAGED_STORY_VIEW_CONTEXT=null;

  function myStoryScreenConfig(screen){
    var business=screen==="cab-stories";
    return {
      key:business?"cab":"ucab",
      actorType:business?"business":"user",
      listId:business?"cabStoriesList":"ucabStoriesList",
      tabsId:business?"cabStoriesTabs":"ucabStoriesTabs"
    };
  }
  function myStoriesEmptyHtml(state){
    return state==="archived"
      ? '<div class="empty my-stories-status"><h3>Arxiv hozircha bo‘sh</h3><p>24 soati tugagan istoriyalar shu yerda saqlanadi.</p></div>'
      : '<div class="empty my-stories-status"><h3>Hali istoriya joylamagansiz</h3><p>Rasm yoki 1 daqiqagacha video joylang.</p><button class="btn btn-primary" type="button" data-my-story-add>Istoriya joylash</button></div>';
  }
  function myStoriesErrorHtml(){
    return '<div class="empty my-stories-status"><h3>Istoriyalar yuklanmadi</h3><p>Internet aloqasini tekshirib qayta urining.</p><button class="btn btn-outline" type="button" data-my-stories-retry>Qayta yuklash</button></div>';
  }
  function myStoryMissingMediaHtml(){
    return '<span class="my-story-thumb-fallback">Media topilmadi</span>';
  }
  function myStoryActionTemplate(storyId,screen){
    return '<button type="button" data-my-story-open="'+storyId+'" data-my-story-screen="'+screen+'">Ko‘rish</button><button type="button" class="danger" data-my-story-delete="'+storyId+'" data-my-story-screen="'+screen+'">O‘chirish</button>';
  }
  function myStoryDate(seconds){
    return new Date(Number(seconds||0)*1000).toLocaleString("uz-UZ",{
      day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"
    });
  }
  function myStoryRemaining(expiresAt){
    var seconds=Math.max(0,Number(expiresAt||0)-Math.floor(Date.now()/1000));
    var hours=Math.floor(seconds/3600),minutes=Math.floor((seconds%3600)/60);
    return hours>0?hours+" soat "+minutes+" daqiqa qoldi":minutes+" daqiqa qoldi";
  }
  function fetchStoryObjectUrl(url){
    return fetch(url,{headers:apiHeaders()}).then(function(response){
      if(!response.ok){
        return response.json().catch(function(){return {};}).then(function(data){
          throw new Error((data&&data.detail)||"Media topilmadi");
        });
      }
      return response.blob();
    }).then(function(blob){
      var objectUrl=URL.createObjectURL(blob);
      MY_STORY_OBJECT_URLS.push(objectUrl);
      return objectUrl;
    });
  }
  function revokeMyStoryObjectUrls(){
    MY_STORY_OBJECT_URLS.splice(0).forEach(function(url){
      try{URL.revokeObjectURL(url);}catch(error){}
    });
  }
```

- [ ] **Step 5: Implement card rendering and sequential thumbnail hydration**

Add these functions after the helpers from Step 4:

```javascript
  function myStoryCardHtml(item,screen){
    var archived=item.state==="archived";
    var stateText=archived?"Arxiv":("Faol · "+myStoryRemaining(item.expires_at));
    var caption=item.caption?esc(item.caption):"Matnsiz istoriya";
    return '<article class="my-story-card" data-my-story-id="'+item.id+'">'+
      '<div class="my-story-thumb" data-my-story-thumb="'+item.id+'" data-my-story-thumb-url="'+esc(item.thumbnail_url)+'">'+
        myStoryMissingMediaHtml()+(item.media_type==="video"?'<span class="my-story-video-badge">▶ Video</span>':'')+
      '</div><div class="my-story-main"><div class="my-story-caption">'+caption+'</div>'+
      '<div class="my-story-meta">'+esc(myStoryDate(item.created_at))+'<br>👁 '+Number(item.view_count||0)+' ko‘rish</div>'+
      '<span class="my-story-state'+(archived?' archived':'')+'">'+esc(stateText)+'</span>'+
      '<div class="my-story-actions">'+myStoryActionTemplate(item.id,screen)+'</div></div></article>';
  }
  function hydrateMyStoryThumbnails(list){
    var nodes=Array.prototype.slice.call(list.querySelectorAll("[data-my-story-thumb-url]"));
    return nodes.reduce(function(chain,node){
      return chain.then(function(){
        return fetchStoryObjectUrl(node.getAttribute("data-my-story-thumb-url")).then(function(url){
          var img=document.createElement("img");img.src=url;img.alt="Istoriya muqovasi";
          var fallback=node.querySelector(".my-story-thumb-fallback");if(fallback)fallback.remove();
          node.insertBefore(img,node.firstChild);
        }).catch(function(){
          node.setAttribute("data-media-missing","1");
        });
      });
    },Promise.resolve());
  }
  function renderMyStories(screen,items){
    var config=myStoryScreenConfig(screen),state=MY_STORIES[config.key].state,list=el(config.listId);
    if(!list)return;
    if(!items.length){list.innerHTML=myStoriesEmptyHtml(state);return;}
    list.innerHTML=items.map(function(item){return myStoryCardHtml(item,screen);}).join("");
    hydrateMyStoryThumbnails(list);
  }
```

- [ ] **Step 6: Implement metadata loading, tabs and retry**

Add:

```javascript
  function loadMyStories(screen,state){
    var config=myStoryScreenConfig(screen),store=MY_STORIES[config.key];
    if(state)store.state=state;
    var list=el(config.listId),tabs=el(config.tabsId);if(!list)return Promise.resolve();
    revokeMyStoryObjectUrls();
    if(tabs)tabs.querySelectorAll("[data-my-story-state]").forEach(function(button){
      button.classList.toggle("on",button.getAttribute("data-my-story-state")===store.state);
    });
    list.innerHTML='<div class="empty my-stories-status"><h3>Yuklanmoqda</h3><p>Istoriyalar olinmoqda.</p></div>';
    var path="/api/stories/mine?actor_type="+encodeURIComponent(config.actorType)+"&state="+encodeURIComponent(store.state);
    return api("GET",path).then(function(items){
      store.items=Array.isArray(items)?items:[];
      renderMyStories(screen,store.items);
    }).catch(function(error){
      if(error.status===401||error.status===403){
        showMsg(error.message);
        nav(config.actorType==="business"?"cabinet":"ucab");
        return;
      }
      list.innerHTML=myStoriesErrorHtml();
      showMsg(error.message);
    });
  }
  function refreshMyStoryScreen(){
    if(current==="ucab-stories"||current==="cab-stories")return loadMyStories(current);
    return Promise.resolve();
  }
```

- [ ] **Step 7: Open authenticated full media in the existing viewer without losing feed state**

Add:

```javascript
  function openManagedStory(storyId,screen){
    var config=myStoryScreenConfig(screen),item=MY_STORIES[config.key].items.filter(function(row){return Number(row.id)===Number(storyId);})[0];
    if(!item)return;
    fetchStoryObjectUrl(item.media_url).then(function(objectUrl){
      MANAGED_STORY_VIEW_CONTEXT={
        groups:STORY_GROUPS,
        groupIndex:STORY_GROUP_INDEX,
        itemIndex:STORY_ITEM_INDEX,
        objectUrl:objectUrl
      };
      STORY_GROUPS=[{
        owner_type:config.actorType,
        owner_id:item.owner_id,
        name:"Mening istoriyam",
        avatar_url:"",
        is_own:true,
        has_unseen:false,
        stories:[Object.assign({},item,{media_url:objectUrl,thumbnail_url:objectUrl,viewed:true})]
      }];
      openStoryViewer(0);
    }).catch(function(error){showMsg(error.message);});
  }
  function restoreManagedStoryViewerContext(){
    if(!MANAGED_STORY_VIEW_CONTEXT)return;
    var context=MANAGED_STORY_VIEW_CONTEXT;
    STORY_GROUPS=context.groups;
    STORY_GROUP_INDEX=context.groupIndex;
    STORY_ITEM_INDEX=context.itemIndex;
    MANAGED_STORY_VIEW_CONTEXT=null;
  }
```

At the end of the existing `closeStoryViewer`, after clearing viewer media, call:

```javascript
    restoreManagedStoryViewerContext();
```

Do not revoke the full-view URL separately there: it is already registered in `MY_STORY_OBJECT_URLS` and is revoked on list reload or when the screen is left.

- [ ] **Step 8: Wire add, retry, tabs, view and delete actions**

Add one delegated click handler near the existing story click handler:

```javascript
  document.addEventListener("click",function(event){
    var stateButton=event.target.closest("[data-my-story-state]");
    if(stateButton){
      loadMyStories(current,stateButton.getAttribute("data-my-story-state"));
      return;
    }
    if(event.target.closest("[data-my-stories-retry]")){
      refreshMyStoryScreen();return;
    }
    if(event.target.closest("[data-my-story-add]")){
      openStoryComposer();return;
    }
    var openButton=event.target.closest("[data-my-story-open]");
    if(openButton){
      openManagedStory(
        Number(openButton.getAttribute("data-my-story-open")),
        openButton.getAttribute("data-my-story-screen")
      );
      return;
    }
    var deleteButton=event.target.closest("[data-my-story-delete]");
    if(deleteButton){
      var storyId=Number(deleteButton.getAttribute("data-my-story-delete"));
      var screen=deleteButton.getAttribute("data-my-story-screen");
      var config=myStoryScreenConfig(screen);
      askConfirm({title:"Istoriyani o‘chirish",text:"Istoriya va uning media fayli butunlay o‘chiriladi.",okText:"O‘chirish",danger:true}).then(function(ok){
        if(!ok)return;
        api("DELETE","/api/stories/"+storyId+"?actor_type="+encodeURIComponent(config.actorType)).then(function(){
          showMsg("Istoriya o‘chirildi.");loadStories();loadMyStories(screen);
        }).catch(function(error){showMsg(error.message);});
      });
    }
  });
```

Update the success branch of existing `deleteStory` to refresh the management screen too:

```javascript
      showMsg("Istoriya o‘chirildi.");
      closeStoryViewer();
      loadStories();
      refreshMyStoryScreen();
```

Update the success branch of existing `uploadStory` to call `refreshMyStoryScreen()` after `loadStories()`.

- [ ] **Step 9: Load and clean up management screens through navigation**

In `nav(screen)`, capture the previous screen before assigning `current` and revoke list Blob URLs when leaving either management screen:

```javascript
    var previousScreen=current;
    if((previousScreen==="ucab-stories"||previousScreen==="cab-stories") && previousScreen!==screen){
      revokeMyStoryObjectUrls();
    }
    current=screen;
```

In `onScreenOpen(screen)`, add:

```javascript
    else if(screen==="ucab-stories" || screen==="cab-stories") loadMyStories(screen);
```

- [ ] **Step 10: Run frontend contracts and JavaScript syntax validation**

Extract the inline script and validate it without changing the source file:

```bash
python -m unittest tests.test_story_frontend_contract -v
python -c "from pathlib import Path; import re; s=Path('static/index.html').read_text(encoding='utf-8'); blocks=re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',s); Path('/tmp/koprik-inline.js').write_text('\n'.join(blocks),encoding='utf-8')"
node --check /tmp/koprik-inline.js
```

Expected: frontend tests report `OK`; Node exits with code 0 and prints no syntax error.

- [ ] **Step 11: Record the task checkpoint**

Run:

```bash
python -m unittest tests.test_story_frontend_contract -v
node --check /tmp/koprik-inline.js
rg -n "function (loadMyStories|fetchStoryObjectUrl|revokeMyStoryObjectUrls|hydrateMyStoryThumbnails|openManagedStory|refreshMyStoryScreen)" static/index.html
```

Expected: tests and syntax check pass; `rg` prints all six functions. Checkpoint files: `static/index.html`, `tests/test_story_frontend_contract.py`.

---

### Task 5: Telefon/planshet smoke testi, build metadata va regressiya

**Files:**
- Modify: `tests/story-ui-smoke.cjs:1-70`
- Modify: `main.py:39, 354`
- Modify: `static/index.html:7`
- Modify: `tests/test_story_frontend_contract.py:60-75`
- Create: `Platforma_v1610_my_stories.zip`
- Create: `Platforma_v1610_my_stories_changed_files.zip`

**Interfaces:**
- Consumes: Tasks 1–4 complete backend/frontend behavior.
- Produces: build header/API value `v1610` and feature flag `"story_archive": True`.
- Produces: phone and tablet screenshots under `artifacts/` during verification.
- Produces: deployable full ZIP and changed-files ZIP.

- [ ] **Step 1: Update build contract test first**

Replace `BuildMetadataTests.test_v1609_and_video_upload_fix_flags_exist` with:

```python
    def test_v1610_story_archive_and_video_upload_flags_exist(self):
        main_text = Path("main.py").read_text(encoding="utf-8")
        html_text = Path("static/index.html").read_text(encoding="utf-8")
        self.assertIn('APP_BUILD = "v1610"', main_text)
        self.assertIn('"stories": True', main_text)
        self.assertIn('"story_archive": True', main_text)
        self.assertIn('"story_video_upload_fix": True', main_text)
        self.assertIn('"railpack_ffmpeg": True', main_text)
        self.assertIn('<!-- BUILD: v1610 -->', html_text)
```

- [ ] **Step 2: Run the build contract and confirm red state**

Run:

```bash
python -m unittest tests.test_story_frontend_contract.BuildMetadataTests -v
```

Expected: failure because the runtime still identifies itself as `v1609` and has no `story_archive` flag.

- [ ] **Step 3: Bump build metadata without removing existing flags**

In `main.py`, change:

```python
APP_BUILD = "v1610"
```

In `app_build()`, add this key directly after `"stories": True` in the returned object:

```python
"story_archive": True,
```

In `static/index.html`, change the build comment to:

```html
<title>Ko‘prik</title><!-- BUILD: v1610 -->
```

- [ ] **Step 4: Extend Playwright API mocks for management metadata and media**

In `tests/story-ui-smoke.cjs`, add `const now = Math.floor(Date.now()/1000);` inside `mockApi`, then add these route branches before the generic `return route.fulfill({ json: [] });`:

```javascript
    if (url.pathname === '/api/stories/mine') {
      const archived = url.searchParams.get('state') === 'archived';
      return route.fulfill({ json: [{
        id: archived ? 12 : 11,
        owner_type: 'user',
        owner_id: 7,
        media_type: 'image',
        caption: archived ? 'Arxivdagi istoriya' : 'Faol istoriya',
        created_at: now - (archived ? 90000 : 300),
        expires_at: archived ? now - 3600 : now + 84000,
        state: archived ? 'archived' : 'active',
        view_count: archived ? 19 : 4,
        thumbnail_url: '/api/stories/' + (archived ? 12 : 11) + '/owner-media?actor_type=user&thumbnail=1',
        media_url: '/api/stories/' + (archived ? 12 : 11) + '/owner-media?actor_type=user'
      }] });
    }
    if (/^\/api\/stories\/(11|12)\/owner-media$/.test(url.pathname)) {
      return route.fulfill({ path: uploadImage, contentType:'image/png' });
    }
    if (/^\/api\/stories\/(11|12)$/.test(url.pathname) && request.method() === 'DELETE') {
      return route.fulfill({ json:{ok:true} });
    }
```

Keep the `/api/stories/feed`, upload and view mocks unchanged so the existing home story flow remains a regression test.

- [ ] **Step 5: Add phone management interactions to the smoke test**

At the end of the existing 390×844 interaction, after closing the public story viewer, add:

```javascript
    await page.click('#cabBtn');
    await page.waitForSelector('[data-screen="ucab"].active');
    await page.click('[data-nav="ucab-stories"]');
    await page.waitForSelector('[data-screen="ucab-stories"].active');
    await page.waitForSelector('[data-my-story-id="11"] img');
    await page.click('[data-my-story-open="11"]');
    await page.waitForSelector('#storyViewer.on');
    await page.click('#storyViewerClose');
    await page.click('#ucabStoriesTabs [data-my-story-state="archived"]');
    await page.waitForSelector('[data-my-story-id="12"] img');
    const managementOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (managementOverflow > 2) throw new Error(`My stories horizontal overflow: ${managementOverflow}px`);
```

Replace the tablet call with an interaction that opens the same screen and checks the two-column grid:

```javascript
  await verifyViewport(browser, { width:820, height:1180 }, 'story-tablet.png', async page => {
    await page.click('#cabBtn');
    await page.click('[data-nav="ucab-stories"]');
    await page.waitForSelector('[data-my-story-id="11"] img');
    const columns = await page.locator('#ucabStoriesList').evaluate(node => getComputedStyle(node).gridTemplateColumns.split(' ').length);
    if (columns !== 2) throw new Error(`Expected 2 tablet columns, received ${columns}`);
  });
```

- [ ] **Step 6: Run all automated Python and syntax tests**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -c "from pathlib import Path; import re; s=Path('static/index.html').read_text(encoding='utf-8'); blocks=re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',s); Path('/tmp/koprik-inline.js').write_text('\n'.join(blocks),encoding='utf-8')"
node --check /tmp/koprik-inline.js
ffmpeg -version
ffprobe -version
```

Expected: every Python test reports `OK`; Node exits 0; both FFmpeg commands print version information and exit 0.

- [ ] **Step 7: Run the responsive browser smoke test**

Start the local app in one terminal:

```bash
TEST_MODE=1 DB_PATH=/tmp/koprik-v1610-ui.db UPLOAD_DIR=/tmp/koprik-v1610-uploads STORY_UPLOAD_DIR=/tmp/koprik-v1610-stories uvicorn main:app --host 127.0.0.1 --port 8090
```

In a second terminal run:

```bash
node tests/story-ui-smoke.cjs
```

Expected: `Story UI smoke test passed for mobile and tablet.` Browser console has no relevant errors; no horizontal overflow is detected; `artifacts/story-mobile.png` and `artifacts/story-tablet.png` exist. If the environment has no launchable Chromium binary, record the exact Playwright launch error and do not claim responsive browser verification passed; Python contracts and Node syntax remain valid but the browser acceptance item stays open.

- [ ] **Step 8: Inspect the two screenshots**

Open `artifacts/story-mobile.png` and `artifacts/story-tablet.png` with the workspace image viewer. Confirm all of the following:

```text
Telefon: bitta karta ustuni, butun Ko‘rish/O‘chirish tugmalari, kesilmagan caption va tablar.
Planshet: ikkita karta ustuni, teng bo‘shliqlar, kesilmagan kartalar va gorizontal scroll yo‘qligi.
Ikkalasi: Faol/Arxiv holati, ko‘rish soni va media muqovasi ko‘rinadi.
```

Expected: all three lines are visually true. If one is false, adjust only the `.my-stories-*` / `.my-story-*` CSS and repeat Steps 6–8.

- [ ] **Step 9: Create full and changed-files ZIP artifacts**

From the parent `work` directory run:

```bash
zip -r ../Platforma_v1610_my_stories.zip Platforma_v1608_stories -x 'Platforma_v1608_stories/__pycache__/*' 'Platforma_v1608_stories/tests/__pycache__/*' 'Platforma_v1608_stories/artifacts/*'
```

From the project directory run:

```bash
zip -r ../../Platforma_v1610_my_stories_changed_files.zip stories.py api.py main.py static/index.html tests/test_stories.py tests/test_story_api_contract.py tests/test_story_integration.py tests/test_story_frontend_contract.py tests/story-ui-smoke.cjs docs/superpowers/specs/2026-07-20-koprik-my-stories-design.md docs/superpowers/plans/2026-07-20-koprik-my-stories-implementation.md
```

Expected: both ZIP commands exit 0 and list only intended files; neither archive contains `__pycache__`, temporary DBs, generated media or screenshots.

- [ ] **Step 10: Verify ZIP contents and final build**

Run:

```bash
unzip -t ../../Platforma_v1610_my_stories.zip
unzip -t ../../Platforma_v1610_my_stories_changed_files.zip
unzip -l ../../Platforma_v1610_my_stories_changed_files.zip
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: both archive integrity checks end with `No errors detected`; changed-files ZIP contains exactly the runtime/test/spec/plan files named in Step 9; the final Python suite reports `OK`.

- [ ] **Step 11: Record the final delivery checkpoint**

Record these values in the handoff:

```text
Build: v1610
Feature: story_archive=true
Full archive: Platforma_v1610_my_stories.zip
Changed files: Platforma_v1610_my_stories_changed_files.zip
Runtime files changed: stories.py, api.py, main.py, static/index.html
Verification: Python suite count/result, Node syntax result, FFmpeg/FFprobe result, Playwright phone/tablet result
Deployment note: Railway Volume must remain mounted at /data so archived media persists across deploys.
```

Expected: every line has an observed value from Steps 6–10; no unverified success statement is included.
