from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import process_channels
from db import prune_old_logs
from config import UPDATE_INTERVAL_HOURS

scheduler = BackgroundScheduler()

def start_scheduler():
    # Refresh streams every UPDATE_INTERVAL_HOURS
    scheduler.add_job(process_channels, 'interval', hours=UPDATE_INTERVAL_HOURS)

    # Prune logs once a day at midnight UTC
    scheduler.add_job(prune_old_logs, 'cron', hour=0, minute=0)

    scheduler.start()
