import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


HEALTH_CACHE_SECONDS = 300
HTTP_TIMEOUT_SECONDS = 5
MAX_MANIFEST_BYTES = 8 * 1024 * 1024

_health_cache = {}
_cache_lock = threading.Lock()


def _is_googlevideo_url(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == "googlevideo.com" or host.endswith(".googlevideo.com")


def clear_health_cache():
    with _cache_lock:
        _health_cache.clear()


def _manifest_entries(body):
    return [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _validate_hls(url):
    manifest_url = url
    for depth in range(2):
        request = Request(manifest_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_MANIFEST_BYTES + 1)
        if len(body) > MAX_MANIFEST_BYTES:
            return False
        text = body.decode("utf-8", errors="replace")
        if not text.lstrip().startswith("#EXTM3U"):
            return False
        entries = _manifest_entries(text)
        if not entries:
            return False

        target_url = urljoin(manifest_url, entries[-1])
        if "#EXT-X-STREAM-INF" in text and depth == 0:
            manifest_url = target_url
            continue

        segment_request = Request(
            target_url,
            headers={"Range": "bytes=0-0", "User-Agent": "Mozilla/5.0"},
        )
        with urlopen(segment_request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            response.read(1)
            return getattr(response, "status", 200) in (200, 206)
    return False


def youtube_stream_is_playable(url):
    if not _is_googlevideo_url(url):
        return True

    now = time.monotonic()
    with _cache_lock:
        cached = _health_cache.get(url)
        if cached and now - cached[0] < HEALTH_CACHE_SECONDS:
            return cached[1]

    try:
        playable = _validate_hls(url)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        playable = False

    with _cache_lock:
        _health_cache[url] = (now, playable)
    return playable
