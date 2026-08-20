import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
import fetcher
import scheduler


with patch.object(scheduler, "start_scheduler"):
    app_module = importlib.import_module("app")


class AdaptiveExtractionTests(unittest.TestCase):
    def test_normalises_separate_video_and_audio_playlists(self):
        info = {
            "title": "Live programme",
            "is_live": True,
            "requested_formats": [
                {
                    "format_id": "270",
                    "url": "https://manifest.googlevideo.com/video.m3u8",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "tbr": 5420.722,
                },
                {
                    "format_id": "234",
                    "url": "https://manifest.googlevideo.com/audio.m3u8",
                    "vcodec": "none",
                    "acodec": None,
                },
            ],
        }

        result = fetcher._normalise_stream_info(
            info,
            "https://www.youtube.com/watch?v=current",
            "channel",
        )

        self.assertEqual(result["stream_mode"], "adaptive")
        self.assertIsNone(result["m3u8"])
        self.assertEqual(result["video_m3u8"], info["requested_formats"][0]["url"])
        self.assertEqual(result["audio_m3u8"], info["requested_formats"][1]["url"])
        self.assertEqual(result["video_height"], 1080)

    def test_keeps_legacy_combined_manifest_shape(self):
        result = fetcher._normalise_stream_info(
            {
                "url": "https://manifest.googlevideo.com/combined.m3u8",
                "is_live": True,
            },
            "https://www.youtube.com/watch?v=current",
        )

        self.assertEqual(result["stream_mode"], "legacy")
        self.assertEqual(result["m3u8"], "https://manifest.googlevideo.com/combined.m3u8")


class AdaptiveDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "db.json")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_adaptive_update_preserves_existing_legacy_rollback_manifest(self):
        legacy_url = "https://manifest.googlevideo.com/combined.m3u8"
        db.update_stream("channel", "https://youtube.test/live", legacy_url, "Channel")

        db.update_stream(
            "channel",
            "https://youtube.test/live",
            None,
            "Channel",
            stream_mode="adaptive",
            video_m3u8="https://manifest.googlevideo.com/video.m3u8",
            audio_m3u8="https://manifest.googlevideo.com/audio.m3u8",
        )

        stream = db.streams_table()["channel"]
        self.assertEqual(stream["m3u8"], legacy_url)
        self.assertEqual(stream["stream_mode"], "adaptive")
        self.assertTrue(stream["video_m3u8"])
        self.assertTrue(stream["audio_m3u8"])


class AdaptiveRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()
        self.stream = {
            "url": "https://youtube.test/live",
            "stream_mode": "adaptive",
            "video_m3u8": "https://manifest.googlevideo.com/video.m3u8",
            "audio_m3u8": "https://manifest.googlevideo.com/audio.m3u8",
            "video_codec": "avc1.640028",
            "audio_codec": "mp4a.40.2",
            "video_width": 1920,
            "video_height": 1080,
            "video_fps": 30,
            "bandwidth": 5420722,
        }

    def test_stream_returns_stable_adaptive_master_playlist(self):
        with (
            patch.object(app_module, "streams_table", return_value={"channel": self.stream}),
            patch.object(app_module, "read_channel_configs", return_value={}),
            patch.object(app_module, "log_access"),
        ):
            response = self.client.get("/stream?name=channel")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/vnd.apple.mpegurl")
        self.assertIn(b'#EXT-X-MEDIA:TYPE=AUDIO', response.data)
        self.assertIn(b"/hls/audio?name=channel", response.data)
        self.assertIn(b"/hls/video?name=channel", response.data)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_media_route_repairs_invalid_signed_playlist_then_serves_fresh_one(self):
        fresh = dict(
            self.stream,
            video_m3u8="https://manifest.googlevideo.com/fresh-video.m3u8",
        )
        with (
            patch.object(app_module, "streams_table", side_effect=[{"channel": self.stream}, {"channel": fresh}]),
            patch.object(app_module, "youtube_stream_is_playable", side_effect=[False, True]),
            patch.object(app_module.repair_coordinator, "request", return_value="redirected") as repair,
            patch.object(app_module, "load_media_playlist", return_value="#EXTM3U\n#EXTINF:5,\nhttps://media.test/segment.ts\n"),
        ):
            response = self.client.get("/hls/video?name=channel")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"https://media.test/segment.ts", response.data)
        repair.assert_called_once_with("channel", timeout=30)


if __name__ == "__main__":
    unittest.main()
