import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from stories import (
    delete_story_files,
    probe_video_seconds,
    transcode_video,
    write_story_bytes,
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg kerak")
class StoryVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.source = self.folder / "source.mp4"
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=teal:s=180x320:d=1",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-shortest", "-c:v", "libx264", "-c:a", "aac",
                str(self.source),
            ],
            check=True,
            timeout=60,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_probe_reads_real_duration(self):
        duration = probe_video_seconds(str(self.source))
        self.assertGreater(duration, 0.8)
        self.assertLess(duration, 1.2)

    def test_transcode_creates_mp4_and_thumbnail(self):
        output = self.folder / "output.mp4"
        thumbnail = self.folder / "thumb.jpg"
        transcode_video(str(self.source), str(output), str(thumbnail))
        self.assertTrue(output.is_file())
        self.assertTrue(thumbnail.is_file())
        self.assertGreater(output.stat().st_size, 0)
        self.assertGreater(thumbnail.stat().st_size, 0)


class StoryFileTests(unittest.TestCase):
    def test_write_and_delete_story_files(self):
        with tempfile.TemporaryDirectory() as folder:
            target = write_story_bytes(folder, "photo.jpg", b"image-data")
            self.assertEqual(Path(target).read_bytes(), b"image-data")
            delete_story_files(folder, "photo.jpg", "")
            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
