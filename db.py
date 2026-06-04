import json
import os
from datetime import datetime, timedelta

DB_PATH = "db.json"
CHANNELS_PATH = "channels.txt"
CHANNELS_DELIM = ","  # using comma as requested

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

# --- channels.txt helpers ---

def read_channels_file():
    """Read channels.txt and return dict: {name: url}."""
    channels = {}
    if not os.path.exists(CHANNELS_PATH):
        return channels
    with open(CHANNELS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(CHANNELS_DELIM)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if name and url:
                    channels[name] = url
    return channels

def write_channels_file(channels_dict):
    """Write dict {name: url} to channels.txt using comma delimiter."""
    lines = [f"{name}{CHANNELS_DELIM}{url}" for name, url in channels_dict.items()]
    with open(CHANNELS_PATH, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

# --- streams (db.json as working state) ---

def update_stream(
    name,
    url,
    m3u8=None,
    channel=None,
    status=None,
    last_error=None,
    resolved_live_url=None,
):
    db = load_db()
    existing = db.get("streams", {}).get(name, {})
    stream = {
        "url": url,
        "m3u8": m3u8,
        "channel": channel
    }
    if status:
        stream["status"] = status
    elif existing.get("status"):
        stream["status"] = existing.get("status")
    if last_error:
        stream["last_error"] = last_error
    if resolved_live_url:
        stream["resolved_live_url"] = resolved_live_url
    if existing.get("last_success"):
        stream["last_success"] = existing.get("last_success")
    if m3u8:
        stream["last_success"] = datetime.utcnow().isoformat()
    stream["last_checked"] = datetime.utcnow().isoformat()
    db["streams"][name] = stream
    save_db(db)

def delete_stream(name):
    db = load_db()
    db["streams"].pop(name, None)
    save_db(db)

def get_stream(name):
    stream = load_db()["streams"].get(name)
    if stream:
        return stream.get("m3u8")
    return None

def streams_table():
    return load_db().get("streams", {})

# --- logging ---

def log_access(name, ip):
    """Record an access event with channel, IP, timestamp, and m3u8."""
    db = load_db()
    stream = db.get("streams", {}).get(name, {})
    channel = stream.get("channel", name)
    m3u8 = stream.get("m3u8")

    if "access_log" not in db:
        db["access_log"] = []

    db["access_log"].append({
        "name": name,
        "channel": channel,
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat(),
        "m3u8": m3u8
    })
    save_db(db)

def get_access_log():
    """Return the list of access log entries."""
    return load_db().get("access_log", [])

def prune_old_logs(days=7):
    """Remove log entries older than N days."""
    db = load_db()
    cutoff = datetime.utcnow() - timedelta(days=days)
    db["access_log"] = [
        log for log in db.get("access_log", [])
        if datetime.fromisoformat(log["timestamp"]) > cutoff
    ]
    save_db(db)
