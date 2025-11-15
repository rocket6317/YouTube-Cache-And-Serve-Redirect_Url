import json
import os
from datetime import datetime

DB_PATH = "db.json"

def init_db():
    if not os.path.exists(DB_PATH) or os.stat(DB_PATH).st_size == 0:
        with open(DB_PATH, 'w') as f:
            json.dump({"streams": {}, "access_log": []}, f)

def load_db():
    with open(DB_PATH, 'r') as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)

def update_stream(name, url, m3u8, channel):
    db = load_db()
    db["streams"][name] = {
        "url": url,
        "m3u8": m3u8,
        "channel": channel
    }
    save_db(db)

def delete_stream(name):
    db = load_db()
    db["streams"].pop(name, None)
    save_db(db)

def get_stream(name):
    stream = load_db()["streams"].get(name)
    if stream and "url" in stream:
        url = stream["url"]
        if "watch?v=" in url:
            return url.replace("watch?v=", "embed/") + "?autoplay=1"
        return url
    return None

def log_access(name, ip):
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
    return load_db().get("access_log", [])

def streams_table():
    return load_db().get("streams", {})
