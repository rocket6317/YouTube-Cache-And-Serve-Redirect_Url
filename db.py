import json
import os
from datetime import datetime, timedelta

DB_PATH = "db.json"

def init_db():
    """Initialize db.json with empty streams and access_log."""
    with open(DB_PATH, 'w') as f:
        json.dump({"streams": {}, "access_log": []}, f)

def load_db():
    """Load db.json safely, reinitialize if missing or corrupted."""
    if not os.path.exists(DB_PATH) or os.stat(DB_PATH).st_size == 0:
        init_db()
    with open(DB_PATH, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("[ERROR] db.json is corrupted or empty. Reinitializing.")
            init_db()
            return load_db()

def save_db(db):
    """Write the current db dictionary back to db.json."""
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)

def update_stream(name, url, m3u8=None, channel=None):
    """
    Add or update a stream entry.
    Persist immediately to db.json so UI changes survive refresh/restart.
    """
    db = load_db()
    db["streams"][name] = {
        "url": url,
        "m3u8": m3u8,
        "channel": channel
    }
    save_db(db)

def delete_stream(name):
    """Remove a stream entry and persist change."""
    db = load_db()
    db["streams"].pop(name, None)
    save_db(db)

def get_stream(name):
    """Return the m3u8 URL for a stream if present."""
    stream = load_db()["streams"].get(name)
    if stream:
        return stream.get("m3u8")
    return None

def log_access(name, ip):
    """Append an access log entry and persist change."""
    db = load_db()
    channel = db["streams"].get(name, {}).get("channel", name)
    db["access_log"].append({
        "name": name,
        "channel": channel,
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_db(db)

def get_access_log():
    """Return all access log entries."""
    return load_db().get("access_log", [])

def streams_table():
    """Return all streams dictionary."""
    return load_db().get("streams", {})

def prune_old_logs(days=7):
    """Remove log entries older than N days and persist change."""
    db = load_db()
    cutoff = datetime.utcnow() - timedelta(days=days)
    db["access_log"] = [
        log for log in db.get("access_log", [])
        if datetime.fromisoformat(log["timestamp"]) > cutoff
    ]
    save_db(db)
