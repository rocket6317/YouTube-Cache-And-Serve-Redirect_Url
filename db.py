from datetime import datetime, timedelta
from tinydb import TinyDB, Query
from config import DB_PATH

streams = {}
last_updated = None

db = TinyDB(DB_PATH)
logs_table = db.table("logs")

def init_db():
    global streams, last_updated
    streams = {}
    last_updated = None
    prune_old_logs()  # clean up on startup

def update_stream(name, url, m3u8, display_name=None):
    streams[name] = {
        "name": name,
        "url": url,
        "m3u8": m3u8,
        "display_name": display_name or name
    }

def get_stream(name):
    return streams[name]["m3u8"] if name in streams else None

def delete_stream(name):
    if name in streams:
        del streams[name]
    logs_table.remove(Query().channel == name)

def log_access(name, ip):
    now = datetime.utcnow().isoformat(timespec="seconds")
    Log = Query()
    existing = logs_table.get((Log.channel == name) & (Log.ip == ip))
    if existing:
        logs_table.update({
            "count": existing["count"] + 1,
            "last_seen": now
        }, doc_ids=[existing.doc_id])
    else:
        logs_table.insert({
            "channel": name,
            "ip": ip,
            "count": 1,
            "last_seen": now
        })
    prune_old_logs()  # prune after each insert

def get_access_log():
    grouped = {}
    for entry in logs_table.all():
        channel = entry["channel"]
        if channel not in grouped:
            grouped[channel] = {}
        grouped[channel][entry["ip"]] = {
            "count": entry["count"],
            "last_seen": entry["last_seen"]
        }
    return grouped

def set_last_updated():
    global last_updated
    last_updated = datetime.utcnow()

def get_last_updated():
    return last_updated

def prune_old_logs():
    """Remove log entries older than 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    Log = Query()
    for entry in logs_table.all():
        try:
            ts = datetime.fromisoformat(entry["last_seen"])
            if ts < cutoff:
                logs_table.remove(doc_ids=[entry.doc_id])
        except Exception:
            # If timestamp parsing fails, drop the entry
            logs_table.remove(doc_ids=[entry.doc_id])
