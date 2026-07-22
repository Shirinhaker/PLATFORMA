import os
import sqlite3
import tempfile
import unittest

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


def make_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE users(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            lat REAL,
            lng REAL,
            avatar_file TEXT DEFAULT ''
        );
        CREATE TABLE businesses(
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            lat REAL,
            lng REAL,
            logo_file TEXT DEFAULT '',
            status TEXT DEFAULT 'active'
        );
        CREATE TABLE follows(
            follower_id INTEGER NOT NULL,
            target_kind TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(follower_id,target_kind,target_id)
        );
        CREATE TABLE business_follows(
            business_id INTEGER NOT NULL,
            target_kind TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(business_id,target_kind,target_id)
        );
        """
    )
    for user_id, name in ((1, "Egasi"), (2, "Ko‘ruvchi"), (3, "Obuna profil"), (4, "Yaqin profil")):
        conn.execute(
            "INSERT INTO users(id,name,lat,lng,avatar_file) VALUES(?,?,?,?,?)",
            (user_id, name, 37.22 + user_id / 1000, 67.28, ""),
        )
    conn.execute(
        "INSERT INTO businesses(id,user_id,name,lat,lng,logo_file,status) VALUES(?,?,?,?,?,?,?)",
        (10, 1, "Egasi biznesi", 37.22, 67.28, "", "active"),
    )
    conn.execute(
        "INSERT INTO businesses(id,user_id,name,lat,lng,logo_file,status) VALUES(?,?,?,?,?,?,?)",
        (11, 3, "Obuna biznes", 37.223, 67.28, "", "active"),
    )
    ensure_story_tables(conn)
    conn.commit()
    return conn


class StoryBase(unittest.TestCase):
    def setUp(self):
        self.conn = make_connection()

    def tearDown(self):
        self.conn.close()

    def create_active_story(
        self,
        owner_type="user",
        owner_id=1,
        creator_id=1,
        filename="story.jpg",
        now=1_000,
    ):
        story_id = create_story_record(
            self.conn,
            {
                "owner_type": owner_type,
                "owner_id": owner_id,
                "created_by_user_id": creator_id,
            },
            {
                "media_type": "image",
                "mime_type": "image/jpeg",
                "caption": "Yangilik",
                "duration_seconds": 0,
            },
            filename,
            "",
            now=now,
        )
        activate_story(self.conn, story_id)
        return story_id


class StorySchemaTests(StoryBase):
    def test_story_tables_exist(self):
        names = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue(
            {"stories", "story_views", "story_reports"}.issubset(names)
        )

    def test_rejects_sixty_one_second_video(self):
        with self.assertRaisesRegex(StoryValidationError, "60 soniya"):
            validate_story_upload("video/mp4", 2_000_000, 61.0, "")

    def test_accepts_image_and_trims_caption(self):
        result = validate_story_upload(
            "image/jpeg", 900_000, 0, " Salom "
        )
        self.assertEqual(result["media_type"], "image")
        self.assertEqual(result["caption"], "Salom")

    def test_rejects_caption_over_two_hundred_characters(self):
        with self.assertRaisesRegex(StoryValidationError, "200"):
            validate_story_upload("image/png", 100, 0, "x" * 201)

    def test_sniffs_supported_file_signatures(self):
        self.assertEqual(sniff_media_type(b"\xff\xd8\xffmore"), "image/jpeg")
        self.assertEqual(sniff_media_type(b"\x89PNG\r\n\x1a\nmore"), "image/png")
        self.assertEqual(sniff_media_type(b"RIFFxxxxWEBPmore"), "image/webp")
        self.assertEqual(sniff_media_type(b"\x00\x00\x00\x18ftypisom"), "video/mp4")

    def test_rejects_signature_mismatch(self):
        self.assertEqual(sniff_media_type(b"not-media"), "")


class StoryLifecycleTests(StoryBase):
    def test_expired_story_is_not_active(self):
        story_id = self.create_active_story(now=1_000)
        self.assertIsNone(
            active_story(
                self.conn,
                story_id,
                now=1_000 + STORY_TTL_SECONDS + 1,
            )
        )

    def test_view_is_counted_once(self):
        story_id = self.create_active_story()
        record_story_view(self.conn, story_id, 2, now=2_000)
        record_story_view(self.conn, story_id, 2, now=2_100)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM story_views WHERE story_id=?", (story_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_eleventh_active_story_is_rejected(self):
        for index in range(MAX_ACTIVE_STORIES):
            self.create_active_story(
                filename=f"{index}.jpg", now=2_000 + index
            )
        with self.assertRaisesRegex(StoryValidationError, "10 ta"):
            self.create_active_story(filename="eleven.jpg", now=2_100)

    def test_failed_story_does_not_use_active_limit(self):
        story_id = create_story_record(
            self.conn,
            {"owner_type": "user", "owner_id": 1, "created_by_user_id": 1},
            {
                "media_type": "image",
                "mime_type": "image/jpeg",
                "caption": "",
                "duration_seconds": 0,
            },
            "failed.jpg",
            "",
            now=3_000,
        )
        fail_story(self.conn, story_id)
        rows = list_owner_stories(self.conn, "user", 1, 3_001)
        self.assertEqual(rows, [])

    def test_managed_stories_split_active_and_archive_with_view_counts(self):
        archived_id = self.create_active_story(filename="archive.jpg", now=1_000)
        active_id = self.create_active_story(
            filename="active.jpg",
            now=1_000 + STORY_TTL_SECONDS,
        )
        record_story_view(self.conn, archived_id, 2, now=1_001)
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


class StoryPermissionTests(StoryBase):
    def test_owner_can_manage_and_other_user_cannot(self):
        story_id = self.create_active_story()
        self.assertTrue(can_manage_story(self.conn, story_id, "user", 1))
        self.assertFalse(can_manage_story(self.conn, story_id, "user", 2))

    def test_business_owner_type_is_separate(self):
        story_id = self.create_active_story(
            owner_type="business", owner_id=10, creator_id=1
        )
        self.assertTrue(
            can_manage_story(self.conn, story_id, "business", 10)
        )
        self.assertFalse(can_manage_story(self.conn, story_id, "user", 1))

    def test_report_is_unique_per_reporter(self):
        story_id = self.create_active_story()
        report_story(self.conn, story_id, 2, "Nomaqbul kontent", now=3_000)
        report_story(self.conn, story_id, 2, "Takroriy shikoyat", now=3_100)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM story_reports "
            "WHERE story_id=? AND reporter_user_id=2",
            (story_id,),
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_owner_can_see_viewer_list(self):
        story_id = self.create_active_story()
        record_story_view(self.conn, story_id, 2, now=2_000)
        viewers = list_story_viewers(self.conn, story_id)
        self.assertEqual(viewers[0]["id"], 2)
        self.assertEqual(viewers[0]["name"], "Ko‘ruvchi")


class StoryFeedTests(StoryBase):
    def test_followed_user_without_story_is_in_feed(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'user',3,1)"
        )

        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            lat=37.222,
            lng=67.28,
            now=5_200,
        )

        self.assertEqual([item["owner_id"] for item in feed], [3])
        self.assertTrue(feed[0]["is_followed"])
        self.assertFalse(feed[0]["has_story"])
        self.assertFalse(feed[0]["has_unseen"])
        self.assertEqual(feed[0]["stories"], [])

    def test_followed_business_without_story_is_in_feed(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'business',11,1)"
        )

        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            now=5_200,
        )

        self.assertEqual(feed[0]["owner_type"], "business")
        self.assertEqual(feed[0]["owner_id"], 11)
        self.assertFalse(feed[0]["has_story"])

    def test_business_actor_sees_followed_profile_without_story(self):
        self.conn.execute(
            "INSERT INTO business_follows(business_id,target_kind,target_id,created_at) "
            "VALUES(10,'user',3,1)"
        )

        feed = list_story_feed(
            self.conn,
            viewer_user_id=1,
            actor_type="business",
            actor_id=10,
            now=5_200,
        )

        self.assertEqual(feed[0]["owner_type"], "user")
        self.assertEqual(feed[0]["owner_id"], 3)
        self.assertTrue(feed[0]["is_followed"])
        self.assertFalse(feed[0]["has_story"])

    def test_followed_profile_without_story_precedes_nonfollowed_active_story(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'user',3,1)"
        )
        self.create_active_story(owner_id=4, creator_id=4, now=5_100)

        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            now=5_200,
        )

        self.assertEqual([item["owner_id"] for item in feed], [3, 4])
        self.assertFalse(feed[0]["has_story"])
        self.assertTrue(feed[1]["has_story"])

    def test_guest_feed_excludes_profiles_without_active_story(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'user',3,1)"
        )
        self.create_active_story(owner_id=4, creator_id=4, now=5_100)

        feed = list_story_feed(
            self.conn,
            viewer_user_id=0,
            actor_type="user",
            actor_id=0,
            now=5_200,
        )

        self.assertEqual([item["owner_id"] for item in feed], [4])
        self.assertTrue(feed[0]["has_story"])

    def test_followed_active_owner_is_not_duplicated(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'user',3,1)"
        )
        self.create_active_story(owner_id=3, creator_id=3, now=5_100)

        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            now=5_200,
        )

        self.assertEqual([item["owner_id"] for item in feed], [3])
        self.assertTrue(feed[0]["has_story"])

    def test_followed_unseen_owner_comes_before_nearby_owner(self):
        self.conn.execute(
            "INSERT INTO follows(follower_id,target_kind,target_id,created_at) "
            "VALUES(2,'user',3,1)"
        )
        self.create_active_story(owner_id=4, creator_id=4, now=5_100)
        followed_story = self.create_active_story(
            owner_id=3, creator_id=3, now=5_000
        )
        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            lat=37.222,
            lng=67.28,
            now=5_200,
        )
        self.assertEqual(feed[0]["owner_id"], 3)
        self.assertEqual(feed[0]["stories"][0]["id"], followed_story)
        self.assertTrue(feed[0]["has_unseen"])

    def test_viewed_owner_moves_after_unseen_owner(self):
        first = self.create_active_story(owner_id=3, creator_id=3, now=6_000)
        self.create_active_story(owner_id=4, creator_id=4, now=5_900)
        record_story_view(self.conn, first, 2, now=6_100)
        feed = list_story_feed(
            self.conn,
            viewer_user_id=2,
            actor_type="user",
            actor_id=2,
            lat=37.222,
            lng=67.28,
            now=6_200,
        )
        self.assertEqual(feed[0]["owner_id"], 4)
        self.assertFalse(feed[-1]["has_unseen"])


class StoryStorageTests(unittest.TestCase):
    def test_storage_directory_can_be_overridden(self):
        from stories import story_storage_dir

        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("STORY_UPLOAD_DIR")
            os.environ["STORY_UPLOAD_DIR"] = folder
            try:
                self.assertEqual(story_storage_dir("unused"), folder)
            finally:
                if old is None:
                    os.environ.pop("STORY_UPLOAD_DIR", None)
                else:
                    os.environ["STORY_UPLOAD_DIR"] = old


if __name__ == "__main__":
    unittest.main()
