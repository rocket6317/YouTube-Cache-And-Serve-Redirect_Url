import logging
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from db import (
    prune_old_logs,
    read_channel_configs,
    mark_stream_checked,
    streams_table,
    set_last_update,
)
from settings import get_global_interval
from stream_service import refresh_stream

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

scheduler = BackgroundScheduler()
refresh_lock = threading.Lock()


def stream_is_due(stream, interval_hours, now=None):
    last_checked = stream.get("last_checked")
    if not last_checked:
        return True
    try:
        return datetime.fromisoformat(last_checked) + timedelta(hours=interval_hours) <= (now or datetime.utcnow())
    except ValueError:
        return True


def refresh_from_channels_txt(source="scheduled", force=False):
    """
    Reads channels.txt, refreshes metadata, updates db.json.
    Returns False when another global refresh is already running.
    """
    if not refresh_lock.acquire(blocking=False):
        logger.warning(f"[REFRESH] Skipping {source} refresh; another refresh is running")
        return False

    try:
        try:
            channels = read_channel_configs()
        except Exception as e:
            logger.error(f"[ERROR] Failed to read channels.txt: {e}")
            return True

        logger.info(f"[REFRESH] {source} refresh found {len(channels)} channels")
        existing_streams = streams_table()

        due_count = 0
        for name, config in channels.items():
            url = config["url"]
            interval = config.get("refresh_hours") or get_global_interval()
            if not force and not stream_is_due(existing_streams.get(name, {}), interval):
                continue
            due_count += 1
            logger.info(f"[FETCH] Fetching info for {name}")
            try:
                info = refresh_stream(
                    name,
                    url,
                    channels=channels,
                    existing=existing_streams.get(name, {}),
                )
            except Exception as exc:
                logger.error(f"[ERROR] Unexpected refresh failure for {name}: {exc}")
                mark_stream_checked(name)
                continue

            if info.get("m3u8"):
                logger.info(f"[CACHE] Updated {name} successfully")
            else:
                logger.warning(
                    f"[WARN] Refresh result for {name}: {info.get('status')}"
                )

        logger.info(f"[REFRESH] {source} refresh attempted {due_count} due streams")
        try:
            prune_old_logs(days=7)
            last_update = set_last_update()
            logger.info(f"[TIMESTAMP] Updated at {last_update}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to finalize refresh: {e}")
        return True
    finally:
        refresh_lock.release()


def start_scheduler():
    """
    Starts the periodic scheduler and triggers a non-blocking startup refresh.
    """
    if scheduler.running:
        return

    scheduler.add_job(
        refresh_from_channels_txt,
        "interval",
        hours=1,
        id="refresh_job",
        replace_existing=True
    )

    scheduler.start()
    logger.info(
        "[SCHEDULER] Scheduler started — due-stream check every hour"
    )
    threading.Thread(
        target=refresh_from_channels_txt,
        kwargs={"source": "startup"},
        name="startup-refresh",
        daemon=True,
    ).start()


def scheduler_running():
    return scheduler.running
