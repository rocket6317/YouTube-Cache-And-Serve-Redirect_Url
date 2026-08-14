import re
from urllib.parse import urlparse


def normalize_handle(value):
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def is_youtube_url(value):
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and host in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    )


def is_m3u8_url(value):
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.hostname)
        and parsed.path.lower().endswith(".m3u8")
    )


def parse_interval(value):
    if value in (None, "", "default"):
        return None
    interval = int(value)
    if not 1 <= interval <= 5:
        raise ValueError("Refresh interval must be Default or between 1 and 5 hours.")
    return interval
