import json
from datetime import datetime

DB_PATH = 'db.json'

def load_db():
    try:
        with open(DB_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"streams": {}, "logs": []}

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
    return load_db()["streams"].get(name, {}).get("m3u8")

def get_all_streams():
    return load_db()["streams"]

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
    return load_db().get("logs", [])
