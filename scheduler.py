from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import process_channels
from db import prune_old_logs
from config import UPDATE_INTERVAL_HOURS
from datetime import datetime

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_channels, 'interval', hours=UPDATE_INTERVAL_HOURS)
    scheduler.add_job(process_channels, 'date', run_date=datetime.utcnow())  # Immediate first run
    scheduler.add_job(prune_old_logs, 'cron', hour=0, minute=0)
    scheduler.start()
