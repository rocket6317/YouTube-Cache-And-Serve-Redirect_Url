from datetime import datetime, timedelta

# In-memory stores (reset on restart)
streams = {}
logs = {}

def init_db():
    global streams, logs
    streams = {}
    logs = {}

def update_stream(name, url, m3u8):
    streams[name] = {"url": url, "m3u8": m3u8}

def get_stream(name):
    return streams[name]["m3u8"] if name in streams else None

def delete_stream(name):
    if name in streams:
        del streams[name]
    if name in logs:
        del logs[name]

def log_access(name, ip):
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
