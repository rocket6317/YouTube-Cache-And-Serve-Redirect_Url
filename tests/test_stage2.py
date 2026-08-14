import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import db
import scheduler
import settings
import stream_service
from validation import is_m3u8_url, is_youtube_url, normalize_handle, parse_interval


class ChannelConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = db.CHANNELS_PATH
        db.CHANNELS_PATH = str(Path(self.temp_dir.name) / "channels.txt")

    def tearDown(self):
        db.CHANNELS_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_two_and_three_column_rows_round_trip(self):
        configs = {
            "default": {"url": "https://youtube.com/@default/live", "refresh_hours": None},
            "fast": {"url": "https://youtube.com/@fast/live", "refresh_hours": 2},
        }
        db.write_channels_file(configs)
        self.assertEqual(db.read_channel_configs(), configs)
        self.assertEqual(db.read_channels_file()["fast"], "https://youtube.com/@fast/live")

    def test_fallback_m3u8_fourth_column_round_trip(self):
        configs = {
            "now": {
                "url": "https://youtube.com/@now/live",
                "refresh_hours": 1,
                "fallback_url": "https://fallback.example.com/now/live.m3u8",
            }
        }
        db.write_channels_file(configs)
        self.assertEqual(db.read_channel_configs(), configs)
        self.assertEqual(db.read_channels_file()["now"], "https://youtube.com/@now/live")

    def test_repair_source_update_preserves_interval_override(self):
        configs = {
            "atv": {"url": "https://youtube.com/watch?v=old", "refresh_hours": 2}
        }
        info = {
            "source_url": "https://youtube.com/@atv/live",
            "m3u8": "https://example.test/live.m3u8",
            "status": "repaired",
        }
        with (
            patch.object(stream_service, "update_stream"),
            patch.object(stream_service, "write_channels_file") as write_channels,
        ):
            stream_service.save_fetch_result(
                "atv",
                configs["atv"]["url"],
                info,
                channels=configs,
                update_channels=True,
            )
        self.assertEqual(configs["atv"]["refresh_hours"], 2)
        write_channels.assert_called_once_with(configs)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = settings.SETTINGS_PATH
        settings.SETTINGS_PATH = str(Path(self.temp_dir.name) / "settings.json")

    def tearDown(self):
        settings.SETTINGS_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_persisted_setting_overrides_and_resets_environment_default(self):
        settings.set_global_interval(2)
        self.assertEqual(settings.get_global_interval(), 2)
        settings.reset_global_interval()
        self.assertEqual(settings.get_global_interval(), settings.UPDATE_INTERVAL_HOURS)


class SchedulingTests(unittest.TestCase):
    def test_due_calculation_uses_last_attempt(self):
        now = datetime.utcnow()
        self.assertFalse(
            scheduler.stream_is_due(
                {"last_checked": (now - timedelta(minutes=30)).isoformat()},
                1,
                now=now,
            )
        )
        self.assertTrue(
            scheduler.stream_is_due(
                {"last_checked": (now - timedelta(hours=2)).isoformat()},
                1,
                now=now,
            )
        )

    def test_scheduled_refresh_skips_not_due_stream(self):
        with (
            patch.object(
                scheduler,
                "read_channel_configs",
                return_value={"atv": {"url": "https://youtube.com/@atv/live", "refresh_hours": 5}},
            ),
            patch.object(
                scheduler,
                "streams_table",
                return_value={"atv": {"last_checked": datetime.utcnow().isoformat()}},
            ),
            patch.object(scheduler, "refresh_stream") as refresh_stream,
            patch.object(scheduler, "prune_old_logs"),
            patch.object(scheduler, "set_last_update"),
        ):
            scheduler.refresh_from_channels_txt(source="scheduled")
        refresh_stream.assert_not_called()

    def test_manual_force_refresh_ignores_due_time(self):
        with (
            patch.object(
                scheduler,
                "read_channel_configs",
                return_value={"atv": {"url": "https://youtube.com/@atv/live", "refresh_hours": 5}},
            ),
            patch.object(
                scheduler,
                "streams_table",
                return_value={"atv": {"last_checked": datetime.utcnow().isoformat()}},
            ),
            patch.object(scheduler, "refresh_stream", return_value={"m3u8": "https://example.test/live"}) as refresh_stream,
            patch.object(scheduler, "prune_old_logs"),
            patch.object(scheduler, "set_last_update"),
        ):
            scheduler.refresh_from_channels_txt(source="manual", force=True)
        refresh_stream.assert_called_once()


class StreamFallbackTests(unittest.TestCase):
    def test_offline_youtube_source_uses_fallback_without_replacing_source(self):
        configs = {
            "now": {
                "url": "https://youtube.com/@now/live",
                "refresh_hours": 1,
                "fallback_url": "https://fallback.example.com/now/live.m3u8",
            }
        }
        no_live = {
            "m3u8": None,
            "source_url": configs["now"]["url"],
            "status": "no_live_found",
            "last_error": "No current YouTube live stream found",
        }
        with (
            patch.object(stream_service, "fetch_info", return_value=None),
            patch.object(stream_service, "repair_live_info", return_value=no_live),
            patch.object(stream_service, "save_fetch_result") as save_result,
        ):
            result = stream_service.refresh_stream(
                "now",
                configs["now"]["url"],
                channels=configs,
            )

        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["m3u8"], configs["now"]["fallback_url"])
        self.assertEqual(result["source_url"], configs["now"]["url"])
        save_result.assert_called_once_with(
            "now",
            configs["now"]["url"],
            result,
            channels=configs,
            update_channels=False,
        )

    def test_youtube_live_takes_priority_over_configured_fallback(self):
        configs = {
            "now": {
                "url": "https://youtube.com/@now/live",
                "refresh_hours": 1,
                "fallback_url": "https://fallback.example.com/now/live.m3u8",
            }
        }
        youtube_live = {
            "m3u8": "https://manifest.googlevideo.com/live.m3u8",
            "source_url": configs["now"]["url"],
            "status": "ok",
        }
        with (
            patch.object(stream_service, "fetch_info", return_value=youtube_live),
            patch.object(stream_service, "save_fetch_result") as save_result,
        ):
            result = stream_service.refresh_stream(
                "now",
                configs["now"]["url"],
                channels=configs,
            )

        self.assertIs(result, youtube_live)
        save_result.assert_called_once_with("now", configs["now"]["url"], youtube_live)


class ValidationTests(unittest.TestCase):
    def test_handle_normalization_and_youtube_validation(self):
        self.assertEqual(normalize_handle(" My ATV Channel! "), "my-atv-channel")
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_youtube_url("https://youtu.be/abc"))
        self.assertFalse(is_youtube_url("https://example.com/watch?v=abc"))
        self.assertTrue(is_m3u8_url("https://fallback.example.com/live.m3u8?token=abc"))
        self.assertFalse(is_m3u8_url("https://fallback.example.com/live.mp4"))
        self.assertIsNone(parse_interval("default"))
        self.assertEqual(parse_interval("3"), 3)
        with self.assertRaises(ValueError):
            parse_interval("6")


if __name__ == "__main__":
    unittest.main()
