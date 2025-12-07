from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db import read_channels_file, update_stream
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS

scheduler = BackgroundScheduler()
last_update = None

def refresh_from_channels_txt():
    """
    Read channels.txt and refresh metadata into db.json.
    """
    global last_update
    channels = read_channels_file()  # {name: url}
    for name, url in channels.items():
        info = fetch_info(url)
        if info:
            update_stream(name, url, info.get("m3u8"), info.get("channel"))
        else:
            # Keep at least URL; metadata can be None
            update_stream(name, url, None, None)
    last_update = datetime.utcnow()

def start_scheduler():
    """
    Start background scheduler to refresh periodically.
    """
    # Run once at startup to populate
    refresh_from_channels_txt()
    # Schedule periodic refresh
    scheduler.add_job(refresh_from_channels_txt, 'interval', hours=UPDATE_INTERVAL_HOURS, id='refresh_job', replace_existing=True)
    scheduler.start()
