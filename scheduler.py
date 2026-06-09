import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from db import (
    prune_old_logs,
    read_channels_file,
    streams_table,
    set_last_update,
)
from config import UPDATE_INTERVAL_HOURS
from stream_service import refresh_stream

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

scheduler = BackgroundScheduler()
refresh_lock = threading.Lock()


def refresh_from_channels_txt(source="scheduled"):
    """
    Reads channels.txt, refreshes metadata, updates db.json.
    Returns False when another global refresh is already running.
    """
    if not refresh_lock.acquire(blocking=False):
        logger.warning(f"[REFRESH] Skipping {source} refresh; another refresh is running")
        return False

    try:
        try:
            channels = read_channels_file()
        except Exception as e:
            logger.error(f"[ERROR] Failed to read channels.txt: {e}")
            return True

        logger.info(f"[REFRESH] {source} refresh found {len(channels)} channels")
        existing_streams = streams_table()

        for name, url in channels.items():
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
                continue

            if info.get("m3u8"):
                logger.info(f"[CACHE] Updated {name} successfully")
            else:
                logger.warning(
                    f"[WARN] Refresh result for {name}: {info.get('status')}"
                )

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
        hours=UPDATE_INTERVAL_HOURS,
        id="refresh_job",
        replace_existing=True
    )

    scheduler.start()
    logger.info(
        f"[SCHEDULER] Scheduler started — interval = {UPDATE_INTERVAL_HOURS} hours"
    )
    threading.Thread(
        target=refresh_from_channels_txt,
        kwargs={"source": "startup"},
        name="startup-refresh",
        daemon=True,
    ).start()


def scheduler_running():
    return scheduler.running
