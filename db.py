from datetime import datetime, timedelta

# In-memory stores (reset on restart)
streams = {}
logs = {}
last_updated = None  # track last refresh time

def init_db():
    global streams, logs, last_updated
    streams = {}
    logs = {}
    last_updated = None

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
    if name in logs:
        del logs[name]

def log_access(name, ip):
    if name not in logs:
        logs[name] = {}
    now = datetime.utcnow().isoformat(timespec="seconds")

    if ip not in logs[name]:
        logs[name][ip] = {"count": 0, "last_seen": now}
    logs[name][ip]["count"] += 1
    logs[name][ip]["last_seen"] = now

def get_access_log():
    return logs

# Timestamp helpers
def set_last_updated():
    global last_updated
    last_updated = datetime.utcnow()

def get_last_updated():
    return last_updated
