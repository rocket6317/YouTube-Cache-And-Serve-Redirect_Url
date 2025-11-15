from datetime import datetime, timedelta
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from config import DB_PATH
import os
import json
import logging

# Safe startup check
if not os.path.exists(DB_PATH) or os.stat(DB_PATH).st_size == 0:
    with open(DB_PATH, 'w') as f:
        json.dump({}, f)

db = TinyDB(DB_PATH, storage=CachingMiddleware(JSONStorage))
streams_table = db.table("streams")
logs_table = db.table("logs")

streams = {}

def init_db():
    global streams
    try:
        streams = {entry["name"]: entry for entry in streams_table.all()}
    except Exception as e:
        logging.warning(f"[DB INIT] Failed to load streams: {e}")
        streams = {}

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
    from datetime import datetime
    timestamp = datetime.utcnow().isoformat()

    # Load existing DB
    with open(DB_PATH, 'r') as f:
        db = json.load(f)

    # Ensure access_log exists
    if "access_log" not in db:
        db["access_log"] = []

    # Append new log entry
    db["access_log"].append({
        "name": name,
        "ip": ip,
        "timestamp": timestamp
    })

    # Save back to file
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)

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
