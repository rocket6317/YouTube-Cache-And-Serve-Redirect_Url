import yt_dlp
import logging
from db import update_stream
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fetch_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "url": info.get("url"),
        "channel": info.get("channel") or info.get("uploader"),
        "title": info.get("title")
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
    try:
        with open("channels.txt") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to read channels.txt: {e}")
        return

    for url in urls:
        name = extract_name(url)
        try:
            info = fetch_info(url)
            m3u8 = info.get("m3u8")
            channel_name = info.get("channel") or name
            update_stream(name, url, m3u8, channel_name)
            logger.info(f"[CACHE] {channel_name} cached as {name}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch {url}: {e}")

    # ✅ Save last update timestamp
    try:
        with open("timestamps.txt", "w") as f:
            f.write(datetime.utcnow().isoformat())
        logger.info(f"[TIMESTAMP] Updated at {datetime.utcnow().isoformat()}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to write timestamps.txt: {e}")
