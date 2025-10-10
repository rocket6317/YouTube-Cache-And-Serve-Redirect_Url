from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import process_channels
from config import UPDATE_INTERVAL_HOURS

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_channels, 'interval', hours=UPDATE_INTERVAL_HOURS)
    scheduler.start()