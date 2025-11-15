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
    from datetime import datetime
    if name not in logs:
        logs[name] = []
    logs[name].append({
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat()
    })
    # prune older than 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    logs[name] = [
        entry for entry in logs[name]
        if datetime.fromisoformat(entry["timestamp"]) >= cutoff
    ]

def get_access_log():
    return logs

# Timestamp helpers
def set_last_updated():
    global last_updated
    last_updated = datetime.utcnow()

def get_last_updated():
    return last_updated
