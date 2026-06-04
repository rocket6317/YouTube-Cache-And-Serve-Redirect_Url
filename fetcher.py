import yt_dlp
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# yt-dlp options – keep quiet and non-intrusive
ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "force_overwrites": False,
}


def _extract_info(url, channel_name=None, fatal=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        if fatal:
            raise
        print(
            f"[ERROR] Failed to fetch info for '{channel_name or url}' at {datetime.utcnow()} "
            f"Reason: {str(e)}"
        )
        return None


def _normalise_stream_info(info, source_url, channel_name=None, repaired=False):
    stream_url = info.get("url")
    if not stream_url:
        print(
            f"[ERROR] No stream URL found for '{channel_name or source_url}' at {datetime.utcnow()}"
        )
        return None

    return {
        "url": stream_url,
        "m3u8": stream_url,
        "channel": info.get("channel") or info.get("uploader"),
        "title": info.get("title"),
        "source_url": source_url,
        "resolved_live_url": source_url if repaired else None,
        "status": "ok",
        "last_error": None,
    }


def fetch_info(url, channel_name=None):
    """
    Safe wrapper around yt-dlp.
    Never raises to caller. Returns:
      - dict with stream info on success
      - None on failure
    """
    info = _extract_info(url, channel_name)
    if not info:
        return None

    return _normalise_stream_info(info, url, channel_name)


def _candidate_live_urls(info, original_url, channel_name=None):
    candidates = []

    def add(url):
        if url and url not in candidates:
            candidates.append(url)

    channel_url = info.get("channel_url") or info.get("uploader_url")
    channel_id = info.get("channel_id") or info.get("uploader_id")
    channel_handle = info.get("channel") or info.get("uploader")

    if channel_url:
        add(channel_url.rstrip("/") + "/live")

    if channel_id:
        if str(channel_id).startswith("@"):
            add(f"https://www.youtube.com/{channel_id}/live")
        elif str(channel_id).startswith("UC"):
            add(f"https://www.youtube.com/channel/{channel_id}/live")

    parsed = urlparse(original_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in path_parts:
        if part.startswith("@"):
            add(f"https://www.youtube.com/{part}/live")
        elif part in ("channel", "c", "user") and len(path_parts) > path_parts.index(part) + 1:
            add(f"https://www.youtube.com/{part}/{path_parts[path_parts.index(part) + 1]}/live")

    if channel_handle:
        handle = str(channel_handle).strip()
        if handle.startswith("@"):
            add(f"https://www.youtube.com/{handle}/live")

    if channel_name:
        fallback = str(channel_name).strip()
        if fallback and " " not in fallback:
            if fallback.startswith("@"):
                add(f"https://www.youtube.com/{fallback}/live")
            else:
                add(f"https://www.youtube.com/@{fallback}/live")
                add(f"https://www.youtube.com/c/{fallback}/live")
                add(f"https://www.youtube.com/user/{fallback}/live")

    return candidates


def repair_live_info(url, channel_name=None):
    """
    Find the current livestream for a saved YouTube URL.

    This is mainly for saved watch?v= links whose broadcast ID changes. It first
    tries the saved URL, then derives channel /live candidates from metadata.
    """
    metadata = _extract_info(url, channel_name)
    if metadata:
        direct = _normalise_stream_info(metadata, url, channel_name)
        if direct:
            direct["status"] = "ok"
            return direct

    if not metadata:
        try:
            with yt_dlp.YoutubeDL({**ydl_opts, "skip_download": True, "ignore_no_formats_error": True}) as ydl:
                metadata = ydl.extract_info(url, download=False) or {}
        except Exception as e:
            print(
                f"[ERROR] Could not read channel metadata for '{channel_name or url}' at "
                f"{datetime.utcnow()} Reason: {str(e)}"
            )
            metadata = {}

    for candidate in _candidate_live_urls(metadata, url, channel_name):
        print(f"[REPAIR] Trying live candidate for '{channel_name or url}': {candidate}")
        candidate_info = _extract_info(candidate, channel_name)
        if not candidate_info:
            continue
        repaired = _normalise_stream_info(candidate_info, candidate, channel_name, repaired=True)
        if repaired:
            repaired["status"] = "repaired"
            return repaired

    return {
        "url": None,
        "m3u8": None,
        "channel": metadata.get("channel") or metadata.get("uploader") or channel_name,
        "title": metadata.get("title"),
        "source_url": url,
        "resolved_live_url": None,
        "status": "no_live_found",
        "last_error": "No current YouTube live stream found",
    }


def extract_name(url):
    if '@' in url:
        return url.split('@')[-1].split('/')[0]
    elif 'watch?v=' in url:
        video_id = parse_qs(urlparse(url).query).get('v', [''])[0]
        return f"video_{video_id}"
    else:
        return "unknown"


def process_channels():
    # Read channels.txt
    try:
        with open("channels.txt") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to read channels.txt: {e}")
        return

    for url in urls:
        name = extract_name(url)

        info = fetch_info(url, name)
        if info is None:
            logger.error(f"[ERROR] Skipping {url} — fetch failed")
            continue

        m3u8 = info["m3u8"]
        channel_name = info["channel"] or name

        from db import update_stream
        update_stream(name, url, m3u8, channel_name)
        logger.info(f"[CACHE] {channel_name} cached as {name}")

    # Save last update timestamp
    try:
        now_iso = datetime.utcnow().isoformat()
        with open("timestamps.txt", "w") as f:
            f.write(now_iso)
        logger.info(f"[TIMESTAMP] Updated at {now_iso}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to write timestamps.txt: {e}")
