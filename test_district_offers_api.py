from pathlib import Path
import unittest

try:
    from .frontend_source import frontend_source
except ImportError:
    from frontend_source import frontend_source


class StoryFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = frontend_source()

    def test_story_elements_exist(self):
        for element_id in (
            "storyRail",
            "storyAddCard",
            "storyFileInput",
            "storyComposer",
            "storyPreview",
            "storyCaption",
            "storyUploadBtn",
            "storyUploadStatus",
            "storyViewer",
            "storyViewerMedia",
            "storyProgress",
            "storyViewersSheet",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_story_functions_exist(self):
        for function_name in (
            "loadStories",
            "openStoryComposer",
            "prepareStoryFile",
            "uploadStory",
            "openStoryViewer",
            "markStoryViewed",
            "closeStoryViewer",
            "openStoryOwnerProfile",
        ):
            self.assertIn(f"function {function_name}(", self.html)

    def test_story_rail_distinguishes_story_and_profile_only_cards(self):
        for value in (
            'data-story-owner="1"',
            'class="story-card \'+state',
            'var state=hasStory?(group.has_unseen?"unseen":"seen"):"no-story"',
            'if(!hasStory){openStoryOwnerProfile(group);return;}',
        ):
            self.assertIn(value, self.html)

    def test_story_viewer_owner_header_is_a_profile_button(self):
        self.assertIn('id="storyOwnerProfileBtn"', self.html)
        self.assertIn(
            'el("storyOwnerProfileBtn").addEventListener("click"',
            self.html,
        )

    def test_story_media_limits_are_visible_in_client(self):
        self.assertIn("60*1000", self.html)
        self.assertIn("100*1024*1024", self.html)
        self.assertIn('maxlength="200"', self.html)

    def test_video_upload_has_separate_transfer_and_processing_states(self):
        self.assertIn("Video serverda tayyorlanmoqda...", self.html)
        self.assertIn("Fayl yuborilmoqda", self.html)
        self.assertIn("storyUploadError", self.html)

    def test_hidden_preview_media_cannot_share_the_preview_width(self):
        self.assertIn(".story-preview [hidden]{display:none!important;}", self.html)

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


class BuildMetadataTests(unittest.TestCase):
    def test_v1615_release_flags_exist(self):
        main_text = Path("main.py").read_text(encoding="utf-8")
        html_text = Path("static/index.html").read_text(encoding="utf-8")
        self.assertIn('APP_BUILD = "v1629"', main_text)
        self.assertIn('"stories": True', main_text)
        self.assertIn('"story_archive": True', main_text)
        self.assertIn('"story_video_upload_fix": True', main_text)
        self.assertIn('"railpack_ffmpeg": True', main_text)
        self.assertIn('"business_subscriptions_demo": True', main_text)
        self.assertIn('"district_offers": True', main_text)
        self.assertIn('"stories_subscription_independent": True', main_text)
        self.assertIn('"pro_follow_map": True', main_text)
        self.assertIn('"temporary_privileged_access_only": False', main_text)
        self.assertIn('<!-- BUILD: v1629 -->', html_text)


if __name__ == "__main__":
    unittest.main()
