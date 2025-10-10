from tinydb import TinyDB, Query
from config import DB_PATH
import json
from datetime import datetime

db = TinyDB(DB_PATH)
Stream = Query()
LOG_PATH = 'access_log.json'

def init_db():
    pass

def update_stream(name, url, m3u8):
    db.upsert({'name': name, 'url': url, 'm3u8': m3u8}, Stream.name == name)

def get_stream(name):
    result = db.search(Stream.name == name)
    return result[0]['m3u8'] if result else None

def delete_stream(name):
    db.remove(Stream.name == name)

def log_access(name, ip):
    try:
        with open(LOG_PATH, 'r') as f:
            logs = json.load(f)
    except:
        logs = {}

    if name not in logs:
        logs[name] = []

    logs[name].append({
        'ip': ip,
        'timestamp': datetime.utcnow().isoformat()
    })

    with open(LOG_PATH, 'w') as f:
        json.dump(logs, f, indent=2)

def get_access_log():
    try:
        with open(LOG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}
