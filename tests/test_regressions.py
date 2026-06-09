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


if __name__ == "__main__":
    unittest.main()
