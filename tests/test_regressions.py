import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import db
import fetcher


class StableChannelRepairTests(unittest.TestCase):
    def test_private_watch_url_repairs_from_stored_channel_url(self):
        old_url = "https://www.youtube.com/watch?v=old-private-video"
        stable_url = "https://www.youtube.com/@atvturkiye/live"

        def fake_extract(url, channel_name=None):
            if url == stable_url:
                return {
                    "url": "https://example.com/atv.m3u8",
                    "channel": "atv",
                    "is_live": True,
                    "channel_id": "UC-atv",
                    "channel_url": "https://www.youtube.com/@atvturkiye",
                }
            return None

        metadata_ydl = Mock()
        metadata_ydl.__enter__ = Mock(return_value=metadata_ydl)
        metadata_ydl.__exit__ = Mock(return_value=False)
        metadata_ydl.extract_info.return_value = {}

        with (
            patch.object(fetcher, "_extract_info", side_effect=fake_extract),
            patch.object(fetcher.yt_dlp, "YoutubeDL", return_value=metadata_ydl),
        ):
            info = fetcher.repair_live_info(
                old_url,
                "atv",
                known_channel_url="https://www.youtube.com/@atvturkiye",
                known_channel_id="UC-atv",
            )

        self.assertEqual(info["status"], "repaired")
        self.assertEqual(info["source_url"], stable_url)
        self.assertEqual(info["channel_url"], "https://www.youtube.com/@atvturkiye")
        self.assertEqual(info["channel_id"], "UC-atv")
        self.assertTrue(info["m3u8"])

    def test_streams_discovery_auto_selects_only_live_candidate(self):
        old_url = "https://www.youtube.com/watch?v=old"
        streams_url = "https://www.youtube.com/@nowtvturkiye/streams"

        metadata = {
            "title": "NOW Canli Yayin",
            "channel_url": "https://www.youtube.com/@nowtvturkiye",
            "channel_id": "UC-now",
        }
        playlist = {
            "entries": [
                {"url": "https://www.youtube.com/watch?v=ended", "title": "NOW Canli Yayin"},
                {"url": "https://www.youtube.com/watch?v=current", "title": "NOW Canli Yayin"},
            ]
        }

        def extract(url, channel_name=None):
            if url == old_url:
                return None
            if url == streams_url:
                return playlist
            if url.endswith("current"):
                return {
                    "url": "https://example.com/current.m3u8",
                    "webpage_url": url,
                    "title": "NOW Canli Yayin",
                    "is_live": True,
                    "live_status": "is_live",
                    "channel_url": "https://www.youtube.com/@nowtvturkiye",
                    "channel_id": "UC-now",
                }
            if url.endswith("ended"):
                return {"url": "https://example.com/ended.mp4", "is_live": False}
            return None

        with (
            patch.object(fetcher, "_extract_info", side_effect=extract),
            patch.object(fetcher, "_read_metadata", return_value=metadata),
            patch.object(fetcher, "_extract_flat_playlist", return_value=playlist),
        ):
            info = fetcher.repair_live_info(old_url, "now")

        self.assertEqual(info["status"], "repaired")
        self.assertEqual(info["source_url"], "https://www.youtube.com/watch?v=current")

    def test_multiple_live_candidates_require_selection_when_titles_are_ambiguous(self):
        old_url = "https://www.youtube.com/watch?v=old"
        metadata = {
            "title": "Tomorrowland Live",
            "channel_url": "https://www.youtube.com/@tomorrowland",
            "channel_id": "UC-tomorrowland",
        }
        playlist = {
            "entries": [
                {"url": "https://www.youtube.com/watch?v=stage-a", "title": "Main Stage"},
                {"url": "https://www.youtube.com/watch?v=stage-b", "title": "Freedom Stage"},
            ]
        }

        def extract(url, channel_name=None):
            if url == old_url:
                return None
            if "watch?v=stage-" in url:
                return {
                    "url": f"https://example.com/{url[-1]}.m3u8",
                    "webpage_url": url,
                    "title": "Main Stage" if url.endswith("a") else "Freedom Stage",
                    "is_live": True,
                    "live_status": "is_live",
                    "channel_url": "https://www.youtube.com/@tomorrowland",
                    "channel_id": "UC-tomorrowland",
                }
            return None

        with (
            patch.object(fetcher, "_extract_info", side_effect=extract),
            patch.object(fetcher, "_read_metadata", return_value=metadata),
            patch.object(fetcher, "_extract_flat_playlist", return_value=playlist),
        ):
            info = fetcher.repair_live_info(old_url, "tomorrowland")

        self.assertEqual(info["status"], "selection_required")
        self.assertEqual(len(info["live_candidates"]), 2)
        self.assertIsNone(info["m3u8"])

    def test_multiple_live_candidates_auto_select_unique_title_match(self):
        candidates = [
            {"title": "Tomorrowland Main Stage Live"},
            {"title": "Tomorrowland Freedom Stage Live"},
        ]
        selected = fetcher._select_live_candidate(
            candidates,
            "Tomorrowland Freedom Stage Live",
        )
        self.assertEqual(selected["title"], "Tomorrowland Freedom Stage Live")


class AtomicDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        self.original_channels_path = db.CHANNELS_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "db.json")
        db.CHANNELS_PATH = str(Path(self.temp_dir.name) / "channels.txt")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_db_path
        db.CHANNELS_PATH = self.original_channels_path
        self.temp_dir.cleanup()

    def test_concurrent_stream_and_access_updates_do_not_erase_cache(self):
        errors = []

        def update_streams():
            try:
                for index in range(100):
                    db.update_stream(
                        f"stream-{index}",
                        f"https://youtube.test/{index}",
                        f"https://m3u8.test/{index}",
                        f"Channel {index}",
                        channel_url=f"https://www.youtube.com/@channel{index}",
                        channel_id=f"UC{index}",
                    )
            except Exception as exc:
                errors.append(exc)

        def log_accesses():
            try:
                for index in range(100):
                    db.log_access(f"stream-{index}", "127.0.0.1")
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=update_streams),
            threading.Thread(target=log_accesses),
            threading.Thread(target=log_accesses),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        data = json.loads(Path(db.DB_PATH).read_text())
        self.assertEqual(len(data["streams"]), 100)
        self.assertEqual(len(data["access_log"]), 200)
        self.assertEqual(
            data["streams"]["stream-99"]["channel_url"],
            "https://www.youtube.com/@channel99",
        )

    def test_stream_refresh_preserves_short_url(self):
        db.update_stream(
            "atv",
            "https://youtube.com/@atv/live",
            "https://m3u8.test/first",
            "ATV",
        )
        db.set_stream_short_url("atv", "https://ur.example/atv")
        db.update_stream(
            "atv",
            "https://youtube.com/@atv/live",
            "https://m3u8.test/second",
            "ATV",
        )
        self.assertEqual(db.streams_table()["atv"]["short_url"], "https://ur.example/atv")


if __name__ == "__main__":
    unittest.main()
