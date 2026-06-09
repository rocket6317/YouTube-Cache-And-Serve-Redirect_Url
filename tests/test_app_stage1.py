import importlib
import unittest
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
