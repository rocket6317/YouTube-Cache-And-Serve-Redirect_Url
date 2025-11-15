from datetime import datetime, timedelta
from tinydb import TinyDB, Query
import os, json
from config import DB_PATH

# Streams are ephemeral (reset on restart)
streams = {}
last_updated = None

# --- Safe TinyDB initialization ---
def safe_open_db(path):
    # If file exists but is empty or invalid, reset it
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                content = f.read().strip()
                if not content:
                    raise ValueError("Empty file")
                json.loads(content)  # validate JSON
        except Exception:
            # Reset file to empty JSON object
            with open(path, "w") as f:
                f.write("{}")
    return TinyDB(path)

db = safe_open_db(DB_PATH)
logs_table = db.table("logs")

# --- Streams management ---
def init_db():
    global streams, last_updated
    streams = {}
    last_updated = None
    prune_old_logs()  # clean up old logs on startup

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

# --- Logging ---
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

# --- Timestamp helpers ---
def set_last_updated():
    global last_updated
    last_updated = datetime.utcnow()

def get_last_updated():
    return last_updated

# --- Pruning ---
def prune_old_logs():
    """Remove log entries older than 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    for entry in logs_table.all():
        try:
            ts = datetime.fromisoformat(entry["last_seen"])
            if ts < cutoff:
                logs_table.remove(doc_ids=[entry.doc_id])
        except Exception:
            # If timestamp parsing fails, drop the entry
            logs_table.remove(doc_ids=[entry.doc_id])
