import yt_dlp
import logging
from db import update_stream
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


def fetch_info(url, channel_name=None):
    """
    Safe wrapper around yt-dlp.
    Never raises to caller. Returns:
      - dict with stream info on success
      - None on failure
    """
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        # Portainer-friendly log line
        print(
            f"[ERROR] Failed to fetch info for '{channel_name or url}' at {datetime.utcnow()} "
            f"Reason: {str(e)}"
        )
        return None

    stream_url = info.get("url")
    if not stream_url:
        print(
            f"[ERROR] No stream URL found for '{channel_name or url}' at {datetime.utcnow()}"
        )
        return None

    return {
        "url": stream_url,
        "m3u8": stream_url,
        "channel": info.get("channel") or info.get("uploader"),
        "title": info.get("title"),
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
