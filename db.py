from tinydb import TinyDB, Query
from config import DB_PATH
from datetime import datetime, timedelta

db = TinyDB(DB_PATH)
Stream = Query()

# In-memory logs (reset on container restart)
logs = {}

def init_db():
    pass

def update_stream(name, url, m3u8):
    db.upsert({'name': name, 'url': url, 'm3u8': m3u8}, Stream.name == name)

def get_stream(name):
    result = db.search(Stream.name == name)
    return result[0]['m3u8'] if result else None

def delete_stream(name):
    db.remove(Stream.name == name)
    if name in logs:
        del logs[name]

def log_access(name, ip):
    if name not in logs:
        logs[name] = []
    logs[name].append({
        'ip': ip,
        'timestamp': datetime.utcnow().isoformat()
    })
    # prune older than 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    logs[name] = [
        entry for entry in logs[name]
        if datetime.fromisoformat(entry['timestamp']) >= cutoff
    ]

def get_access_log():
    return logs
