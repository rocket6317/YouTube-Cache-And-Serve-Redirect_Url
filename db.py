from datetime import datetime, timedelta
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from config import DB_PATH

db = TinyDB(DB_PATH, storage=CachingMiddleware(JSONStorage))
streams_table = db.table("streams")
logs_table = db.table("logs")

streams = {}

def init_db():
    global streams
    streams = {entry["name"]: entry for entry in streams_table.all()}

def get_stream(name):
    return streams.get(name, {}).get("url")

def delete_stream(name):
    global streams
    Stream = Query()
    streams_table.remove(Stream.name == name)
    streams.pop(name, None)

def update_stream(name, url, m3u8, display_name):
    Stream = Query()
    existing = streams_table.get(Stream.name == name)
    if existing:
        streams_table.update({
            "url": m3u8,
            "display_name": display_name
        }, doc_ids=[existing.doc_id])
    else:
        streams_table.insert({
            "name": name,
            "url": m3u8,
            "display_name": display_name
        })
    streams[name] = {
        "name": name,
        "url": m3u8,
        "display_name": display_name
    }

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

def prune_old_logs(days=7):
    cutoff = datetime.utcnow() - timedelta(days=days)
    Log = Query()
    logs_table.remove(Log.last_seen.test(lambda ts: datetime.fromisoformat(ts) < cutoff))
