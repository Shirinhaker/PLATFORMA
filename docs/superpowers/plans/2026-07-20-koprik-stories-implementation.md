# Ko‘prik Stories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Barcha foydalanuvchi, mutaxassis va bizneslar rasm yoki 60 soniyagacha video istoriya joylaydigan, bosh sahifa va profilda 24 soat ko‘rinadigan funksiyani v1607 asosida v1608 ga qo‘shish.

**Architecture:** SQLite migratsiyasi istoriya, ko‘rish va shikoyat yozuvlarini saqlaydi. Yangi `stories.py` moduli media tekshiruvi, FFmpeg qayta ishlashi, fayl hayot sikli va ma’lumotlar operatsiyalarini `api.py` dan ajratadi; `api.py` faqat autentifikatsiya va HTTP javoblarini boshqaradi. Hozirgi bitta sahifali `static/index.html` ichiga mavjud ranglar va komponentlar bilan mos istoriya qatori, joylash oynasi va ko‘ruvchi qo‘shiladi.

**Tech Stack:** Python 3.12, FastAPI, SQLite, vanilla HTML/CSS/JavaScript, FFmpeg/FFprobe, `unittest`.

## Global Constraints

- Rasm: JPEG, PNG yoki WebP; 10 MB dan oshmaydi.
- Video: MP4, MOV yoki WebM; 100 MB dan oshmaydi va davomiyligi 60 soniyagacha.
- Har bir aktorda bir vaqtda ko‘pi bilan 10 ta faol istoriya.
- Matn 200 belgigacha.
- Istoriya 24 soatdan keyin barcha faol ro‘yxatlar va media javoblaridan yo‘qoladi.
- Oddiy foydalanuvchi va mutaxassis `user` aktori, biznes esa `business` aktori sifatida joylaydi.
- `ads` ruxsati berilgan faol xodim biznes nomidan istoriya joylay oladi; boshqa xodimlar joylay olmaydi.
- Musiqa, stiker, filtr, so‘rovnoma, havola, doimiy arxiv va javob yozish birinchi versiyaga kirmaydi.
- Mavjud profil, reklama, e’lon, xarita, bildirishnoma va buyurtma oqimlari o‘zgarmaydi.
- Manba ZIP git tarixi bilan kelmagan; shu sabab commit bosqichlari bajarilmaydi, tekshirilgan yakun alohida v1608 ZIP sifatida saqlanadi.

---

## Fayl tuzilishi

- Create `stories.py`: media tekshiruvi, FFmpeg, fayl yozish/o‘chirish, story query va serializer.
- Modify `database.py`: `stories`, `story_views`, `story_reports` jadvallari va indekslari.
- Modify `api.py`: istoriya HTTP endpointlari va autentifikatsiya.
- Modify `static/index.html`: story rail, composer, viewer, CSS va JS boshqaruvi.
- Create `nixpacks.toml`: Railway/Nixpacks muhitiga FFmpeg qo‘shish.
- Create `tests/test_stories.py`: schema, validatsiya, muddat, ko‘rish, ruxsat va feed testlari.
- Create `tests/test_story_frontend_contract.py`: HTML/JS element va funksiyalarining kontrakt testi.
- Modify `main.py`: build raqamini `v1608` ga ko‘tarish va build xususiyatiga `stories` qo‘shish.

---

### Task 1: Istoriya sxemasi va domen yordamchilari

**Files:**
- Create: `stories.py`
- Modify: `database.py:39-443`
- Test: `tests/test_stories.py`

**Interfaces:**
- Consumes: `sqlite3.Connection`, Unix vaqt, `owner_type`, `owner_id`.
- Produces: `ensure_story_tables(conn)`, `validate_story_upload(content_type, size_bytes, duration_seconds, caption)`, `create_story_record(conn, actor, media)`, `record_story_view(conn, story_id, viewer_user_id, now)`, `active_story(conn, story_id, now)`.

- [ ] **Step 1: Schema va validatsiya uchun muvaffaqiyatsiz test yozish**

```python
import sqlite3
import unittest

from stories import StoryValidationError, ensure_story_tables, validate_story_upload


class StorySchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_story_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_story_tables_exist(self):
        names = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        self.assertTrue({"stories", "story_views", "story_reports"}.issubset(names))

    def test_rejects_sixty_one_second_video(self):
        with self.assertRaisesRegex(StoryValidationError, "60 soniya"):
            validate_story_upload("video/mp4", 2_000_000, 61.0, "")

    def test_accepts_image_and_trims_caption(self):
        result = validate_story_upload("image/jpeg", 900_000, 0, " Salom ")
        self.assertEqual(result["media_type"], "image")
        self.assertEqual(result["caption"], "Salom")
```

- [ ] **Step 2: Testning kerakli sabab bilan yiqilishini ko‘rish**

Run: `python -m unittest tests.test_stories.StorySchemaTests -v`

Expected: `ModuleNotFoundError: No module named 'stories'`.

- [ ] **Step 3: Bitta sxema manbasini migratsiyaga ulash**

`database.py::_migrate` oxirida sxemani takrorlamasdan moduldagi yagona funksiyani chaqiring:

```python
from stories import ensure_story_tables
ensure_story_tables(conn)
```

- [ ] **Step 4: Minimal `stories.py` validatsiya modulini yozish**

```python
import time

STORY_TTL_SECONDS = 24 * 60 * 60
MAX_ACTIVE_STORIES = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MAX_VIDEO_SECONDS = 60.0
MAX_CAPTION_LENGTH = 200

IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/webm"}


class StoryValidationError(ValueError):
    pass


def ensure_story_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS stories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_type TEXT NOT NULL CHECK(owner_type IN ('user','business')),
        owner_id INTEGER NOT NULL,
        created_by_user_id INTEGER NOT NULL,
        media_type TEXT NOT NULL CHECK(media_type IN ('image','video')),
        media_filename TEXT NOT NULL,
        thumbnail_filename TEXT DEFAULT '',
        mime_type TEXT NOT NULL,
        caption TEXT DEFAULT '',
        duration_seconds REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'processing',
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        deleted_at INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS story_views(
        story_id INTEGER NOT NULL,
        viewer_user_id INTEGER NOT NULL,
        viewed_at INTEGER NOT NULL,
        PRIMARY KEY(story_id,viewer_user_id),
        FOREIGN KEY(story_id) REFERENCES stories(id) ON DELETE CASCADE,
        FOREIGN KEY(viewer_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS story_reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        reporter_user_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        created_at INTEGER NOT NULL,
        UNIQUE(story_id,reporter_user_id),
        FOREIGN KEY(story_id) REFERENCES stories(id) ON DELETE CASCADE,
        FOREIGN KEY(reporter_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_stories_active
        ON stories(status,expires_at,owner_type,owner_id,created_at);
    CREATE INDEX IF NOT EXISTS idx_story_views_story
        ON story_views(story_id,viewed_at);
    CREATE INDEX IF NOT EXISTS idx_story_reports_status
        ON story_reports(status,created_at);
    """)


def validate_story_upload(content_type, size_bytes, duration_seconds, caption):
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    clean_caption = (caption or "").strip()
    if len(clean_caption) > MAX_CAPTION_LENGTH:
        raise StoryValidationError("Istoriya matni 200 belgidan oshmasin.")
    if mime in IMAGE_MIMES:
        if size_bytes <= 0 or size_bytes > MAX_IMAGE_BYTES:
            raise StoryValidationError("Rasm hajmi 10 MB dan oshmasin.")
        return {"media_type": "image", "mime_type": mime, "caption": clean_caption, "duration_seconds": 0.0}
    if mime in VIDEO_MIMES:
        if size_bytes <= 0 or size_bytes > MAX_VIDEO_BYTES:
            raise StoryValidationError("Video hajmi 100 MB dan oshmasin.")
        if duration_seconds <= 0 or duration_seconds > MAX_VIDEO_SECONDS:
            raise StoryValidationError("Video 60 soniyadan oshmasin.")
        return {"media_type": "video", "mime_type": mime, "caption": clean_caption, "duration_seconds": float(duration_seconds)}
    raise StoryValidationError("Istoriya uchun JPG, PNG, WEBP, MP4, MOV yoki WEBM fayl tanlang.")
```

- [ ] **Step 5: Schema va validatsiya testlarini o‘tkazish**

Run: `python -m unittest tests.test_stories.StorySchemaTests -v`

Expected: 3 tests, `OK`.

---

### Task 2: Istoriya hayot sikli, feed va ko‘rishlar

**Files:**
- Modify: `stories.py`
- Test: `tests/test_stories.py`

**Interfaces:**
- Consumes: Task 1 sxemasi va validatsiya natijasi.
- Produces: `create_story_record`, `activate_story`, `list_story_feed`, `list_owner_stories`, `record_story_view`, `list_story_viewers`, `soft_delete_story`, `report_story`.

- [ ] **Step 1: 24 soat, 10 ta limit va ko‘rishning yagona sanalishi uchun test yozish**

```python
def test_expired_story_is_not_active(self):
    story_id = create_story_record(
        self.conn,
        {"owner_type": "user", "owner_id": 1, "created_by_user_id": 1},
        {"media_type": "image", "mime_type": "image/jpeg", "caption": "", "duration_seconds": 0},
        "one.jpg",
        "",
        now=1_000,
    )
    activate_story(self.conn, story_id)
    self.assertIsNone(active_story(self.conn, story_id, now=1_000 + STORY_TTL_SECONDS + 1))

def test_view_is_counted_once(self):
    story_id = self._active_story()
    record_story_view(self.conn, story_id, 9, now=2_000)
    record_story_view(self.conn, story_id, 9, now=2_100)
    count = self.conn.execute(
        "SELECT COUNT(*) FROM story_views WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    self.assertEqual(count, 1)

def test_eleventh_active_story_is_rejected(self):
    for index in range(10):
        self._active_story(filename=f"{index}.jpg")
    with self.assertRaisesRegex(StoryValidationError, "10 ta"):
        create_story_record(
            self.conn,
            {"owner_type": "user", "owner_id": 1, "created_by_user_id": 1},
            {"media_type": "image", "mime_type": "image/jpeg", "caption": "", "duration_seconds": 0},
            "eleven.jpg",
            "",
            now=2_000,
        )
```

- [ ] **Step 2: Testni bajarib yangi funksiyalar yo‘qligi sabab yiqilishini tekshirish**

Run: `python -m unittest tests.test_stories.StoryLifecycleTests -v`

Expected: import xatosi yoki `NameError` yangi funksiyalar yaratilmagani uchun.

- [ ] **Step 3: Hayot sikli funksiyalarini minimal SQL bilan yozish**

```python
def create_story_record(conn, actor, media, media_filename, thumbnail_filename, now=None):
    now = int(time.time() if now is None else now)
    count = conn.execute(
        "SELECT COUNT(*) FROM stories WHERE owner_type=? AND owner_id=? "
        "AND status IN ('processing','active') AND deleted_at=0 AND expires_at>?",
        (actor["owner_type"], actor["owner_id"], now),
    ).fetchone()[0]
    if count >= MAX_ACTIVE_STORIES:
        raise StoryValidationError("Bir vaqtda ko‘pi bilan 10 ta faol istoriya joylash mumkin.")
    cur = conn.execute(
        "INSERT INTO stories(owner_type,owner_id,created_by_user_id,media_type,media_filename,"
        "thumbnail_filename,mime_type,caption,duration_seconds,status,created_at,expires_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,'processing',?,?)",
        (actor["owner_type"], actor["owner_id"], actor["created_by_user_id"], media["media_type"],
         media_filename, thumbnail_filename, media["mime_type"], media["caption"],
         media["duration_seconds"], now, now + STORY_TTL_SECONDS),
    )
    conn.commit()
    return cur.lastrowid


def activate_story(conn, story_id):
    conn.execute("UPDATE stories SET status='active' WHERE id=? AND status='processing'", (story_id,))
    conn.commit()


def active_story(conn, story_id, now=None):
    now = int(time.time() if now is None else now)
    return conn.execute(
        "SELECT * FROM stories WHERE id=? AND status='active' AND deleted_at=0 AND expires_at>?",
        (story_id, now),
    ).fetchone()


def record_story_view(conn, story_id, viewer_user_id, now=None):
    now = int(time.time() if now is None else now)
    if not active_story(conn, story_id, now):
        raise StoryValidationError("Istoriya topilmadi yoki muddati tugagan.")
    conn.execute(
        "INSERT INTO story_views(story_id,viewer_user_id,viewed_at) VALUES(?,?,?) "
        "ON CONFLICT(story_id,viewer_user_id) DO NOTHING",
        (story_id, viewer_user_id, now),
    )
    conn.commit()
```

`list_story_feed` aktyor ma’lumotini `users`, `businesses`, `profile_images`, `follows` va `business_follows` dan oladi. Natija guruhlangan quyidagi kontraktni qaytaradi:

```python
{
    "owner_type": "user",
    "owner_id": 7,
    "name": "Ali",
    "avatar_url": "/profile-media/user/7",
    "is_followed": True,
    "has_unseen": True,
    "stories": [
        {
            "id": 41,
            "media_type": "image",
            "media_url": "/story-media/41",
            "thumbnail_url": "/story-thumbnail/41",
            "caption": "Bugungi yangilik",
            "created_at": 1_721_000_000,
            "expires_at": 1_721_086_400,
            "viewed": False,
        }
    ],
}
```

Tartib kaliti: `is_own DESC`, `has_unseen DESC`, `is_followed DESC`, `distance_group ASC`, `latest_story_at DESC`.

- [ ] **Step 4: Hayot sikli testlarini o‘tkazish**

Run: `python -m unittest tests.test_stories.StoryLifecycleTests -v`

Expected: 3 tests, `OK`.

---

### Task 3: Media qayta ishlash va FastAPI endpointlari

**Files:**
- Modify: `stories.py`
- Modify: `api.py:1-180` and append before the next major section
- Create: `nixpacks.toml`
- Test: `tests/test_stories.py`

**Interfaces:**
- Consumes: Task 2 domen funksiyalari, `api.require_user`, `api.require_business`, `main.UPLOAD_DIR`.
- Produces: `/api/stories/feed`, `/api/stories`, `/api/stories/{id}/view`, `/api/stories/{id}/viewers`, `/api/stories/{id}`, `/api/stories/{id}/reports`, `/story-media/{id}`, `/story-thumbnail/{id}`.

- [ ] **Step 1: Media probe va ruxsat testlarini yozish**

```python
def test_owner_can_delete_and_other_user_cannot(self):
    story_id = self._active_story()
    self.assertTrue(can_manage_story(self.conn, story_id, "user", 1))
    self.assertFalse(can_manage_story(self.conn, story_id, "user", 2))

def test_report_is_unique_per_reporter(self):
    story_id = self._active_story()
    report_story(self.conn, story_id, 8, "Nomaqbul kontent", now=3_000)
    report_story(self.conn, story_id, 8, "Takror", now=3_100)
    count = self.conn.execute(
        "SELECT COUNT(*) FROM story_reports WHERE story_id=? AND reporter_user_id=8",
        (story_id,),
    ).fetchone()[0]
    self.assertEqual(count, 1)
```

- [ ] **Step 2: Testlarni bajarib yangi funksiyalar yo‘qligi sabab yiqilishini tekshirish**

Run: `python -m unittest tests.test_stories.StoryPermissionTests -v`

Expected: import xatosi yoki `NameError`.

- [ ] **Step 3: Xususiy media papkasi va FFmpeg amallarini yozish**

`stories.py` quyidagi aniq vazifalarni bajaradi:

```python
def story_storage_dir(upload_dir):
    base = os.environ.get("STORY_UPLOAD_DIR", "").strip()
    if not base:
        base = os.path.join(os.path.dirname(os.path.abspath(upload_dir)), "stories")
    os.makedirs(base, exist_ok=True)
    return base


def probe_video_seconds(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return float(result.stdout.strip())


def transcode_video(source_path, output_path, thumbnail_path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", source_path, "-t", "60", "-vf", "scale=720:-2:force_original_aspect_ratio=decrease", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-c:a", "aac", "-movflags", "+faststart", output_path],
        capture_output=True,
        timeout=180,
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "0", "-i", output_path, "-frames:v", "1", "-vf", "scale=480:-2", thumbnail_path],
        capture_output=True,
        timeout=60,
        check=True,
    )
```

Rasm fayli signature va MIME bo‘yicha tekshiriladi, UUID nom bilan yoziladi. Video vaqtinchalik faylga yoziladi, `ffprobe` bilan serverda davomiyligi tekshiriladi, so‘ng MP4/H.264 ga aylantiriladi. Xato bo‘lsa vaqtinchalik va qisman yaratilgan fayllar o‘chiriladi, story `failed` qilinadi.

- [ ] **Step 4: FastAPI endpointlarini yozish**

`POST /api/stories` `multipart/form-data` qabul qiladi: `file`, `caption`, `actor_type`. `actor_type=user` uchun `require_user`, `actor_type=business` uchun `require_business` ishlatiladi. Xodim sessiyasida `need_perm(conn, init_data, "ads")` tekshiriladi; egasi bu tekshiruvdan avtomatik o‘tadi. Endpoint avval media faylini vaqtinchalik papkaga oqim bilan yozadi, limitdan oshganda darhol to‘xtaydi, Task 1 validatsiyasini chaqiradi, Task 2 yozuvini `processing` yaratadi, media tayyor bo‘lgach `active` qiladi.

`GET /story-media/{id}` va `GET /story-thumbnail/{id}` har so‘rovda `active_story` ni tekshiradi. Javob `FileResponse` bilan `Cache-Control: private, max-age=300` yuboriladi. Muddati o‘tgan, o‘chirilgan yoki `failed` yozuv 404 qaytaradi.

`GET /api/stories/{id}/viewers` va `DELETE /api/stories/{id}` da joriy actor story egasi bilan solishtiriladi. `POST /api/stories/{id}/reports` matnni 10–300 belgi oralig‘ida tekshiradi.

- [ ] **Step 5: Railway uchun FFmpeg paketini qo‘shish**

`nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = ["...", "ffmpeg"]
```

- [ ] **Step 6: Ruxsat va media testlarini o‘tkazish**

Run: `python -m unittest tests.test_stories.StoryPermissionTests -v`

Expected: 2 tests, `OK`.

---

### Task 4: Bosh sahifa qatori, joylash oynasi va ko‘ruvchi

**Files:**
- Modify: `static/index.html:1-578` for CSS
- Modify: `static/index.html:629-665` for story rail and overlays
- Modify: `static/index.html:1901-1975` for upload helper
- Modify: `static/index.html:3380-3420` for navigation hooks
- Modify: `static/index.html:8643-8735` for actor avatars
- Modify: `static/index.html:10960-11040` for boot
- Test: `tests/test_story_frontend_contract.py`

**Interfaces:**
- Consumes: Task 3 JSON endpoints and current `ME`, `activeMode`, `apiHeaders`, `showMsg` helpers.
- Produces: `loadStories()`, `openStoryComposer()`, `prepareStoryFile(file)`, `uploadStory()`, `openStoryViewer(groupIndex, storyIndex)`, `markStoryViewed(id)`, `closeStoryViewer()`.

- [ ] **Step 1: Frontend kontraktining muvaffaqiyatsiz testini yozish**

```python
from pathlib import Path
import unittest


class StoryFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("static/index.html").read_text(encoding="utf-8")

    def test_story_elements_exist(self):
        for element_id in (
            "storyRail", "storyAddCard", "storyFileInput", "storyComposer",
            "storyPreview", "storyCaption", "storyUploadBtn", "storyViewer",
            "storyViewerMedia", "storyProgress", "storyViewersSheet",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_story_functions_exist(self):
        for function_name in (
            "loadStories", "openStoryComposer", "prepareStoryFile", "uploadStory",
            "openStoryViewer", "markStoryViewed", "closeStoryViewer",
        ):
            self.assertIn(f"function {function_name}(", self.html)
```

- [ ] **Step 2: Testni bajarib elementlar yo‘qligi sabab yiqilishini tekshirish**

Run: `python -m unittest tests.test_story_frontend_contract -v`

Expected: 2 tests fail, `storyRail` va `loadStories` topilmaydi.

- [ ] **Step 3: Mavjud dizayn tokenlari bilan story rail yozish**

Home section ichida reklama banneridan oldin:

```html
<section class="story-strip" aria-label="Istoriyalar">
  <div class="story-rail" id="storyRail">
    <button class="story-card story-add" id="storyAddCard" type="button" aria-label="Istoriya qo‘shish">
      <span class="story-thumb"><span class="story-plus">+</span></span>
      <span class="story-name">Istoriya</span>
    </button>
  </div>
</section>
```

`.story-thumb` 80 × 80 px, `border-radius:18px`, `object-fit:cover`; ko‘rilmagan holat `2px solid var(--primary)`, ko‘rilgan holat `var(--line)`. Rail `display:flex`, `overflow-x:auto`, `scroll-snap-type:x mandatory` bo‘ladi.

- [ ] **Step 4: Composer va viewer HTML/CSS yozish**

Composer pastdan chiqadigan `position:fixed` panel bo‘ladi. Yashirin file input `accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"` va `capture="environment"` ishlatadi. Preview rasm uchun `<img>`, video uchun `<video controls playsinline>` ishlatadi. Matn `maxlength="200"`, progress va bekor qilish tugmasi bor.

Viewer `position:fixed; inset:0; z-index:7000; background:#071514` va markaziy 9:16 media maydonidan iborat. Yuqorida segment progress, egasi, vaqt, yopish va menyu; pastda egasi ko‘rsa ko‘rganlar tugmasi ko‘rinadi.

- [ ] **Step 5: Yuklash va ko‘rish JavaScriptini yozish**

`prepareStoryFile` rasm hajmi, video hajmi va video metadata davomiyligini brauzerda tekshiradi. `uploadStory` `FormData` yaratadi va `XMLHttpRequest` ishlatadi, chunki `xhr.upload.onprogress` real foizni beradi. Headerlar `apiHeaders()` dan ko‘chiriladi; `actor_type` `actorType()` dan olinadi.

`loadStories` `/api/stories/feed?actor_type=` ni chaqirib, xavfsiz `esc()` yordamida kartochkalarni render qiladi. Media URL faqat server qaytargan `/story-media/` va `/story-thumbnail/` qiymatlaridan olinadi. Ko‘rilmagan guruhlar yashil, ko‘rilgan guruhlar xira chegara oladi.

`openStoryViewer` rasmda 5 soniya, videoda video davomiyligi bo‘yicha progress yuritadi; chap/o‘ng tap oldingi/keyingiga o‘tadi. Har story ochilganda `markStoryViewed` bir marta POST yuboradi. Egasi uchun `Ko‘rganlar` va `O‘chirish`, boshqalar uchun `Shikoyat qilish` chiqadi.

- [ ] **Step 6: Boot va profil integratsiyasini qo‘shish**

`boot()` foydalanuvchi holatini olgach `loadStories()` chaqiradi. `nav("home")` ga qaytilganda feed yangilanadi. O‘z kartochkasidagi avatar `activeMode` ga qarab `CURRENT_USER_AVATAR` yoki `CURRENT_BIZ_LOGO` dan olinadi. Profil kartalarida faol istoriya bo‘lsa `.has-story` halqasi qo‘shilib, avatar bosilganda rasm kattalashtirish o‘rniga istoriya ochiladi.

- [ ] **Step 7: Frontend kontrakt testini o‘tkazish**

Run: `python -m unittest tests.test_story_frontend_contract -v`

Expected: 2 tests, `OK`.

---

### Task 5: Build raqami, to‘liq test va responsiv QA

**Files:**
- Modify: `main.py:39,351-354`
- Modify: `static/index.html` only if QA finds story-specific defects
- Test: `tests/test_stories.py`
- Test: `tests/test_story_frontend_contract.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: v1608 build, verified ZIP deliverable.

- [ ] **Step 1: Build metadata testini yozish**

```python
from pathlib import Path
import unittest


class BuildMetadataTests(unittest.TestCase):
    def test_v1608_and_story_flag_exist(self):
        main_text = Path("main.py").read_text(encoding="utf-8")
        self.assertIn('APP_BUILD = "v1608"', main_text)
        self.assertIn('"stories": True', main_text)
```

- [ ] **Step 2: Testning v1607 sabab yiqilishini tekshirish**

Run: `python -m unittest tests.test_story_frontend_contract.BuildMetadataTests -v`

Expected: `APP_BUILD = "v1608"` topilmagani uchun fail.

- [ ] **Step 3: Build metadata yangilash**

`main.py` da `APP_BUILD = "v1608"` qiling va `/api/build` javobiga `"stories": True`, `"story_image_upload": True`, `"story_video_upload": True`, `"story_views": True` xususiyatlarini kiriting.

- [ ] **Step 4: Python sintaksisi va barcha unit testlarni ishga tushirish**

Run: `python -m compileall -q main.py api.py database.py stories.py tests`

Expected: exit 0 va chiqishda xato yo‘q.

Run: `python -m unittest discover -s tests -v`

Expected: barcha testlar `OK`.

- [ ] **Step 5: FFmpeg mavjudligini va 1 soniyalik test videosini tekshirish**

Run: `ffmpeg -version`

Expected: exit 0.

Run: `ffmpeg -f lavfi -i color=c=teal:s=360x640:d=1 -f lavfi -i anullsrc -shortest -c:v libx264 -c:a aac /tmp/koprik-story.mp4 -y`

Expected: `/tmp/koprik-story.mp4` yaratiladi.

Run: `ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /tmp/koprik-story.mp4`

Expected: taxminan `1.000000`.

- [ ] **Step 6: Ishlayotgan serverda asosiy oqimni tekshirish**

Run: `TEST_MODE=1 DB_PATH=/tmp/koprik-stories.db UPLOAD_DIR=/tmp/koprik-uploads uvicorn main:app --host 127.0.0.1 --port 8000`

Expected: server `http://127.0.0.1:8000` da ishga tushadi va `/api/build` `v1608` qaytaradi.

Target flow: `bosh sahifa -> + Istoriya -> rasm/video tanlash -> preview -> Joylash -> kvadrat kartochka -> to‘liq ekran -> ko‘rilgan holat`.

Desktop viewport: 1280 × 800. Mobil viewport: 390 × 844. Ikkalasida gorizontal story rail, 80 × 80 kvadrat, composer, viewer, progress, yopish va ortiqcha scroll tekshiriladi. Konsolda story oqimiga tegishli xato bo‘lmasligi shart.

- [ ] **Step 7: Yakuniy ZIP yaratish va tarkibini tekshirish**

Run: `python -m zipfile -c Platforma_v1608_stories.zip main.py api.py database.py stories.py requirements.txt nixpacks.toml catalog_data.py access_config.py education_statistics.py push_worker.py ai_agent.py static tests docs`

Expected: ZIP yaratiladi.

Run: `python -m zipfile -l Platforma_v1608_stories.zip`

Expected: `stories.py`, `nixpacks.toml`, ikkala test fayli, story CSS/JS saqlangan `static/index.html` va yangilangan backend fayllari ro‘yxatda bor.
