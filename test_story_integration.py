import unittest
from pathlib import Path


class ListingMediaFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("static/index.html").read_text(encoding="utf-8")
        # v1628: CSS va JS index.html ichida
        cls.css = cls.html
        cls.js = cls.html
        cls.main = Path("main.py").read_text(encoding="utf-8")

    def test_upload_selection_renders_real_image_and_video_previews(self):
        for value in (
            "function listingMediaVisualHtml(",
            'class="listing-upload-open"',
            'listingMediaVisualHtml(m,"listing-upload-visual")',
            "primeListingVideoPreviews(box)",
        ):
            self.assertIn(value, self.js)

    def test_published_listing_media_uses_one_shared_card_size(self):
        self.assertIn("function listingMediaGridHtml(", self.js)
        self.assertIn("aspect-ratio:4/3", self.css)
        self.assertIn(".listing-media-card img,.listing-media-card video", self.css)
        self.assertIn("object-fit:cover", self.css)

    def test_image_and_video_open_in_large_viewer(self):
        self.assertIn('id="imageViewerVideo"', self.html)
        self.assertIn("function openListingMediaViewer(", self.js)
        self.assertIn("data-listing-media-src", self.js)
        self.assertIn("video.play()", self.js)

    def test_submit_waits_until_media_upload_finishes(self):
        self.assertIn("var listingUploadPending = 0;", self.js)
        self.assertIn("if(listingUploadPending>0)", self.js)
        self.assertIn("Media yuklanishi tugashini kuting.", self.js)

    def test_release_metadata_is_v1629(self):
        self.assertIn('APP_BUILD = "v1629"', self.main)
        self.assertIn('"listing_media_preview_v1624": True', self.main)


if __name__ == "__main__":
    unittest.main()
