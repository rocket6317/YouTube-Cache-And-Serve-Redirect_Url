import os


def _interval_from_env():
    try:
        value = int(os.getenv("UPDATE_INTERVAL_HOURS", "5"))
    except ValueError:
        return 5
    return value if 1 <= value <= 5 else 5


UPDATE_INTERVAL_HOURS = _interval_from_env()
DB_PATH = "db.json"
