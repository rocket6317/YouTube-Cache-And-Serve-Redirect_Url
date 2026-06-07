import logging
from apscheduler.schedulers.background import BackgroundScheduler
from db import (
    read_channels_file,
    write_channels_file,
    update_stream,
    streams_table,
    set_last_update,
)
from fetcher import fetch_info, repair_live_info
from config import UPDATE_INTERVAL_HOURS

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

scheduler = BackgroundScheduler()


def save_fetch_result(name, original_url, info, channels):
    new_url = info.get("source_url") or info.get("resolved_live_url") or original_url
    update_stream(
        name,
        new_url,
        info.get("m3u8"),
        info.get("channel") or name,
        status=info.get("status"),
        last_error=info.get("last_error"),
        resolved_live_url=info.get("resolved_live_url"),
        channel_url=info.get("channel_url"),
        channel_id=info.get("channel_id"),
    )
    if new_url != original_url:
        channels[name] = new_url
        write_channels_file(channels)
    return new_url


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
    existing_streams = streams_table()

    for name, url in channels.items():
        logger.info(f"[FETCH] Fetching info for {name}")

        info = fetch_info(url, name)

        if info is None:
            existing = existing_streams.get(name, {})
            repaired = repair_live_info(
                url,
                name,
                known_channel_url=existing.get("channel_url"),
                known_channel_id=existing.get("channel_id"),
            )
            save_fetch_result(name, url, repaired, channels)
            logger.warning(
                f"[WARN] Repair refresh result for {name}: {repaired.get('status')}"
            )
            continue

        # Successful fetch
        save_fetch_result(name, url, info, channels)
        logger.info(f"[CACHE] Updated {name} successfully")

    # Update last_update timestamp in db.json
    try:
        last_update = set_last_update()
        logger.info(f"[TIMESTAMP] Updated at {last_update}")
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
