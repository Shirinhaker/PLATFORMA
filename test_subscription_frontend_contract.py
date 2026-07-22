import base64
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import unittest


TEST_ROOT = tempfile.mkdtemp(prefix="koprik-story-api-")
os.environ["DB_PATH"] = os.path.join(TEST_ROOT, "platforma.db")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_ROOT, "uploads")
os.environ["STORY_UPLOAD_DIR"] = os.path.join(TEST_ROOT, "stories")
os.environ["TEST_MODE"] = "1"

from fastapi.testclient import TestClient

import access_config
from database import db
from main import app


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class StoryApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_restricted = access_config.PROJECT_ACCESS_RESTRICTED
        access_config.PROJECT_ACCESS_RESTRICTED = False
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        now = int(time.time())
        conn = db()
        conn.execute(
            "INSERT INTO users(login,pass_hash,role,name,created_at) VALUES(?,?,?,?,?)",
            ("story_owner", "x", "user", "Istoriya egasi", now),
        )
        cls.owner_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO users(login,pass_hash,role,name,created_at) VALUES(?,?,?,?,?)",
            ("story_viewer", "x", "user", "Tomoshabin", now),
        )
        cls.viewer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        cls.owner_token = "owner-token"
        cls.viewer_token = "viewer-token"
        for user_id, token in ((cls.owner_id, cls.owner_token), (cls.viewer_id, cls.viewer_token)):
            conn.execute(
                "INSERT INTO mobile_sessions(user_id,token_hash,created_at,expires_at,last_used_at,revoked_at) VALUES(?,?,?,?,?,0)",
                (user_id, hashlib.sha256(token.encode()).hexdigest(), now, now + 3600, now),
            )
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
            (cls.business_id, "Reklama xodimi", "active", now, '["ads"]', 1),
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
            (cls.business_id, "Oddiy xodim", "active", now, '["items"]', 1),
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
        conn.commit()
        conn.close()
        cls.video_path = os.path.join(TEST_ROOT, "portrait.mp4")
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", "color=c=0x0E8C84:s=240x320:d=1", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", cls.video_path,
            ],
            check=True,
            timeout=30,
        )

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        access_config.PROJECT_ACCESS_RESTRICTED = cls.original_restricted
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def auth(self, token):
        return {"Authorization": "Bearer " + token}

    def staff_auth(self, token):
        return {
            "X-Telegram-Init-Data": "staff:" + token,
            "X-Staff-Token": token,
        }

    def test_create_feed_view_viewers_media_and_delete(self):
        created = self.client.post(
            "/api/stories",
            headers=self.auth(self.owner_token),
            files={"file": ("story.png", PNG_1X1, "image/png")},
            data={"caption": "Bugungi yangilik", "actor_type": "user"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        story_id = created.json()["story"]["id"]

        feed = self.client.get("/api/stories/feed?actor_type=user", headers=self.auth(self.viewer_token))
        self.assertEqual(feed.status_code, 200, feed.text)
        owner_group = next(
            group
            for group in feed.json()
            if group["owner_type"] == "user" and group["owner_id"] == self.owner_id
        )
        self.assertIn(story_id, [story["id"] for story in owner_group["stories"]])

        media = self.client.get(f"/story-media/{story_id}")
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.content, PNG_1X1)

        viewed = self.client.post(f"/api/stories/{story_id}/view", headers=self.auth(self.viewer_token))
        self.assertEqual(viewed.status_code, 200, viewed.text)
        viewers = self.client.get(
            f"/api/stories/{story_id}/viewers?actor_type=user",
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(viewers.status_code, 200, viewers.text)
        self.assertEqual(viewers.json()[0]["name"], "Tomoshabin")

        deleted = self.client.delete(
            f"/api/stories/{story_id}?actor_type=user",
            headers=self.auth(self.owner_token),
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.client.get(f"/story-media/{story_id}").status_code, 404)

    def test_portrait_mp4_upload_is_processed_and_published(self):
        with open(self.video_path, "rb") as source:
            video_bytes = source.read()
        created = self.client.post(
            "/api/stories",
            headers=self.auth(self.owner_token),
            files={"file": ("portrait.mp4", video_bytes, "video/mp4")},
            data={"caption": "Video sinovi", "actor_type": "user"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        story = created.json()["story"]
        self.assertEqual(story["media_type"], "video")
        self.assertGreater(story["duration_seconds"], 0)
        media = self.client.get(story["media_url"])
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.headers["content-type"], "video/mp4")

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


if __name__ == "__main__":
    unittest.main()
