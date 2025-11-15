from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import process_channels
from db import set_last_updated
from config import UPDATE_INTERVAL_HOURS

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(refresh_streams, 'interval', hours=UPDATE_INTERVAL_HOURS)
    scheduler.start()

def refresh_streams():
    process_channels()
    set_last_updated()
