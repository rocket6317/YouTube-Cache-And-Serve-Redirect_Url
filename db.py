import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl

DATA_DIR = os.getenv("DATA_DIR", ".")
DB_PATH = os.path.join(DATA_DIR, "db.json")
CHANNELS_PATH = os.path.join(DATA_DIR, "channels.txt")
CHANNELS_DELIM = ","  # using comma as requested

os.makedirs(DATA_DIR, exist_ok=True)
_thread_lock = threading.RLock()


@contextmanager
def _file_lock(path):
    lock_path = f"{path}.lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    with _thread_lock:
        with open(lock_path, "a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _empty_db():
    return {"streams": {}, "access_log": []}


def _atomic_write_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".db-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as temp_file:
            json.dump(data, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _load_db_unlocked():
    if not os.path.exists(DB_PATH) or os.stat(DB_PATH).st_size == 0:
        data = _empty_db()
        _atomic_write_json(DB_PATH, data)
        return data
    try:
        with open(DB_PATH, "r") as db_file:
            data = json.load(db_file)
    except json.JSONDecodeError:
        print("[ERROR] db.json is corrupted or empty. Reinitializing.")
        data = _empty_db()
        _atomic_write_json(DB_PATH, data)
    data.setdefault("streams", {})
    data.setdefault("access_log", [])
    return data


def _mutate_db(mutator):
    with _file_lock(DB_PATH):
        data = _load_db_unlocked()
        mutator(data)
        _atomic_write_json(DB_PATH, data)
        return data

def init_db():
    """Initialize db.json with empty streams and access_log."""
    with _file_lock(DB_PATH):
        _atomic_write_json(DB_PATH, _empty_db())

def load_db():
    """Load db.json safely, reinitialize if missing or corrupted."""
    with _file_lock(DB_PATH):
        return _load_db_unlocked()

def save_db(db):
    """Atomically replace db.json. Prefer targeted mutation helpers."""
    with _file_lock(DB_PATH):
        _atomic_write_json(DB_PATH, db)

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
            if len(parts) in (2, 3):
                name, url = parts[0].strip(), parts[1].strip()
                if name and url:
                    channels[name] = url
    return channels

def read_channel_configs():
    """Read channels.txt including optional per-stream refresh intervals."""
    configs = {}
    if not os.path.exists(CHANNELS_PATH):
        return configs
    with open(CHANNELS_PATH, "r") as channel_file:
        for line in channel_file:
            parts = [part.strip() for part in line.strip().split(CHANNELS_DELIM)]
            if not parts or not parts[0] or parts[0].startswith("#") or len(parts) not in (2, 3):
                continue
            interval = None
            if len(parts) == 3 and parts[2]:
                try:
                    candidate = int(parts[2])
                    interval = candidate if 1 <= candidate <= 5 else None
                except ValueError:
                    pass
            configs[parts[0]] = {"url": parts[1], "refresh_hours": interval}
    return configs

def write_channels_file(channels_dict):
    """Write dict {name: url} to channels.txt using comma delimiter."""
    lines = []
    for name, value in channels_dict.items():
        if isinstance(value, dict):
            url = value["url"]
            interval = value.get("refresh_hours")
        else:
            url = value
            interval = None
        line = f"{name}{CHANNELS_DELIM}{url}"
        if interval is not None:
            line += f"{CHANNELS_DELIM}{interval}"
        lines.append(line)
    content = "\n".join(lines) + ("\n" if lines else "")
    with _file_lock(CHANNELS_PATH):
        directory = os.path.dirname(os.path.abspath(CHANNELS_PATH))
        fd, temp_path = tempfile.mkstemp(prefix=".channels-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w") as temp_file:
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, CHANNELS_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

# --- streams (db.json as working state) ---

def update_stream(
    name,
    url,
    m3u8=None,
    channel=None,
    status=None,
    last_error=None,
    resolved_live_url=None,
    channel_url=None,
    channel_id=None,
):
    def mutate(data):
        existing = data["streams"].get(name, {})
        stream = {
            "url": url,
            "m3u8": m3u8,
            "channel": channel,
        }
        if status:
            stream["status"] = status
        elif existing.get("status"):
            stream["status"] = existing.get("status")
        if last_error:
            stream["last_error"] = last_error
        for key, value in (
            ("resolved_live_url", resolved_live_url),
            ("channel_url", channel_url or existing.get("channel_url")),
            ("channel_id", channel_id or existing.get("channel_id")),
        ):
            if value:
                stream[key] = value
        if existing.get("last_success"):
            stream["last_success"] = existing.get("last_success")
        if m3u8:
            stream["last_success"] = datetime.utcnow().isoformat()
        stream["last_checked"] = datetime.utcnow().isoformat()
        data["streams"][name] = stream

    _mutate_db(mutate)

def delete_stream(name):
    _mutate_db(lambda data: data["streams"].pop(name, None))

def clear_stream_source(name, url):
    def mutate(data):
        existing = data["streams"].get(name, {})
        data["streams"][name] = {
            "url": url,
            "m3u8": None,
            "channel": existing.get("channel") or name,
            "status": "failed",
            "last_error": "Source changed; validation pending",
            "last_checked": datetime.utcnow().isoformat(),
        }
    _mutate_db(mutate)

def mark_stream_checked(name):
    def mutate(data):
        stream = data["streams"].setdefault(name, {})
        stream["last_checked"] = datetime.utcnow().isoformat()
    _mutate_db(mutate)

def get_stream(name):
    stream = load_db()["streams"].get(name)
    if stream:
        return stream.get("m3u8")
    return None

def streams_table():
    return load_db().get("streams", {})

# --- logging ---

def log_access(name, ip, outcome="redirected"):
    """Record an access event with channel, IP, timestamp, and m3u8."""
    def mutate(data):
        stream = data["streams"].get(name, {})
        data["access_log"].append({
            "name": name,
            "channel": stream.get("channel", name),
            "ip": ip,
            "timestamp": datetime.utcnow().isoformat(),
            "m3u8": stream.get("m3u8"),
            "outcome": outcome,
        })

    _mutate_db(mutate)

def get_access_log():
    """Return the list of access log entries."""
    return load_db().get("access_log", [])

def prune_old_logs(days=7):
    """Remove log entries older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    def mutate(data):
        data["access_log"] = [
            log for log in data["access_log"]
            if datetime.fromisoformat(log["timestamp"]) > cutoff
        ]

    _mutate_db(mutate)


def set_last_update(timestamp=None):
    value = timestamp or datetime.utcnow().isoformat()
    _mutate_db(lambda data: data.__setitem__("last_update", value))
    return value
