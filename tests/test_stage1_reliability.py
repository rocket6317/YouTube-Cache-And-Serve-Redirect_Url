import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import db
from repair_coordinator import RepairCoordinator
from runtime_health import check_readiness
import scheduler


class RepairCoordinatorTests(unittest.TestCase):
    def test_concurrent_requests_share_one_repair(self):
        started = threading.Event()
        release = threading.Event()
        calls = []

        def repair(name):
            calls.append(name)
            started.set()
            release.wait(2)
            return True

        coordinator = RepairCoordinator(repair, cooldown_seconds=300)
        outcomes = []

        def request():
            outcomes.append(coordinator.request("atv", timeout=2))

        first = threading.Thread(target=request)
        second = threading.Thread(target=request)
        first.start()
        self.assertTrue(started.wait(1))
        second.start()
        release.set()
        first.join()
        second.join()

        self.assertEqual(calls, ["atv"])
        self.assertEqual(outcomes, ["redirected", "redirected"])

    def test_timeout_does_not_cancel_background_repair(self):
        release = threading.Event()

        def repair(_name):
            release.wait(2)
            return True

        coordinator = RepairCoordinator(repair, cooldown_seconds=300)
        self.assertEqual(
            coordinator.request("atv", timeout=0.01),
            "repair_timeout",
        )
        release.set()
        time.sleep(0.05)
        self.assertEqual(coordinator.request("atv", timeout=1), "redirected")

    def test_failed_repair_enters_cooldown(self):
        calls = []

        def repair(name):
            calls.append(name)
            return False

        coordinator = RepairCoordinator(repair, cooldown_seconds=300)
        self.assertEqual(coordinator.request("atv", timeout=1), "repair_failed")
        self.assertEqual(coordinator.request("atv", timeout=1), "cooldown")
        self.assertEqual(calls, ["atv"])


class DatabaseStage1Tests(unittest.TestCase):
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

    def test_access_log_records_outcome(self):
        db.log_access("atv", "127.0.0.1", outcome="repair_failed")
        self.assertEqual(db.get_access_log()[0]["outcome"], "repair_failed")

    def test_prune_old_logs_keeps_only_last_seven_days(self):
        old = (datetime.utcnow() - timedelta(days=8)).isoformat()
        recent = (datetime.utcnow() - timedelta(days=2)).isoformat()

        def seed(data):
            data["access_log"] = [
                {"name": "old", "timestamp": old},
                {"name": "recent", "timestamp": recent},
            ]

        db._mutate_db(seed)
        db.prune_old_logs(days=7)
        self.assertEqual([entry["name"] for entry in db.get_access_log()], ["recent"])


class ReadinessTests(unittest.TestCase):
    def test_readiness_requires_database_writable_data_and_scheduler(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertTrue(
                check_readiness(
                    db_loader=lambda: {"streams": {}},
                    data_dir=temp_dir,
                    scheduler_running=lambda: True,
                )
            )
            self.assertFalse(
                check_readiness(
                    db_loader=lambda: {"streams": {}},
                    data_dir=temp_dir,
                    scheduler_running=lambda: False,
                )
            )

    def test_readiness_returns_false_on_database_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(
                check_readiness(
                    db_loader=lambda: (_ for _ in ()).throw(ValueError("bad db")),
                    data_dir=temp_dir,
                    scheduler_running=lambda: True,
                )
            )


class GlobalRefreshLockTests(unittest.TestCase):
    def test_overlapping_global_refresh_is_rejected(self):
        scheduler.refresh_lock.acquire()
        try:
            self.assertFalse(scheduler.refresh_from_channels_txt(source="manual"))
        finally:
            scheduler.refresh_lock.release()

    def test_one_stream_exception_does_not_stop_remaining_refreshes(self):
        with (
            patch.object(
                scheduler,
                "read_channels_file",
                return_value={
                    "bad": "https://youtube.test/bad",
                    "good": "https://youtube.test/good",
                },
            ),
            patch.object(scheduler, "streams_table", return_value={}),
            patch.object(
                scheduler,
                "refresh_stream",
                side_effect=[
                    RuntimeError("unexpected"),
                    {"m3u8": "https://m3u8.test/good"},
                ],
            ) as refresh_stream,
            patch.object(scheduler, "prune_old_logs"),
            patch.object(scheduler, "set_last_update", return_value="now"),
        ):
            self.assertTrue(scheduler.refresh_from_channels_txt(source="test"))

        self.assertEqual(refresh_stream.call_count, 2)

    def test_start_scheduler_triggers_background_refresh(self):
        fake_scheduler = Mock()
        fake_scheduler.running = False
        fake_thread = Mock()
        with (
            patch.object(scheduler, "scheduler", fake_scheduler),
            patch.object(scheduler.threading, "Thread", return_value=fake_thread),
        ):
            scheduler.start_scheduler()

        fake_scheduler.start.assert_called_once()
        fake_thread.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
