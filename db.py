import json
import os
from datetime import datetime, timedelta

DB_PATH = "db.json"

def init_db():
    with open(DB_PATH, 'w') as f:
        json.dump({"streams": {}, "access_log": []}, f)

def load_db():
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
    if stream and "m3u8" in stream:
        return stream["m3u8"]
    return None

def log_access(name, ip, cf_ip=None):
    db = load_db()
    db.setdefault("logs", []).append({
        "channel": name,
        "ip": ip,
        "cf_ip": cf_ip or ip,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_db(db)

def get_access_log():
    return load_db().get("access_log", [])

def streams_table():
    return load_db().get("streams", {})

def prune_old_logs(days=7):
    db = load_db()
    cutoff = datetime.utcnow() - timedelta(days=days)
    db["access_log"] = [
        log for log in db.get("access_log", [])
        if datetime.fromisoformat(log["timestamp"]) > cutoff
    ]
    save_db(db)
