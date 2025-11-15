from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import process_channels
from db import prune_old_logs
from config import UPDATE_INTERVAL_HOURS

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(refresh_streams, 'interval', hours=UPDATE_INTERVAL_HOURS)
    scheduler.add_job(prune_logs, 'cron', hour=0, minute=0)  # Midnight UTC
    scheduler.start()

def refresh_streams():
    process_channels()

def prune_logs():
    prune_old_logs(days=7)
