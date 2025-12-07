from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db import read_channels_file, update_stream, load_db, save_db
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS

scheduler = BackgroundScheduler()

def refresh_from_channels_txt():
    """Read channels.txt and refresh metadata into db.json, update last_update in db.json."""
    channels = read_channels_file()
    print(f"[Scheduler] Reading channels.txt: found {len(channels)} entries")

    for name, url in channels.items():
        print(f"[Scheduler] Fetching info for {name}")
        info = fetch_info(url)
        if info:
            update_stream(name, url, info.get("m3u8"), info.get("channel"))
            print(f"[Scheduler] Updated {name} successfully")
        else:
            update_stream(name, url, None, None)
            print(f"[Scheduler] Failed to fetch info for {name}")

    # persist last_update in db.json
    db = load_db()
    db["last_update"] = datetime.utcnow().isoformat()
    save_db(db)

    print(f"[Scheduler] Finished refresh, db.json updated at {db['last_update']}")

def start_scheduler():
    """Start background scheduler to refresh periodically (only once)."""
    print("[Scheduler] Initial startup refresh triggered")
    refresh_from_channels_txt()  # run once at startup
    scheduler.add_job(refresh_from_channels_txt, 'interval',
                      hours=UPDATE_INTERVAL_HOURS,
                      id='refresh_job', replace_existing=True)
    scheduler.start()
    print("[Scheduler] Scheduler started and job scheduled")
