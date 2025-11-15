from datetime import datetime, timedelta
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

db = TinyDB("db.json", storage=CachingMiddleware(JSONStorage))
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

def get_last_updated():
    meta = db.table("meta").get(doc_id=1)
    if meta and "last_updated" in meta:
        return datetime.fromisoformat(meta["last_updated"])
    return None

def set_last_updated():
    db.table("meta").upsert({"last_updated": datetime.utcnow().isoformat(timespec="seconds")}, doc_ids=[1])

def update_stream(name, url, display_name):
    Stream = Query()
    existing = streams_table.get(Stream.name == name)
    if existing:
        streams_table.update({
            "url": url,
            "display_name": display_name
        }, doc_ids=[existing.doc_id])
    else:
        streams_table.insert({
            "name": name,
            "url": url,
            "display_name": display_name
        })
