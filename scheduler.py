import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db import read_channels_file, update_stream, load_db, save_db
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

scheduler = BackgroundScheduler()


def refresh_from_channels_txt():
    """
    Reads channels.txt, refreshes metadata, updates db.json.
    Never throws — safe for startup and scheduler.
    """
    try:
        channels = read_channels_file()
    except Exception as e:
        logger.error(f"[ERROR] Failed to read channels.txt: {e}")
        return

    logger.info(f"[SCHEDULER] Found {len(channels)} channels")

    for name, url in channels.items():
        logger.info(f"[FETCH] Fetching info for {name}")

        info = fetch_info(url, name)

        if info is None:
            # Store failure cleanly
            update_stream(name, url, None, None)
            logger.warning(f"[WARN] Failed to fetch info for {name}")
            continue

        # Successful fetch
        update_stream(
            name,
            url,
            info.get("m3u8"),
            info.get("channel") or name
        )
        logger.info(f"[CACHE] Updated {name} successfully")

    # Update last_update timestamp in db.json
    try:
        db = load_db()
        db["last_update"] = datetime.utcnow().isoformat()
        save_db(db)
        logger.info(f"[TIMESTAMP] Updated at {db['last_update']}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to update db.json timestamp: {e}")


def start_scheduler():
    """
    Runs initial refresh and starts periodic scheduler.
    Must never crash Gunicorn worker.
    """
    logger.info("[SCHEDULER] Initial startup refresh triggered")
    refresh_from_channels_txt()

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
