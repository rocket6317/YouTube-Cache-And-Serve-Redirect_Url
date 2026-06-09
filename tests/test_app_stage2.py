import importlib
import unittest
from unittest.mock import patch

import scheduler


with patch.object(scheduler, "start_scheduler"):
    app_module = importlib.import_module("app")


class Stage2DashboardRouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_add_normalizes_handle_and_preserves_interval(self):
        with (
            patch.object(app_module, "read_channel_configs", return_value={}),
            patch.object(app_module, "fetch_info", return_value=None),
            patch.object(app_module, "update_stream"),
            patch.object(app_module, "write_channels_file") as write_channels,
        ):
            response = self.client.post(
                "/dashboard/add",
                data={
                    "name": " My ATV Channel! ",
                    "url": "https://www.youtube.com/@atv/live",
                    "refresh_hours": "2",
                },
            )
        self.assertEqual(response.status_code, 302)
        write_channels.assert_called_once_with(
            {
                "my-atv-channel": {
                    "url": "https://www.youtube.com/@atv/live",
                    "refresh_hours": 2,
                }
            }
        )

    def test_dashboard_renders_interval_and_failed_source_controls(self):
        with (
            patch.object(
                app_module,
                "streams_table",
                return_value={"atv": {"url": "https://youtube.com/watch?v=old", "status": "failed"}},
            ),
            patch.object(
                app_module,
                "read_channel_configs",
                return_value={"atv": {"url": "https://youtube.com/watch?v=old", "refresh_hours": 2}},
            ),
            patch.object(app_module, "load_db", return_value={}),
            patch.object(app_module, "get_global_interval", return_value=5),
        ):
            response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Edit Source", response.data)
        self.assertIn(b'value="2" selected', response.data)

    def test_dashboard_renders_ambiguous_live_candidate_selector(self):
        with (
            patch.object(
                app_module,
                "streams_table",
                return_value={
                    "tomorrowland": {
                        "status": "selection_required",
                        "live_candidates": [
                            {
                                "title": "Main Stage",
                                "url": "https://www.youtube.com/watch?v=main",
                            }
                        ],
                    }
                },
            ),
            patch.object(
                app_module,
                "read_channel_configs",
                return_value={
                    "tomorrowland": {
                        "url": "https://www.youtube.com/watch?v=old",
                        "refresh_hours": None,
                    }
                },
            ),
            patch.object(app_module, "load_db", return_value={}),
            patch.object(app_module, "get_global_interval", return_value=5),
        ):
            response = self.client.get("/dashboard")
        self.assertIn(b"Select Live Stream", response.data)
        self.assertIn(b"Main Stage", response.data)

    def test_add_rejects_normalized_collision_with_existing_handle(self):
        with (
            patch.object(
                app_module,
                "read_channel_configs",
                return_value={"Now TV": {"url": "https://youtube.com/watch?v=old", "refresh_hours": None}},
            ),
            patch.object(app_module, "write_channels_file") as write_channels,
        ):
            response = self.client.post(
                "/dashboard/add",
                data={"name": "now tv", "url": "https://youtube.com/@now/live"},
            )
        self.assertEqual(response.status_code, 302)
        write_channels.assert_not_called()

    def test_edit_source_preserves_interval_and_repairs(self):
        configs = {
            "atv": {"url": "https://youtube.com/watch?v=old", "refresh_hours": 2}
        }
        with (
            patch.object(app_module, "streams_table", return_value={"atv": {"status": "failed"}}),
            patch.object(app_module, "read_channel_configs", return_value=configs),
            patch.object(app_module, "write_channels_file") as write_channels,
            patch.object(app_module, "clear_stream_source"),
            patch.object(app_module, "repair_stream", return_value=True),
        ):
            response = self.client.post(
                "/dashboard/edit-source",
                data={"name": "atv", "url": "https://youtube.com/@atv/live"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(configs["atv"]["refresh_hours"], 2)
        write_channels.assert_called_once_with(configs)

    def test_select_live_candidate_updates_source_and_preserves_interval(self):
        configs = {
            "tomorrowland": {"url": "https://youtube.com/watch?v=old", "refresh_hours": 2}
        }
        streams = {
            "tomorrowland": {
                "status": "selection_required",
                "live_candidates": [
                    {"url": "https://www.youtube.com/watch?v=stage-a", "title": "Main Stage"}
                ],
            }
        }
        info = {
            "source_url": "https://www.youtube.com/watch?v=stage-a",
            "m3u8": "https://example.test/main.m3u8",
            "status": "ok",
            "is_live": True,
        }
        with (
            patch.object(app_module, "streams_table", return_value=streams),
            patch.object(app_module, "read_channel_configs", return_value=configs),
            patch.object(app_module, "fetch_info", return_value=info),
            patch.object(app_module, "save_fetch_result") as save_result,
        ):
            response = self.client.post(
                "/dashboard/select-live",
                data={"name": "tomorrowland", "url": "https://www.youtube.com/watch?v=stage-a"},
            )
        self.assertEqual(response.status_code, 302)
        save_result.assert_called_once_with(
            "tomorrowland",
            "https://youtube.com/watch?v=old",
            info,
            channels=configs,
            update_channels=True,
        )

    def test_logs_page_uses_newest_two_hundred_raw_events(self):
        logs = [
            {"channel": "atv", "ip": "127.0.0.1", "timestamp": f"2026-01-01T00:00:{index:03d}"}
            for index in range(250)
        ]
        with patch.object(app_module, "get_access_log", return_value=logs):
            response = self.client.get("/logs?page=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Next", response.data)
        self.assertIn(b"Access Count</th>", response.data)
        self.assertIn(b"<td>200</td>", response.data)


if __name__ == "__main__":
    unittest.main()
