import importlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import scheduler


with patch.object(scheduler, "start_scheduler"):
    app_module = importlib.import_module("app")


class StreamRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_missing_cached_stream_repairs_and_redirects(self):
        with (
            patch.object(app_module, "get_stream", side_effect=[None, "https://example.com/live.m3u8"]),
            patch.object(app_module, "read_channels_file", return_value={"atv": "https://youtube.test/live"}),
            patch.object(app_module.repair_coordinator, "request", return_value="redirected"),
            patch.object(app_module, "log_access") as log_access,
        ):
            response = self.client.get("/stream?name=atv")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "https://example.com/live.m3u8")
        log_access.assert_called_once_with("atv", "127.0.0.1", outcome="redirected")

    def test_stale_googlevideo_cache_repairs_before_redirect(self):
        stale_stream = {
            "m3u8": "https://manifest.googlevideo.com/api/manifest/hls_playlist/live.m3u8",
            "last_success": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        }
        configs = {
            "atv": {
                "url": "https://youtube.com/@atv/live",
                "refresh_hours": 1,
            }
        }
        with (
            patch.object(app_module, "streams_table", return_value={"atv": stale_stream}),
            patch.object(app_module, "read_channel_configs", return_value=configs),
            patch.object(
                app_module,
                "get_stream",
                side_effect=[stale_stream["m3u8"], "https://manifest.googlevideo.com/fresh.m3u8"],
            ),
            patch.object(app_module.repair_coordinator, "request", return_value="redirected") as repair,
            patch.object(app_module, "youtube_stream_is_playable", return_value=True),
            patch.object(app_module, "log_access"),
        ):
            response = self.client.get("/stream?name=atv")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "https://manifest.googlevideo.com/fresh.m3u8")
        repair.assert_called_once_with("atv", timeout=30)

    def test_invalid_googlevideo_cache_repairs_before_interval(self):
        cached_url = "https://manifest.googlevideo.com/cached.m3u8"
        fresh_url = "https://manifest.googlevideo.com/fresh.m3u8"
        stream = {
            "m3u8": cached_url,
            "last_success": datetime.utcnow().isoformat(),
        }
        configs = {
            "kizilcikserbeti": {
                "url": "https://youtube.com/@kizilcikserbetidizi/live",
                "refresh_hours": 1,
            }
        }
        with (
            patch.object(app_module, "streams_table", return_value={"kizilcikserbeti": stream}),
            patch.object(app_module, "read_channel_configs", return_value=configs),
            patch.object(app_module, "get_stream", side_effect=[cached_url, fresh_url]),
            patch.object(
                app_module,
                "youtube_stream_is_playable",
                side_effect=lambda url: url == fresh_url,
            ),
            patch.object(app_module.repair_coordinator, "request", return_value="redirected") as repair,
            patch.object(app_module, "log_access"),
        ):
            response = self.client.get("/stream?name=kizilcikserbeti")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, fresh_url)
        repair.assert_called_once_with("kizilcikserbeti", timeout=30)

    def test_invalid_googlevideo_cache_is_not_served_when_repair_fails(self):
        cached_url = "https://manifest.googlevideo.com/broken.m3u8"
        stream = {
            "m3u8": cached_url,
            "last_success": datetime.utcnow().isoformat(),
        }
        with (
            patch.object(app_module, "streams_table", return_value={"atv": stream}),
            patch.object(app_module, "read_channel_configs", return_value={}),
            patch.object(app_module, "read_channels_file", return_value={"atv": "https://youtube.test/live"}),
            patch.object(app_module, "get_stream", return_value=cached_url),
            patch.object(app_module, "youtube_stream_is_playable", return_value=False),
            patch.object(app_module.repair_coordinator, "request", return_value="repair_failed"),
            patch.object(app_module, "log_access") as log_access,
        ):
            response = self.client.get("/stream?name=atv")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "30")
        log_access.assert_called_once_with("atv", "127.0.0.1", outcome="repair_failed")

    def test_direct_fallback_does_not_refresh_on_playback_request(self):
        fallback_stream = {
            "m3u8": "https://fallback.example.com/now/live.m3u8",
            "status": "fallback",
            "last_success": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        }
        with (
            patch.object(app_module, "streams_table", return_value={"now": fallback_stream}),
            patch.object(app_module, "read_channel_configs", return_value={}),
            patch.object(app_module, "get_stream", return_value=fallback_stream["m3u8"]),
            patch.object(app_module.repair_coordinator, "request") as repair,
            patch.object(app_module, "log_access"),
        ):
            response = self.client.get("/stream?name=now")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, fallback_stream["m3u8"])
        repair.assert_not_called()

    def test_failed_repair_returns_503_with_retry_after_and_logs_outcome(self):
        with (
            patch.object(app_module, "get_stream", return_value=None),
            patch.object(app_module, "read_channels_file", return_value={"atv": "https://youtube.test/live"}),
            patch.object(app_module.repair_coordinator, "request", return_value="cooldown"),
            patch.object(app_module, "log_access") as log_access,
        ):
            response = self.client.get("/stream?name=atv")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "30")
        log_access.assert_called_once_with("atv", "127.0.0.1", outcome="cooldown")

    def test_unknown_stream_stays_404(self):
        with (
            patch.object(app_module, "get_stream", return_value=None),
            patch.object(app_module, "read_channels_file", return_value={}),
            patch.object(app_module, "streams_table", return_value={}),
            patch.object(app_module.repair_coordinator, "request") as request_repair,
        ):
            response = self.client.get("/stream?name=unknown")

        self.assertEqual(response.status_code, 404)
        request_repair.assert_not_called()


if __name__ == "__main__":
    unittest.main()
