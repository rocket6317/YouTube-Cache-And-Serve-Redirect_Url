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
    """Read channels.txt and refresh metadata into db.json, update last_update in db.json."""
    channels = read_channels_file()
    logger.info(f"Reading channels.txt: found {len(channels)} entries")

    for name, url in channels.items():
        logger.info(f"Fetching info for {name}")
        info = fetch_info(url)
        if info:
            update_stream(name, url, info.get("m3u8"), info.get("channel"))
            logger.info(f"Updated {name} successfully")
        else:
            update_stream(name, url, None, None)
            logger.warning(f"Failed to fetch info for {name}")

    db = load_db()
    db["last_update"] = datetime.utcnow().isoformat()
    save_db(db)

    logger.info(f"Finished refresh, db.json updated at {db['last_update']}")

def start_scheduler():
    logger.info("Initial startup refresh triggered")
    refresh_from_channels_txt()
    scheduler.add_job(refresh_from_channels_txt, 'interval',
                      hours=UPDATE_INTERVAL_HOURS,
                      id='refresh_job', replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started and job scheduled")
